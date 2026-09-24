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
from app.engine.growth import growth_stage
from app.engine.season import default_planting_date

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
        "SELECT root_depth_in, base_temp_f, gdd_total, stage_days FROM crops WHERE id = 'corn'"  # D-009: corn-only in v1
    )).fetchone()
    if not crop:
        return False, "crop corn missing"
    root_depth = crop[0]

    frost = session.execute(text(
        "SELECT frost_kill_50 FROM counties WHERE fips = :f"
    ), {"f": fips}).scalar()
    maturity_days = sum(int(x) for x in crop[3].split(",")) if crop[3] else 130
    planting = default_planting_date(frost, maturity_days, run_date)
    history_start = planting
    history = session.execute(text(
        "SELECT obs_date, tmax_f, tmin_f, precip_in, et0_in FROM daily_historical "
        "WHERE county_fips = :f AND obs_date >= :s AND obs_date < :d ORDER BY obs_date"
    ), {"f": fips, "s": history_start, "d": run_date}).fetchall()
    if planting >= run_date:
        return False, "season has not started"
    expected = (date.fromisoformat(run_date) - date.fromisoformat(history_start)).days
    if len(history) != expected or any(
        r[1] is None or r[2] is None or
        (r[3] is None or r[4] is None) for r in history
    ):
        return False, "incomplete planting-to-run history"
    # Replay from planting each run: equivalent to carrying each day's water
    # forward, while also incorporating corrections to historical inputs.
    weather_series = [{"tmax_f": r[1], "tmin_f": r[2], "precip_in": r[3], "et0_in": r[4]}
                      for r in history]
    total_gdd = sum(max(0, (r[1] + r[2]) / 2 - crop[1]) for r in history)

    soil = session.execute(text(
        "SELECT soil_type, awc FROM soils WHERE county_fips = :f"
    ), {"f": fips}).fetchone()
    if not soil:
        return False, "no soil row"
    soil_type, awc = soil
    aw = root_depth * awc

    cell = session.execute(text(
        "SELECT id FROM field_cells WHERE county_fips = :f AND crop_id = 'corn' LIMIT 1"  # D-009
    ), {"f": fips}).fetchone()
    if not cell:
        session.execute(text(
            "INSERT INTO field_cells (county_fips, crop_id, row, col, soil_type, awc) "
            "VALUES (:f, 'corn', 0, 0, :soil_type, :awc)"  # D-009: corn-only in v1
        ), {"f": fips, "soil_type": soil_type, "awc": awc})
        session.commit()
        cell = session.execute(text(
            "SELECT id FROM field_cells WHERE county_fips = :f AND crop_id = 'corn' LIMIT 1"  # D-009
        ), {"f": fips}).fetchone()
    cell_id = cell[0]

    # Unknown starting moisture spans wilting point through field capacity.
    # The interval tracks initialization uncertainty only, not forecast/model error.
    endpoints = [spinup_soil_moisture(
        weather_series=weather_series, aw=aw, crop_id="corn", initial_sw=start,
    )[0] for start in (0.0, aw)]
    low, high = [v / aw * 100 if aw > 0 else 0.0 for v in endpoints]
    soil_pct = (low + high) / 2

    # Re-running a date replaces its model estimate; no duplicate stale rows.
    session.execute(text(
        "DELETE FROM daily_records WHERE cell_id = :cell AND record_date = :date"
    ), {"cell": cell_id, "date": run_date})
    session.execute(text(
        "INSERT INTO daily_records "
        "(cell_id, record_date, soil_moisture_pct, gdd, growth_stage, soil_min_pct, soil_max_pct) "
        "VALUES (:cell, :date, :pct, :gdd, :stage, :low, :high) "
        "ON CONFLICT DO NOTHING"
    ), {"cell": cell_id, "date": run_date, "pct": round(soil_pct, 2), "gdd": total_gdd,
         "stage": growth_stage(total_gdd / crop[2]), "low": low, "high": high})
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
    except Exception:  # noqa: BLE001 — report operation failure at this boundary
        res["nws_fail"] += 1

    try:
        om_forecast(session, county, tz="America/New_York")
        res["om_fc_ok"] += 1
    except Exception:  # noqa: BLE001 — report operation failure at this boundary
        res["om_fc_fail"] += 1

    # History for soil spin-up + last-7-day rain/ET on the dashboard.
    # Archive API lags ~1 day; request through yesterday only.
    hist_start = (date.fromisoformat(run_date) - timedelta(days=history_days)).strftime("%Y-%m-%d")
    season = session.execute(text(
        "SELECT c.frost_kill_50, p.stage_days FROM counties c CROSS JOIN crops p "
        "WHERE c.fips = :f AND p.id = 'corn'"
    ), {"f": county["fips"]}).one()
    maturity = sum(int(x) for x in season[1].split(",")) if season[1] else 130
    hist_start = min(hist_start, default_planting_date(season[0], maturity, run_date))
    hist_end = (date.fromisoformat(run_date) - timedelta(days=1)).strftime("%Y-%m-%d")
    weather_series: list[dict] = []
    try:
        om_history(session, county, hist_start, hist_end, tz="America/New_York")
        res["om_hist_ok"] += 1
        rows = session.execute(text(
            "SELECT tmax_f, tmin_f, precip_in, et0_in FROM daily_historical "
            "WHERE county_fips = :f AND obs_date BETWEEN :s AND :e ORDER BY obs_date"
        ), {"f": county["fips"], "s": hist_start, "e": hist_end}).fetchall()
        weather_series = [
            {"tmax_f": r[0], "tmin_f": r[1], "precip_in": r[2] or 0.0, "et0_in": r[3]}
            for r in rows
        ]
    except Exception as exc:  # noqa: BLE001 — report operation failure at this boundary
        res["om_hist_fail"] += 1
        print(f"  History error for {county['fips']}: {exc}")

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
        except Exception:  # noqa: BLE001 — report operation failure at this boundary
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
        "advisories_degraded": 0,
        "degraded_counties": [],
        "advisories_generated": 0,
        "advisory_errors": 0,
        "counties_skipped": 0,
        "skip_reasons": {},
        "sms_sent": 0,
        "sms_rate_limited": 0,
    }

    counties = _inscope_counties(session, states)
    if not counties:
        raise RuntimeError("No in-scope counties found in DB")

    print(f"Nightly pipeline: {len(counties)} in-scope counties, date={run_date}")

    # Counties whose soil-water history could not be rebuilt this run. Their
    # advice is forced uncertain rather than issued confidently (D-017).
    degraded: set[str] = set()

    for i, county in enumerate(counties):
        weather_series, step = _fetch_one_county_weather(session, county, run_date, HISTORY_LOOKBACK_DAYS)
        for k, v in step.items():
            results[k] += v

        # Spin-up on whatever history we have (if we got at least a day)
        if len(weather_series) >= 1:
            ok, _detail = _sync_cell_and_spinup(session, county, weather_series, run_date)
            results["spinup_ok" if ok else "spinup_fail"] += 1
            if not ok:
                degraded.add(county["fips"])
        else:
            results["spinup_fail"] += 1
            degraded.add(county["fips"])

        results["counties_processed"] += 1

        if (i + 1) % 20 == 0:
            print(f"  Progress: {i+1}/{len(counties)} counties")

    usdm_ok, usdm_fail = _fetch_drought_all(session, counties, run_date)
    results["usdm_ok"] = usdm_ok
    results["usdm_fail"] = usdm_fail

    # Rebuild advisories (M3 hash chain)
    adv = generate_all(run_date, degraded_fips=degraded)
    results["advisories_generated"] = adv["advisories_generated"]
    results["advisories_degraded"] = adv.get("advisories_degraded", 0)
    results["degraded_counties"] = sorted(degraded)
    results["advisory_errors"] = adv["errors"]
    results["counties_skipped"] = adv.get("counties_skipped", 0)
    results["skip_reasons"] = adv.get("skip_reasons", {})

    # Optional SMS
    if send_sms:
        results.update(_send_sms_advisories(session, run_date))

    results["finished_at"] = datetime.now(timezone.utc).isoformat()

    # Log the whole run (single ingest_runs row, source='nightly_pipeline')
    # Status semantics:
    #   "success"  — at least one advisory generated, no errors
    #   "warning"  — pipeline ran but every advisory was skipped (no data issues)
    #   "error"    — at least one advisory failed to generate
    total_counties = results["counties_processed"]
    skipped = results["counties_skipped"]
    generated = results["advisories_generated"]
    errors = results["advisory_errors"]

    if errors > 0:
        status = "error"
    elif generated == 0 and total_counties > 0 and skipped == total_counties:
        # Every county was skipped — pipeline produced nothing useful
        status = "warning"
    else:
        status = "success"

    payload = json.dumps(results, default=str)
    session.execute(text(
        "INSERT INTO ingest_runs "
        "(source, started_at, finished_at, rows_upserted, status, error_message) "
        "VALUES ('nightly_pipeline', :start, :end, :rows, :status, :msg)"
    ), {
        "start": results["started_at"],
        "end": results["finished_at"],
        "rows": results["counties_processed"],
        "status": status,
        "msg": payload,
    })
    session.commit()

    print("\nNightly pipeline complete:")
    for k, v in results.items():
        print(f"  {k}: {v}")
    return results


