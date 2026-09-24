"""A county whose soil spin-up failed must not issue confident advice.

Erie County (36029) lost its Open-Meteo archive fetch to a TLS timeout during
the 2026-09-22 nightly run. Its spin-up failed, so its soil-water history was
never rebuilt — yet it still produced `HOLD` at 90.4% soil moisture with
advice_uncertain=False, against a 65.1% statewide average, and the run
reported success. See DECISIONS.md D-017.
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.advisor import service
from app.db.connection import engine

TEST_DATE = "2026-01-20"   # no pipeline data on this date

# Shape mirrors _build_water_state's return. Deliberately confident:
# advice_uncertain False, so any True in the result came from the degradation.
CONFIDENT_STATE = {
    "advice_uncertain": False,
    "soil_min_pct": 74.0, "soil_max_pct": 78.0,
    "gdd": 25.0, "soil_pct": 76.0, "depletion": 0.24,
    "mad": 0.50, "base_mad": 0.50, "aw": 7.2, "etc_in": 0.26,
    "forecast_rain_7d": 0.0, "refill_amount": 0.0,
    "drought_level": "NONE", "soil_type": "silt loam", "crop_id": "corn",
    "county_name": "Erie", "county_state": "NY", "date": TEST_DATE,
}


@pytest.fixture()
def one_county(monkeypatch):
    """Restrict generate_all to a single real county with a synthetic state."""
    with Session(engine) as s:
        row = s.execute(text(
            "SELECT fips FROM counties WHERE state='NY' ORDER BY fips LIMIT 1"
        )).fetchone()
    if not row:
        pytest.skip("no NY counties seeded")
    target = row[0]

    def only_target(session, fips, date):
        if fips != target:
            return None, "test_filter"
        return dict(CONFIDENT_STATE), None

    monkeypatch.setattr(service, "_build_water_state", only_target)
    _cleanup(target)
    yield target
    _cleanup(target)


def _cleanup(fips):
    with Session(engine) as s:
        s.execute(text(
            "DELETE FROM advisories WHERE county_fips=:f "
            "AND source_data->>'date' = :d"
        ), {"f": fips, "d": TEST_DATE})
        s.commit()


def _stored_flag(fips):
    with Session(engine) as s:
        row = s.execute(text(
            "SELECT source_data FROM advisories "
            "WHERE county_fips=:f AND source_data->>'date' = :d "
            "ORDER BY generated_at DESC LIMIT 1"
        ), {"f": fips, "d": TEST_DATE}).fetchone()
    assert row is not None, "no advisory was written"
    data = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    return data["advice_uncertain"]


def test_failed_spinup_forces_uncertain(one_county):
    """The whole point: degraded data must not produce confident advice."""
    res = service.generate_all(TEST_DATE, degraded_fips={one_county})
    assert res["advisories_generated"] == 1
    assert _stored_flag(one_county) is True


def test_healthy_county_keeps_its_computed_flag(one_county):
    """Control — without degradation the computed value is preserved."""
    res = service.generate_all(TEST_DATE)
    assert res["advisories_generated"] == 1
    assert _stored_flag(one_county) is False


def _stage_for_sms(fips, phone):
    """Put the advisory on TEST_DATE so _send_sms_advisories can find it.

    That function filters on DATE(generated_at), which generate_all sets to the
    wall clock. Without this the send would find nothing and report 0 sent —
    passing for the wrong reason.
    """
    with Session(engine) as s:
        s.execute(text(
            "UPDATE advisories SET generated_at = :ts "
            "WHERE county_fips=:f AND source_data->>'date' = :d"
        ), {"ts": f"{TEST_DATE} 12:00:00+00", "f": fips, "d": TEST_DATE})
        s.execute(text("DELETE FROM outbox WHERE phone_to=:p"), {"p": phone})
        s.execute(text("DELETE FROM subscribers WHERE phone=:p"), {"p": phone})
        s.execute(text(
            "INSERT INTO subscribers (county_fips, phone, active) VALUES (:f,:p,true)"
        ), {"f": fips, "p": phone})
        s.commit()


def _unstage(phone):
    with Session(engine) as s:
        s.execute(text("DELETE FROM outbox WHERE phone_to=:p"), {"p": phone})
        s.execute(text("DELETE FROM subscribers WHERE phone=:p"), {"p": phone})
        s.commit()


def test_degraded_advisory_is_not_texted(one_county):
    """advice_uncertain already gates SMS; degradation must reach that gate."""
    from app.nightly import _send_sms_advisories

    phone = "+15557770001"
    service.generate_all(TEST_DATE, degraded_fips={one_county})
    _stage_for_sms(one_county, phone)
    try:
        with Session(engine) as s:
            assert _send_sms_advisories(s, TEST_DATE)["sms_sent"] == 0
    finally:
        _unstage(phone)


def test_healthy_advisory_is_texted(one_county):
    """Control for the test above — proves the assertion can detect a send."""
    from app.nightly import _send_sms_advisories

    phone = "+15557770002"
    service.generate_all(TEST_DATE)
    _stage_for_sms(one_county, phone)
    try:
        with Session(engine) as s:
            assert _send_sms_advisories(s, TEST_DATE)["sms_sent"] == 1
    finally:
        _unstage(phone)


def test_pipeline_passes_failed_spinup_counties_to_generate_all(monkeypatch):
    """The Erie path end to end: a spin-up failure must reach generate_all.

    This is the layer the bug actually lived in — generate_all was called with
    no knowledge of which counties had failed, so a county with no rebuilt
    history still produced confident advice.
    """
    from app import nightly

    seen = {}

    monkeypatch.setattr(nightly, "_inscope_counties",
                        lambda session, states: [{"fips": "36029", "name": "Erie",
                                                  "latitude": 42.9, "longitude": -78.8}])
    monkeypatch.setattr(nightly, "_fetch_one_county_weather",
                        lambda session, county, run_date, lookback: ([{"day": 1}], {}))
    # Erie's spin-up fails, exactly as the TLS timeout made it fail.
    monkeypatch.setattr(nightly, "_sync_cell_and_spinup",
                        lambda session, county, series, run_date: (False, "tls timeout"))
    monkeypatch.setattr(nightly, "_fetch_drought_all", lambda session, counties, d: (0, 0))

    def capture(date, degraded_fips=()):
        seen["degraded"] = set(degraded_fips)
        return {"advisories_generated": 1, "advisories_degraded": 1,
                "errors": 0, "counties_skipped": 0, "skip_reasons": {}}

    # run_pipeline imports generate_all inside the function, so patch the source.
    monkeypatch.setattr(service, "generate_all", capture)

    with Session(engine) as s:
        res = nightly.run_pipeline(s, TEST_DATE, send_sms=False)

    assert seen["degraded"] == {"36029"}, "failed spin-up never reached generate_all"
    assert res["degraded_counties"] == ["36029"]
    assert res["advisories_degraded"] == 1
