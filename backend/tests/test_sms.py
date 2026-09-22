"""Tests for SMS Gateway — formatting, rate limiting, outbox, dry-run send."""
import json

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.connection import engine
from app.sms.gateway import (
    TwilioConfig,
    check_rate_limit,
    format_advisory_sms,
    log_outbox,
    send_batch_sms,
    send_sms,
)

# ---------------------------------------------------------------------------
# Formatter tests
# ---------------------------------------------------------------------------

def test_format_advisory_sms_basic():
    adv = {
        "county": "Cedar",
        "state": "NE",
        "action": "IRRIGATE",
        "gdd": 24.5,
        "etc": 0.29,
        "soil_pct": 56.0,
        "depletion": 44.0,
        "etc0": 0.254,
    }
    msg = format_advisory_sms(adv)
    assert "Cedar,NE" in msg
    assert "IRRIGATE" in msg
    assert "GDD:24.5" in msg
    assert "ETc:0.29" in msg
    assert len(msg) <= 160


def test_format_advisory_sms_with_rain():
    adv = {
        "county": "Story",
        "state": "IA",
        "action": "HOLD",
        "gdd": 22.0,
        "etc": 0.19,
        "soil_pct": 70.0,
        "depletion": 30.0,
        "etc0": 0.165,
        "rain": 1.5,
    }
    msg = format_advisory_sms(adv)
    assert "Rain:1.5" in msg
    assert len(msg) <= 160


def test_format_advisory_sms_truncation():
    adv = {
        "county": "SomeVeryLongCountyName",
        "state": "XX",
        "action": "IRRIGATE_NOW",
        "gdd": 99.9,
        "etc": 9.99,
        "soil_pct": 100.0,
        "depletion": 99.0,
        "etc0": 9.99,
    }
    msg = format_advisory_sms(adv)
    assert len(msg) <= 160


# ---------------------------------------------------------------------------
# Outbox + rate limiting tests
# ---------------------------------------------------------------------------

def test_outbox_insert():
    with Session(engine) as s:
        log_outbox(s, "31027", "+15551234567", "test message",
                   status="dry_run", twilio_sid="DRY_RUN_SIMULATED")
        row = s.execute(text(
            "SELECT county_fips, phone_to, body, status FROM outbox "
            "WHERE county_fips = '31027' ORDER BY sent_at DESC LIMIT 1"
        )).fetchone()
        assert row is not None
        assert row[0] == "31027"
        assert row[3] == "dry_run"
        s.execute(text("DELETE FROM outbox WHERE county_fips = '31027'"))
        s.commit()


def test_rate_limit_allows_first():
    with Session(engine) as s:
        s.execute(text("DELETE FROM outbox WHERE county_fips = 'TST01'"))
        s.commit()
        assert check_rate_limit(s, "TST01") is True


def test_rate_limit_blocks_after_recent_send():
    with Session(engine) as s:
        s.execute(text("DELETE FROM outbox WHERE county_fips = 'TST02'"))
        s.execute(text(
            "INSERT INTO outbox (county_fips, phone_to, body, status, sent_at) "
            "VALUES ('TST02', '+15550000000', 'test', 'sent', now())"
        ))
        s.commit()
        assert check_rate_limit(s, "TST02") is False
        s.execute(text("DELETE FROM outbox WHERE county_fips = 'TST02'"))
        s.commit()


# ---------------------------------------------------------------------------
# Dry-run send tests
# ---------------------------------------------------------------------------

def test_send_sms_dry_run():
    with Session(engine) as s:
        s.execute(text("DELETE FROM outbox WHERE county_fips = 'DRY01'"))
        s.commit()
        config = TwilioConfig(dry_run=True)
        ok = send_sms(s, "+15551234567", "test", county_fips="DRY01", config=config)
        assert ok is True
        row = s.execute(text(
            "SELECT status, body FROM outbox WHERE county_fips = 'DRY01' "
            "ORDER BY sent_at DESC LIMIT 1"
        )).fetchone()
        assert row[0] == "dry_run"
        assert row[1] == "test"
        s.execute(text("DELETE FROM outbox WHERE county_fips = 'DRY01'"))
        s.commit()


