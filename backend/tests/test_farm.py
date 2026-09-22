"""Tests for Farm API — planting_date on farm crops."""
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.connection import engine
from app.main import app

client = TestClient(app)

_FARM_EMAIL = "farm-test@test.com"


def setup_module():
    with Session(engine) as s:
        s.execute(text(
            "DELETE FROM farms WHERE user_id IN "
            "(SELECT id FROM users WHERE email = :e)"
        ), {"e": _FARM_EMAIL})
        s.execute(text("DELETE FROM users WHERE email = :e"), {"e": _FARM_EMAIL})
        s.commit()
    r = client.post("/api/auth/register", json={
        "email": _FARM_EMAIL, "password": "testpass123",
    })
    assert r.status_code == 200
    client.cookies.set("session", r.cookies.get("session"))


def teardown_module():
    client.cookies.clear()
    with Session(engine) as s:
        s.execute(text(
            "DELETE FROM farms WHERE user_id IN "
            "(SELECT id FROM users WHERE email = :e)"
        ), {"e": _FARM_EMAIL})
        s.execute(text("DELETE FROM users WHERE email = :e"), {"e": _FARM_EMAIL})
        s.commit()


def _delete_farms():
    with Session(engine) as s:
        s.execute(text("DELETE FROM farms"))
        s.commit()


def test_create_farm_with_planting_dates():
    _delete_farms()
    r = client.post("/api/farm", json={
        "county_fips": "36037",
        "name": "Springfield",
        "acres": 120,
        "crops": [
            {"crop_id": "corn", "planting_date": "2026-05-01"},
            {"crop_id": "soy", "planting_date": "2026-05-20"},
        ],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["crops"] == [
        {"crop_id": "corn", "planting_date": "2026-05-01"},
        {"crop_id": "soy", "planting_date": "2026-05-20"},
    ]


def test_create_farm_legacy_crop_ids_still_works():
    _delete_farms()
    r = client.post("/api/farm", json={
        "county_fips": "36037",
        "name": "Legacy Field",
        "crop_ids": ["corn", "soy"],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["crops"] == [
        {"crop_id": "corn", "planting_date": None},
        {"crop_id": "soy", "planting_date": None},
    ]


def test_list_farms_includes_planting_dates():
    _delete_farms()
    client.post("/api/farm", json={
        "county_fips": "36037",
        "name": "River Bend",
        "crops": [{"crop_id": "potatoes", "planting_date": "2026-06-01"}],
    })
    r = client.get("/api/farm")
    assert r.status_code == 200
    body = r.json()
    assert any(
        f["name"] == "River Bend"
        and f["crops"] == [{"crop_id": "potatoes", "planting_date": "2026-06-01"}]
        for f in body
    )


def test_farm_endpoints_require_auth():
    c = TestClient(app, cookies={})
    assert c.get("/api/farm").status_code == 401
    assert c.post("/api/farm", json={"county_fips": "36037", "name": "X",
                                     "crop_ids": ["corn"]}).status_code == 401