def _send_sms_advisories(session: Session, run_date: str) -> dict:
    """Send SMS advisories to subscribers (dry-run unless Twilio configured).

    Reads the advisory that generate_all already produced for each county/date,
    then formats and sends. No recomputation — single source of truth.
    """
    from app.sms.gateway import TwilioConfig, format_advisory_sms
    from app.sms.gateway import send_sms as do_send

    res = {"sms_sent": 0, "sms_rate_limited": 0}
    config = TwilioConfig.from_env()
    subscribers = session.execute(text(
        "SELECT DISTINCT county_fips, phone FROM subscribers WHERE active = true"
    )).fetchall()

    for fips, phone in subscribers:
        # Read the advisory that generate_all already stored for this county/date
        adv_row = session.execute(text(
            "SELECT source_data FROM advisories "
            "WHERE county_fips = :f AND DATE(generated_at) = :d "
            "ORDER BY generated_at DESC LIMIT 1"
        ), {"f": fips, "d": run_date}).fetchone()
        if not adv_row or not adv_row[0]:
            continue

        source = adv_row[0] if isinstance(adv_row[0], dict) else {}
        if source.get("advice_uncertain"):
            continue
        decision = source.get("decision", "HOLD")

        sms_body = {
            "county": source.get("county_name", ""),
            "state": source.get("county_state", ""),
            "action": decision,
            "gdd": source.get("gdd", 0),
            "etc": source.get("etc_in", 0),
            "soil_pct": source.get("soil_pct", 0),
            "depletion": source.get("depletion", 0) * 100,
            "etc0": source.get("etc_in", 0),
            "rain": source.get("forecast_rain_7d", 0),
        }
        body = format_advisory_sms(sms_body)
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
