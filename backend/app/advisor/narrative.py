"""M3 Advisor — narrative generation from engine output.

Decision logic:
  IRRIGATE — engine says depletion >= MAD → use engine decision directly
  HOLD     — engine says depletion < MAD, AND (depletion < MAD-buffer OR rain >= threshold)
  SCHEDULE — engine says HOLD, BUT depletion in [MAD-buffer, MAD) AND forecast rain < threshold

Templates: deterministic, no LLM in v1.
"""
from __future__ import annotations


# ── Tunable constants (Adjustment 1) ───────────────────────────────────
SCHEDULE_LOOKAHEAD_MAD: float = 0.10   # depletion must be >= mad - 0.10
SCHEDULE_MIN_RAIN_IN: float = 0.5      # suppress SCHEDULE if forecast rain >= this

# ── Decision types ─────────────────────────────────────────────────────
DECISION = {"HOLD", "SCHEDULE", "IRRIGATE"}

# ── Severity mapping (Adjustment 3) ────────────────────────────────────
SEVERITY: dict[str, str] = {
    "HOLD": "info",
    "SCHEDULE": "watch",
    "IRRIGATE": "action",
}


def _days_until_trigger(
    depletion: float, mad: float, aw: float, etc_in: float
) -> float | None:
    """Estimate days until depletion reaches MAD.

    days = (mad - depletion) × aw / etc_in

    Returns None when etc_in <= 0 (cannot compute — insufficient ET data).
    """
    if etc_in <= 0:
        return None
    return (mad - depletion) * aw / etc_in


def build_narrative(state: dict) -> tuple[str, str, str, str]:
    """Build advisory narrative from water-balance state. Pure — no DB.

    Args:
        state: dict with keys:
            soil_pct (float 0-100), depletion (float 0-1), mad (float 0-1),
            aw (float, inches), etc_in (float, in/day),
            forecast_rain_7d (float, inches), refill_amount (float, inches),
            drought_level (str), soil_type (str), crop_id (str),
            county_name (str), county_state (str), date (str YYYY-MM-DD)

    Returns:
        (decision, severity, headline, body)
    """
    depletion = state["depletion"]
    mad = state["mad"]
    aw = state["aw"]
    etc_in = state["etc_in"]
    rain_7d = state["forecast_rain_7d"]
    soil_pct = state["soil_pct"]
    refill = state["refill_amount"]
    county = state["county_name"]
    state_code = state["county_state"]
    crop = state["crop_id"]
    soil_type = state["soil_type"]

    # ── Decision logic ──────────────────────────────────────────────────
    # IRRIGATE: engine says depletion >= MAD
    if depletion >= mad:
        decision = "IRRIGATE"
        headline = f"IRRIGATE \u00b7 {county}, {state_code}"
        body = (
            f"Root zone at {soil_pct:.0f}% \u2014 below {mad*100:.0f}% trigger. "
            f"Apply {refill:.2f}\" to refill. {soil_type} \u00b7 {crop}."
        )
        return decision, SEVERITY[decision], headline, body

    # SCHEDULE: depletion in [MAD - buffer, MAD) AND low forecast rain
    schedule_floor = mad - SCHEDULE_LOOKAHEAD_MAD
    if depletion >= schedule_floor and rain_7d < SCHEDULE_MIN_RAIN_IN:
        days = _days_until_trigger(depletion, mad, aw, etc_in)
        decision = "SCHEDULE"
        if days is not None:
            headline = f"PLAN: irrigate by ~{days:.0f} days \u00b7 {county}, {state_code}"
            body = (
                f"Root zone at {soil_pct:.0f}%, approaching {mad*100:.0f}% trigger. "
                f"ETc {etc_in:.2f}\"/day. Plan to irrigate in ~{days:.0f} days."
            )
        else:
            headline = f"PLAN: irrigate soon \u00b7 {county}, {state_code}"
            body = (
                f"Root zone at {soil_pct:.0f}%, approaching {mad*100:.0f}% trigger. "
                f"Irrigation needed soon — forecast data unavailable."
            )
        return decision, SEVERITY[decision], headline, body

    # HOLD: low depletion or adequate rain
    decision = "HOLD"
    headline = f"HOLD irrigation \u00b7 {county}, {state_code}"
    rain_str = f"{rain_7d:.1f}\"" if rain_7d > 0 else "none"
    body = (
        f"Root zone at {soil_pct:.0f}% (trigger {mad*100:.0f}%). "
        f"{rain_str} rain expected next 7 days. "
        f"Resume monitoring."
    )
    return decision, SEVERITY[decision], headline, body
