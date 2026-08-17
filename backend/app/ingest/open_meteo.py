"""Open-Meteo historical + forecast connector (no API key needed)."""
from __future__ import annotations

import time
from datetime import datetime, timedelta

import httpx
from sqlalchemy.orm import Session
from sqlalchemy import text

ARCHIVE_URL = (
    "https://archive-api.open-meteo.com/v1/archive"
    "?latitude={lat}&longitude={lon}"
    "&start_date={start}&end_date={end}"
    "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,et0_fao_evapotranspiration"
    "&temperature_unit=fahrenheit&precipitation_unit=inch&timezone=America/Chicago"
)
FORECAST_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lat}&longitude={lon}"
    "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,et0_fao_evapotranspiration"
    "&temperature_unit=fahrenheit&precipitation_unit=inch&forecast_days=7&timezone=America/Chicago"
)


def _fetch_json(url: str) -> dict:
    with httpx.Client() as client:
        resp = client.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()


def fetch_history(session: Session, county: dict, start_date: str, end_date: str) -> int:
    fips = county["fips"]
    lat = county["latitude"]
    lon = county["longitude"]

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

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


def fetch_forecast(session: Session, county: dict) -> int:
    fips = county["fips"]
    lat = county["latitude"]
    lon = county["longitude"]

    url = FORECAST_URL.format(lat=lat, lon=lon)
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
