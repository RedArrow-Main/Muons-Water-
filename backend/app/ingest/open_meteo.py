"""Open-Meteo historical + forecast connector (no API key needed)."""
from __future__ import annotations

import time
from datetime import date, timedelta
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

ARCHIVE_URL = (
    "https://archive-api.open-meteo.com/v1/archive"
    "?latitude={lat}&longitude={lon}"
    "&start_date={start}&end_date={end}"
    "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,et0_fao_evapotranspiration"
    "&temperature_unit=fahrenheit&precipitation_unit=inch&timezone={tz}"
)
FORECAST_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lat}&longitude={lon}"
    "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,et0_fao_evapotranspiration"
    "&temperature_unit=fahrenheit&precipitation_unit=inch&forecast_days=7&timezone={tz}"
)

_STATE_TZ = {
    "NY": "America/New_York",
    "NE": "America/Chicago",
    "IA": "America/Chicago",
    "KS": "America/Chicago",
}


def tz_for_state(state: str) -> str:
    """Open-Meteo daily buckets are timezone-sensitive; NY is Eastern."""
    return _STATE_TZ.get(state, "America/New_York")


def fetch_archive_daily(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    tz: str = "America/New_York",
    timeout: int = 30,
) -> dict[str, Any] | None:
    """Fetch daily archive from Open-Meteo. Returns dict with keys:
    time, temperature_2m_max, temperature_2m_min, precipitation_sum,
    et0_fao_evapotranspiration — or None on error.

    This is the shared helper used by both the advisor and dashboard.
    """
    url = ARCHIVE_URL.format(lat=lat, lon=lon, start=start_date, end=end_date, tz=tz)
    try:
        with httpx.Client() as client:
            resp = client.get(url, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            if data.get("error"):
                return None
            return data.get("daily")
    except (httpx.HTTPError, ValueError):
        return None


def _fetch_json(url: str) -> dict:
    with httpx.Client() as client:
        resp = client.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            raise ValueError(f"Open-Meteo API error: {data.get('reason', 'unknown')}")
        return data


def fetch_history(session: Session, county: dict, start_date: str, end_date: str,
                  tz: str = "America/Chicago") -> int:
    fips = county["fips"]
    lat = county["latitude"]
    lon = county["longitude"]

    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)

    stmt = text("""
        INSERT INTO daily_historical (county_fips, obs_date, tmax_f, tmin_f, precip_in, et0_in)
        VALUES (:fips, :date, :tmax, :tmin, :precip, :et0)
        ON CONFLICT (county_fips, obs_date) DO UPDATE SET
            tmax_f = EXCLUDED.tmax_f,
            tmin_f = EXCLUDED.tmin_f,
            precip_in = EXCLUDED.precip_in,
            et0_in = EXCLUDED.et0_in
    """)

    count = 0
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(chunk_start + timedelta(days=364), end)
        url = ARCHIVE_URL.format(
            lat=lat, lon=lon,
            start=chunk_start.strftime("%Y-%m-%d"),
            end=chunk_end.strftime("%Y-%m-%d"),
            tz=tz,
        )
        data = _fetch_json(url)
        daily = data.get("daily", {})
        dates = daily.get("time", [])
        tmax_list = daily.get("temperature_2m_max", [])
        tmin_list = daily.get("temperature_2m_min", [])
        precip_list = daily.get("precipitation_sum", [])
        et0_list = daily.get("et0_fao_evapotranspiration", [])

        for i, d in enumerate(dates):
            session.execute(stmt, {
                "fips": fips,
                "date": d,
                "tmax": tmax_list[i] if i < len(tmax_list) else None,
                "tmin": tmin_list[i] if i < len(tmin_list) else None,
                "precip": precip_list[i] if i < len(precip_list) else None,
                "et0": et0_list[i] if i < len(et0_list) else None,
            })
            count += 1
        session.commit()
        chunk_start = chunk_end + timedelta(days=1)
        time.sleep(0.5)

    return count


def fetch_forecast(session: Session, county: dict, tz: str = "America/Chicago") -> int:
    fips = county["fips"]
    lat = county["latitude"]
    lon = county["longitude"]

    url = FORECAST_URL.format(lat=lat, lon=lon, tz=tz)
    data = _fetch_json(url)
    daily = data.get("daily", {})
    dates = daily.get("time", [])
    tmax_list = daily.get("temperature_2m_max", [])
    tmin_list = daily.get("temperature_2m_min", [])
    precip_list = daily.get("precipitation_sum", [])
    et0_list = daily.get("et0_fao_evapotranspiration", [])

    stmt = text("""
        INSERT INTO daily_forecast (county_fips, forecast_date, tmax_f, tmin_f, precip_in, et0_in, source)
        VALUES (:fips, :date, :tmax, :tmin, :precip, :et0, 'open-meteo')
        ON CONFLICT (county_fips, forecast_date) DO UPDATE SET
            et0_in = EXCLUDED.et0_in
    """)

    count = 0
    for i, d in enumerate(dates):
        session.execute(stmt, {
            "fips": fips,
            "date": d,
            "tmax": tmax_list[i] if i < len(tmax_list) else None,
            "tmin": tmin_list[i] if i < len(tmin_list) else None,
            "precip": precip_list[i] if i < len(precip_list) else None,
            "et0": et0_list[i] if i < len(et0_list) else None,
        })
        count += 1
    session.commit()
    time.sleep(0.5)
    return count
