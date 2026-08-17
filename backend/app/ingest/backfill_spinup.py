"""Backfill historical weather + run spin-up for all in-scope counties.

Steps:
1. Fetch 90 days of Open-Meteo archive (2026-05-01 to 2026-08-05)
2. Ensure field_cells exist for each county
3. Run spinup_soil_moisture() to estimate current soil moisture
4. Store result in daily_records (so service.py reads real per-county state)
"""
from __future__ import annotations

import sys
import time

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.connection import engine
from app.engine.spinup import spinup_soil_moisture

INSCOPE_STATES = {"NE", "IA", "KS", "NY"}
ARCHIVE_URL = (
    "https://archive-api.open-meteo.com/v1/archive"
    "?latitude={lat}&longitude={lon}"
    "&start_date={start}&end_date={end}"
    "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,et0_fao_evapotranspiration"
    "&temperature_unit=fahrenheit&precipitation_unit=inch&timezone=America/Chicago"
)
# 90 days before 2026-08-06
HIST_START = "2026-05-01"
HIST_END = "2026-08-05"


def backfill_historical_and_spinup() -> dict:
    results = {
        "total_inscope": 297,
        "hist_ok": 0,
        "hist_fail": 0,
        "spinup_ok": 0,
        "spinup_fail": 0,
        "field_cells_created": 0,
        "errors": [],
    }

    with Session(engine) as session:
        counties = session.execute(text(
            "SELECT c.fips, c.name, c.state, c.latitude, c.longitude, "
            "s.soil_type, s.awc "
            "FROM counties c JOIN soils s ON c.fips = s.county_fips "
            "WHERE c.state IN :states ORDER BY c.fips"
        ), {"states": tuple(INSCOPE_STATES)}).fetchall()

        print(f"Processing {len(counties)} in-scope counties...")

        # Crop params (corn)
        crop = session.execute(text(
            "SELECT base_temp_f, root_depth_in, mad_fraction, kc_mid "
            "FROM crops WHERE id = 'corn'"
        )).fetchone()
        root_depth = crop[1]
        kc_mid = crop[3]

        hist_stmt = text("""
            INSERT INTO daily_historical (county_fips, obs_date, tmax_f, tmin_f, precip_in, et0_in)
            VALUES (:fips, :date, :tmax, :tmin, :precip, :et0)
            ON CONFLICT (county_fips, obs_date) DO UPDATE SET
                tmax_f = EXCLUDED.tmax_f, tmin_f = EXCLUDED.tmin_f,
                precip_in = EXCLUDED.precip_in, et0_in = EXCLUDED.et0_in
        """)

        with httpx.Client() as client:
            for i, county in enumerate(counties):
                fips, name, state, lat, lon, soil_type, awc = county
                aw = root_depth * awc

                if (i + 1) % 50 == 0:
                    print(f"  Progress: {i+1}/{len(counties)}")

                # 1. Fetch historical weather (90 days)
                try:
                    url = ARCHIVE_URL.format(lat=lat, lon=lon, start=HIST_START, end=HIST_END)
                    resp = client.get(url, timeout=30)
                    resp.raise_for_status()
                    data = resp.json()
                    daily = data.get("daily", {})
                    dates = daily.get("time", [])
                    tmax_list = daily.get("temperature_2m_max", [])
                    tmin_list = daily.get("temperature_2m_min", [])
                    precip_list = daily.get("precipitation_sum", [])
                    et0_list = daily.get("et0_fao_evapotranspiration", [])

                    weather_series = []
                    for j, d in enumerate(dates):
                        tmax = tmax_list[j] if j < len(tmax_list) else None
                        tmin = tmin_list[j] if j < len(tmin_list) else None
                        precip = precip_list[j] if j < len(precip_list) else 0.0
                        et0 = et0_list[j] if j < len(et0_list) else None

                        session.execute(hist_stmt, {
                            "fips": fips, "date": d,
                            "tmax": tmax, "tmin": tmin,
                            "precip": precip, "et0": et0,
                        })

                        weather_series.append({
                            "tmax_f": tmax, "tmin_f": tmin,
                            "precip_in": precip or 0.0,
                            "et0_in": et0,
                        })

                    session.commit()
                    results["hist_ok"] += 1
                    time.sleep(0.3)

                except Exception as e:
                    results["hist_fail"] += 1
                    results["errors"].append(f"HIST {fips}: {str(e)[:80]}")
                    continue

                # 2. Ensure field_cell exists
                try:
                    cell = session.execute(text(
                        "SELECT id FROM field_cells "
                        "WHERE county_fips = :f AND crop_id = 'corn' LIMIT 1"
                    ), {"f": fips}).fetchone()

                    if not cell:
                        session.execute(text(
                            "INSERT INTO field_cells "
                            "(county_fips, crop_id, row, col, soil_type, awc) "
                            "VALUES (:f, 'corn', 0, 0, :soil, :awc)"
                        ), {"f": fips, "soil": soil_type, "awc": awc})
                        session.commit()
                        cell = session.execute(text(
                            "SELECT id FROM field_cells "
                            "WHERE county_fips = :f AND crop_id = 'corn' LIMIT 1"
                        ), {"f": fips}).fetchone()
                        results["field_cells_created"] += 1

                    cell_id = cell[0]

                    # 3. Run spin-up (only on the 90-day weather_series we just fetched)
                    sw, depletion = spinup_soil_moisture(
                        weather_series=weather_series,
                        aw=aw,
                        kc=kc_mid,
                    )
                    soil_pct = sw / aw * 100 if aw > 0 else 0.0

                    # 4. Store in daily_records (today's date)
                    session.execute(text(
                        "INSERT INTO daily_records "
                        "(cell_id, record_date, soil_moisture_pct, gdd, growth_stage) "
                        "VALUES (:cell, '2026-08-06', :pct, 0, 'vegetative') "
                        "ON CONFLICT DO NOTHING"
                    ), {"cell": cell_id, "pct": round(soil_pct, 2)})
                    session.commit()
                    results["spinup_ok"] += 1

                except Exception as e:
                    results["spinup_fail"] += 1
                    results["errors"].append(f"SPINUP {fips}: {str(e)[:80]}")

        print(f"\nBackfill complete:")
        print(f"  Historical OK: {results['hist_ok']}, FAIL: {results['hist_fail']}")
        print(f"  Field cells created: {results['field_cells_created']}")
        print(f"  Spin-up OK: {results['spinup_ok']}, FAIL: {results['spinup_fail']}")
        if results["errors"]:
            print(f"  Errors ({len(results['errors'])}):")
            for e in results["errors"][:5]:
                print(f"    {e}")

        return results


if __name__ == "__main__":
    backfill_historical_and_spinup()
