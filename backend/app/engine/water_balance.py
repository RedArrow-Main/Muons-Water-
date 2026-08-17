"""Water balance calculations — ETc, soil water, irrigation decisions."""
from __future__ import annotations


def compute_etc(et0_in: float, kc: float) -> float:
    """Calculate crop evapotranspiration.

    ETc = Kc × ET0

    Args:
        et0_in: Reference ET in inches
        kc: Crop coefficient (dimensionless)

    Returns:
        ETc in inches
    """
    return kc * et0_in


def soil_water_step(
    sw_prev: float,
    aw: float,
    rain_in: float,
    irrigation_in: float,
    etc_in: float,
) -> float:
    """Advance soil water by one day.

    SW(t+1) = min(AW, SW(t) + rain + irrigation - ETc)

    Args:
        sw_prev: Previous day's soil water (inches)
        aw: Available water capacity (inches)
        rain_in: Rainfall today (inches)
        irrigation_in: Irrigation applied (inches)
        etc_in: Crop ET today (inches)

    Returns:
        New soil water level (inches)
    """
    return max(0.0, min(aw, sw_prev + rain_in + irrigation_in - etc_in))


def should_irrigate(depletion: float, mad: float) -> str:
    """Determine if irrigation is needed.

    IRRIGATE WHEN depletion ≥ MAD (e.g., 0.50)

    Args:
        depletion: Current depletion fraction (0–1)
        mad: Management allowable depletion (0–1)

    Returns:
        "IRRIGATE" or "HOLD"
    """
    return "IRRIGATE" if depletion >= mad else "HOLD"


def refill_amount(sw_current: float, aw: float) -> float:
    """Calculate irrigation amount to refill to 90% of AW.

    refill = 0.9 × AW - SW_current

    Args:
        sw_current: Current soil water (inches)
        aw: Available water capacity (inches)

    Returns:
        Inches of irrigation needed (≥ 0)
    """
    return max(0.0, 0.9 * aw - sw_current)


# ---------------------------------------------------------------------------
# Season simulation — runs soil-water-balance over injected weather series
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Stage-weighted stress config
# ---------------------------------------------------------------------------
# Each stage is defined by (gdd_frac_low, gdd_frac_high, sensitivity_weight).
# gdd_frac = cumulative_gdd / gdd_to_maturity for the crop.
# The weight scales daily water-deficit contributions during that stage.
STAGE_WEIGHTS: list[tuple[float, float, float]] = [
    # (gdd_frac_low, gdd_frac_high, weight)
    (0.00, 0.50, 0.4),   # Vegetative — low sensitivity
    (0.50, 0.62, 1.5),   # Pollination (critical) — high sensitivity
    (0.62, 0.90, 1.0),   # Grain fill — moderate sensitivity
    (0.90, 1.00, 0.3),   # Maturity — low sensitivity
]

# Crop parameters by ID:
#   (base_temp_f, root_depth_in, mad_fraction, kc_initial, kc_mid, kc_end, gdd_to_maturity)
CROP_PARAMS = {
    "corn":      (50.0, 36.0, 0.50, 0.30, 1.15, 0.90, 2700),
    "soy":       (50.0, 24.0, 0.50, 0.40, 1.10, 0.80, 2500),
    "alfalfa":   (41.0, 30.0, 0.50, 0.40, 1.05, 0.85, 1800),
    "cover":     (40.0, 10.0, 0.45, 0.30, 0.60, 0.55, 1200),
    # FAO-56 reference values — pending agronomist sign-off
    "cotton":    (58.0, 60.0, 0.55, 0.35, 1.15, 0.70, 2800),
    "sorghum":   (50.0, 48.0, 0.50, 0.35, 1.10, 0.55, 2200),
    "potatoes":  (45.0, 30.0, 0.45, 0.45, 1.15, 0.75, 1600),
    "peanuts":   (54.0, 30.0, 0.50, 0.40, 1.15, 0.60, 2500),
    "sunflower": (46.0, 50.0, 0.50, 0.35, 1.10, 0.55, 2000),
}

# Default fallback for unknown crops
_CROP_PARAMS_DEFAULT = (50.0, 36.0, 0.5, 0.30, 1.15, 0.90, 2700)


