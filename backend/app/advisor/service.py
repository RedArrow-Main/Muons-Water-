"""M3 Advisor — service layer: generate_advisory, generate_all.

Wires engine output → narrative → compose → store. All data is injected;
no live fetching. generate_all() is called by the nightly cron.
"""
from __future__ import annotations

import json

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.advisor.compose import build_advisory
from app.advisor.narrative import build_narrative
from app.db.connection import engine

# Scope: v1 targets Corn Belt states (NE, IA, KS) plus New York (NY pivot)
INSCOPE_STATES = {"NE", "IA", "KS", "NY"}


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

    return build_advisory(
        county_fips=county_fips,
        crop_id=water_state.get("crop_id", "corn"),
        date=date,
        decision=decision,
        severity=severity,
        headline=headline,
        body=body,
        source_data=water_state,
        prev_hash=prev_hash,
    )


def _build_water_state(
    session: Session,
    fips: str,
    date: str,
) -> dict | None:
    """Build water_state dict from DB for a county. Returns None if data missing."""
    # County
    county = session.execute(text(
        "SELECT fips, name, state FROM counties WHERE fips = :f"
    ), {"f": fips}).fetchone()
    if not county:
        return None

    # Scope check — only process in-scope states (NE, IA, KS)
    if county[2] not in INSCOPE_STATES:
        return None

    # Soil
    soil = session.execute(text(
        "SELECT soil_type, awc FROM soils WHERE county_fips = :f"
    ), {"f": fips}).fetchone()
    if not soil:
        return None

    # Crop (corn default)
    crop = session.execute(text(
        "SELECT base_temp_f, root_depth_in, mad_fraction, kc_mid FROM crops WHERE id = 'corn'"
    )).fetchone()
    if not crop:
        return None

    base_temp, root_depth, mad, kc_mid = crop
    awc = soil[1]
    aw = root_depth * awc

    # Latest soil water from daily_records or default to 60%
    prev_record = session.execute(text(
        "SELECT soil_moisture_pct FROM daily_records dr "
        "JOIN field_cells fc ON dr.cell_id = fc.id "
        "WHERE fc.county_fips = :f AND fc.crop_id = 'corn' "
        "ORDER BY dr.record_date DESC LIMIT 1"
    ), {"f": fips}).fetchone()
    soil_pct = prev_record[0] if prev_record else 60.0
    sw = soil_pct / 100.0 * aw

    # Today's forecast
    fc = session.execute(text(
        "SELECT tmax_f, tmin_f, precip_in, et0_in "
        "FROM daily_forecast WHERE county_fips = :f "
        "ORDER BY forecast_date LIMIT 1"
    ), {"f": fips}).fetchone()

    if not fc or not fc[0] or not fc[1]:
        return None

    from app.engine.gdd import gdd_daily
    from app.engine.water_balance import compute_etc, soil_water_step, refill_amount

    tmax, tmin = fc[0], fc[1]
    rain = fc[2] or 0
    et0 = fc[3]

    gdd_val = gdd_daily(tmax, tmin, base_temp)
    etc_val = compute_etc(et0, kc_mid) if et0 else 0

    # Advance soil water
    sw_new = soil_water_step(sw, aw, rain, 0, etc_val)
    depletion = 1.0 - sw_new / aw if aw > 0 else 0.0

    # 7-day forecast rain sum
    fc_7d = session.execute(text(
        "SELECT COALESCE(SUM(precip_in), 0) FROM daily_forecast "
        "WHERE county_fips = :f AND forecast_date >= :d"
    ), {"f": fips, "d": date}).fetchall()
    rain_7d = fc_7d[0][0] if fc_7d else 0.0

    # Drought level
    drought = session.execute(text(
        "SELECT usdm_level FROM drought_status "
        "WHERE county_fips = :f ORDER BY week_ending DESC LIMIT 1"
    ), {"f": fips}).fetchone()
    drought_level = drought[0] if drought else "NONE"

    return {
        "gdd": gdd_val,
        "soil_pct": sw_new / aw * 100 if aw > 0 else 0.0,
        "depletion": depletion,
        "mad": mad,
        "aw": aw,
        "etc_in": etc_val,
        "forecast_rain_7d": rain_7d,
        "refill_amount": refill_amount(sw_new, aw),
        "drought_level": drought_level,
        "soil_type": soil[0],
        "crop_id": "corn",
        "county_name": county[1],
        "county_state": county[2],
        "date": date,
    }


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
        "advisories_generated": 0,
        "errors": 0,
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

                water_state = _build_water_state(session, fips, date)
                if water_state is None:
                    results["counties_processed"] += 1
                    continue

                advisory = generate_advisory(fips, date, water_state, prev_hash)
                if advisory is None:
                    # Insufficient data (e.g. etc_in <= 0) — skip silently
                    results["counties_processed"] += 1
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
            except Exception:
                results["errors"] += 1

            results["counties_processed"] += 1

        session.commit()

    return results
