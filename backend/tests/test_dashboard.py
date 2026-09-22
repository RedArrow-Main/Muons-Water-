"""Tests for Dashboard API endpoints — with auth protection."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.connection import engine
from app.main import app

client = TestClient(app)


# Shared auth session
_TOKEN = None




def setup_module():
    global _TOKEN
    with Session(engine) as s:
        # Delete farms first (FK: farms.user_id -> users.id)
        s.execute(text(
            "DELETE FROM farms WHERE user_id IN "
            "(SELECT id FROM users WHERE email = 'dash@test.com')"
        ))
        s.execute(text("DELETE FROM users WHERE email = 'dash@test.com'"))
        s.commit()
    r = client.post("/api/auth/register", json={
        "email": "dash@test.com", "password": "testpass123",
    })
    _TOKEN = r.cookies.get("session")
    client.cookies.set("session", _TOKEN)




def teardown_module():
    client.cookies.clear()
    with Session(engine) as s:
        s.execute(text(
            "DELETE FROM farms WHERE user_id IN "
            "(SELECT id FROM users WHERE email = 'dash@test.com')"
        ))
        s.execute(text("DELETE FROM users WHERE email = 'dash@test.com'"))
        s.commit()




# ---------------------------------------------------------------------------
# Health (public)
# ---------------------------------------------------------------------------


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True




# ---------------------------------------------------------------------------
# Counties (public)
# ---------------------------------------------------------------------------


def test_list_counties():
    r = client.get("/api/counties")
    assert r.status_code == 200
    data = r.json()
    ny = [c for c in data if c["state"] == "NY"]
    assert len(ny) == 62
    assert data[0]["fips"]
    assert "lat" in data[0]




# ---------------------------------------------------------------------------
# Crop Library (public)
# ---------------------------------------------------------------------------


def test_list_crops():
    r = client.get("/api/crops")
    assert r.status_code == 200
    data = r.json()
    ids = {c["id"] for c in data}
    assert {"corn", "soy", "alfalfa", "cover", "potatoes", "sunflower",
            "cabbage", "onions", "sweet corn"} == ids
    assert len(data) == 9
    corn = next(c for c in data if c["id"] == "corn")
    assert corn["gdd_total"] == 2700
    assert corn["base_temp_f"] == 50.0
    assert corn["mad_fraction"] == 0.5




# ---------------------------------------------------------------------------
# Advisory (auth required)
# ---------------------------------------------------------------------------


def test_get_advisory_cedar_ne():
    """Legacy Corn Belt coverage — D-006 made NY the sole product scope, so
    NE/IA/KS counties are legacy/stale and are NOT loaded by
    `app.db.bootstrap` (NY-only, the standard local/CI setup — see
    README.md Quickstart). They're only present if `app.db.seed` was also
    run. Skip rather than fail when the row genuinely isn't seeded, so this
    test doesn't flip pass/fail based on which seeding path was used; if the
    county IS present (dev DB seeded from legacy data), still assert it
    responds correctly.
    """
    r = client.get("/api/advisory/31027")
    if r.status_code == 404:
        pytest.skip("NE county 31027 not seeded (bootstrap.py is NY-only per D-006); "
                     "run `python -m app.db.seed` for legacy Corn Belt coverage")
    assert r.status_code == 200
    data = r.json()
    assert data["county"]["name"] == "Cedar"
    assert data["county"]["state"] == "NE"
    assert data["soil"]["type"] in ("silt loam", "SILT LOAM")
    assert "forecast" in data
    assert "gdd" in data["today"]
    assert "action" in data["today"]
    assert "planting_window" in data
    assert "frost_50pct" in data["planting_window"]




def test_get_advisory_story_ia():
    """Legacy Corn Belt coverage — see test_get_advisory_cedar_ne docstring."""
    r = client.get("/api/advisory/19169")
    if r.status_code == 404:
        pytest.skip("IA county 19169 not seeded (bootstrap.py is NY-only per D-006); "
                     "run `python -m app.db.seed` for legacy Corn Belt coverage")
    assert r.status_code == 200
    data = r.json()
    assert data["county"]["name"] == "Story"
    assert data["county"]["state"] == "IA"




def test_get_advisory_uses_real_soil_from_db():
    r = client.get("/api/advisory/36029")
    assert r.status_code == 200
    data = r.json()
    assert data["soil"]["type"] == "silt loam"
    assert abs(data["soil"]["awc"] - 0.1183) < 1e-4




# ---------------------------------------------------------------------------
# _get_soil_awc fallback — must not mislabel non-Corn-Belt states
# ---------------------------------------------------------------------------


def test_get_soil_awc_ny_uses_state_default_not_nebraska_bucket():
    """A NY county with no `soils` row must fall back to the real NY SSURGO
    state default (see app.ingest.ssurgo.STATE_DEFAULTS), not the legacy
    Nebraska/Kansas/Iowa lat/lon buckets that used to catch any lat >= 41
    (which covers all of NY) and silently returned another state's soil.
    """
    from app.dashboard.routes import _get_soil_awc
    from app.ingest.ssurgo import STATE_DEFAULTS


    # Genesee County, NY — real coordinates (~43.0 N, -78.2 W), lat >= 41
    # used to fall into the "Nebraska" branch of the old lat/lon-only logic.
    soil_type, awc = _get_soil_awc("NY", 43.0, -78.2)
    assert (soil_type, awc) == STATE_DEFAULTS["NY"]
    assert soil_type != "SAND"  # old NE-Sandhills-style value it used to risk




def test_get_soil_awc_legacy_corn_belt_states_unaffected():
    """KS/NE/IA keep their existing quadrant-bucket behavior."""
    from app.dashboard.routes import _get_soil_awc


    soil_type, awc = _get_soil_awc("NE", 42.5, -101.5)
    assert soil_type  # still returns one of the legacy NE bucket values
    assert 0.0 < awc < 1.0




def test_get_advisory_not_found():
    r = client.get("/api/advisory/00000")
    assert r.status_code == 404




def test_get_advisory_unauthenticated():
    c = TestClient(app, cookies={})
    r = c.get("/api/advisory/31027")
    assert r.status_code == 401




# ---------------------------------------------------------------------------
# Advisory — crop + planting date, growth stage, stage-adjusted MAD
# ---------------------------------------------------------------------------


_MAD_FACTORS = {
    "vegetative": 1.0, "pollination": 0.6, "grain_fill": 0.8, "maturity": 1.0,
}




def test_get_advisory_with_crop_and_planting_date():
    r = client.get("/api/advisory/36037?crop_id=corn&planting_date=2026-08-01")
    assert r.status_code == 200
    data = r.json()
    crop = data["crop"]
    assert crop["id"] == "corn"
    assert crop["planting_date"] == "2026-08-01"
    assert crop["base_mad"] == 0.5
    assert crop["growth_stage"] in _MAD_FACTORS
    assert crop["stage_label"]
    assert crop["gdd_to_maturity"] == 2700
    assert 0.0 <= crop["gdd_pct"] <= 100.0
    # Stage-adjusted MAD = base_mad × factor of the current stage
    assert crop["mad"] == pytest.approx(
        crop["base_mad"] * _MAD_FACTORS[crop["growth_stage"]], abs=0.001
    )
    assert "forecast" in data
    assert "growth_stage" in crop




def test_get_advisory_soy_stage_weight_lower():
    """Soy has same GDD base but deeper season — verify engine wiring."""
    r = client.get("/api/advisory/36037?crop_id=soy&planting_date=2026-08-01")
    assert r.status_code == 200
    crop = r.json()["crop"]
    assert crop["id"] == "soy"
    assert crop["gdd_to_maturity"] == 2500
    assert crop["mad"] == pytest.approx(
        crop["base_mad"] * _MAD_FACTORS[crop["growth_stage"]], abs=0.001
    )




def test_get_advisory_unknown_crop_404():
    r = client.get("/api/advisory/36037?crop_id=banana&planting_date=2026-08-01")
    assert r.status_code == 404




def test_get_advisory_default_planting_date():
    """No planting_date → backend sets the county's latest safe plant date."""
    r = client.get("/api/advisory/36037?crop_id=corn")
    assert r.status_code == 200
    crop = r.json()["crop"]
    assert crop["planting_date"]
    assert crop["growth_stage"] in _MAD_FACTORS