def simulate_season(
    weather_series: list[dict],
    crop_id: str,
    soil_awc: float,
    start_sw_frac: float = 0.6,
    use_irrigation: bool = False,
) -> dict:
    """Run soil-water-balance over a daily weather series. Pure — no DB, no fetch.

    Args:
        weather_series: list of dicts, each with keys:
            tmax_f, tmin_f, precip_in, et0_in  (all floats; may be None for et0)
        crop_id: "corn", "soy", "alfalfa", "cover", "cotton", "sorghum",
            "potatoes", "peanuts", or "sunflower"
        soil_awc: soil available water capacity (inches)
        start_sw_frac: initial soil water as fraction of AW (default 0.6)
        use_irrigation: if True, irrigate when depletion >= MAD

    Returns:
        dict with:
            cumulative_deficit: total unmet crop water demand (inches)
            days_below_mad: count of days with depletion >= MAD
            total_irrigation: total irrigation applied (inches)
            total_gdd: accumulated GDD over the season
            total_etc: total crop ET (inches)
            total_rain: total rainfall (inches)
            days: number of days simulated
    """
    from app.engine.gdd import gdd_daily

    base_temp, root_depth, mad, _kc_initial, kc, _kc_end, _gdd_maturity = CROP_PARAMS.get(
        crop_id, _CROP_PARAMS_DEFAULT
    )
    aw = root_depth * soil_awc

    sw = start_sw_frac * aw  # initial soil water (inches)
    cumulative_deficit = 0.0
    days_below_mad = 0
    total_irrigation = 0.0
    total_gdd = 0.0
    total_etc = 0.0
    total_rain = 0.0

    for day in weather_series:
        tmax = day.get("tmax_f")
        tmin = day.get("tmin_f")
        precip = day.get("precip_in") or 0.0
        et0 = day.get("et0_in")

        # Skip days with missing temperature
        if tmax is None or tmin is None:
            continue

        # If ET0 missing, estimate via Hargreaves rough approximation
        if et0 is None:
            tmean = (tmax + tmin) / 2
            et0 = max(0.01, 0.0019 * max(0, tmean - 32) * max(0.01, (tmax - tmin) ** 0.5))

        gdd = gdd_daily(tmax, tmin, base_temp)
        etc = compute_etc(et0, kc)
        total_gdd += gdd
        total_etc += etc
        total_rain += precip

        # Irrigation decision
        irrigation = 0.0
        depletion = 1.0 - sw / aw if aw > 0 else 0.0

        if use_irrigation and depletion >= mad:
            irrigation = refill_amount(sw, aw)
            total_irrigation += irrigation

        # Soil water balance with deficit tracking
        # Water entering the root zone: rain + irrigation
        # Water leaving: ETc (capped by available water)
        potential_sw = sw + precip + irrigation - etc
        if potential_sw < 0:
            # Crop demanded more water than available — deficit is the shortfall
            daily_deficit = -potential_sw
            sw = 0.0
        else:
            daily_deficit = 0.0
            sw = min(aw, potential_sw)

        cumulative_deficit += daily_deficit

        # Track days below MAD
        depletion = 1.0 - sw / aw if aw > 0 else 0.0
        if depletion >= mad:
            days_below_mad += 1

    return {
        "cumulative_deficit": round(cumulative_deficit, 4),
        "days_below_mad": days_below_mad,
        "total_irrigation": round(total_irrigation, 4),
        "total_gdd": round(total_gdd, 1),
        "total_etc": round(total_etc, 4),
        "total_rain": round(total_rain, 4),
        "days": len(weather_series),
    }


def _stage_weight(gdd_frac: float) -> float:
    """Return the sensitivity weight for a given GDD fraction.

    Args:
        gdd_frac: cumulative GDD / gdd_to_maturity (0.0–1.0+)

    Returns:
        Weight from STAGE_WEIGHTS for the matching band.
    """
    for low, high, weight in STAGE_WEIGHTS:
        if low <= gdd_frac < high:
            return weight
    # gdd_frac >= 1.0 → use last band (maturity)
    return STAGE_WEIGHTS[-1][2]


