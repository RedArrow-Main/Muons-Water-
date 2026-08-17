"""Load all US counties into the database (idempotent upsert)."""
from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import text

from .counties_data import get_counties


def load_counties(session: Session) -> int:
    stmt = text("""
        INSERT INTO counties (fips, name, state, latitude, longitude,
                              frost_kill_10, frost_kill_50, frost_kill_90)
        VALUES (:fips, :name, :state, :latitude, :longitude,
                :frost_kill_10, :frost_kill_50, :frost_kill_90)
        ON CONFLICT (fips) DO UPDATE SET
            name = EXCLUDED.name,
            state = EXCLUDED.state,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            frost_kill_10 = EXCLUDED.frost_kill_10,
            frost_kill_50 = EXCLUDED.frost_kill_50,
            frost_kill_90 = EXCLUDED.frost_kill_90
    """)
    counties = get_counties()
    count = 0
    for county in counties:
        session.execute(stmt, {
            "fips": county["fips"],
            "name": county["name"],
            "state": county["state"],
            "latitude": county["latitude"],
            "longitude": county["longitude"],
            "frost_kill_10": county["frost_kill_10"],
            "frost_kill_50": county["frost_kill_50"],
            "frost_kill_90": county["frost_kill_90"],
        })
        count += 1
    session.commit()
    print(f"Upserted {count} counties")
    return count
