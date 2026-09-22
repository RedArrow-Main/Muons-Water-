"""Database engine and session factory."""
from __future__ import annotations

import os
from urllib.parse import urlparse

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Managed-database hosts: if we are pointed at one of these, it is the real thing.
_PROD_HOST_HINTS = ("neon.tech", "render.com", "amazonaws.com")

# What the real environment supplied, captured BEFORE .env can fill in the gaps.
# Everything else in the app resolves its URL through here, so this snapshot is
# taken once, at first import, while os.environ still reflects only the shell.
_SHELL_URL = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")

load_dotenv()  # load .env before reading env vars


def _looks_production(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(hint in host for hint in _PROD_HOST_HINTS)


def resolve_database_url() -> str:
    """Return the URL to connect to, refusing an *implicit* production database.

    The repo's `.env` doubles as the Render deployment config, so it holds the
    production URL. `load_dotenv()` fills in whatever the shell left unset,
    which meant a bare `python -m app.db.seed` wrote straight to production
    with no indication it had done so. A production host is therefore only
    honoured when an environment variable named it explicitly — which is how
    Render itself supplies it, so deployment is unaffected.

    Escape hatch for deliberate production work: FURROWCAST_ALLOW_PROD_DB=1.
    """
    url = _SHELL_URL or os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "No database configured — set DATABASE_URL (or TEST_DATABASE_URL)."
        )
    if (
        _SHELL_URL is None
        and _looks_production(url)
        and not os.environ.get("FURROWCAST_ALLOW_PROD_DB")
    ):
        raise RuntimeError(
            f"Refusing to connect to {urlparse(url).hostname!r}: it looks like "
            "production, and the URL came from .env rather than the environment. "
            "Set DATABASE_URL explicitly for local work (the Makefile targets do "
            "this), or set FURROWCAST_ALLOW_PROD_DB=1 if you really mean it."
        )
    return url


DATABASE_URL = resolve_database_url()

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass
