"""Tests for engine.water_balance — stage-weighted deficit + pollination window."""
from __future__ import annotations

import pytest

from app.engine.water_balance import (
    _stage_weight,
    simulate_season,
    simulate_season_stage_weighted,
)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_day(tmax: float, tmin: float, precip: float = 0.0, et0: float = 0.28) -> dict:
    """Shorthand for building a weather-series day dict."""
    return {"tmax_f": tmax, "tmin_f": tmin, "precip_in": precip, "et0_in": et0}


# ---------------------------------------------------------------------------
# TASK 3a — Hand-computed case
# ---------------------------------------------------------------------------
# Hand math (corn, soil_awc=0.20, root_depth=36 in → AW = 7.2 in):
#
# Stage bands (corn gdd_to_maturity = 2700):
#   Vegetative  0.00–0.50  weight 0.4  →  0–1350 GDD
#   Pollination 0.50–0.62  weight 1.5  →  1350–1674 GDD
#   Grain-fill  0.62–0.90  weight 1.0  →  1674–2430 GDD
#   Maturity    0.90–1.00  weight 0.3  →  2430–2700 GDD
#
# Synthetic series: 3 days of identical weather.
# Day 1: tmax=89°F, tmin=71°F → avg=80 → GDD=30, ETc=0.322 in
#         SW: 60% of 7.2 = 4.32 → 4.32−0.322 = 3.998 → deficit 0
# Day 2: same → SW 3.998 → 3.676 → deficit 0
# Day 3: same → SW 3.676 → 3.354 → deficit 0
# No deficit yet (depletion never hits 0.50).
#
# To force a deficit, start with very low SW so the crop can't get water:
# start_sw_frac = 0.0 → SW = 0 on day 0.
# Day 1: SW=0, ETc=0.322 → potential = -0.322 → deficit = 0.322, SW = 0
# Day 2: same → deficit 0.322
# Day 3: same → deficit 0.322
# cumulative_deficit = 0.966
#
# Stage weighting:
#   After 3 days at 30 GDD/day = 90 GDD cumulative → frac = 90/2700 = 0.0333
#   All 3 days fall in Vegetative band (0.00–0.50, weight 0.4)
#   stage_weighted_deficit = 0.322 × 0.4 × 3 = 0.3864
#
# Now force deficit INSIDE pollination (gdd_frac 0.50–0.62 = 1350–1674 GDD):
# We need 1350 GDD before pollination. At 30 GDD/day → 45 vegetative days.
#   Vegetative: 45 days × 0.322 deficit × 0.4 = 5.796
#   Pollination: 1 day × 0.322 deficit × 1.5 = 0.483
#   Total season_weighted = 5.796 + 0.483 = 6.279
#   Total cumulative_deficit = 46 × 0.322 = 14.812


def test_hand_computed_vegetative_deficit():
    """3-day drought, all in vegetative stage → weight 0.4."""
    # start_sw_frac=0 → immediate deficit every day
    series = [_make_day(89, 71)] * 3
    result = simulate_season_stage_weighted(
        series, "corn", soil_awc=0.20, start_sw_frac=0.0
    )
    # Each day: deficit = 0.322 (ETc = 1.15 × 0.28)
    assert result["cumulative_deficit"] == pytest.approx(0.966, abs=0.001)
    assert result["stage_weighted_deficit"] == pytest.approx(0.3864, abs=0.001)


def test_hand_computed_pollination_deficit():
    """45 vegetative days + 1 pollination day. Pollination deficit × 1.5."""
    # 45 vegetative days → 45 × 30 GDD = 1350 GDD (frac 0.50 → pollination starts)
    # Day 46: pollination (weight 1.5)
    vegetative = [_make_day(89, 71)] * 45
    pollination = [_make_day(89, 71)] * 1
    series = vegetative + pollination

    result = simulate_season_stage_weighted(
        series, "corn", soil_awc=0.20, start_sw_frac=0.0
    )

    # Daily deficit = 0.322 in each day
    daily_def = 0.322  # 1.15 × 0.28
    n_days = 46
    expected_cumulative = daily_def * n_days
    # 44 vegetative days (idx 0–43) × 0.4 + 2 pollination days (idx 44–45) × 1.5
    expected_weighted = (44 * daily_def * 0.4) + (2 * daily_def * 1.5)

    assert result["cumulative_deficit"] == pytest.approx(expected_cumulative, abs=0.01)
    assert result["stage_weighted_deficit"] == pytest.approx(expected_weighted, abs=0.01)
    assert result["days"] == 46


