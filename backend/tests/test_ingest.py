"""Tests for the data pipeline ingest module."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://user:password@127.0.0.1:5432/furrowcast",
)

engine = create_engine(DATABASE_URL)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


def _get_count(session: Session, table: str) -> int:
    return session.execute(text(f"SELECT count(*) FROM {table}")).scalar()


def _get_count_where(session: Session, table: str, where: str) -> int:
    return session.execute(text(f"SELECT count(*) FROM {table} WHERE {where}")).scalar()


# ── county_loader tests ────────────────────────────────────────────────────

@patch("app.ingest.county_loader.get_counties", return_value=[
    {"fips": "99001", "name": "TestAlpha", "state": "NE", "latitude": 41.0, "longitude": -97.0,
     "frost_kill_10": 260, "frost_kill_50": 270, "frost_kill_90": 280},
    {"fips": "99002", "name": "TestBeta", "state": "IA", "latitude": 42.0, "longitude": -93.0,
     "frost_kill_10": 265, "frost_kill_50": 275, "frost_kill_90": 285},
    {"fips": "99003", "name": "TestGamma", "state": "KS", "latitude": 38.0, "longitude": -98.0,
     "frost_kill_10": 278, "frost_kill_50": 288, "frost_kill_90": 298},
])
def test_county_loader(mock_get):
    from app.ingest.county_loader import load_counties
    with Session(engine) as session:
        session.execute(text("DELETE FROM counties WHERE fips IN ('99001','99002','99003')"))
        session.commit()
        count = load_counties(session)
        assert count == 3
        row = session.execute(text("SELECT name, state FROM counties WHERE fips='99001'")).fetchone()
        assert row[0] == "TestAlpha"
        assert row[1] == "NE"
        session.execute(text("DELETE FROM counties WHERE fips IN ('99001','99002','99003')"))
        session.commit()


@patch("app.ingest.county_loader.get_counties", return_value=[
    {"fips": "99001", "name": "TestAlpha", "state": "NE", "latitude": 41.0, "longitude": -97.0,
     "frost_kill_10": 260, "frost_kill_50": 270, "frost_kill_90": 280},
])
def test_county_loader_idempotent(mock_get):
    from app.ingest.county_loader import load_counties
    with Session(engine) as session:
        session.execute(text("DELETE FROM counties WHERE fips='99001'"))
        session.commit()
        load_counties(session)
        load_counties(session)
        count = _get_count_where(session, "counties", "fips='99001'")
        assert count == 1
        session.execute(text("DELETE FROM counties WHERE fips='99001'"))
        session.commit()


# ── NWS parser tests ──────────────────────────────────────────────────────

def test_nws_parse_grid_response():
    data = _load_fixture("nws_points_oax.json")
    props = data["properties"]
    assert props["gridId"] == "OAX"
    assert props["gridX"] == 31
    assert props["gridY"] == 122


def test_nws_parse_forecast():
    from app.ingest.noaa_nws import _parse_daily_periods
    data = _load_fixture("nws_gridpoints_forecast.json")
    daily_rows = _parse_daily_periods(data["properties"])
    assert len(daily_rows) == 7
    first = daily_rows[0]
    assert first["forecast_date"] == "2026-08-02"
    assert abs(first["tmax_f"] - 87.98) < 0.1  # 31.1°C → 87.98°F
    assert abs(first["tmin_f"] - 64.94) < 0.1  # 18.3°C → 64.94°F
    assert first["precip_in"] == 0.0
    third = daily_rows[2]
    assert abs(third["tmax_f"] - 84.92) < 0.1  # 29.4°C → 84.92°F
    assert abs(third["precip_in"] - 63.5) < 0.01  # 63.5mm


# ── Open-Meteo parser tests ──────────────────────────────────────────────

def test_open_meteo_parse_archive():
    data = _load_fixture("open_meteo_archive.json")
    daily = data["daily"]
    assert len(daily["time"]) == 10
    assert daily["time"][0] == "2026-07-01"
    assert daily["temperature_2m_max"][0] == 88.5
    assert daily["temperature_2m_min"][0] == 65.3
    assert daily["precipitation_sum"][2] == 0.12
    assert daily["et0_fao_evapotranspiration"][0] == 0.28


def test_open_meteo_parse_forecast():
    data = _load_fixture("open_meteo_forecast.json")
    daily = data["daily"]
    assert len(daily["time"]) == 7
    assert daily["time"][0] == "2026-08-02"
    assert all(isinstance(v, float) for v in daily["et0_fao_evapotranspiration"])
    assert daily["et0_fao_evapotranspiration"][0] == 0.27


# ── USDM test ─────────────────────────────────────────────────────────────

def test_usdm_parse():
    from app.ingest.usdm import _parse_usdm_csv
    # Real USDM CSV shape: MapDate,FIPS,County,State,None,D0,D1,D2,D3,D4,
    #                       ValidStart,ValidEnd,StatisticFormatID
    sample_csv = (
        "MapDate,FIPS,County,State,None,D0,D1,D2,D3,D4,ValidStart,ValidEnd,StatisticFormatID\n"
        "20260811,36073,Orleans County,NY,394.23,0.00,0.00,0.00,0.00,0.00,2026-08-11,2026-08-17,1\n"
        "20260804,36073,Orleans County,NY,0.00,15.30,5.10,0.00,0.00,0.00,2026-08-04,2026-08-10,1\n"
        "20260728,36073,Orleans County,NY,0.00,42.10,18.70,3.40,0.00,0.00,2026-07-28,2026-08-03,1\n"
    )
    rows = _parse_usdm_csv(sample_csv)
    assert len(rows) == 3
    # Row 1: all bands 0 -> NONE, week_ending = ValidEnd
    assert rows[0]["week_ending"] == "2026-08-17"
    assert rows[0]["usdm_level"] == "NONE"
    # Row 2: D0=15.30, D1=5.10 -> dominant D1
    assert rows[1]["week_ending"] == "2026-08-10"
    assert rows[1]["usdm_level"] == "D1"
    # Row 3: D0..D2 > 0 -> dominant D2 (highest severity with coverage)
    assert rows[2]["week_ending"] == "2026-08-03"
    assert rows[2]["usdm_level"] == "D2"


def test_usdm_parse_graceful_failure():
    from app.ingest.usdm import _parse_usdm_csv
    assert _parse_usdm_csv("not csv at all") == []
    assert _parse_usdm_csv("") == []


# ── ingest_runs logging test ──────────────────────────────────────────────

def test_ingest_run_logging():
    with Session(engine) as session:
        before = _get_count(session, "ingest_runs")
        session.execute(
            text("""
                INSERT INTO ingest_runs (source, started_at, finished_at, rows_upserted, status)
                VALUES ('test_source', :started, :finished, 42, 'ok')
            """),
            {"started": datetime.utcnow(), "finished": datetime.utcnow()},
        )
        session.commit()
        after = _get_count(session, "ingest_runs")
        assert after == before + 1
        row = session.execute(
            text("SELECT source, rows_upserted, status FROM ingest_runs ORDER BY id DESC LIMIT 1")
        ).fetchone()
        assert row[0] == "test_source"
        assert row[1] == 42
        assert row[2] == "ok"
