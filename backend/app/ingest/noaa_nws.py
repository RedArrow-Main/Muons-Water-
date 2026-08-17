"""NOAA NWS forecast connector."""
from __future__ import annotations

import time
from datetime import datetime, timedelta

import httpx
from sqlalchemy.orm import Session
from sqlalchemy import text

NWS_POINTS_URL = "https://api.weather.gov/points/{lat},{lon}"
NWS_GRID_URL = "https://api.weather.gov/gridpoints/{grid_id}/{grid_x},{grid_y}"
HEADERS = {"User-Agent": "(FurrowCast, contact@furrowcast.app)"}


def _resolve_grid(client: httpx.Client, lat: float, lon: float) -> tuple[str, int, int]:
    resp = client.get(NWS_POINTS_URL.format(lat=lat, lon=lon), headers=HEADERS, timeout=15)
    resp.raise_for_status()
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


def fetch_nws_forecast(session: Session, county: dict) -> int:
    fips = county["fips"]
    grid_id = county.get("grid_id")
    grid_x = county.get("grid_x")
    grid_y = county.get("grid_y")

    with httpx.Client() as client:
        if not grid_id or grid_x is None or grid_y is None:
            grid_id, grid_x, grid_y = _resolve_grid(client, county["latitude"], county["longitude"])
            session.execute(
                text("UPDATE counties SET grid_id=:gid, grid_x=:gx, grid_y=:gy WHERE fips=:fips"),
                {"gid": grid_id, "gx": grid_x, "gy": grid_y, "fips": fips},
            )
            session.commit()
            time.sleep(1)

        resp = client.get(
            NWS_GRID_URL.format(grid_id=grid_id, grid_x=grid_x, grid_y=grid_y),
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()

    daily_rows = _parse_daily_periods(resp.json()["properties"])

    stmt = text("""
        INSERT INTO daily_forecast (county_fips, forecast_date, tmax_f, tmin_f, precip_in, source)
        VALUES (:fips, :date, :tmax, :tmin, :precip, 'nws')
        ON CONFLICT (county_fips, forecast_date) DO UPDATE SET
            tmax_f = EXCLUDED.tmax_f,
            tmin_f = EXCLUDED.tmin_f,
            precip_in = EXCLUDED.precip_in
    """)
    count = 0
    for row in daily_rows:
        session.execute(stmt, {
            "fips": fips,
            "date": row["forecast_date"],
            "tmax": row["tmax_f"],
            "tmin": row["tmin_f"],
            "precip": row["precip_in"],
        })
        count += 1
    session.commit()
    time.sleep(1)
    return count