# ---------------------------------------------------------------------------
# TASK 3b — Pollination-window dates
# ---------------------------------------------------------------------------
# Corn gdd_to_maturity = 2700
# 0.50 × 2700 = 1350 → pollination start
# 0.62 × 2700 = 1674 → pollination end
# At 30 GDD/day: start at day 45, end at day 55.8 → day 56


def test_pollination_window_dates():
    """Pollination window spans the correct GDD range."""
    # 60 days of weather → 60 × 30 = 1800 GDD cumulative
    series = [_make_day(89, 71)] * 60

    result = simulate_season_stage_weighted(
        series, "corn", soil_awc=0.20, start_sw_frac=0.6
    )

    # 1350 GDD → day 44 (0-indexed: 44×30=1350), 1674 GDD → day 55 (55×30=1650 < 1674, 56×30=1680 ≥ 1674)
    # Actually: 55×30=1650 < 1674, but 56×30=1680 ≥ 1674
    # Wait: 0.62 × 2700 = 1674. 55×30=1650 < 1674. 56×30=1680 ≥ 1674.
    # But the code checks prev_frac < 0.62 <= gdd_frac.
    # At idx=55: cum_gdd=1680, prev_cum=1650, prev_frac=1650/2700=0.6111, gdd_frac=1680/2700=0.6222
    # 0.6111 < 0.62 and 0.6222 >= 0.62 → pollination_end = 55
    assert result["pollination_start"] == 44
    assert result["pollination_end"] == 55