def test_get_advisory_uses_farm_crop_default():
    """Farm's crop + planting_date become the advisory defaults."""
    body = None
    try:
        r = client.post("/api/farm", json={
            "county_fips": "36037",
            "name": "Contract Test Farm",
            "crops": [{"crop_id": "soy", "planting_date": "2026-08-01"}],
        })
        assert r.status_code == 200
        body = r.json()
        assert body["crops"] == [{"crop_id": "soy", "planting_date": "2026-08-01"}]


        r = client.get("/api/advisory/36037")
        assert r.status_code == 200
        crop = r.json()["crop"]
        assert crop["id"] == "soy"
        assert crop["planting_date"] == "2026-08-01"
    finally:
        if body and body.get("id"):
            client.delete(f"/api/farm/{body['id']}")




# ---------------------------------------------------------------------------
# Outbox (auth required)
# ---------------------------------------------------------------------------


def test_get_outbox():
    r = client.get("/api/outbox/31027")
    assert r.status_code == 200
    assert isinstance(r.json(), list)




def test_get_outbox_unauthenticated():
    c = TestClient(app, cookies={})
    r = c.get("/api/outbox/31027")
    assert r.status_code == 401




# ---------------------------------------------------------------------------
# Stats (auth required)
# ---------------------------------------------------------------------------


