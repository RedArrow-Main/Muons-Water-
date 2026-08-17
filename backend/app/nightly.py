"""Nightly pipeline — run all connectors, spin-up, and regenerate advisories.

Scheduled every night (see scripts/nightly.sh and .github/workflows/nightly-ingest.yml)
and triggerable on demand via POST /api/admin/refresh.

Steps:
1. NWS forecast -> daily_forecast (in-scope counties)
2. Open-Meteo forecast (ET0 overlay) -> daily_forecast
3. Open-Meteo history (last N days) -> daily_historical
4. USDM drought -> drought_status
5. Soil spin-up from fresh history -> daily_records
6. Regenerate advisories -> advisories (M3 hash chain)
7. Optionally send SMS advisories

Every connector's outcome is logged to ingest_runs.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.connection import engine

# Scope: New York is the sole product target (SPEC.md v1.8).
# CAUTION: connections.py may hold legacy rows; we filter by state here.
DEFAULT_STATES = ("NY",)
HISTORY_LOOKBACK_DAYS = 14


def _inscope_counties(session: Session, states: tuple[str, ...]) -> list[dict]:
    """Return in-scope counties as dicts for the connectors."""
    rows = session.execute(text(
        "SELECT fips, name, state, latitude, longitude FROM counties "
        "WHERE state IN :states ORDER BY fips"
    ), {"states": tuple(states)}).fetchall()
    return [
        {
            "fips": r[0], "name": r[1], "state": r[2],
            "latitude": r[3], "longitude": r[4],
        }
        for r in rows
    ]


def _sync_cell_and_spinup(
    session: Session,
    county: dict,
    weather_series: list[dict],
    run_date: str,
) -> tuple[bool, str]:
    """Ensure field_cell exists, run spin-up, store today's soil moisture.

    Returns (ok, detail_or_error).
    """
    from app.engine.spinup import spinup_soil_moisture

    fips = county["fips"]

    crop = session.execute(text(
        "SELECT base_temp_f, root_depth_in, mad_fraction, kc_mid "
        "FROM crops WHERE id = 'corn'"
    )).fetchone()
    if not crop:
        return False, "crop corn missing"
    base_temp, root_depth, _mad, kc_mid = crop

    soil = session.execute(text(
        "SELECT awc FROM soils WHERE county_fips = :f"
    ), {"f": fips}).fetchone()
    if not soil:
        return False, "no soil row"
    aw = root_depth * soil[0]

    cell = session.execute(text(
        "SELECT id FROM field_cells WHERE county_fips = :f AND crop_id = 'corn' LIMIT 1"
    ), {"f": fips}).fetchone()
    if not cell:
        session.execute(text(
            "INSERT INTO field_cells (county_fips, crop_id, row, col, soil_type, awc) "
            "VALUES (:f, 'corn', 0, 0, :soil_type, :awc)"
        ), {"f": fips, "soil_type": soil[0], "awc": soil[0]})
        session.commit()
        cell = session.execute(text(
            "SELECT id FROM field_cells WHERE county_fips = :f AND crop_id = 'corn' LIMIT 1"
        ), {"f": fips}).fetchone()
    cell_id = cell[0]

    # Spin-up from the fresh history we just fetched
    sw, _depletion = spinup_soil_moisture(
        weather_series=weather_series,
        aw=aw,
        kc=kc_mid,
        base_temp_f=base_temp,
    )
    soil_pct = sw / aw * 100 if aw > 0 else 0.0

    session.execute(text(
        "INSERT INTO daily_records "
        "(cell_id, record_date, soil_moisture_pct, gdd, growth_stage) "
        "VALUES (:cell, :date, :pct, 0, 'vegetative') "
        "ON CONFLICT DO NOTHING"
    ), {"cell": cell_id, "date": run_date, "pct": round(soil_pct, 2)})
    session.commit()
    return True, ""


def _fetch_one_county_weather(
    session: Session,
    county: dict,
    run_date: str,
    history_days: int,
) -> tuple[list[dict], dict]:
    """Fetch NWS forecast, Open-Meteo forecast (ET0) and recent history.

    Returns (weather_series_for_spinup, per-step result counters).
    """
    from app.ingest.noaa_nws import fetch_nws_forecast
    from app.ingest.open_meteo import fetch_forecast as om_forecast
    from app.ingest.open_meteo import fetch_history as om_history

    res = {"nws_ok": 0, "nws_fail": 0, "om_fc_ok": 0, "om_fc_fail": 0,
           "om_hist_ok": 0, "om_hist_fail": 0}

    try:
        fetch_nws_forecast(session, county)
        res["nws_ok"] += 1
    except Exception:
        res["nws_fail"] += 1

    try:
        om_forecast(session, county)
        res["om_fc_ok"] += 1
    except Exception:
        res["om_fc_fail"] += 1

    # History for soil spin-up + last-7-day rain/ET on the dashboard
    hist_start = (date.fromisoformat(run_date) - timedelta(days=history_days)).strftime("%Y-%m-%d")
    weather_series: list[dict] = []
    try:
        om_history(session, county, hist_start, run_date)
        res["om_hist_ok"] += 1
        rows = session.execute(text(
            "SELECT tmax_f, tmin_f, precip_in, et0_in FROM daily_historical "
            "WHERE county_fips = :f AND obs_date BETWEEN :s AND :e ORDER BY obs_date"
        ), {"f": county["fips"], "s": hist_start, "e": run_date}).fetchall()
        weather_series = [
            {"tmax_f": r[0], "tmin_f": r[1], "precip_in": r[2] or 0.0, "et0_in": r[3]}
            for r in rows
        ]
    except Exception:
        res["om_hist_fail"] += 1

    return weather_series, res


def _fetch_drought_all(session: Session, counties: list[dict], run_date: str) -> tuple[int, int]:
    """Fetch USDM drought for all in-scope counties. Returns (ok, fail)."""
    from app.ingest.usdm import fetch_drought

    start = (date.fromisoformat(run_date) - timedelta(days=7)).strftime("%Y-%m-%d")
    ok = 0
    fail = 0
    for county in counties:
        try:
            n = fetch_drought(session, county, start, run_date)
            if n:
                ok += 1
            else:
                fail += 1
        except Exception:
            fail += 1
    return ok, fail


def run_pipeline(
    session: Session,
    run_date: str,
    send_sms: bool = False,
    states: tuple[str, ...] = DEFAULT_STATES,
) -> dict:
    """Run the full nightly pipeline for in-scope states (NY by default)."""
    from app.advisor.service import generate_all

    results = {
        "date": run_date,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "states": list(states),
        "counties_processed": 0,
        "nws_ok": 0, "nws_fail": 0,
        "om_fc_ok": 0, "om_fc_fail": 0,
        "om_hist_ok": 0, "om_hist_fail": 0,
        "usdm_ok": 0, "usdm_fail": 0,
        "spinup_ok": 0, "spinup_fail": 0,
        "advisories_generated": 0,
        "advisory_errors": 0,
        "sms_sent": 0,
        "sms_rate_limited": 0,
    }

    counties = _inscope_counties(session, states)
    if not counties:
        raise RuntimeError("No in-scope counties found in DB")

    print(f"Nightly pipeline: {len(counties)} in-scope counties, date={run_date}")

    for i, county in enumerate(counties):
        weather_series, step = _fetch_one_county_weather(session, county, run_date, HISTORY_LOOKBACK_DAYS)
        for k, v in step.items():
            results[k] += v

        # Spin-up on whatever history we have (if we got at least a day)
        if len(weather_series) >= 1:
            ok, _detail = _sync_cell_and_spinup(session, county, weather_series, run_date)
            results["spinup_ok" if ok else "spinup_fail"] += 1
        else:
            results["spinup_fail"] += 1

        results["counties_processed"] += 1

        if (i + 1) % 20 == 0:
            print(f"  Progress: {i+1}/{len(counties)} counties")

    usdm_ok, usdm_fail = _fetch_drought_all(session, counties, run_date)
    results["usdm_ok"] = usdm_ok
    results["usdm_fail"] = usdm_fail

    # Rebuild advisories (M3 hash chain)
    adv = generate_all(run_date)
    results["advisories_generated"] = adv["advisories_generated"]
    results["advisory_errors"] = adv["errors"]

    # Optional SMS
    if send_sms:
        results.update(_send_sms_advisories(session, run_date))

    results["finished_at"] = datetime.now(timezone.utc).isoformat()

    # Log the whole run (single ingest_runs row, source='nightly_pipeline')
    payload = json.dumps(results, default=str)
    session.execute(text(
        "INSERT INTO ingest_runs "
        "(source, started_at, finished_at, rows_upserted, status, error_message) "
        "VALUES ('nightly_pipeline', :start, :end, :rows, 'success', :msg)"
    ), {
        "start": results["started_at"],
        "end": results["finished_at"],
        "rows": results["counties_processed"],
        "msg": payload,
    })
    session.commit()

    print("\nNightly pipeline complete:")
    for k, v in results.items():
        print(f"  {k}: {v}")
    return results


def _send_sms_advisories(session: Session, run_date: str) -> dict:
    """Send SMS advisories to subscribers (dry-run unless Twilio configured)."""
    from app.engine.gdd import gdd_daily
    from app.engine.water_balance import compute_etc, should_irrigate, soil_water_step
    from app.sms.gateway import TwilioConfig, format_advisory_sms
    from app.sms.gateway import send_sms as do_send

    res = {"sms_sent": 0, "sms_rate_limited": 0}
    config = TwilioConfig.from_env()
    subscribers = session.execute(text(
        "SELECT DISTINCT county_fips, phone FROM subscribers WHERE active = true"
    )).fetchall()

    for fips, phone in subscribers:
        fc = session.execute(text(
            "SELECT forecast_date, tmax_f, tmin_f, precip_in, et0_in "
            "FROM daily_forecast WHERE county_fips = :f ORDER BY forecast_date LIMIT 1"
        ), {"f": fips}).fetchone()
        if not fc or not fc[1] or not fc[2] or not fc[4]:
            continue

        soil = session.execute(text(
            "SELECT awc FROM soils WHERE county_fips = :f"
        ), {"f": fips}).fetchone()
        aw = 36 * soil[0] if soil else 7.2

        gdd = gdd_daily(fc[1], fc[2], 50)
        etc_val = compute_etc(fc[4], 1.15)
        sw = 0.6 * aw
        sw = soil_water_step(sw, aw, fc[3] or 0, 0, etc_val)
        dep = 1 - sw / aw
        action = should_irrigate(dep, 0.5)

        adv = {
            "county": "", "state": "", "action": action,
            "gdd": gdd, "etc": etc_val, "etc0": fc[4],
            "soil_pct": sw / aw * 100, "depletion": dep * 100,
            "rain": fc[3],
        }
        body = format_advisory_sms(adv)
        ok = do_send(session, phone, body, county_fips=fips, config=config)
        if ok:
            res["sms_sent"] += 1
        else:
            res["sms_rate_limited"] += 1

    return res


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FurrowCast nightly pipeline")
    parser.add_argument("--date", default=datetime.now(timezone.utc).date().strftime("%Y-%m-%d"),
                        help="Run date YYYY-MM-DD (default: today)")
    parser.add_argument("--sms", action="store_true", help="Send SMS advisories")
    parser.add_argument("--state", default="NY", help="Comma-separated state codes (default NY)")
    args = parser.parse_args()

    with Session(engine) as s:
        try:
            r = run_pipeline(s, args.date, send_sms=args.sms,
                             states=tuple(args.state.upper().split(",")))
            raise SystemExit(0 if r["advisory_errors"] == 0 else 1)
        except Exception as exc:  # log failure to ingest_runs then re-raise
            s.execute(text(
                "INSERT INTO ingest_runs (source, started_at, finished_at, rows_upserted, status, error_message) "
                "VALUES ('nightly_pipeline', :start, :end, 0, 'error', :err)"
            ), {
                "start": datetime.now(timezone.utc).isoformat(),
                "end": datetime.now(timezone.utc).isoformat(),
                "err": str(exc)[:500],
            })
            s.commit()
            raise