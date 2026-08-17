"""Tests that the DB has been seeded correctly."""
from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://user:password@127.0.0.1:5432/furrowcast",
)

engine = create_engine(DATABASE_URL)


def test_county_count():
    with Session(engine) as db:
        result = db.execute(text("SELECT count(*) FROM counties WHERE state = 'NY'"))
        assert result.scalar() == 62


def test_crop_count():
    with Session(engine) as db:
        result = db.execute(text("SELECT count(*) FROM crops"))
        assert result.scalar() == 9


def test_soil_count():
    with Session(engine) as db:
        result = db.execute(text("SELECT count(*) FROM soils"))
        assert result.scalar() >= 7


def test_counties_have_required_fips():
    required = {"36037", "36003", "36001", "36109"}
    with Session(engine) as db:
        result = db.execute(text("SELECT fips FROM counties WHERE state = 'NY'"))
        fips = {row[0] for row in result}
        assert required.issubset(fips)


def test_crops_have_required_ids():
    expected_ids = {"corn", "soy", "alfalfa", "cover", "cotton", "sorghum",
                    "potatoes", "peanuts", "sunflower"}
    with Session(engine) as db:
        result = db.execute(text("SELECT id FROM crops"))
        ids = {row[0] for row in result}
        assert ids == expected_ids