def test_get_stats():
    r = client.get("/api/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["counties"] >= 62
    assert "forecast_rows" in data
    assert "ingests" in data
    assert "last_pipeline_at" in data
    assert "last_pipeline_status" in data
    assert "last_pipeline_rows" in data




def test_get_stats_unauthenticated():
    c = TestClient(app, cookies={})
    r = c.get("/api/stats")
    assert r.status_code == 401




# ---------------------------------------------------------------------------
# Advisory data_as_of (pipeline freshness)
# ---------------------------------------------------------------------------


def test_get_advisory_data_as_of():
    r = client.get("/api/advisory/36037")
    assert r.status_code == 200
    data = r.json()
    assert "data_as_of" in data
    assert set(data["data_as_of"].keys()) == {
        "last_pipeline_at", "last_pipeline_status", "last_pipeline_rows",
    }
    assert data["data_as_of"]["last_pipeline_at"] is None or isinstance(
        data["data_as_of"]["last_pipeline_at"], str)




# ---------------------------------------------------------------------------
# Admin refresh (auth required)
# ---------------------------------------------------------------------------


def test_admin_refresh_unauthenticated():
    c = TestClient(app, cookies={})
    r = c.post("/api/admin/refresh", json={})
    assert r.status_code == 401




def test_admin_refresh_runs_pipeline(monkeypatch):
    fake = {
        "counties_processed": 62,
        "nws_ok": 62, "nws_fail": 0,
        "om_fc_ok": 62, "om_fc_fail": 0,
        "om_hist_ok": 62, "om_hist_fail": 0,
        "usdm_ok": 62, "usdm_fail": 0,
        "spinup_ok": 62, "spinup_fail": 0,
        "advisories_generated": 62, "advisory_errors": 0,
    }
    calls = {}


    def fake_pipeline(_s, run_date, send_sms=False, states=("NY",)):
        calls["date"] = run_date
        calls["sms"] = send_sms
        calls["states"] = list(states)
        return fake


    import app.nightly as nightly_module
    monkeypatch.setattr(nightly_module, "run_pipeline", fake_pipeline)
    r = client.post("/api/admin/refresh", json={"date": "2026-08-17"})
    assert r.status_code == 200
    assert r.json() == fake
    assert calls["date"] == "2026-08-17"
    assert calls["sms"] is False
    assert calls["states"] == ["NY"]

@pytest.mark.parametrize("low,high,uncertain", [(60, 60, False), (0, 100, True)])
def test_forecast_preserves_season_gdd_and_stored_water(monkeypatch, low, high, uncertain):
    from app.dashboard import routes

    monkeypatch.setattr(routes, '_historical_temps', lambda *a, **k: {
        str(i): (89, 71) for i in range(46)
    })
    monkeypatch.setattr(routes, '_fetch_json', lambda *a, **k: {'daily': {
        'time': ['2026-09-08'], 'temperature_2m_max': [89],
        'temperature_2m_min': [71], 'precipitation_sum': [0],
        'et0_fao_evapotranspiration': [0.28],
    }})
    monkeypatch.setattr(routes, 'fetch_archive_daily', lambda *a, **k: None)
    monkeypatch.setattr(routes, '_initial_soil_pct', lambda *a: (60.0, 'stored', low, high), raising=False)
    response = client.get('/api/advisory/36037?crop_id=corn&planting_date=2026-05-15')
    assert response.status_code == 200
    data = response.json()
    assert data['crop']['cumulative_gdd'] == 1380
    assert data['today']['etc'] == pytest.approx(0.336)
    assert data['today']['advice_uncertain'] is uncertain
    assert data['today']['soil_water'] == pytest.approx(
        round(0.60 * data['crop']['aw'] - 0.336, 3), abs=0.004
    )


def test_initial_soil_uses_matching_date_and_crop():
    from app.dashboard.routes import _initial_soil_pct

    with Session(engine) as session:
        cell = session.execute(text(
            "INSERT INTO field_cells (county_fips,crop_id,row,col,soil_type,awc) "
            "VALUES ('36037','soy',999,999,'test',0.2) RETURNING id"
        )).scalar_one()
        session.execute(text(
            "INSERT INTO daily_records (cell_id,record_date,soil_moisture_pct,soil_min_pct,soil_max_pct) "
            "VALUES (:id,'2099-01-01',42,42,42)"
        ), {'id': cell})
        session.commit()
        try:
            assert _initial_soil_pct('36037', 'soy', '2099-01-01') == (42, 'stored', 42, 42)
            assert _initial_soil_pct('36037', 'corn', '2099-01-01') == (50, 'assumed', 0, 100)
            assert _initial_soil_pct('36037', 'soy', '2099-01-02') == (50, 'assumed', 0, 100)
        finally:
            session.execute(text('DELETE FROM daily_records WHERE cell_id=:id'), {'id': cell})
            session.execute(text('DELETE FROM field_cells WHERE id=:id'), {'id': cell})
            session.commit()
