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
# Kc curve (FAO-56): gdd_frac < 0.10 → kc_initial=0.30; 0.10–0.50 ramp
# to kc_mid=1.20; 0.50–0.62 → kc_mid; etc.
#
# --- 3-day vegetative deficit (start_sw_frac=0.0, SW=0) ---
# gdd_frac stays < 0.10 → Kc = 0.30 (kc_initial)
# ETc = 0.30 × 0.28 = 0.084 in/day
# cumulative_deficit = 3 × 0.084 = 0.252
# stage_weighted_deficit = 3 × 0.084 × 0.4 = 0.1008
#
# --- 46-day pollination deficit (45 veg + 1 pollination, start_sw_frac=0.0) ---
# gdd_frac runs 0.011 → 0.511 across 46 days (Kc varies per day)
# Days 0–8: gdd_frac < 0.10 → Kc=0.30 → ETc=0.084
# Days 9–43: Kc ramps 0.30 → 1.20 (gdd_frac 0.11 → 0.49)
# Days 44–45: gdd_frac ≥ 0.50 → Kc=1.20 → ETc=0.336
# Hand sum of daily deficits (SW=0): cumulative_deficit = 8.778
# Stage-weighted: 44 veg days × avg × 0.4 + 2 poll days × 0.336 × 1.5 = 4.2504


def test_hand_computed_vegetative_deficit():
    """3-day drought, all in vegetative stage → weight 0.4."""
    # start_sw_frac=0 → immediate deficit every day
    series = [_make_day(89, 71)] * 3
    result = simulate_season_stage_weighted(
        series, "corn", soil_awc=0.20, start_sw_frac=0.0
    )
    # Each day: gdd_frac=0.033 (<0.10) → Kc = kc_initial = 0.30
    # deficit = ETc = 0.30 × 0.28 = 0.084
    assert result["cumulative_deficit"] == pytest.approx(0.252, abs=0.001)
    assert result["stage_weighted_deficit"] == pytest.approx(0.1008, abs=0.001)


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

    # Kc varies by GDD fraction (not constant 1.20):
    #   days 0-8: gdd_frac < 0.10 → Kc = kc_initial = 0.30 → ETc = 0.084
    #   days 9-43: Kc ramps 0.30 → 1.20 (gdd_frac 0.11 → 0.49)
    #   days 44-45: gdd_frac >= 0.50 → Kc = kc_mid = 1.20 → ETc = 0.336
    expected_cumulative = 8.778
    # Stage-weighted: 44 vegetative days (idx 0–43) × 0.4 + 2 pollination days (idx 44–45) × 1.5
    expected_weighted = 4.2504

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
# Crop library tests (M8: NY scope — cabbage, onions, sweet corn)
# ---------------------------------------------------------------------------

def test_crop_params_has_all_nine():
    """CROP_PARAMS contains all 9 crops with correct tuple length."""
    from app.engine.water_balance import CROP_PARAMS
    expected = {"corn", "soy", "alfalfa", "cover", "potatoes", "sunflower",
                "cabbage", "onions", "sweet corn"}
    assert set(CROP_PARAMS.keys()) == expected
    for crop_id, params in CROP_PARAMS.items():
        assert len(params) == 7, f"{crop_id} params tuple should be 7-element"


def test_crop_params_values_cabbage():
    """Cabbage: Kc + p match FAO-56 Table 12 / 22 exactly.

    root_depth 18 in sits just BELOW FAO-56 Table 22's Zr range (0.5-0.8 m =
    20-31 in). Zr is the MAXIMUM effective depth under ideal conditions; a
    shallower effective zone is deliberate for NY and errs conservative
    (smaller AW -> higher depletion -> irrigates sooner). See D-013.
    """
    from app.engine.water_balance import CROP_PARAMS
    base_temp, root, mad, kc_ini, kc_mid, kc_end, gdd = CROP_PARAMS["cabbage"]
    assert base_temp == 45.0
    assert root == 18.0
    assert mad == 0.45
    assert kc_ini == 0.70
    assert kc_mid == 1.05
    assert kc_end == 0.95
    assert gdd == 2000


def test_crop_params_values_onions():
    """Onions: Kc from FAO-56 Table 12, p from Table 22 (D-013)."""
    from app.engine.water_balance import CROP_PARAMS
    base_temp, root, mad, kc_ini, kc_mid, kc_end, gdd = CROP_PARAMS["onions"]
    assert base_temp == 40.0
    assert root == 14.0
    assert mad == 0.30  # FAO-56 Table 22 p = 0.30 (onion, dry) — was 0.50, D-013
    assert kc_ini == 0.70
    assert kc_mid == 1.05
    assert kc_end == 0.75
    assert gdd == 1800


def test_crop_params_values_sweet_corn():
    """Sweet corn: FAO-56 Table 12 sweet maize, fresh harvest (D-013)."""
    from app.engine.water_balance import CROP_PARAMS
    base_temp, root, mad, kc_ini, kc_mid, kc_end, gdd = CROP_PARAMS["sweet corn"]
    assert base_temp == 50.0
    assert root == 24.0
    assert mad == 0.50
    assert kc_ini == 0.30
    # kc_mid 1.15 IS FAO-56's sweet-maize value (field maize is 1.20)
    assert kc_mid == 1.15
    assert kc_end == 1.05  # FAO-56 Table 12 sweet maize, fresh harvest — was 0.90, D-013
    assert gdd == 2200


