"""Fetch Open-Meteo ET0 forecast for all counties missing it."""
import time
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.connection import engine
from app.ingest.open_meteo import fetch_forecast

with Session(engine) as s:
    missing = s.execute(text(
        "SELECT c.fips, c.name, c.state, c.latitude, c.longitude "
        "FROM counties c "
        "WHERE c.state IN ('NE','IA','KS') "
        "AND NOT EXISTS "
        "(SELECT 1 FROM daily_forecast df WHERE df.county_fips = c.fips AND df.et0_in IS NOT NULL) "
        "ORDER BY c.fips"
    )).fetchall()
    print(f"Counties missing ET0: {len(missing)}")
    ok = 0
    fail = 0
    for i, c in enumerate(missing):
        fips, name, state, lat, lon = c
        county = {"fips": fips, "name": name, "state": state, "latitude": lat, "longitude": lon}
        try:
            fetch_forecast(s, county)
            ok += 1
        except Exception as e:
            fail += 1
            if fail <= 3:
                print(f"  FAIL {fips} {name}: {str(e)[:60]}")
        if (i + 1) % 50 == 0:
            print(f"  Progress: {i+1}/{len(missing)} (ok={ok}, fail={fail})")
    print(f"Done: ok={ok}, fail={fail}")
