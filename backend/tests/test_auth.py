"""Tests for Auth — register, login, session, protected routes."""
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app
from app.db.connection import engine
from app.auth.routes import hash_password

client = TestClient(app)


def _cleanup():
    with Session(engine) as s:
        s.execute(text("DELETE FROM users WHERE email LIKE '%@test.com'"))
        s.commit()


def setup_function():
    _cleanup()


def teardown_function():
    _cleanup()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def test_register_success():
    r = client.post("/api/auth/register", json={
        "email": "farmer@test.com",
        "password": "securepass123",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "farmer@test.com"
    assert data["phone"] is None
    assert "session" in r.cookies


def test_register_with_phone():
    r = client.post("/api/auth/register", json={
        "email": "farmer2@test.com",
        "password": "securepass123",
        "phone": "+15551234567",
    })
    assert r.status_code == 200
    assert r.json()["phone"] == "+15551234567"


def test_register_duplicate_email():
    client.post("/api/auth/register", json={
        "email": "dup@test.com", "password": "securepass123",
    })
    r = client.post("/api/auth/register", json={
        "email": "dup@test.com", "password": "otherpass123",
    })
    assert r.status_code == 409


def test_register_invalid_email():
    r = client.post("/api/auth/register", json={
        "email": "not-an-email", "password": "securepass123",
    })
    assert r.status_code == 400


def test_register_short_password():
    r = client.post("/api/auth/register", json={
        "email": "short@test.com", "password": "123",
    })
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def test_login_success():
    client.post("/api/auth/register", json={
        "email": "login@test.com", "password": "securepass123",
    })
    r = client.post("/api/auth/login", json={
        "email": "login@test.com", "password": "securepass123",
    })
    assert r.status_code == 200
    assert r.json()["email"] == "login@test.com"
    assert "session" in r.cookies


def test_login_wrong_password():
    client.post("/api/auth/register", json={
        "email": "wrong@test.com", "password": "securepass123",
    })
    r = client.post("/api/auth/login", json={
        "email": "wrong@test.com", "password": "wrongpassword",
    })
    assert r.status_code == 401


def test_login_nonexistent_email():
    r = client.post("/api/auth/login", json={
        "email": "nobody@test.com", "password": "securepass123",
    })
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# /me — session check
# ---------------------------------------------------------------------------

def test_me_authenticated():
    r = client.post("/api/auth/register", json={
        "email": "me@test.com", "password": "securepass123",
    })
    token = r.cookies.get("session")
    assert token is not None
    client.cookies.set("session", token)
    r2 = client.get("/api/auth/me")
    assert r2.status_code == 200
    assert r2.json()["email"] == "me@test.com"
    client.cookies.clear()


def test_me_unauthenticated():
    r = client.get("/api/auth/me")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

def test_logout():
    r = client.post("/api/auth/register", json={
        "email": "logout@test.com", "password": "securepass123",
    })
    token = r.cookies.get("session")
    assert token is not None
    # Verify authenticated
    client.cookies.set("session", token)
    r2 = client.get("/api/auth/me")
    assert r2.status_code == 200
    # Logout clears cookie
    r3 = client.post("/api/auth/logout")
    assert r3.status_code == 200
    assert "session" not in r3.cookies  # cookie deleted
    client.cookies.clear()


# ---------------------------------------------------------------------------
# Add phone
# ---------------------------------------------------------------------------

def test_add_phone():
    r = client.post("/api/auth/register", json={
        "email": "phone@test.com", "password": "securepass123",
    })
    token = r.cookies.get("session")
    client.cookies.set("session", token)
    r2 = client.post("/api/auth/phone", json={"phone": "+15559876543"})
    assert r2.status_code == 200
    assert r2.json()["phone"] == "+15559876543"

    r3 = client.get("/api/auth/me")
    assert r3.json()["phone"] == "+15559876543"
    client.cookies.clear()


def test_add_phone_unauthenticated():
    r = client.post("/api/auth/phone", json={"phone": "+15550000000"})
    assert r.status_code == 401
