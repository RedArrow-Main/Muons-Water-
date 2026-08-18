"""Bootstrap a fresh database for the NY-only demo.

Runs after `alembic upgrade head` on a brand-new database (e.g. Neon).
Loads:
  - all 62 NY counties (with frost dates) from counties_data.py
  - the 9 crops from seed.py
  - default soils for NY counties
Idempotent (upserts). Does NOT fetch weather — run the nightly pipeline
(`python -m app.nightly`) or trigger POST /api/admin/refresh to populate
forecasts, history, spin-up and advisories.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.connection import engine
from app.db.seed import CROPS
from app.ingest.counties_data import get_counties, get_soil_defaults

load_dotenv()


def bootstrap(session: Session) -> dict:
    results = {"counties": 0, "crops": 0, "soils": 0}

    # --- NY counties only ---
    for c in get_counties():
        if c["state"] != "NY":
            continue
        session.execute(text("""
            INSERT INTO counties (fips, name, state, latitude, longitude,
                                  frost_kill_10, frost_kill_50, frost_kill_90)
            VALUES (:fips, :name, :state, :lat, :lon, :f10, :f50, :f90)
            ON CONFLICT (fips) DO UPDATE SET
                name = EXCLUDED.name,
                state = EXCLUDED.state,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                frost_kill_10 = EXCLUDED.frost_kill_10,
                frost_kill_50 = EXCLUDED.frost_kill_50,
                frost_kill_90 = EXCLUDED.frost_kill_90
        """), {
            "fips": c["fips"], "name": c["name"], "state": c["state"],
            "lat": c["latitude"], "lon": c["longitude"],
            "f10": c["frost_kill_10"], "f50": c["frost_kill_50"],
            "f90": c["frost_kill_90"],
        })
        results["counties"] += 1

    # --- crops ---
    for crop in CROPS:
        crop_id, base_f, gdd, root_in, mad, kc_ini, kc_mid, kc_end, stage_days = crop
        session.execute(text("""
            INSERT INTO crops (
                id, base_temp_f, gdd_total, root_depth_in, mad_fraction,
                kc_initial, kc_mid, kc_end, stage_days)
            VALUES (:id, :base_f, :gdd, :root_in, :mad,
                    :kc_ini, :kc_mid, :kc_end, :stage_days)
            ON CONFLICT (id) DO UPDATE SET
                base_temp_f = EXCLUDED.base_temp_f,
                gdd_total = EXCLUDED.gdd_total,
                root_depth_in = EXCLUDED.root_depth_in,
                mad_fraction = EXCLUDED.mad_fraction,
                kc_initial = EXCLUDED.kc_initial,
                kc_mid = EXCLUDED.kc_mid,
                kc_end = EXCLUDED.kc_end,
                stage_days = EXCLUDED.stage_days
        """), {
            "id": crop_id, "base_f": base_f, "gdd": gdd, "root_in": root_in,
            "mad": mad, "kc_ini": kc_ini, "kc_mid": kc_mid, "kc_end": kc_end,
            "stage_days": stage_days,
        })
        results["crops"] += 1

    # --- soils for NY ---
    for s in get_soil_defaults():
        if s["county_fips"] not in {c["fips"] for c in get_counties() if c["state"] == "NY"}:
            continue
        session.execute(text("""
            INSERT INTO soils (county_fips, soil_type, awc)
            VALUES (:fips, :soil, :awc)
            ON CONFLICT (county_fips) DO UPDATE SET
                soil_type = EXCLUDED.soil_type,
                awc = EXCLUDED.awc
        """), {"fips": s["county_fips"], "soil": s["soil_type"], "awc": s["awc"]})
        results["soils"] += 1

    session.commit()
    print(f"Bootstrap complete: {results['counties']} NY counties, "
          f"{results['crops']} crops, {results['soils']} soils")
    return results


if __name__ == "__main__":
    with Session(engine) as s:
        bootstrap(s)
