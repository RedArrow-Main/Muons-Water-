"""Transactional regression for seasonal spin-up; leaves local data untouched."""
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.connection import engine
from app.nightly import _sync_cell_and_spinup


def test_season_history_and_repeat_run(monkeypatch):
    from app.engine import spinup

    original = spinup.spinup_soil_moisture
    calls = []

    def capture(**kwargs):
        calls.append((len(kwargs['weather_series']), kwargs['initial_sw']))
        return original(**kwargs)

    monkeypatch.setattr(spinup, 'spinup_soil_moisture', capture)
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            with Session(bind=connection) as session:
                session.execute(text("DELETE FROM daily_historical WHERE county_fips='36039'"))
                start = date(2026, 5, 15)
                for i in range(61):
                    session.execute(text(
                        "INSERT INTO daily_historical VALUES ('36039',:d,89,71,0,0.28)"
                    ), {'d': (start + timedelta(days=i)).isoformat()})
                county = {'fips': '36039'}
                for _ in range(2):
                    ok, detail = _sync_cell_and_spinup(session, county, [], '2026-07-15')
                    assert ok, detail
                # 47 days before the 14-day window, each (89+71)/2-50=30 GDD.
                assert len(calls) == 4
                assert all(n == 61 for n, _ in calls)
                assert calls[0][1] == 0
                assert calls[1][1] > 0
                records = session.execute(text(
                    "SELECT dr.gdd,dr.growth_stage FROM daily_records dr "
                    "JOIN field_cells fc ON fc.id=dr.cell_id WHERE fc.county_fips='36039' "
                    "AND fc.crop_id='corn' AND dr.record_date='2026-07-15'"
                )).all()
                assert records == [(1830, 'grain_fill')]
                session.execute(text(
                    "DELETE FROM daily_historical WHERE county_fips='36039' AND obs_date='2026-06-01'"
                ))
                assert _sync_cell_and_spinup(session, county, [], '2026-07-15') == (
                    False, 'incomplete planting-to-run history'
                )
        finally:
            transaction.rollback()
