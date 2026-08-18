"""Growth-stage determination grounded in accumulated GDD.

A crop advances through phenological growth stages as it accumulates growing
degree days (GDD) since planting. Stage bands are defined by GDD fraction
(cumulative_gdd / gdd_to_maturity) — see SPEC.md §4. The same band table
drives stage-weighted deficit (water_balance.STAGE_WEIGHTS).

The Management Allowable Depletion (MAD / refill point) is adjusted by stage:
critical stages (pollination) refill earlier (lower MAD) to protect a
yield-limiting window, while vegetative/maturity sustain the crop's normal MAD.
"""
from __future__ import annotations

from app.engine.water_balance import STAGE_WEIGHTS

# Display keys — order must match STAGE_WEIGHTS bands
_STAGE_NAMES: tuple[str, ...] = ("vegetative", "pollination", "grain_fill", "maturity")

# MAD multiplier per stage (SPEC.md §4 "Stage-adjusted MAD")
STAGE_MAD_FACTORS: dict[str, float] = {
    "vegetative": 1.00,
    "pollination": 0.60,
    "grain_fill": 0.80,
    "maturity": 1.00,
}


def stage_index(gdd_frac: float) -> int:
    """Index into STAGE_WEIGHTS for a GDD fraction (0.0 = first band)."""
    for idx, (low, high, _weight) in enumerate(STAGE_WEIGHTS):
        if low <= gdd_frac < high:
            return idx
    return len(STAGE_WEIGHTS) - 1  # gdd_frac >= 1.0 → maturity


def growth_stage(gdd_frac: float) -> str:
    """Human-machine stage key for a GDD fraction."""
    return _STAGE_NAMES[stage_index(gdd_frac)]


def stage_label(gdd_frac: float) -> str:
    """Pretty stage name, e.g. 'Pollination'."""
    return _STAGE_NAMES[stage_index(gdd_frac)].replace("_", " ").title()


def stage_weight(gdd_frac: float) -> float:
    """Sensitivity weight for a GDD fraction (matches water_balance)."""
    return STAGE_WEIGHTS[stage_index(gdd_frac)][2]


def gdd_fraction(cumulative_gdd: float, gdd_to_maturity: float) -> float:
    """Fraction of the season completed (0.0–1.0+; clamped to 0 if no target)."""
    if not gdd_to_maturity or gdd_to_maturity <= 0:
        return 0.0
    return round(cumulative_gdd / gdd_to_maturity, 4)


def cumulative_gdd(day_temps: list[tuple[float, float]], base_temp_f: float) -> float:
    """Sum daily GDD over a series of (tmax_f, tmin_f) pairs.

    GDD_day = max(0, (tmax + tmin)/2 − base_temp)
    """
    from app.engine.gdd import gdd_daily

    return round(sum(gdd_daily(tmax, tmin, base_temp_f) for tmax, tmin in day_temps), 1)


def stage_mad_factor(gdd_frac: float) -> float:
    """MAD multiplier for the growth stage a GDD fraction falls in."""
    return STAGE_MAD_FACTORS[growth_stage(gdd_frac)]


def adjusted_mad(base_mad: float, gdd_frac: float) -> float:
    """Stage-adjusted management allowable depletion (refill point).

    adjusted_mad = base_mad × stage_mad_factor(gdd_frac)
    """
    return round(base_mad * stage_mad_factor(gdd_frac), 3)