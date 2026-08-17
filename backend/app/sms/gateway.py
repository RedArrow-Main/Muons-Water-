"""SMS Gateway — message formatting, rate limiting, outbox tracking, Twilio integration."""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Message formatter — advisory dict → SMS text (≤160 chars)
# ---------------------------------------------------------------------------

def format_advisory_sms(advisory: dict) -> str:
    """Convert advisory data into a short SMS message.

    Args:
        advisory: dict with keys: county, state, action, gdd, etcc, soil_pct,
                  depletion, etc0, forecast_summary
    Returns:
        SMS text (target ≤160 chars)
    """
    parts = []
    parts.append(f"{advisory['county']},{advisory['state']} — {advisory['action']}")
    parts.append(f"GDD:{advisory['gdd']:.1f} ETc:{advisory['etc']:.2f}\"")
    parts.append(f"Soil:{advisory['soil_pct']:.0f}% Depl:{advisory['depletion']:.0f}%")
    if advisory.get("rain"):
        parts.append(f"Rain:{advisory['rain']:.1f}\"")
    parts.append(f"ET0:{advisory['etc0']:.2f}\"")
    msg = " | ".join(parts)
    if len(msg) > 160:
        msg = msg[:157] + "..."
    return msg


# ---------------------------------------------------------------------------
# Rate limiter — 1 SMS per county per hour
# ---------------------------------------------------------------------------

def check_rate_limit(session: Session, county_fips: str, cooldown_min: int = 60) -> bool:
    """Return True if allowed (no SMS sent in last cooldown_min)."""
    hrs = cooldown_min / 60.0
    row = session.execute(text(
        "SELECT sent_at FROM outbox WHERE county_fips = :fips "
        "AND sent_at > now() - (:hrs || ' hours')::interval "
        "ORDER BY sent_at DESC LIMIT 1"
    ), {"fips": county_fips, "hrs": str(hrs)}).fetchone()
    if not row:
        return True
    elapsed = (datetime.now(timezone.utc) - row[0]).total_seconds() / 60
    return elapsed >= cooldown_min


# ---------------------------------------------------------------------------
# Outbox — insert and query sent messages
# ---------------------------------------------------------------------------

def log_outbox(session: Session, county_fips: str, phone: str, body: str,
               status: str = "sent", twilio_sid: str | None = None,
               error: str | None = None) -> None:
    """Insert a record into outbox."""
    session.execute(text(
        "INSERT INTO outbox (county_fips, phone_to, body, status, twilio_sid, error_msg, sent_at) "
        "VALUES (:fips, :phone, :body, :status, :sid, :err, now())"
    ), {"fips": county_fips, "phone": phone, "body": body,
        "status": status, "sid": twilio_sid, "err": error})
    session.commit()


def get_recent_outbox(session: Session, county_fips: str, hours: int = 24) -> list:
    """Return recent outbox rows for a county."""
    rows = session.execute(text(
        "SELECT phone_to, body, status, twilio_sid, error_msg, sent_at "
        "FROM outbox WHERE county_fips = :fips AND sent_at > now() - interval ':hrs hours' "
        "ORDER BY sent_at DESC"
    ), {"fips": county_fips, "hrs": hours}).fetchall()
    return rows


# ---------------------------------------------------------------------------
# Twilio send — dry-run mode when no credentials configured
# ---------------------------------------------------------------------------

@dataclass
class TwilioConfig:
    account_sid: str = ""
    auth_token: str = ""
    from_number: str = ""
    dry_run: bool = True

    @classmethod
    def from_env(cls) -> "TwilioConfig":
        import os
        sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        token = os.getenv("TWILIO_AUTH_TOKEN", "")
        from_n = os.getenv("TWILIO_FROM_NUMBER", "")
        dry = not (sid and token and from_n)
        return cls(account_sid=sid, auth_token=token, from_number=from_n, dry_run=dry)


def send_sms(session: Session, to: str, body: str,
             county_fips: str = "", config: TwilioConfig | None = None) -> bool:
    """Send SMS via Twilio (or dry-run). Returns True on success.

    - Checks rate limit
    - Sends (or simulates)
    - Logs to outbox
    """
    if config is None:
        config = TwilioConfig.from_env()

    # Rate limit
    if county_fips and not check_rate_limit(session, county_fips):
        log_outbox(session, county_fips, to, body, status="rate_limited",
                   error="Already sent within cooldown window")
        return False

    if config.dry_run:
        # Simulate
        log_outbox(session, county_fips, to, body, status="dry_run",
                   twilio_sid="DRY_RUN_SIMULATED")
        return True

    # Real Twilio send
    try:
        from twilio.rest import Client
        client = Client(config.account_sid, config.auth_token)
        msg = client.messages.create(
            body=body,
            from_=config.from_number,
            to=to,
        )
        log_outbox(session, county_fips, to, body, status="sent",
                   twilio_sid=msg.sid)
        return True
    except Exception as e:
        log_outbox(session, county_fips, to, body, status="failed",
                   error=str(e))
        return False


def send_batch_sms(session: Session, recipients: list[dict],
                   config: TwilioConfig | None = None) -> dict:
    """Send SMS to multiple recipients.

    recipients: [{"phone": "+1...", "fips": "31027", "body": "msg"}, ...]
    Returns: {"sent": N, "rate_limited": N, "failed": N}
    """
    results = {"sent": 0, "rate_limited": 0, "failed": 0}
    for r in recipients:
        ok = send_sms(session, r["phone"], r["body"],
                      county_fips=r.get("fips", ""), config=config)
        if ok:
            results["sent"] += 1
        else:
            # Check what happened
            last = session.execute(text(
                "SELECT status FROM outbox WHERE county_fips = :fips "
                "ORDER BY sent_at DESC LIMIT 1"
            ), {"fips": r.get("fips", "")}).fetchone()
            if last and last[0] == "rate_limited":
                results["rate_limited"] += 1
            else:
                results["failed"] += 1
        time.sleep(0.1)  # small delay between sends
    return results
