"""Reference data integrity guard.

Runs LAST (filename sorts after all other test files).  Compares full seed
sets in the database against the authoritative source files:
  - counties_data.get_counties() (NY subset) → counties table
  - seed.CROPS → crops table
  - counties_data.get_soil_defaults() (NY subset) → soils table

Every differing field, plus rows present in one side but not the other, is
reported.  A guard that has only ever passed is untested — see 1c proof.
"""
from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.connection import engine


def _row_diff(
    expected: dict[str, Any],
    actual: dict[str, Any],
    fields: list[str],
    rtol: float = 0.005,
) -> list[str]:
    """Return list of 'field: expected X, got Y' strings for mismatched fields."""
    diffs = []
    for f in fields:
        e, a = expected.get(f), actual.get(f)
        if e is None or a is None:
            if e != a:
                diffs.append(f"{f}: expected {e!r}, got {a!r}")
            continue
        if isinstance(e, float) and isinstance(a, float):
            if (abs(e) > 0 and abs(e - a) / abs(e) > rtol) or (
                abs(e - a) > 1e-9 and abs(e) == 0
            ):
                diffs.append(f"{f}: expected {e}, got {a}")
        elif e != a:
            diffs.append(f"{f}: expected {e!r}, got {a!r}")
    return diffs


def test_reference_data_integrity():
    """Compare full seed sets in DB against source-of-truth files.

    Fails with a readable diff listing every drifted field, missing row,
    or extra row.  Fix the preservation fixture or the offending test.
    """
    from app.db.seed import CROPS
    from app.ingest.counties_data import get_counties, get_soil_defaults

    errors: list[str] = []

    with Session(engine) as session:
        # ── 1. Counties (NY subset from counties_data) ──────────────────
        expected_ny = {
            c["fips"]: c for c in get_counties() if c["state"] == "NY"
        }
        db_rows = session.execute(text(
            "SELECT fips, name, state, latitude, longitude, "
            "frost_kill_10, frost_kill_50, frost_kill_90 "
            "FROM counties WHERE state = 'NY'"
        )).fetchall()
        db_counties = {
            r[0]: {
                "fips": r[0], "name": r[1], "state": r[2],
                "latitude": r[3], "longitude": r[4],
                "frost_kill_10": r[5], "frost_kill_50": r[6],
                "frost_kill_90": r[7],
            }
            for r in db_rows
        }

        county_fields = [
            "name", "state", "latitude", "longitude",
            "frost_kill_10", "frost_kill_50", "frost_kill_90",
        ]
        for fips, exp in expected_ny.items():
            if fips not in db_counties:
                errors.append(f"county {fips} ({exp['name']}): MISSING from DB")
                continue
            diffs = _row_diff(exp, db_counties[fips], county_fields)
            for d in diffs:
                errors.append(f"county {fips} ({exp['name']}): {d}")

        for fips in db_counties:
            if fips not in expected_ny:
                errors.append(
                    f"county {fips} ({db_counties[fips]['name']}): "
                    f"EXTRA in DB (not in counties_data NY set)"
                )

        # ── 2. Crops (from seed.py) ─────────────────────────────────────
        expected_crops = {c[0]: {
            "id": c[0], "base_temp_f": c[1], "gdd_total": c[2],
            "root_depth_in": c[3], "mad_fraction": c[4],
            "kc_initial": c[5], "kc_mid": c[6], "kc_end": c[7],
            "stage_days": c[8],
        } for c in CROPS}

        db_crop_rows = session.execute(text(
            "SELECT id, base_temp_f, gdd_total, root_depth_in, "
            "mad_fraction, kc_initial, kc_mid, kc_end, stage_days "
            "FROM crops"
        )).fetchall()
        db_crops = {
            r[0]: {
                "id": r[0], "base_temp_f": r[1], "gdd_total": r[2],
                "root_depth_in": r[3], "mad_fraction": r[4],
                "kc_initial": r[5], "kc_mid": r[6], "kc_end": r[7],
                "stage_days": r[8],
            }
            for r in db_crop_rows
        }

        crop_fields = [
            "base_temp_f", "gdd_total", "root_depth_in", "mad_fraction",
            "kc_initial", "kc_mid", "kc_end", "stage_days",
        ]
        for crop_id, exp in expected_crops.items():
            if crop_id not in db_crops:
                errors.append(f"crop {crop_id}: MISSING from DB")
                continue
            diffs = _row_diff(exp, db_crops[crop_id], crop_fields)
            for d in diffs:
                errors.append(f"crop {crop_id}: {d}")

        for crop_id in db_crops:
            if crop_id not in expected_crops:
                errors.append(
                    f"crop {crop_id}: EXTRA in DB (not in seed.CROPS)"
                )

        # ── 3. Soils (NY subset — SSURGO overrides + state defaults) ────
        from app.ingest.ssurgo import NY_COUNTY_SSURGO

        # Start with state defaults, then apply SSURGO overrides
        expected_soils = {}
        for s in get_soil_defaults():
            if s["county_fips"] in expected_ny:
                expected_soils[s["county_fips"]] = dict(s)
        for fips, (soil_type, awc) in NY_COUNTY_SSURGO.items():
            if fips in expected_soils:
                expected_soils[fips]["soil_type"] = soil_type
                expected_soils[fips]["awc"] = awc
        db_soil_rows = session.execute(text(
            "SELECT s.county_fips, s.soil_type, s.awc "
            "FROM soils s JOIN counties c ON c.fips = s.county_fips "
            "WHERE c.state = 'NY'"
        )).fetchall()
        db_soils = {
            r[0]: {"county_fips": r[0], "soil_type": r[1], "awc": r[2]}
            for r in db_soil_rows
        }

        soil_fields = ["soil_type", "awc"]
        for fips, exp in expected_soils.items():
            if fips not in db_soils:
                errors.append(
                    f"soil {fips}: MISSING from DB "
                    f"(expected {exp['soil_type']}/{exp['awc']})"
                )
                continue
            diffs = _row_diff(exp, db_soils[fips], soil_fields)
            for d in diffs:
                errors.append(f"soil {fips}: {d}")

        for fips in db_soils:
            if fips not in expected_soils:
                errors.append(
                    f"soil {fips}: EXTRA in DB (not in NY soil defaults)"
                )

    if errors:
        msg = "Reference data drift detected:\n" + "\n".join(
            f"  - {e}" for e in errors
        )
        pytest.fail(msg)