def test_pollination_window_with_dates():
    """When planting_date is given, window uses date strings."""
    series = [_make_day(89, 71)] * 60

    result = simulate_season_stage_weighted(
        series, "corn", soil_awc=0.20, start_sw_frac=0.6, planting_date="2024-05-01"
    )

    # planting_date is day 0; day 44 = planting_date + 44 days = 2024-06-14
    from datetime import datetime, timedelta, timezone
    base = datetime(2024, 5, 1, tzinfo=timezone.utc)
    assert result["pollination_start"] == (base + timedelta(days=44)).strftime("%Y-%m-%d")
    assert result["pollination_end"] == (base + timedelta(days=55)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# TASK 3c — Edge cases
# ---------------------------------------------------------------------------


def test_boundary_exact_gdd_frac():
    """gdd_frac exactly on boundary (1350 GDD) → pollination band starts."""
    # 45 days × 30 GDD = 1350 → frac = 1350/2700 = 0.50 exactly
    series = [_make_day(89, 71)] * 46  # day 44 (0-indexed) crosses into pollination
    result = simulate_season_stage_weighted(
        series, "corn", soil_awc=0.20, start_sw_frac=0.6
    )
    assert result["pollination_start"] == 44


def test_short_season_never_reaches_pollination():
    """A very short season never hits pollination → window at last day."""
    series = [_make_day(89, 71)] * 5  # only 150 GDD
    result = simulate_season_stage_weighted(
        series, "corn", soil_awc=0.20, start_sw_frac=0.6
    )
    # pollination_start/end fall back to last day index
    assert result["pollination_start"] == 4
    assert result["pollination_end"] == 4


def test_late_planting_date_labeling():
    """planting_date shifts the date labels correctly."""
    series = [_make_day(89, 71)] * 50
    result = simulate_season_stage_weighted(
        series, "corn", soil_awc=0.20, start_sw_frac=0.6, planting_date="2024-06-01"
    )
    # Day 0 = June 1, day 44 = July 15
    assert result["pollination_start"] == "2024-07-15"


def test_stage_weight_function():
    """_stage_weight returns correct weights for each band."""
    assert _stage_weight(0.0) == 0.4
    assert _stage_weight(0.25) == 0.4
    assert _stage_weight(0.50) == 1.5
    assert _stage_weight(0.55) == 1.5
    assert _stage_weight(0.62) == 1.0
    assert _stage_weight(0.75) == 1.0
    assert _stage_weight(0.90) == 0.3
    assert _stage_weight(0.95) == 0.3
    assert _stage_weight(1.0) == 0.3  # edge: exactly 1.0 → last band
    assert _stage_weight(1.5) == 0.3  # beyond maturity → last band


def test_stage_weighted_returns_all_keys():
    """Result dict contains both old and new keys."""
    series = [_make_day(89, 71)] * 10
    result = simulate_season_stage_weighted(
        series, "corn", soil_awc=0.20
    )
    # Original keys
    assert "cumulative_deficit" in result
    assert "days_below_mad" in result
    assert "total_irrigation" in result
    assert "total_gdd" in result
    assert "total_etc" in result
    assert "total_rain" in result
    assert "days" in result
    # New keys
    assert "stage_weighted_deficit" in result
    assert "pollination_start" in result
    assert "pollination_end" in result


def test_stage_weighted_matches_original_when_all_same_weight():
    """If all weights were 1.0, stage_weighted == cumulative_deficit."""
    # Monkey-patch STAGE_WEIGHTS to all 1.0
    import app.engine.water_balance as wb
    original = wb.STAGE_WEIGHTS
    wb.STAGE_WEIGHTS = [(0.0, 1.0, 1.0)]
    try:
        series = [_make_day(89, 71)] * 10
        result = simulate_season_stage_weighted(
            series, "corn", soil_awc=0.20, start_sw_frac=0.0
        )
        assert result["stage_weighted_deficit"] == pytest.approx(
            result["cumulative_deficit"], abs=0.001
        )
    finally:
        wb.STAGE_WEIGHTS = original


def test_missing_et0_uses_hargreaves():
    """ET0 missing → Hargreaves estimate used, same as original engine."""
    series = [{"tmax_f": 89, "tmin_f": 71, "precip_in": 0.0, "et0_in": None}] * 5
    result = simulate_season_stage_weighted(
        series, "corn", soil_awc=0.20, start_sw_frac=0.6
    )
    # Should still produce valid results (ET0 estimated)
    assert result["days"] == 5
    assert result["total_etc"] > 0


def test_original_simulate_season_unchanged():
    """Existing simulate_season still works with new 7-element CROP_PARAMS."""
    series = [_make_day(89, 71)] * 3
    result = simulate_season(series, "corn", soil_awc=0.20)
    assert result["days"] == 3
    assert result["total_gdd"] == pytest.approx(90.0, abs=0.1)


# ---------------------------------------------------------------------------
# New crop library tests (M5: cotton, sorghum, potatoes, peanuts, sunflower)
# ---------------------------------------------------------------------------

def test_crop_params_has_all_nine():
    """CROP_PARAMS contains all 9 crops with correct tuple length."""
    from app.engine.water_balance import CROP_PARAMS
    expected = {"corn", "soy", "alfalfa", "cover", "cotton", "sorghum",
                "potatoes", "peanuts", "sunflower"}
    assert set(CROP_PARAMS.keys()) == expected
    for crop_id, params in CROP_PARAMS.items():
        assert len(params) == 7, f"{crop_id} params tuple should be 7-element"


def test_crop_params_values_cotton():
    """Cotton parameters match FAO-56 reference values."""
    from app.engine.water_balance import CROP_PARAMS
    base_temp, root, mad, kc_ini, kc_mid, kc_end, gdd = CROP_PARAMS["cotton"]
    assert base_temp == 58.0
    assert root == 60.0
    assert mad == 0.55
    assert kc_ini == 0.35
    assert kc_mid == 1.15
    assert kc_end == 0.70
    assert gdd == 2800


def test_crop_params_values_sorghum():
    """Sorghum parameters match FAO-56 reference values."""
    from app.engine.water_balance import CROP_PARAMS
    base_temp, root, mad, kc_ini, kc_mid, kc_end, gdd = CROP_PARAMS["sorghum"]
    assert base_temp == 50.0
    assert root == 48.0
    assert mad == 0.50
    assert kc_ini == 0.35
    assert kc_mid == 1.10
    assert kc_end == 0.55
    assert gdd == 2200


def test_crop_params_values_potatoes():
    """Potatoes parameters match FAO-56 reference values."""
    from app.engine.water_balance import CROP_PARAMS
    base_temp, root, mad, kc_ini, kc_mid, kc_end, gdd = CROP_PARAMS["potatoes"]
    assert base_temp == 45.0
    assert root == 30.0
    assert mad == 0.45
    assert kc_ini == 0.45
    assert kc_mid == 1.15
    assert kc_end == 0.75
    assert gdd == 1600


def test_crop_params_values_peanuts():
    """Peanuts parameters match FAO-56 reference values."""
    from app.engine.water_balance import CROP_PARAMS
    base_temp, root, mad, kc_ini, kc_mid, kc_end, gdd = CROP_PARAMS["peanuts"]
    assert base_temp == 54.0
    assert root == 30.0
    assert mad == 0.50
    assert kc_ini == 0.40
    assert kc_mid == 1.15
    assert kc_end == 0.60
    assert gdd == 2500


def test_crop_params_values_sunflower():
    """Sunflower parameters match FAO-56 reference values."""
    from app.engine.water_balance import CROP_PARAMS
    base_temp, root, mad, kc_ini, kc_mid, kc_end, gdd = CROP_PARAMS["sunflower"]
    assert base_temp == 46.0
    assert root == 50.0
    assert mad == 0.50
    assert kc_ini == 0.35
    assert kc_mid == 1.10
    assert kc_end == 0.55
    assert gdd == 2000


def test_simulate_season_cotton():
    """Cotton simulation runs and produces sensible output."""
    # 3 hot days (cotton base=58°F, so GDD=0 on cool days)
    series = [_make_day(95, 75)] * 3
    result = simulate_season(series, "cotton", soil_awc=0.20)
    assert result["days"] == 3
    # GDD: avg=(95+75)/2=85, GDD=85-58=27 per day → 81 total
    assert result["total_gdd"] == pytest.approx(81.0, abs=0.1)
    # ETc: kc_mid=1.15 × 0.28 = 0.322 per day → 0.966 total
    assert result["total_etc"] == pytest.approx(0.966, abs=0.01)


def test_simulate_season_potatoes():
    """Potatoes simulation runs and produces sensible output."""
    # Potatoes base=45°F, so GDD is higher than corn on same temps
    series = [_make_day(89, 71)] * 3
    result = simulate_season(series, "potatoes", soil_awc=0.20)
    assert result["days"] == 3
    # GDD: avg=80, GDD=80-45=35 per day → 105 total
    assert result["total_gdd"] == pytest.approx(105.0, abs=0.1)


def test_simulate_season_sorghum():
    """Sorghum simulation runs and produces sensible output."""
    series = [_make_day(95, 75)] * 3
    result = simulate_season(series, "sorghum", soil_awc=0.20)
    assert result["days"] == 3
    # GDD: avg=85, GDD=85-50=35 per day → 105 total
    assert result["total_gdd"] == pytest.approx(105.0, abs=0.1)


def test_simulate_season_peanuts():
    """Peanuts simulation runs and produces sensible output."""
    series = [_make_day(95, 75)] * 3
    result = simulate_season(series, "peanuts", soil_awc=0.20)
    assert result["days"] == 3
    # GDD: avg=85, GDD=85-54=31 per day → 93 total
    assert result["total_gdd"] == pytest.approx(93.0, abs=0.1)


def test_simulate_season_sunflower():
    """Sunflower simulation runs and produces sensible output."""
    series = [_make_day(89, 71)] * 3
    result = simulate_season(series, "sunflower", soil_awc=0.20)
    assert result["days"] == 3
    # GDD: avg=80, GDD=80-46=34 per day → 102 total
    assert result["total_gdd"] == pytest.approx(102.0, abs=0.1)


def test_new_crops_deeper_root_holds_more_water():
    """Cotton (60\" root) depletes slower than potatoes (30\" root) on same weather."""
    series = [_make_day(89, 71)] * 30
    # Cotton: AW = 60 × 0.20 = 12.0
    result_cotton = simulate_season(series, "cotton", soil_awc=0.20)
    # Potatoes: AW = 30 × 0.20 = 6.0
    result_potatoes = simulate_season(series, "potatoes", soil_awc=0.20)
    # Cotton has 2× AW, so should have fewer days below MAD
    assert result_cotton["days_below_mad"] <= result_potatoes["days_below_mad"]


def test_spinup_cotton_uses_kc_params():
    """Spin-up for cotton passes kc_initial/kc_end correctly."""
    from app.engine.spinup import spinup_soil_moisture
    series = [_make_day(95, 75)] * 30
    aw = 60 * 0.20  # cotton root depth × AWC
    sw, depletion = spinup_soil_moisture(
        weather_series=series, aw=aw, kc=1.15,
        base_temp_f=58.0, gdd_to_maturity=2800.0,
        kc_initial=0.35, kc_end=0.70,
    )
    assert 0.0 <= depletion <= 1.0
    assert sw >= 0.0


def test_spinup_potatoes_uses_kc_params():
    """Spin-up for potatoes passes kc_initial/kc_end correctly."""
    from app.engine.spinup import spinup_soil_moisture
    series = [_make_day(89, 71)] * 30
    aw = 30 * 0.20  # potatoes root depth × AWC
    sw, depletion = spinup_soil_moisture(
        weather_series=series, aw=aw, kc=1.15,
        base_temp_f=45.0, gdd_to_maturity=1600.0,
        kc_initial=0.45, kc_end=0.75,
    )
    assert 0.0 <= depletion <= 1.0
    assert sw >= 0.0