def test_send_sms_rate_limited():
    with Session(engine) as s:
        s.execute(text("DELETE FROM outbox WHERE county_fips = 'RLMT1'"))
        s.execute(text(
            "INSERT INTO outbox (county_fips, phone_to, body, status, sent_at) "
            "VALUES ('RLMT1', '+15550000000', 'prev', 'sent', now())"
        ))
        s.commit()
        config = TwilioConfig(dry_run=True)
        ok = send_sms(s, "+15551234567", "second", county_fips="RLMT1", config=config)
        assert ok is False
        row = s.execute(text(
            "SELECT status FROM outbox WHERE county_fips = 'RLMT1' "
            "ORDER BY sent_at DESC LIMIT 1"
        )).fetchone()
        assert row[0] == "rate_limited"
        s.execute(text("DELETE FROM outbox WHERE county_fips = 'RLMT1'"))
        s.commit()


def test_send_batch_sms_dry_run():
    with Session(engine) as s:
        s.execute(text("DELETE FROM outbox WHERE county_fips IN ('BAT01','BAT02')"))
        s.commit()
        config = TwilioConfig(dry_run=True)
        recipients = [
            {"phone": "+15551111111", "fips": "BAT01", "body": "msg1"},
            {"phone": "+15552222222", "fips": "BAT02", "body": "msg2"},
        ]
        results = send_batch_sms(s, recipients, config=config)
        assert results["sent"] == 2
        assert results["rate_limited"] == 0
        assert results["failed"] == 0
        s.execute(text("DELETE FROM outbox WHERE county_fips IN ('BAT01','BAT02')"))
        s.commit()


# ---------------------------------------------------------------------------
# _send_sms_advisories integration test (TASK 1 — exercises the nightly.py
# query that previously referenced nonexistent `decision` and `date` columns)
# ---------------------------------------------------------------------------

def test_send_sms_advisories_extracts_decision_from_source_data():
    """_send_sms_advisories must read decision from source_data JSON, not a
    nonexistent `decision` column.  Regression test for the bug fixed in
    nightly.py (column `decision` and `date` did not exist on `advisories`)."""
    from app.nightly import _send_sms_advisories

    test_fips = "36001"  # Albany, NY — exists in counties table
    test_phone = "+15559990000"
    # A date the nightly pipeline has never written, so the SELECT below can only
    # match the row this test inserts.
    today = "2026-01-15"
    unique_hash = "testhash_sms_regression"

    with Session(engine) as s:
        # Clean up
        s.execute(text("DELETE FROM outbox WHERE county_fips = :f"), {"f": test_fips})
        s.execute(text("DELETE FROM subscribers WHERE county_fips = :f AND phone = :p"),
                  {"f": test_fips, "p": test_phone})
        s.execute(text("DELETE FROM advisories WHERE hash = :h"), {"h": unique_hash})
        s.execute(text(
            "DELETE FROM advisories WHERE county_fips = :f AND DATE(generated_at) = :d"
        ), {"f": test_fips, "d": today})
        s.commit()

        # Insert an advisory with source_data containing 'decision'
        source_data = json.dumps({
            "county_name": "Albany", "county_state": "NY",
            "crop_id": "corn", "decision": "IRRIGATE",
            "gdd": 30.0, "etc_in": 0.32, "soil_pct": 55.0,
            "depletion": 0.55, "forecast_rain_7d": 0.0,
        })
        s.execute(text(
            "INSERT INTO advisories "
            "(county_fips, crop_id, type, severity, headline, body, "
            " source_data, hash, prev_hash, status, generated_at) "
            "VALUES (:f, 'corn', 'water_budget', 'action', 'TEST', 'body', "
            "        :sd, :h, NULL, 'active', :gen)"
        ), {"f": test_fips, "sd": source_data, "h": unique_hash,
            "gen": f"{today} 12:00:00+00"})

        # Insert a subscriber
        s.execute(text(
            "INSERT INTO subscribers (county_fips, phone, active) "
            "VALUES (:f, :p, true)"
        ), {"f": test_fips, "p": test_phone})
        s.commit()

        # Call _send_sms_advisories — must not crash
        result = _send_sms_advisories(s, today)

        # Verify SMS was sent (dry-run)
        assert result["sms_sent"] >= 1
        outbox = s.execute(text(
            "SELECT body FROM outbox WHERE county_fips = :f "
            "ORDER BY sent_at DESC LIMIT 1"
        ), {"f": test_fips}).fetchone()
        assert outbox is not None
        assert "IRRIGATE" in outbox[0]

        # Clean up
        s.execute(text("DELETE FROM outbox WHERE county_fips = :f"), {"f": test_fips})
        s.execute(text("DELETE FROM subscribers WHERE county_fips = :f AND phone = :p"),
                  {"f": test_fips, "p": test_phone})
        s.execute(text("DELETE FROM advisories WHERE hash = :h"), {"h": unique_hash})
        s.commit()
