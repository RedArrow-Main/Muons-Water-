"""Re-run spin-up with corrected function for all 297 counties."""
from __future__ import annotations

import statistics

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.connection import engine
from app.engine.spinup import spinup_soil_moisture


def rerun_spinup() -> None:
    with Session(engine) as session:
        cells = session.execute(text(
            "SELECT fc.id, fc.county_fips, fc.awc, c.root_depth_in, c.kc_mid "
            "FROM field_cells fc "
            "JOIN crops c ON fc.crop_id = c.id "
        "WHERE fc.county_fips IN "
        "(SELECT fips FROM counties WHERE state IN ('NE','IA','KS','NY')) "
            "AND fc.crop_id = 'corn'"
        )).fetchall()

        print(f"Re-processing {len(cells)} field cells...")

        ok = 0
        for cell_id, fips, awc, root_depth, kc in cells:
            aw = root_depth * awc

            hist = session.execute(text(
                "SELECT tmax_f, tmin_f, precip_in, et0_in "
                "FROM daily_historical "
                "WHERE county_fips = :f "
                "AND obs_date >= '2026-05-01' AND obs_date <= '2026-08-05' "
                "ORDER BY obs_date"
            ), {"f": fips}).fetchall()

            if not hist:
                continue

            weather = [
                {"tmax_f": r[0], "tmin_f": r[1],
                 "precip_in": r[2] or 0.0, "et0_in": r[3]}
                for r in hist
            ]

            sw, depletion = spinup_soil_moisture(
                weather_series=weather, aw=aw, kc=kc,
            )
            soil_pct = sw / aw * 100 if aw > 0 else 0.0

            session.execute(text(
                "UPDATE daily_records SET soil_moisture_pct = :pct "
                "WHERE cell_id = :cell"
            ), {"cell": cell_id, "pct": round(soil_pct, 2)})
            ok += 1

        session.commit()
        print(f"Updated {ok} daily_records with corrected spin-up")

    # Verify
    with engine.connect() as c:
        pcts = c.execute(text(
            "SELECT soil_moisture_pct FROM daily_records"
        )).fetchall()
        values = [r[0] for r in pcts]
        print(f"\nCorrected soil_pct distribution ({len(values)} counties):")
        print(f"  Min:    {min(values):.1f}%")
        print(f"  Max:    {max(values):.1f}%")
        print(f"  Mean:   {statistics.mean(values):.1f}%")
        print(f"  Median: {statistics.median(values):.1f}%")
        print(f"  StdDev: {statistics.stdev(values):.1f}%")
        neg = sum(1 for v in values if v < 0)
        print(f"  Negative values: {neg}/{len(values)}")


if __name__ == "__main__":
    rerun_spinup()
