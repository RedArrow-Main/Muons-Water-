"""M3 Advisor — service layer: generate_advisory, generate_all.

Wires engine output → narrative → compose → store. All data is injected;
no live fetching. generate_all() is called by the nightly cron.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.advisor.compose import build_advisory
from app.advisor.narrative import build_narrative
from app.db.connection import engine
from app.engine.growth import adjusted_mad
from app.engine.kc import kc_for_gdd_frac
from app.engine.season import default_planting_date
from app.ingest.open_meteo import fetch_archive_daily, tz_for_state

# Scope: New York is the sole product target (SPEC.md v1.8 / D-006).
INSCOPE_STATES = {"NY"}


def generate_advisory(
    county_fips: str,
    date: str,
    water_state: dict,
    prev_hash: str | None = None,
) -> dict | None:
    """Generate a single advisory for one county. Pure — no DB, no fetch.

    Args:
        county_fips: 5-digit FIPS code
        date: YYYY-MM-DD
        water_state: dict with soil_pct, depletion, mad, aw, etc_in, etc.
        prev_hash: hash of previous advisory for this county (for chaining)

    Returns:
        Advisory dict, or None if water_state has insufficient data
        (e.g. etc_in <= 0 means no valid ET forecast).
    """
    # Data sufficiency gate — skip if key inputs are missing/zero
    if water_state.get("etc_in", 0) <= 0:
        return None

    decision, severity, headline, body = build_narrative(water_state)
    enriched_state = {**water_state, "decision": decision}

    return build_advisory(
        county_fips=county_fips,
        crop_id=water_state.get("crop_id", "corn"),
        date=date,
        decision=decision,
        severity=severity,
        headline=headline,
        body=body,
        source_data=enriched_state,
        prev_hash=prev_hash,
    )


def _ensure_history_coverage(
    session: Session,
    fips: str,
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    tz: str = "America/New_York",
) -> bool:
    """Ensure daily_historical covers [start_date, end_date]. Fetch missing gaps from live archive.

    Coverage is defined as: MIN(obs_date) <= start_date. Interior holes are
    tolerated (GDD summation handles them via COALESCE).

    Returns True if coverage back to start_date was achieved, False otherwise.
    """
    # Check what we already have
    rows = session.execute(text(
        "SELECT obs_date FROM daily_historical "
        "WHERE county_fips = :f AND obs_date >= :s AND obs_date <= :e"
    ), {"f": fips, "s": start_date, "e": end_date}).fetchall()
    existing = {r[0] for r in rows}

    # Build set of required dates
    sd = date.fromisoformat(start_date)
    ed = date.fromisoformat(end_date)
    required = set()
    cur = sd
    while cur <= ed:
        required.add(cur.isoformat())
        cur += timedelta(days=1)

    missing = required - existing
    if not missing:
        return True

    # Fetch missing range from live archive via shared helper
    gap_start = min(missing)
    gap_end = max(missing)
    daily = fetch_archive_daily(lat, lon, gap_start, gap_end, tz=tz)
    if daily is None:
        return False

    dates = daily.get("time", [])
    tmax_list = daily.get("temperature_2m_max", [])
    tmin_list = daily.get("temperature_2m_min", [])
    precip_list = daily.get("precipitation_sum", [])
    et0_list = daily.get("et0_fao_evapotranspiration", [])

    stmt = text("""
        INSERT INTO daily_historical (county_fips, obs_date, tmax_f, tmin_f, precip_in, et0_in)
        VALUES (:fips, :date, :tmax, :tmin, :precip, :et0)
        ON CONFLICT (county_fips, obs_date) DO UPDATE SET
            tmax_f = EXCLUDED.tmax_f,
            tmin_f = EXCLUDED.tmin_f,
            precip_in = EXCLUDED.precip_in,
            et0_in = EXCLUDED.et0_in
    """)

    for i, d in enumerate(dates):
        if d in missing:
            session.execute(stmt, {
                "fips": fips,
                "date": d,
                "tmax": tmax_list[i] if i < len(tmax_list) else None,
                "tmin": tmin_list[i] if i < len(tmin_list) else None,
                "precip": precip_list[i] if i < len(precip_list) else None,
                "et0": et0_list[i] if i < len(et0_list) else None,
            })
    session.commit()
    return True


def _build_water_state(
    session: Session,
    fips: str,
    advisory_date: str,
) -> tuple[dict | None, str | None]:
    """Build water_state dict from DB for a county.

    Returns (water_state, skip_reason).  skip_reason is None on success,
    or a short string explaining why the county was skipped.
    """

    # County — need frost_kill_50 for default planting-date anchor, plus lat/lon
    # for live archive fetch if daily_historical has gaps.
    county = session.execute(text(
        "SELECT fips, name, state, frost_kill_50, latitude, longitude "
        "FROM counties WHERE fips = :f"
    ), {"f": fips}).fetchone()
    if not county:
        return None, "county_not_found"

    # Scope check — only process in-scope states (NY)
    if county[2] not in INSCOPE_STATES:
        return None, "out_of_scope"

    frost_50 = county[3]

    # Soil
    soil = session.execute(text(
        "SELECT soil_type, awc FROM soils WHERE county_fips = :f"
    ), {"f": fips}).fetchone()
    if not soil:
        return None, "no_soil_data"

    # Crop (corn default) — D-009: advisory generation is corn-only in v1
    crop = session.execute(text(
        "SELECT base_temp_f, root_depth_in, mad_fraction, kc_initial, kc_mid, kc_end, "
        "gdd_total, stage_days "
        "FROM crops WHERE id = 'corn'"
    )).fetchone()
    if not crop:
        return None, "no_crop_data"

    base_temp, root_depth, mad, _kc_initial, _kc_mid, _kc_end, gdd_to_maturity, stage_days = crop
    awc = soil[1]
    aw = root_depth * awc

    # Default planting date — mirror dashboard's latest-safe-plant anchor:
    # frost_kill_50 minus maturity_days (sum of stage_days CSV).
    maturity_days = 130  # corn fallback (25+35+45+25 from seed.py)
    if stage_days:
        try:
            maturity_days = sum(int(x) for x in str(stage_days).split(",") if x.strip())
        except (ValueError, TypeError):
            maturity_days = 130

    # The region's TYPICAL planting date, NOT the latest-safe-plant date — see
    # app/engine/season.py for why. Year derives from the advisory date.
    planting_date = default_planting_date(frost_50, maturity_days, advisory_date)

    # Ensure daily_historical covers back to planting_date.
    # Live archive fetch fills gaps that the nightly 14-day window misses.
    # The archive API lags ~1 day, so query through yesterday only.
    date_obj = date.fromisoformat(advisory_date)
    yesterday = (date_obj - timedelta(days=1)).isoformat()
    _ensure_history_coverage(session, fips, county[4], county[5],
                             planting_date, yesterday, tz=tz_for_state(county[2]))

    # Cumulative GDD from planting to yesterday for growth-stage Kc
    # Compute from temperatures in daily_historical (no nonexistent gdd column).
    # COVERAGE GUARD: earliest obs_date must reach planting_date (interior holes OK).
    cum_gdd_row = session.execute(text(
        "SELECT COUNT(*), COALESCE(SUM(GREATEST(0, (tmax_f + tmin_f) / 2.0 - :base_temp)), 0) "
        "FROM daily_historical "
        "WHERE county_fips = :f "
        "  AND obs_date >= :planting_date AND obs_date < :d "
        "  AND tmax_f IS NOT NULL AND tmin_f IS NOT NULL"
    ), {"f": fips, "base_temp": base_temp, "planting_date": planting_date, "d": advisory_date}).fetchone()
    cum_gdd = cum_gdd_row[1] if cum_gdd_row else 0.0

    earliest_row = session.execute(text(
        "SELECT MIN(obs_date) FROM daily_historical "
        "WHERE county_fips = :f AND obs_date >= :planting_date"
    ), {"f": fips, "planting_date": planting_date}).fetchone()
    earliest_obs = earliest_row[0] if earliest_row else None

    if earliest_obs is None or earliest_obs > planting_date:
        return None, "no_history_coverage"

    gdd_frac = cum_gdd / gdd_to_maturity if gdd_to_maturity > 0 else 0.0
    stage_kc = kc_for_gdd_frac("corn", gdd_frac)  # D-009: corn-only in v1
    stage_mad = adjusted_mad(mad, gdd_frac)

    # Current-day model estimate and initialization interval; unknown means [0,100].
    prev_record = session.execute(text(
        "SELECT soil_moisture_pct, soil_min_pct, soil_max_pct FROM daily_records dr "
        "JOIN field_cells fc ON dr.cell_id = fc.id "
        "WHERE fc.county_fips = :f AND fc.crop_id = 'corn' "  # D-009: corn-only
        "AND dr.record_date = :d ORDER BY dr.id DESC LIMIT 1"
    ), {"f": fips, "d": advisory_date}).fetchone()
    soil_pct = prev_record[0] if prev_record else 50.0
    low_pct = prev_record[1] if prev_record and prev_record[1] is not None else 0.0
    high_pct = prev_record[2] if prev_record and prev_record[2] is not None else 100.0
    sw = soil_pct / 100.0 * aw

    # Today's forecast
    fc = session.execute(text(
        "SELECT tmax_f, tmin_f, precip_in, et0_in "
        "FROM daily_forecast WHERE county_fips = :f "
        "AND forecast_date = :d ORDER BY forecast_date LIMIT 1"
    ), {"f": fips, "d": advisory_date}).fetchone()

    if not fc or not fc[0] or not fc[1]:
        return None, "no_forecast_data"

    from app.engine.gdd import gdd_daily
    from app.engine.water_balance import compute_etc, refill_amount, soil_water_step

    tmax, tmin = fc[0], fc[1]
    rain = fc[2] or 0
    et0 = fc[3]

    gdd_val = gdd_daily(tmax, tmin, base_temp)
    etc_val = compute_etc(et0, stage_kc) if et0 else 0

    # Advance soil water
    sw_new = soil_water_step(sw, aw, rain, 0, etc_val)
    depletion = 1.0 - sw_new / aw if aw > 0 else 0.0

    # 7-day forecast rain sum
    fc_7d = session.execute(text(
        "SELECT COALESCE(SUM(precip_in), 0) FROM daily_forecast "
        "WHERE county_fips = :f AND forecast_date >= :d"
    ), {"f": fips, "d": advisory_date}).fetchall()
    rain_7d = fc_7d[0][0] if fc_7d else 0.0

    # Drought level
    drought = session.execute(text(
        "SELECT usdm_level FROM drought_status "
        "WHERE county_fips = :f ORDER BY week_ending DESC LIMIT 1"
    ), {"f": fips}).fetchone()
    drought_level = drought[0] if drought else "NONE"

    low = soil_water_step(low_pct / 100 * aw, aw, rain, 0, etc_val)
    high = soil_water_step(high_pct / 100 * aw, aw, rain, 0, etc_val)
    # Both action thresholds must agree before advice is suitable for SMS.
    uncertain = any(1-high/aw < threshold <= 1-low/aw
                    for threshold in (stage_mad, stage_mad-0.10))
    return {
        "advice_uncertain": uncertain,
        "soil_min_pct": low / aw * 100,
        "soil_max_pct": high / aw * 100,
        "gdd": gdd_val,
        "soil_pct": sw_new / aw * 100 if aw > 0 else 0.0,
        "depletion": depletion,
        "mad": stage_mad,
        "base_mad": mad,
        "aw": aw,
        "etc_in": etc_val,
        "forecast_rain_7d": rain_7d,
        "refill_amount": refill_amount(sw_new, aw),
        "drought_level": drought_level,
        "soil_type": soil[0],
        "crop_id": "corn",  # D-009: advisory generation is corn-only in v1
        "county_name": county[1],
        "county_state": county[2],
        "date": advisory_date,
    }, None


def generate_all(date: str) -> dict:
    """Generate advisories for all counties with sufficient data.

    Called by nightly cron after ingestion completes.
    Writes to DB (advisories table).

    Returns:
        dict with summary: {counties_processed, advisories_generated, ...}
    """
    results = {
        "date": date,
        "counties_processed": 0,
        "counties_skipped": 0,
        "advisories_generated": 0,
        "errors": 0,
        "skip_reasons": {},
    }

    with Session(engine) as session:
        counties = session.execute(text(
            "SELECT fips FROM counties ORDER BY fips"
        )).fetchall()

        for (fips,) in counties:
            try:
                # Get previous advisory hash for chaining
                prev = session.execute(text(
                    "SELECT hash FROM advisories "
                    "WHERE county_fips = :f ORDER BY generated_at DESC LIMIT 1"
                ), {"f": fips}).fetchone()
                prev_hash = prev[0] if prev else None

                water_state, skip_reason = _build_water_state(session, fips, date)
                if water_state is None:
                    results["counties_processed"] += 1
                    results["counties_skipped"] += 1
                    reason = skip_reason or "unknown"
                    results["skip_reasons"][reason] = results["skip_reasons"].get(reason, 0) + 1
                    continue

                advisory = generate_advisory(fips, date, water_state, prev_hash)
                if advisory is None:
                    # Insufficient data (e.g. etc_in <= 0) — skip silently
                    results["counties_processed"] += 1
                    results["counties_skipped"] += 1
                    results["skip_reasons"]["insufficient_et"] = results["skip_reasons"].get("insufficient_et", 0) + 1
                    continue

                # Store
                session.execute(text(
                    "INSERT INTO advisories "
                    "(county_fips, crop_id, type, severity, headline, body, "
                    " source_data, hash, prev_hash, status, generated_at) "
                    "VALUES (:fips, :crop, :type, :sev, :headline, :body, "
                    "        :source, :hash, :prev, :status, :gen_at)"
                ), {
                    "fips": advisory["county_fips"],
                    "crop": advisory["crop_id"],
                    "type": advisory["type"],
                    "sev": advisory["severity"],
                    "headline": advisory["headline"],
                    "body": advisory["body"],
                    "source": json.dumps(advisory["source_data"]),
                    "hash": advisory["hash"],
                    "prev": advisory["prev_hash"],
                    "status": advisory["status"],
                    "gen_at": advisory["generated_at"],
                })

                results["advisories_generated"] += 1
            except Exception as exc:  # noqa: BLE001 — report operation failure at this boundary
                results["errors"] += 1
                print(f"  Advisory error for {fips}: {exc}")
                session.rollback()

            results["counties_processed"] += 1

        session.commit()

    return results
