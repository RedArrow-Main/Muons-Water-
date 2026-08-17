"""Growing Degree Days (GDD) calculation."""
from __future__ import annotations


def gdd_daily(tmax_f: float, tmin_f: float, base_temp_f: float = 50.0) -> float:
    """Calculate daily GDD using the standard formula.

    GDD = max(0, (tmax + tmin) / 2 - base_temp)

    Args:
        tmax_f: Maximum temperature in °F
        tmin_f: Minimum temperature in °F
        base_temp_f: Base temperature in °F (default: 50°F for corn/soy)

    Returns:
        GDD value (≥ 0)
    """
    return max(0.0, (tmax_f + tmin_f) / 2 - base_temp_f)
