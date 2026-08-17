"""Soil-moisture spin-up from historical weather.

Runs the water balance forward from field capacity through a historical
weather series to estimate current soil moisture. Pure — no DB, no fetch.
"""
from __future__ import annotations

from app.engine.gdd import gdd_daily


def _kc_for_gdd_frac(gdd_frac: float, kc_initial: float = 0.30,
                      kc_mid: float = 1.15, kc_end: float = 0.60) -> float:
    """Return crop coefficient based on GDD fraction of maturity.

    FAO-56-style curve for corn:
      0.00–0.10: kc_initial (seedling)
      0.10–0.50: ramp initial → mid (vegetative)
      0.50–0.62: kc_mid (pollination, peak water use)
      0.62–0.90: ramp mid → end (grain fill)
      0.90–1.00: kc_end (maturity, dry-down)
    """
    if gdd_frac < 0.10:
        return kc_initial
    if gdd_frac < 0.50:
        t = (gdd_frac - 0.10) / 0.40
        return kc_initial + t * (kc_mid - kc_initial)
    if gdd_frac < 0.62:
        return kc_mid
    if gdd_frac < 0.90:
        t = (gdd_frac - 0.62) / 0.28
        return kc_mid + t * (kc_end - kc_mid)
    return kc_end


def spinup_soil_moisture(
    weather_series: list[dict],
    aw: float,
    kc: float,
    base_temp_f: float = 50.0,
    gdd_to_maturity: float = 2700.0,
    use_gdd_scaling: bool = True,
    kc_initial: float = 0.30,
    kc_end: float = 0.60,
) -> tuple[float, float]:
    """Estimate current soil moisture by stepping through historical weather.

    Starts at field capacity (SW = AW, i.e. 100% full) and advances the
    water balance day by day with NO irrigation (rain-fed only).
    Uses GDD-based Kc scaling (FAO-56 curve) for realistic seasonal water use.

    Args:
        weather_series: list of dicts, each with keys:
            tmax_f, tmin_f, precip_in, et0_in (all floats)
        aw: available water capacity (inches) = root_depth × AWC
        kc: crop coefficient (dimensionless). When use_gdd_scaling=True,
            this is kc_mid (upper bound). When False, used as flat Kc.
        base_temp_f: base temperature for GDD (default 50°F for corn)
        gdd_to_maturity: total GDD to reach maturity (default 2700 for corn)
        use_gdd_scaling: if True, use GDD-based Kc curve. If False, use flat kc.
        kc_initial: Kc at initial/seedling stage (used when use_gdd_scaling=True)
        kc_end: Kc at end/maturity stage (used when use_gdd_scaling=True)

    Returns:
        (sw, depletion) tuple:
            sw: current soil water (inches)
            depletion: 1 - sw / aw (fraction, 0–1); 0 = field capacity
    """
    if aw <= 0:
        return (0.0, 0.0)

    sw = aw  # start at field capacity (100%)
    cumulative_gdd = 0.0

    for day in weather_series:
        tmax = day.get("tmax_f")
        tmin = day.get("tmin_f")
        precip = day.get("precip_in") or 0.0
        et0 = day.get("et0_in")

        if tmax is None or tmin is None:
            continue

        # If ET0 missing, rough Hargreaves approximation
        if et0 is None:
            tmean = (tmax + tmin) / 2
            et0 = max(0.01, 0.0019 * max(0, tmean - 32) * max(0.01, (tmax - tmin) ** 0.5))

        if use_gdd_scaling:
            gdd = gdd_daily(tmax, tmin, base_temp_f)
            cumulative_gdd += gdd
            gdd_frac = cumulative_gdd / gdd_to_maturity if gdd_to_maturity > 0 else 0.0
            stage_kc = _kc_for_gdd_frac(gdd_frac, kc_initial=kc_initial, kc_mid=kc, kc_end=kc_end)
        else:
            stage_kc = kc

        etc = stage_kc * et0

        # SW(t+1) = min(AW, SW(t) + rain - ETc), no irrigation
        # Clamp to [0, AW] — soil water can't go below 0 (wilting point)
        sw = max(0.0, min(aw, sw + precip - etc))

    depletion = 1.0 - sw / aw
    return (sw, depletion)