def simulate_season_stage_weighted(
    weather_series: list[dict],
    crop_id: str,
    soil_awc: float,
    start_sw_frac: float = 0.6,
    planting_date: str | None = None,
    use_irrigation: bool = False,
) -> dict:
    """Run soil-water-balance with stage-weighted deficit. Pure — no DB, no fetch.

    Like simulate_season, but also computes a stage_weighted_deficit where
    daily deficits are multiplied by the crop's growth-stage sensitivity
    weight.  Returns the pollination-window start/end dates (the dates
    cumulative GDD crosses 50 % and 62 % of gdd_to_maturity).

    Args:
        weather_series: list of dicts with keys:
            tmax_f, tmin_f, precip_in, et0_in (all floats; et0 may be None)
        crop_id: "corn", "soy", "alfalfa", "cover", "cotton", "sorghum",
            "potatoes", "peanuts", or "sunflower"
        soil_awc: soil available water capacity (inches)
        start_sw_frac: initial soil water as fraction of AW (default 0.6)
        planting_date: optional YYYY-MM-DD string; used only for date labels
            in the returned pollination window dict.  If None, the i-th day
            is labelled as day index.

    Returns:
        dict with:
            cumulative_deficit: total unmet crop water demand (inches)
            stage_weighted_deficit: Σ(daily_deficit × stage_weight)
            pollination_start: date (or index) when cum_gdd first ≥ 0.50 × gdd_to_maturity
            pollination_end: date (or index) when cum_gdd first ≥ 0.62 × gdd_to_maturity
            days_below_mad: count of days with depletion ≥ MAD
            total_irrigation: total irrigation applied (inches)
            total_gdd: accumulated GDD over the season
            total_etc: total crop ET (inches)
            total_rain: total rainfall (inches)
            days: number of days simulated
    """
    from app.engine.gdd import gdd_daily

    base_temp, root_depth, mad, _kc_initial, kc, _kc_end, gdd_to_maturity = CROP_PARAMS.get(
        crop_id, _CROP_PARAMS_DEFAULT
    )
    aw = root_depth * soil_awc

    sw = start_sw_frac * aw
    cumulative_deficit = 0.0
    stage_weighted_deficit = 0.0
    total_gdd = 0.0
    cumulative_gdd = 0.0
    total_etc = 0.0
    total_rain = 0.0
    total_irrigation = 0.0
    days_below_mad = 0

    pollination_start = None
    pollination_end = None

    for idx, day in enumerate(weather_series):
        tmax = day.get("tmax_f")
        tmin = day.get("tmin_f")
        precip = day.get("precip_in") or 0.0
        et0 = day.get("et0_in")

        if tmax is None or tmin is None:
            continue

        # If ET0 missing, estimate via Hargreaves rough approximation
        if et0 is None:
            tmean = (tmax + tmin) / 2
            et0 = max(0.01, 0.0019 * max(0, tmean - 32) * max(0.01, (tmax - tmin) ** 0.5))

        gdd = gdd_daily(tmax, tmin, base_temp)
        etc = compute_etc(et0, kc)
        total_gdd += gdd
        cumulative_gdd += gdd
        total_etc += etc
        total_rain += precip

        # Determine GDD fraction and stage weight
        gdd_frac = cumulative_gdd / gdd_to_maturity if gdd_to_maturity > 0 else 0.0
        weight = _stage_weight(gdd_frac)

        # Track pollination window boundaries
        prev_frac = (cumulative_gdd - gdd) / gdd_to_maturity if gdd_to_maturity > 0 else 0.0
        date_label = planting_date  # None → use index
        if planting_date and idx > 0:
            from datetime import datetime, timedelta, timezone
            base = datetime.strptime(planting_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            date_label = (base + timedelta(days=idx)).strftime("%Y-%m-%d")
        elif planting_date and idx == 0:
            date_label = planting_date

        if prev_frac < 0.50 <= gdd_frac and pollination_start is None:
            pollination_start = date_label if date_label is not None else idx
        if prev_frac < 0.62 <= gdd_frac and pollination_end is None:
            pollination_end = date_label if date_label is not None else idx

        # Irrigation decision
        irrigation = 0.0
        depletion = 1.0 - sw / aw if aw > 0 else 0.0
        if use_irrigation and depletion >= mad:
            irrigation = refill_amount(sw, aw)
            total_irrigation += irrigation

        # Soil water balance with deficit tracking
        potential_sw = sw + precip + irrigation - etc
        if potential_sw < 0:
            daily_deficit = -potential_sw
            sw = 0.0
        else:
            daily_deficit = 0.0
            sw = min(aw, potential_sw)

        cumulative_deficit += daily_deficit
        stage_weighted_deficit += daily_deficit * weight

        # Track days below MAD
        depletion = 1.0 - sw / aw if aw > 0 else 0.0
        if depletion >= mad:
            days_below_mad += 1

    # If pollination window was never reached (very short season), set to last day
    if pollination_start is None:
        pollination_start = len(weather_series) - 1
    if pollination_end is None:
        pollination_end = len(weather_series) - 1

    return {
        "cumulative_deficit": round(cumulative_deficit, 4),
        "stage_weighted_deficit": round(stage_weighted_deficit, 4),
        "pollination_start": pollination_start,
        "pollination_end": pollination_end,
        "days_below_mad": days_below_mad,
        "total_irrigation": round(total_irrigation, 4),
        "total_gdd": round(total_gdd, 1),
        "total_etc": round(total_etc, 4),
        "total_rain": round(total_rain, 4),
        "days": len(weather_series),
    }
