"""Seed the database with launch-set data (idempotent).

Run:
    cd backend && source .venv/bin/activate && python -m app.db.seed
"""
from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(os.path.dirname(_HERE))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# Resolved centrally so the production-database guard applies here too.
from app.db.connection import DATABASE_URL

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

COUNTIES = [
    # FIPS, Name, State, Lat, Lon, Frost-kill 10%, 50%, 90%
    ("31027", "Cedar",   "NE", 42.599,  -97.488, 274, 285, 296),
    ("31047", "Dawson",  "NE", 40.870,  -99.820, 272, 283, 294),
    ("31137", "Phelps",  "NE", 40.529,  -99.404, 273, 284, 295),
    ("19169", "Story",   "IA", 42.036,  -93.465, 271, 282, 293),
    ("19015", "Boone",   "IA", 42.036,  -93.931, 270, 281, 292),
    ("20055", "Finney",  "KS", 38.044, -100.736, 277, 290, 302),
    ("20069", "Gray",    "KS", 37.737, -100.436, 278, 291, 303),
]

CROPS = [
    # id, base_f, gdd, root_depth_in, mad, kc_ini, kc_mid, kc_end,
    # stage_days: initial, development, mid, late
    # corn kc_end 0.60 = FAO-56 Table 12, maize (grain) harvested at HIGH
    # MOISTURE. 0.35 is the dry-harvest row; ~1.05-1.15 is silage cut green;
    # 1.05 is sweet corn. The previous 0.90 matched none of these — see
    # DECISIONS.md D-010.
    # kc_mid corn 1.20 / soy 1.15 / alfalfa 0.95 = FAO-56 Table 12 (D-014).
    # Corn's former 1.15 was sweet corn's Kc_mid, not field maize's.
    ("corn",      50, 2700, 36, 0.50, 0.30, 1.20, 0.60, "25,35,45,25"),
    ("soy",       50, 2500, 24, 0.50, 0.40, 1.15, 0.50, "20,30,40,25"),
    ("alfalfa",   41, 1800, 30, 0.50, 0.40, 0.95, 0.90, "15,25,30,20"),
    ("cover",     40, 1200, 10, 0.45, 0.30, 0.60, 0.55, "15,20,30,40"),
    ("potatoes",  45, 1600, 24, 0.35, 0.50, 1.15, 0.75, "25,30,35,25"),
    ("sunflower", 46, 2000, 50, 0.50, 0.35, 1.10, 0.35, "25,35,40,30"),
    # FAO-56 reference values — pending agronomist sign-off
    ("cabbage",   45, 2000, 18, 0.45, 0.70, 1.05, 0.95, "20,25,35,25"),
    ("onions",    40, 1800, 14, 0.30, 0.70, 1.05, 0.75, "15,25,35,25"),
    ("sweet corn",50, 2200, 24, 0.50, 0.30, 1.15, 1.05, "20,30,40,25"),
]

# county_fips, soil_type, awc (available water capacity, in/in)
SOILS = [
    ("31027", "SILT LOAM",                0.20),
    ("31047", "SILTY CLAY LOAM",          0.16),
    ("31137", "SILT LOAM",                0.20),
    ("19169", "SILT LOAM",                0.20),
    ("19015", "SILT LOAM",                0.20),
    ("20055", "SANDY LOAM",               0.11),
    ("20069", "SANDY LOAM",               0.11),
]


def seed(session: Session) -> None:
    """Insert seed rows idempotent (upsert via ON CONFLICT DO NOTHING)."""

    for (
        fips, name, state, lat, lon,
        frost_10, frost_50, frost_90,
    ) in COUNTIES:
        session.execute(
            text("""
                INSERT INTO counties (
                    fips, name, state, latitude, longitude,
                    frost_kill_10, frost_kill_50, frost_kill_90
                )
                VALUES (:fips, :name, :state, :lat, :lon,
                        :f10, :f50, :f90)
                ON CONFLICT (fips) DO UPDATE
                    SET name         = EXCLUDED.name,
                        state        = EXCLUDED.state,
                        latitude     = EXCLUDED.latitude,
                        longitude    = EXCLUDED.longitude,
                        frost_kill_10 = EXCLUDED.frost_kill_10,
                        frost_kill_50 = EXCLUDED.frost_kill_50,
                        frost_kill_90 = EXCLUDED.frost_kill_90
            """),
            {
                "fips": fips, "name": name, "state": state,
                "lat": lat, "lon": lon,
                "f10": frost_10, "f50": frost_50, "f90": frost_90,
            },
        )

    for (
        crop_id, base_f, gdd, root_in, mad,
        kc_ini, kc_mid, kc_end, stage_days,
    ) in CROPS:
        session.execute(
            text("""
                INSERT INTO crops (
                    id, base_temp_f, gdd_total,
                    root_depth_in, mad_fraction,
                    kc_initial, kc_mid, kc_end,
                    stage_days
                )
                VALUES (
                    :id, :base_f, :gdd,
                    :root_in, :mad,
                    :kc_ini, :kc_mid, :kc_end,
                    :stage_days
                )
                ON CONFLICT (id) DO UPDATE
                    SET base_temp_f  = EXCLUDED.base_temp_f,
                        gdd_total    = EXCLUDED.gdd_total,
                        root_depth_in = EXCLUDED.root_depth_in,
                        mad_fraction = EXCLUDED.mad_fraction,
                        kc_initial   = EXCLUDED.kc_initial,
                        kc_mid       = EXCLUDED.kc_mid,
                        kc_end       = EXCLUDED.kc_end,
                        stage_days   = EXCLUDED.stage_days
            """),
            {
                "id": crop_id, "base_f": base_f, "gdd": gdd,
                "root_in": root_in, "mad": mad,
                "kc_ini": kc_ini, "kc_mid": kc_mid, "kc_end": kc_end,
                "stage_days": stage_days,
            },
        )

    for county_fips, soil_type, awc in SOILS:
        session.execute(
            text("""
                INSERT INTO soils (county_fips, soil_type, awc)
                VALUES (:fips, :soil, :awc)
                ON CONFLICT (county_fips) DO UPDATE
                    SET soil_type = EXCLUDED.soil_type,
                        awc       = EXCLUDED.awc
            """),
            {"fips": county_fips, "soil": soil_type, "awc": awc},
        )

    session.commit()
    print("Seed complete: 7 counties, 9 crops, 7 soils")


if __name__ == "__main__":
    eng = create_engine(DATABASE_URL)
    with Session(eng) as session:
        seed(session)
