"""Soil-moisture spin-up from historical weather.

Runs the water balance forward from field capacity through a historical
weather series to estimate current soil moisture. Pure — no DB, no fetch.
"""
from __future__ import annotations

from app.engine.gdd import gdd_daily
from app.engine.kc import CROP_PARAMS, kc_for_gdd_frac


def spinup_soil_moisture(
    weather_series: list[dict],
    aw: float,
    crop_id: str = "corn",
    kc: float | None = None,
    base_temp_f: float | None = None,
    gdd_to_maturity: float | None = None,
    use_gdd_scaling: bool = True,
    initial_gdd: float = 0.0,
    initial_sw: float | None = None,
) -> tuple[float, float]:
    """Estimate current soil moisture by stepping through historical weather.

    Starts at field capacity (SW = AW, i.e. 100% full) and advances the
    water balance day by day with NO irrigation (rain-fed only).
    Uses GDD-based Kc scaling (FAO-56 curve) for realistic seasonal water use.

    Args:
        weather_series: list of dicts, each with keys:
            tmax_f, tmin_f, precip_in, et0_in (all floats)
        aw: available water capacity (inches) = root_depth × AWC
        crop_id: crop identifier (default "corn"). Used to look up
            base_temp_f, gdd_to_maturity, and the Kc curve from CROP_PARAMS.
        kc: flat crop coefficient — only used when use_gdd_scaling=False.
            Defaults to kc_mid from CROP_PARAMS if not provided.
        base_temp_f: base temperature for GDD. Defaults to CROP_PARAMS value.
        gdd_to_maturity: total GDD to reach maturity. Defaults to CROP_PARAMS value.
        initial_sw: starting water in inches; None preserves legacy full-capacity behavior.
        initial_gdd: accumulated GDD before the first weather day.
        use_gdd_scaling: if True, use GDD-based Kc curve. If False, use flat kc.

    Returns:
        (sw, depletion) tuple:
            sw: current soil water (inches)
            depletion: 1 - sw / aw (fraction, 0–1); 0 = field capacity
    """
    params = CROP_PARAMS.get(crop_id, CROP_PARAMS.get("corn"))
    _base, _root, _mad, _kc_init, kc_mid_db, _kc_end, gdd_mat_db = params

    base_temp = base_temp_f if base_temp_f is not None else _base
    mat_gdd = gdd_to_maturity if gdd_to_maturity is not None else gdd_mat_db
    flat_kc = kc if kc is not None else kc_mid_db

    if aw <= 0:
        return (0.0, 0.0)

    sw = aw if initial_sw is None else max(0.0, min(aw, initial_sw))
    cumulative_gdd = initial_gdd

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
            gdd = gdd_daily(tmax, tmin, base_temp)
            cumulative_gdd += gdd
            gdd_frac = cumulative_gdd / mat_gdd if mat_gdd > 0 else 0.0
            stage_kc = kc_for_gdd_frac(crop_id, gdd_frac)
        else:
            stage_kc = flat_kc

        etc = stage_kc * et0

        # SW(t+1) = min(AW, SW(t) + rain - ETc), no irrigation
        # Clamp to [0, AW] — soil water can't go below 0 (wilting point)
        sw = max(0.0, min(aw, sw + precip - etc))

    depletion = 1.0 - sw / aw
    return (sw, depletion)
