"""Season calendar helpers — Julian-day conversion and planting-date defaults.

Single source of truth for turning a county's frost-date normals (stored as
Julian day-of-year) into calendar dates. Previously this logic was duplicated
in `advisor/service.py` and `dashboard/routes.py`, both with the year hardcoded
to 2026 — which silently produced planting dates a full year early from January
2027 onward, feeding gdd_frac -> Kc -> stage-adjusted MAD -> the irrigate
decision. Duplicated helpers caused several rounds of advisor/dashboard
divergence, so both callers use this module.
"""
from __future__ import annotations

from datetime import date, timedelta

# Typical planting date for NY field corn, as (month, day).
#
# Used as the DEFAULT assumption when a farm has not supplied a planting date.
# Deliberately NOT the "latest safe plant date" (frost_kill_50 - maturity_days):
# that is the last date on which a crop could still finish, so using it as a
# default models every farmer as having planted as late as possible. A farmer
# who actually planted May 5 would be modelled at ~May 25-30, losing ~300-400
# GDD, landing in an earlier stage with a lower Kc and a LESS conservative MAD —
# an error in the yield-losing direction during pollination.
#
# NY corn planting runs roughly May 5-30 (Cornell CCE guidance); mid-May is the
# central tendency.
NY_TYPICAL_PLANTING = (5, 15)


def julian_to_date(julian: int, ref_date: str) -> str:
    """Convert a Julian day-of-year to an ISO date in ref_date's year.

    Args:
        julian: day-of-year, 1-366 (may fall outside if callers subtract from it)
        ref_date: YYYY-MM-DD; supplies the calendar year to anchor against.

    Returns:
        ISO YYYY-MM-DD.

    The year comes from `ref_date`, never from a hardcoded constant. For an
    advisory dated in Nov-Mar the frost-derived date lands earlier in that same
    calendar year — i.e. in the season that has just ended, which is the correct
    reading of "what stage is the crop planted this season".
    """
    year = date.fromisoformat(ref_date).year
    return (date(year, 1, 1) + timedelta(days=julian - 1)).isoformat()


def latest_safe_planting_date(
    frost_kill_50: int | None, maturity_days: int, ref_date: str
) -> str | None:
    """Last date a crop could be planted and still reach maturity before frost.

    This is a genuine agronomic quantity (used for planting-window advice), but
    it is NOT a good default assumption for an already-growing crop — see
    `typical_planting_date`.
    """
    if not frost_kill_50:
        return None
    return julian_to_date(frost_kill_50 - maturity_days, ref_date)


def typical_planting_date(ref_date: str) -> str:
    """Default planting date to assume when the farm has not told us one.

    Anchored to `ref_date`'s year so it is correct in any season.
    """
    month, day = NY_TYPICAL_PLANTING
    return date(date.fromisoformat(ref_date).year, month, day).isoformat()


def default_planting_date(
    frost_kill_50: int | None, maturity_days: int, ref_date: str
) -> str:
    """The planting date to assume for stage/Kc/MAD when none was supplied.

    Returns the region's TYPICAL planting date, clamped so it can never fall
    after the latest date at which the crop could still finish (which would
    imply a crop that cannot mature). Falls back to the typical date when the
    county has no frost normal.
    """
    typical = typical_planting_date(ref_date)
    latest = latest_safe_planting_date(frost_kill_50, maturity_days, ref_date)
    if latest is None:
        return typical
    return min(typical, latest)
