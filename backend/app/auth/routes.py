"""Auth — user registration, login, session management."""
from __future__ import annotations

import os
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from jose import JWTError, jwt
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.connection import engine

router = APIRouter(prefix="/api/auth", tags=["auth"])

ph = PasswordHasher()

# Config
SECRET_KEY = os.environ.get("SECRET_KEY", "CHANGE_ME_IN_PRODUCTION")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

# ---------------------------------------------------------------------------
# Rate limiter — 5 failed attempts per IP per 15 minutes
# ---------------------------------------------------------------------------
_login_attempts: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT = 5
_RATE_WINDOW = 900  # 15 minutes


def _check_rate_limit(ip: str) -> bool:
    """Return True if allowed (under rate limit)."""
    now = time.time()
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < _RATE_WINDOW]
    return len(_login_attempts[ip]) < _RATE_LIMIT


def _record_failure(ip: str) -> None:
    _login_attempts[ip].append(time.time())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> int | None:
    """Return user_id or None if invalid."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None


def get_current_user(session: Session, token: str | None = None) -> dict | None:
    """Return user dict or None if not authenticated."""
    if not token:
        return None
    user_id = decode_token(token)
    if not user_id:
        return None
    row = session.execute(text(
        "SELECT id, email, phone, phone_verified, created_at FROM users WHERE id = :id"
    ), {"id": user_id}).fetchone()
    if not row:
        return None
    return {"id": row[0], "email": row[1], "phone": row[2],
            "phone_verified": row[3], "created_at": str(row[4])}


# ---------------------------------------------------------------------------
# Dependency for protected routes
# ---------------------------------------------------------------------------

def get_db():
    with Session(engine) as s:
        yield s


def require_auth(
    session: Session = Depends(get_db),
    session_token: str | None = Cookie(default=None, alias="session"),
) -> dict:
    """FastAPI dependency — raises 401 if not authenticated.

    Dev bypass: set FURROWCAST_DEV_PUBLIC=1 to make protected routes public
    for local development (frontend has no login UI yet).
    """
    if os.environ.get("FURROWCAST_DEV_PUBLIC") == "1":
        return {"id": 0, "email": "dev@local", "dev": True}
    user = get_current_user(session, session_token)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/register")
def register(body: dict, response: Response):
    """Register with email + password. Phone optional."""
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    phone = body.get("phone", "").strip() or None

    if not email or "@" not in email:
        raise HTTPException(400, "Invalid email")
    if len(password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    with Session(engine) as s:
        existing = s.execute(text(
            "SELECT id FROM users WHERE email = :email"
        ), {"email": email}).fetchone()
        if existing:
            raise HTTPException(409, "Email already registered")

        pw_hash = hash_password(password)
        s.execute(text(
            "INSERT INTO users (email, password_hash, phone) VALUES (:email, :pw, :phone)"
        ), {"email": email, "pw": pw_hash, "phone": phone})
        s.commit()

        user = s.execute(text(
            "SELECT id, email, phone, phone_verified, created_at FROM users WHERE email = :email"
        ), {"email": email}).fetchone()

    token = create_token(user[0])
    response.set_cookie(
        "session", token,
        httponly=True, samesite="lax", max_age=ACCESS_TOKEN_EXPIRE_DAYS * 86400,
    )
    return {
        "id": user[0], "email": user[1], "phone": user[2],
        "phone_verified": user[3], "created_at": str(user[4]),
    }


@router.post("/login")
def login(body: dict, response: Response, request: Request):
    """Login with email + password. Rate limited: 5 attempts / 15 min per IP."""
    ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(ip):
        raise HTTPException(429, "Too many login attempts. Try again in 15 minutes.")

    email = body.get("email", "").strip().lower()
    password = body.get("password", "")

    with Session(engine) as s:
        user = s.execute(text(
            "SELECT id, email, password_hash, phone, phone_verified, created_at "
            "FROM users WHERE email = :email"
        ), {"email": email}).fetchone()

    if not user or not verify_password(password, user[2]):
        _record_failure(ip)
        raise HTTPException(401, "Invalid email or password")

    token = create_token(user[0])
    response.set_cookie(
        "session", token,
        httponly=True, samesite="lax", max_age=ACCESS_TOKEN_EXPIRE_DAYS * 86400,
    )
    return {
        "id": user[0], "email": user[1], "phone": user[3],
        "phone_verified": user[4], "created_at": str(user[5]),
    }


@router.post("/logout")
def logout(response: Response):
    """Clear session cookie."""
    response.delete_cookie("session")
    return {"ok": True}


@router.get("/me")
def me(session_cookie: str | None = Cookie(default=None, alias="session")):
    """Return current user or 401."""
    if not session_cookie:
        raise HTTPException(401, "Not authenticated")
    with Session(engine) as s:
        user = get_current_user(s, session_cookie)
    if not user:
        raise HTTPException(401, "Invalid or expired session")
    return user


@router.post("/phone")
def add_phone(body: dict, session_cookie: str | None = Cookie(default=None, alias="session")):
    """Add or update phone number for SMS alerts."""
    if not session_cookie:
        raise HTTPException(401, "Not authenticated")

    user_id = decode_token(session_cookie)
    if not user_id:
        raise HTTPException(401, "Invalid session")

    phone = body.get("phone", "").strip()
    if not phone:
        raise HTTPException(400, "Phone number required")

    with Session(engine) as s:
        s.execute(text(
            "UPDATE users SET phone = :phone WHERE id = :id"
        ), {"phone": phone, "id": user_id})
        s.commit()

    return {"ok": True, "phone": phone}
