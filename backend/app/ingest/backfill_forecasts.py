"""Backfill forecast data for all in-scope (NE/IA/KS) counties.

Resumable: skips counties that already have forecast rows.
Handles NWS rate limits with throttling + retries.
"""
from __future__ import annotations

import sys
import time

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.connection import engine

NWS_POINTS_URL = "https://api.weather.gov/points/{lat},{lon}"
NWS_GRID_URL = "https://api.weather.gov/gridpoints/{grid_id}/{grid_x},{grid_y}"
HEADERS = {"User-Agent": "(FurrowCast, contact@furrowcast.app)"}
INSCOPE_STATES = {"NE", "IA", "KS"}
MAX_RETRIES = 3
RETRY_DELAY = 5
THROTTLE_DELAY = 1.5  # seconds between NWS API calls


def _nws_get(client: httpx.Client, url: str, retries: int = MAX_RETRIES) -> httpx.Response:
    """GET with retry on 429/5xx."""
    for attempt in range(retries):
        try:
            resp = client.get(url, headers=HEADERS, timeout=20)
            if resp.status_code == 429 or resp.status_code >= 500:
                wait = RETRY_DELAY * (attempt + 1)
                print(f"    NWS {resp.status_code}, retry {attempt+1}/{retries} in {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        except httpx.TimeoutException:
            wait = RETRY_DELAY * (attempt + 1)
            print(f"    NWS timeout, retry {attempt+1}/{retries} in {wait}s...")
            time.sleep(wait)
    raise Exception(f"NWS API failed after {retries} retries: {url}")  # noqa: TRY002


def _resolve_grid(client: httpx.Client, lat: float, lon: float) -> tuple[str, int, int]:
    resp = _nws_get(client, NWS_POINTS_URL.format(lat=lat, lon=lon))
    props = resp.json()["properties"]
    return props["gridId"], props["gridX"], props["gridY"]


def _parse_daily_periods(properties: dict) -> list[dict]:
    tmax_vals = properties.get("maxTemperature", {}).get("values", [])
    tmin_vals = properties.get("minTemperature", {}).get("values", [])
    precip_vals = properties.get("quantitativePrecipitation", {}).get("values", [])

    daily: dict[str, dict] = {}
    for entry in tmax_vals:
        date_str = entry["validTime"].split("T")[0]
        daily.setdefault(date_str, {})["tmax_f"] = entry["value"] * 9 / 5 + 32
    for entry in tmin_vals:
        date_str = entry["validTime"].split("T")[0]
        daily.setdefault(date_str, {})["tmin_f"] = entry["value"] * 9 / 5 + 32
    for entry in precip_vals:
        date_str = entry["validTime"].split("T")[0]
        daily.setdefault(date_str, {})["precip_in"] = entry["value"]

    rows = []
    for date_str in sorted(daily):
        d = daily[date_str]
        rows.append({
            "forecast_date": date_str,
            "tmax_f": d.get("tmax_f"),
            "tmin_f": d.get("tmin_f"),
            "precip_in": d.get("precip_in"),
        })
    return rows


def backfill_forecasts(date: str | None = None) -> dict:
    """Backfill NWS + Open-Meteo forecasts for all in-scope counties.

    Resumable: skips counties that already have forecast rows.
    """
    results = {
        "total_inscope": 0,
        "skipped_existing": 0,
        "nws_ok": 0,
        "nws_fail": 0,
        "om_ok": 0,
        "om_fail": 0,
        "grid_resolved": 0,
        "errors": [],
    }

    with Session(engine) as session:
        # Get all in-scope counties
        counties = session.execute(text(
            "SELECT fips, name, state, latitude, longitude, grid_id, grid_x, grid_y "
            "FROM counties WHERE state IN :states ORDER BY fips"
        ), {"states": tuple(INSCOPE_STATES)}).fetchall()

        results["total_inscope"] = len(counties)
        print(f"Backfill: {len(counties)} in-scope counties (NE/IA/KS)")

        # Check which counties already have forecast data
        existing = set()
        if date:
            rows = session.execute(text(
                "SELECT DISTINCT county_fips FROM daily_forecast "
                "WHERE forecast_date = :d AND county_fips IN "
                "(SELECT fips FROM counties WHERE state IN :states)"
            ), {"d": date, "states": tuple(INSCOPE_STATES)}).fetchall()
            existing = {r[0] for r in rows}
        else:
            rows = session.execute(text(
                "SELECT DISTINCT county_fips FROM daily_forecast "
                "WHERE county_fips IN "
                "(SELECT fips FROM counties WHERE state IN :states)"
            ), {"states": tuple(INSCOPE_STATES)}).fetchall()
            existing = {r[0] for r in rows}

        print(f"  Counties with existing forecast: {len(existing)}")

        # Open-Meteo forecast URL template
        OM_FORECAST_URL = (
            "https://api.open-meteo.com/v1/forecast"
            "?latitude={lat}&longitude={lon}"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,et0_fao_evapotranspiration"
            "&temperature_unit=fahrenheit&precipitation_unit=inch&forecast_days=7&timezone=America/Chicago"
        )

        nws_stmt = text("""
            INSERT INTO daily_forecast (county_fips, forecast_date, tmax_f, tmin_f, precip_in, source)
            VALUES (:fips, :date, :tmax, :tmin, :precip, 'nws')
            ON CONFLICT (county_fips, forecast_date) DO UPDATE SET
                tmax_f = EXCLUDED.tmax_f,
                tmin_f = EXCLUDED.tmin_f,
                precip_in = EXCLUDED.precip_in
        """)

        om_stmt = text("""
            INSERT INTO daily_forecast (county_fips, forecast_date, tmax_f, tmin_f, precip_in, et0_in, source)
            VALUES (:fips, :date, :tmax, :tmin, :precip, :et0, 'open-meteo')
            ON CONFLICT (county_fips, forecast_date) DO UPDATE SET
                et0_in = EXCLUDED.et0_in
        """)

        processed = 0
        with httpx.Client() as client:
            for i, county in enumerate(counties):
                fips, _name, _state, lat, lon, grid_id, grid_x, grid_y = county

                # Skip if already has forecast
                if fips in existing:
                    results["skipped_existing"] += 1
                    continue

                processed += 1
                if processed % 25 == 0:
                    print(f"  Progress: {processed} new / {len(counties)} total")

                # 1. NWS grid resolution + forecast
                try:
                    if not grid_id or grid_x is None or grid_y is None:
                        grid_id, grid_x, grid_y = _resolve_grid(client, lat, lon)
                        session.execute(
                            text("UPDATE counties SET grid_id=:gid, grid_x=:gx, grid_y=:gy WHERE fips=:fips"),
                            {"gid": grid_id, "gx": grid_x, "gy": grid_y, "fips": fips},
                        )
                        session.commit()
                        results["grid_resolved"] += 1
                        time.sleep(THROTTLE_DELAY)

                    resp = _nws_get(client, NWS_GRID_URL.format(grid_id=grid_id, grid_x=grid_x, grid_y=grid_y))
                    daily_rows = _parse_daily_periods(resp.json()["properties"])

                    for row in daily_rows:
                        session.execute(nws_stmt, {
                            "fips": fips,
                            "date": row["forecast_date"],
                            "tmax": row["tmax_f"],
                            "tmin": row["tmin_f"],
                            "precip": row["precip_in"],
                        })
                    session.commit()
                    results["nws_ok"] += 1
                    time.sleep(THROTTLE_DELAY)
                except Exception as e:  # noqa: BLE001 — catch-all for resumable backfill
                    results["nws_fail"] += 1
                    err_msg = f"NWS {fips}: {str(e)[:80]}"
                    results["errors"].append(err_msg)
                    if len(results["errors"]) <= 5:
                        print(f"  {err_msg}")

                # 2. Open-Meteo forecast (ET0 overlay)
                try:
                    url = OM_FORECAST_URL.format(lat=lat, lon=lon)
                    resp = client.get(url, timeout=30)
                    resp.raise_for_status()
                    data = resp.json()
                    daily = data.get("daily", {})
                    dates = daily.get("time", [])
                    tmax_list = daily.get("temperature_2m_max", [])
                    tmin_list = daily.get("temperature_2m_min", [])
                    precip_list = daily.get("precipitation_sum", [])
                    et0_list = daily.get("et0_fao_evapotranspiration", [])

                    for j, d in enumerate(dates):
                        session.execute(om_stmt, {
                            "fips": fips,
                            "date": d,
                            "tmax": tmax_list[j] if j < len(tmax_list) else None,
                            "tmin": tmin_list[j] if j < len(tmin_list) else None,
                            "precip": precip_list[j] if j < len(precip_list) else None,
                            "et0": et0_list[j] if j < len(et0_list) else None,
                        })
                    session.commit()
                    results["om_ok"] += 1
                    time.sleep(0.5)
                except Exception as e:  # noqa: BLE001 — catch-all for resumable backfill
                    results["om_fail"] += 1
                    err_msg = f"OM {fips}: {str(e)[:80]}"
                    results["errors"].append(err_msg)
                    if len(results["errors"]) <= 10:
                        print(f"  {err_msg}")

        print("\nBackfill complete:")
        print(f"  Total in-scope: {results['total_inscope']}")
        print(f"  Skipped (existing): {results['skipped_existing']}")
        print(f"  NWS OK: {results['nws_ok']}, FAIL: {results['nws_fail']}")
        print(f"  Open-Meteo OK: {results['om_ok']}, FAIL: {results['om_fail']}")
        print(f"  Grids resolved: {results['grid_resolved']}")
        print(f"  Errors: {len(results['errors'])}")

        return results


if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    backfill_forecasts(date_arg)
