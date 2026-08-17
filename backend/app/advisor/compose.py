"""M3 Advisor — advisory composition + hash chain.

Builds advisory dicts from narrative output. Each advisory is hash-linked
to its predecessor for the same county, forming a tamper-evident chain.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone


def _canonical(obj: dict) -> str:
    """Deterministic JSON serialization for hashing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _hash_content(prev_hash: str | None, content: dict) -> str:
    """SHA-256 hash of prev_hash + canonical(content).

    The chain works by including the previous hash in the input, so any
    mutation upstream breaks all downstream hashes.
    """
    raw = (prev_hash or "") + _canonical(content)
    return hashlib.sha256(raw.encode()).hexdigest()


def build_advisory(
    county_fips: str,
    crop_id: str,
    date: str,
    decision: str,
    severity: str,
    headline: str,
    body: str,
    source_data: dict,
    prev_hash: str | None,
) -> dict:
    """Build an advisory dict with hash chain. Pure — no DB.

    Args:
        county_fips: 5-digit FIPS code
        crop_id: "corn", "soy", etc.
        date: YYYY-MM-DD advisory date
        decision: "HOLD", "SCHEDULE", or "IRRIGATE"
        severity: "info", "watch", or "action"
        headline: one-line headline
        body: plain-language advisory body
        source_data: audit trail dict (Adjustment 3)
        prev_hash: hash of previous advisory for this county

    Returns:
        dict with all advisory fields + hash
    """
    content = {
        "county_fips": county_fips,
        "crop_id": crop_id,
        "date": date,
        "decision": decision,
        "severity": severity,
        "headline": headline,
        "body": body,
    }
    advisory_hash = _hash_content(prev_hash, content)

    return {
        "county_fips": county_fips,
        "crop_id": crop_id,
        "date": date,
        "type": "water_budget",
        "decision": decision,
        "severity": severity,
        "headline": headline,
        "body": body,
        "source_data": source_data,
        "hash": advisory_hash,
        "prev_hash": prev_hash,
        "status": "active",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def verify_chain(chain: list[dict]) -> bool:
    """Verify hash chain integrity. Pure — no DB.

    Walks the chain, re-hashing each advisory and checking that each
    advisory's prev_hash matches the previous advisory's hash.

    Args:
        chain: list of advisory dicts in chronological order (oldest first)

    Returns:
        True if chain is valid, False if tampered or broken
    """
    if not chain:
        return True

    prev_hash: str | None = None
    for advisory in chain:
        # Check prev_hash linkage
        if advisory["prev_hash"] != prev_hash:
            return False

        # Re-compute hash from content
        content = {
            "county_fips": advisory["county_fips"],
            "crop_id": advisory["crop_id"],
            "date": advisory["date"],
            "decision": advisory["decision"],
            "severity": advisory["severity"],
            "headline": advisory["headline"],
            "body": advisory["body"],
        }
        expected_hash = _hash_content(prev_hash, content)
        if advisory["hash"] != expected_hash:
            return False

        prev_hash = advisory["hash"]

    return True