def test_crop_params_values_potatoes():
    """Potatoes: Kc from Table 12, p and Zr cap from Table 22 (D-013)."""
    from app.engine.water_balance import CROP_PARAMS
    base_temp, root, mad, kc_ini, kc_mid, kc_end, gdd = CROP_PARAMS["potatoes"]
    assert base_temp == 45.0
    # Zr max is 0.6 m = 23.6 in; 30 in EXCEEDED it, inflating AW ~25% and so
    # understating depletion on a shallow-rooted, stress-sensitive crop. D-013.
    assert root == 24.0
    assert mad == 0.35   # FAO-56 Table 22 p = 0.35 — was 0.45, D-013
    assert kc_ini == 0.50  # FAO-56 Table 12 potato — was 0.45, D-013
    assert kc_mid == 1.15
    assert kc_end == 0.75
    assert gdd == 1600


def test_crop_params_values_sunflower():
    """Sunflower: FAO-56 Table 12 / 22, with p deviation noted (D-013)."""
    from app.engine.water_balance import CROP_PARAMS
    base_temp, root, mad, kc_ini, kc_mid, kc_end, gdd = CROP_PARAMS["sunflower"]
    assert base_temp == 46.0
    assert root == 50.0
    # p 0.50 vs FAO-56's 0.45 — ours is slightly LESS conservative; flagged in
    # D-013, not changed (sunflower is drought-tolerant).
    assert mad == 0.50
    assert kc_ini == 0.35
    # FAO-56 prints kc_mid as a 1.0-1.15 range; 1.10 sits inside it.
    assert kc_mid == 1.10
    assert kc_end == 0.35  # FAO-56 Table 12 sunflower — was 0.55, D-013
    assert gdd == 2000


def test_simulate_season_sweet_corn():
    """Sweet corn simulation runs and produces sensible output."""
    # 3 hot days (sweet corn base=50°F, so GDD=0 on cool days)
    series = [_make_day(95, 75)] * 3
    result = simulate_season(series, "sweet corn", soil_awc=0.20)
    assert result["days"] == 3
    # GDD: avg=(95+75)/2=85, GDD=85-50=35 per day → 105 total
    assert result["total_gdd"] == pytest.approx(105.0, abs=0.1)
    # gdd_frac=105/2200=0.048 (<0.10) → Kc = kc_initial = 0.30
    # ETc: 0.30 × 0.28 = 0.084 per day → 0.252 total
    assert result["total_etc"] == pytest.approx(0.252, abs=0.01)


def test_simulate_season_potatoes():
    """Potatoes simulation runs and produces sensible output."""
    # Potatoes base=45°F, so GDD is higher than corn on same temps
    series = [_make_day(89, 71)] * 3
    result = simulate_season(series, "potatoes", soil_awc=0.20)
    assert result["days"] == 3
    # GDD: avg=80, GDD=80-45=35 per day → 105 total
    assert result["total_gdd"] == pytest.approx(105.0, abs=0.1)


def test_simulate_season_cabbage():
    """Cabbage simulation runs and produces sensible output."""
    # Cabbage base=45°F, so GDD is higher than sweet corn on same temps
    series = [_make_day(89, 71)] * 3
    result = simulate_season(series, "cabbage", soil_awc=0.20)
    assert result["days"] == 3
    # GDD: avg=80, GDD=80-45=35 per day → 105 total
    assert result["total_gdd"] == pytest.approx(105.0, abs=0.1)


def test_simulate_season_onions():
    """Onions simulation runs and produces sensible output."""
    series = [_make_day(95, 75)] * 3
    result = simulate_season(series, "onions", soil_awc=0.20)
    assert result["days"] == 3
    # GDD: avg=85, GDD=85-40=45 per day → 135 total
    assert result["total_gdd"] == pytest.approx(135.0, abs=0.1)


def test_simulate_season_sunflower():
    """Sunflower simulation runs and produces sensible output."""
    series = [_make_day(89, 71)] * 3
    result = simulate_season(series, "sunflower", soil_awc=0.20)
    assert result["days"] == 3
    # GDD: avg=80, GDD=80-46=34 per day → 102 total
    assert result["total_gdd"] == pytest.approx(102.0, abs=0.1)


def test_new_crops_deeper_root_holds_more_water():
    """Sweet corn (24\" root) depletes slower than cabbage (18\" root) on same weather."""
    series = [_make_day(89, 71)] * 30
    # Sweet corn: AW = 24 × 0.20 = 4.8
    result_sweet = simulate_season(series, "sweet corn", soil_awc=0.20)
    # Cabbage: AW = 18 × 0.20 = 3.6
    result_cabbage = simulate_season(series, "cabbage", soil_awc=0.20)
    # Sweet corn has 1.33× AW, so should have fewer days below MAD
    assert result_sweet["days_below_mad"] <= result_cabbage["days_below_mad"]


def test_spinup_cabbage_uses_kc_params():
    """Spin-up for cabbage uses crop-specific Kc curve via crop_id."""
    from app.engine.spinup import spinup_soil_moisture
    series = [_make_day(95, 75)] * 30
    aw = 18 * 0.20  # cabbage root depth × AWC
    sw, depletion = spinup_soil_moisture(
        weather_series=series, aw=aw, crop_id="cabbage",
    )
    assert 0.0 <= depletion <= 1.0
    assert sw >= 0.0


def test_spinup_potatoes_uses_kc_params():
    """Spin-up for potatoes uses crop-specific Kc curve via crop_id."""
    from app.engine.spinup import spinup_soil_moisture
    series = [_make_day(89, 71)] * 30
    aw = 24 * 0.20  # potatoes root depth × AWC (24 in = FAO-56 Zr max, D-013)
    sw, depletion = spinup_soil_moisture(
        weather_series=series, aw=aw, crop_id="potatoes",
    )
    assert 0.0 <= depletion <= 1.0
    assert sw >= 0.0
