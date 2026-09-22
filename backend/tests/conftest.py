"""Shared pytest fixtures for test isolation.

The Makefile ``test`` target sets DATABASE_URL to ``…/furrowcast_test``,
keeping all test writes off the dev/prod database.  This conftest adds a
safety guard and a session fixture for transactional isolation.
"""
from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Safety guard — refuse to run against a database that looks like production
# ---------------------------------------------------------------------------
_DB_URL = os.environ.get("DATABASE_URL", "")

_PROD_HINTS = (
    "neon.tech",       # Neon serverless (production)
    "render.com",     # Render managed DB
    "amazonaws.com",  # RDS
    "furrowcast",     # bare name = dev database (no _test suffix)
)

# Only enforce the guard when the URL doesn't look like a test database.
# CI sets ``…/furrowcast_test`` and the Makefile does the same.
def _is_test_db(url: str) -> bool:
    return bool(re.search(r"furrowcast[_-]test", url))


if _DB_URL and not _is_test_db(_DB_URL) and not os.environ.get("FURROWCAST_ALLOW_PROD_DB"):
    raise RuntimeError(
        f"DATABASE_URL does not look like a test database: {_DB_URL!r}. "
        "Set TEST_DATABASE_URL or use `make test` (which sets DATABASE_URL "
        "to …/furrowcast_test).  Override with FURROWCAST_ALLOW_PROD_DB=1."
    )


# ---------------------------------------------------------------------------
# Session fixture — optional, for tests that want transactional isolation
# ---------------------------------------------------------------------------
@pytest.fixture()
def db_session():
    """Yield a Session that rolls back after the test."""
    engine = create_engine(os.environ.get("DATABASE_URL", _DB_URL))
    with Session(engine) as session:
        yield session
        session.rollback()


# ---------------------------------------------------------------------------
# Keep the suite off the live Open-Meteo API
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _stub_open_meteo_forecast(request, monkeypatch):
    """Serve the 7-day forecast from a fixture instead of the network.

    ``/api/advisory/{fips}`` fetches Open-Meteo live and raises 502 when that
    call fails, so all 23 advisory tests were one rate-limit away from red —
    precisely the conditions on a shared CI runner. Tests needing specific
    weather still override this with their own ``monkeypatch.setattr``, which
    applies after this fixture. Mark a test ``live_network`` to opt out.
    """
    if request.node.get_closest_marker("live_network"):
        return
    from app.dashboard import routes
    from app.ingest import open_meteo

    today = datetime.now(timezone.utc).date()
    days = [(today + timedelta(days=i)).isoformat() for i in range(7)]
    monkeypatch.setattr(routes, "_fetch_json", lambda *a, **k: {
        "daily": _synthetic_daily(days),
    })

    # The archive API is a second live call, reached via _historical_temps and
    # the season backfill. Serve the same synthetic shape over the requested
    # range so GDD accumulation stays deterministic.
    def _fake_archive(lat, lon, start_date, end_date, tz=None, timeout=None):
        try:
            first, last = date.fromisoformat(start_date), date.fromisoformat(end_date)
        except (TypeError, ValueError):
            return None
        if last < first:
            return None
        span = [(first + timedelta(days=i)).isoformat()
                for i in range((last - first).days + 1)]
        return _synthetic_daily(span)

    from app.advisor import service as advisor_service
    monkeypatch.setattr(routes, "fetch_archive_daily", _fake_archive)
    monkeypatch.setattr(advisor_service, "fetch_archive_daily", _fake_archive)
    monkeypatch.setattr(open_meteo, "fetch_archive_daily", _fake_archive)


def _synthetic_daily(days: list[str]) -> dict:
    """Open-Meteo `daily` payload: warm, dry, steady ET0."""
    n = len(days)
    return {
        "time": days,
        "temperature_2m_max": [86.0] * n,
        "temperature_2m_min": [64.0] * n,
        "precipitation_sum": [0.0] * n,
        "et0_fao_evapotranspiration": [0.25] * n,
    }
