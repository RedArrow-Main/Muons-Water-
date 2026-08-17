"""Tests for Dashboard API endpoints — with auth protection."""
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app
from app.db.connection import engine

client = TestClient(app)

# Shared auth session
_TOKEN = None


def setup_module():
    global _TOKEN
    with Session(engine) as s:
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
# Advisory (auth required)
# ---------------------------------------------------------------------------

def test_get_advisory_cedar_ne():
    r = client.get("/api/advisory/31027")
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
    r = client.get("/api/advisory/19169")
    assert r.status_code == 200
    data = r.json()
    assert data["county"]["name"] == "Story"
    assert data["county"]["state"] == "IA"


def test_get_advisory_not_found():
    r = client.get("/api/advisory/00000")
    assert r.status_code == 404


def test_get_advisory_unauthenticated():
    c = TestClient(app, cookies={})
    r = c.get("/api/advisory/31027")
    assert r.status_code == 401


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
