"""The production-database guard in app.db.connection.

`.env` doubles as the Render deployment config, so it holds the production
Neon URL, and load_dotenv() fills in whatever the shell left unset. A bare
`python -m app.db.seed` therefore used to write straight to production with
no indication it had done so. See DECISIONS.md D-016.
"""
from __future__ import annotations

import pytest

from app.db import connection

_PROD = "postgresql+psycopg2://u:p@ep-plain.us-east-2.aws.neon.tech:5432/db"
_DEV = "postgresql+psycopg2://user:password@127.0.0.1:5432/furrowcast"


def _resolve(monkeypatch, shell_url, env_url, allow=None):
    """Re-run resolution with a chosen shell/.env split."""
    monkeypatch.setattr(connection, "_SHELL_URL", shell_url)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("FURROWCAST_ALLOW_PROD_DB", raising=False)
    if env_url is not None:
        monkeypatch.setenv("DATABASE_URL", env_url)
    if allow is not None:
        monkeypatch.setenv("FURROWCAST_ALLOW_PROD_DB", allow)
    return connection.resolve_database_url()


def test_refuses_production_url_supplied_only_by_dotenv(monkeypatch):
    with pytest.raises(RuntimeError, match="looks like production"):
        _resolve(monkeypatch, shell_url=None, env_url=_PROD)


def test_allows_production_when_the_environment_named_it(monkeypatch):
    # How Render supplies it in the real deployment — must keep working.
    assert _resolve(monkeypatch, shell_url=_PROD, env_url=_PROD) == _PROD


def test_allows_a_local_url_from_dotenv(monkeypatch):
    assert _resolve(monkeypatch, shell_url=None, env_url=_DEV) == _DEV


def test_escape_hatch_permits_deliberate_production_work(monkeypatch):
    assert _resolve(monkeypatch, shell_url=None, env_url=_PROD, allow="1") == _PROD


def test_missing_configuration_is_an_error(monkeypatch):
    with pytest.raises(RuntimeError, match="No database configured"):
        _resolve(monkeypatch, shell_url=None, env_url=None)


@pytest.mark.parametrize(("host", "is_prod"), [
    ("ep-plain.us-east-2.aws.neon.tech", True),
    ("dpg-abc123.oregon-postgres.render.com", True),
    ("mydb.abc123.us-east-1.rds.amazonaws.com", True),
    ("127.0.0.1", False),
    ("localhost", False),
    ("db", False),
])
def test_production_host_detection(host, is_prod):
    assert connection._looks_production(f"postgresql://u:p@{host}:5432/db") is is_prod
