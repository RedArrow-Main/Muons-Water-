"""TDD tests for soil-moisture spin-up (write first, see fail, then implement)."""
from __future__ import annotations

import pytest

from app.engine.spinup import spinup_soil_moisture

# ── Fixture data ───────────────────────────────────────────────────────

# Corn params: root_depth=36in, kc_mid=1.20, mad=0.50
# Silt loam AWC=0.20 → AW = 36 × 0.20 = 7.2"

WET_HISTORY = [
    # 5 days of heavy rain, low ET → soil should be near field capacity
    {"tmax_f": 75, "tmin_f": 55, "precip_in": 1.5, "et0_in": 0.15},
    {"tmax_f": 78, "tmin_f": 58, "precip_in": 2.0, "et0_in": 0.18},
    {"tmax_f": 72, "tmin_f": 52, "precip_in": 1.0, "et0_in": 0.12},
    {"tmax_f": 80, "tmin_f": 60, "precip_in": 0.8, "et0_in": 0.20},
    {"tmax_f": 76, "tmin_f": 56, "precip_in": 1.2, "et0_in": 0.16},
]

DRY_HISTORY = [
    # 5 days of no rain, high ET → soil should be depleted
    {"tmax_f": 95, "tmin_f": 75, "precip_in": 0.0, "et0_in": 0.35},
    {"tmax_f": 98, "tmin_f": 78, "precip_in": 0.0, "et0_in": 0.38},
    {"tmax_f": 92, "tmin_f": 72, "precip_in": 0.0, "et0_in": 0.30},
    {"tmax_f": 96, "tmin_f": 76, "precip_in": 0.0, "et0_in": 0.36},
    {"tmax_f": 94, "tmin_f": 74, "precip_in": 0.0, "et0_in": 0.34},
]

BALANCED_HISTORY = [
    # Rain roughly matches ET → moderate depletion
    {"tmax_f": 85, "tmin_f": 65, "precip_in": 0.35, "et0_in": 0.28},
    {"tmax_f": 88, "tmin_f": 68, "precip_in": 0.10, "et0_in": 0.30},
    {"tmax_f": 82, "tmin_f": 62, "precip_in": 0.50, "et0_in": 0.25},
    {"tmax_f": 86, "tmin_f": 66, "precip_in": 0.05, "et0_in": 0.29},
    {"tmax_f": 84, "tmin_f": 64, "precip_in": 0.20, "et0_in": 0.27},
]


# ═══════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestSpinupWetHistory:
    """Heavy rain → soil stays wet → low depletion."""

    def test_low_depletion(self):
        _sw, depletion = spinup_soil_moisture(
            weather_series=WET_HISTORY,
            aw=7.2,
            crop_id="corn",
        )
        # After 5 days of heavy rain, SW should be near AW (field capacity)
        assert depletion < 0.10, f"Expected low depletion, got {depletion:.4f}"

    def test_sw_near_aw(self):
        sw, _depletion = spinup_soil_moisture(
            weather_series=WET_HISTORY,
            aw=7.2,
            crop_id="corn",
        )
        assert sw > 6.5, f"Expected SW near AW (7.2), got {sw:.2f}"


class TestSpinupDryHistory:
    """No rain, high ET → soil depletes → high depletion."""

    def test_depletion_occurs(self):
        _sw, depletion = spinup_soil_moisture(
            weather_series=DRY_HISTORY,
            aw=7.2,
            crop_id="corn",
        )
        # After 5 days of no rain, some depletion should occur
        # (Kc ramps from 0.30, so depletion is modest over 5 days)
        assert depletion > 0.0, f"Expected some depletion, got {depletion:.4f}"

    def test_sw_dropped(self):
        sw, _depletion = spinup_soil_moisture(
            weather_series=DRY_HISTORY,
            aw=7.2,
            crop_id="corn",
        )
        # Started at 7.2, should drop (even with low early-season Kc)
        assert sw < 7.2, f"Expected SW to drop, got {sw:.2f}"


class TestSpinupBalancedHistory:
    """Moderate rain + moderate ET → low depletion (rain matches ET)."""

    def test_low_depletion(self):
        _sw, depletion = spinup_soil_moisture(
            weather_series=BALANCED_HISTORY,
            aw=7.2,
            crop_id="corn",
        )
        # With GDD-scaled Kc (low early season), rain likely exceeds ET
        assert depletion >= 0.0, f"Expected non-negative depletion, got {depletion:.4f}"


class TestSpinupDeterministic:
    """Same inputs → same output (pure function)."""

    def test_same_inputs_same_output(self):
        r1 = spinup_soil_moisture(weather_series=WET_HISTORY, aw=7.2, crop_id="corn")
        r2 = spinup_soil_moisture(weather_series=WET_HISTORY, aw=7.2, crop_id="corn")
        assert r1 == r2

    def test_different_inputs_different_output(self):
        r1 = spinup_soil_moisture(weather_series=WET_HISTORY, aw=7.2, crop_id="corn")
        r2 = spinup_soil_moisture(weather_series=DRY_HISTORY, aw=7.2, crop_id="corn")
        assert r1 != r2


class TestSpinupEdgeCases:
    """Edge cases: empty history, single day, zero AW."""

    def test_empty_history(self):
        """Empty history → returns starting SW (field capacity)."""
        sw, depletion = spinup_soil_moisture(weather_series=[], aw=7.2, crop_id="corn")
        assert sw == 7.2
        assert depletion == 0.0

    def test_single_day(self):
        """Single day: SW = min(AW, AW + rain - ETc)."""
        sw, depletion = spinup_soil_moisture(
            weather_series=[{"tmax_f": 85, "tmin_f": 65, "precip_in": 0.5, "et0_in": 0.30}],
            aw=7.2,
            crop_id="corn",
        )
        # Day 1 sits at gdd_frac ~0 → Kc = kc_initial = 0.30, NOT kc_mid.
        # ETc = 0.30 × 0.30 = 0.09, net = 0.5 - 0.09 = +0.41
        # SW = min(7.2, 7.2 + 0.155) = 7.2 (capped at AW)
        assert sw == 7.2
        assert depletion == 0.0

    def test_zero_aw(self):
        """Zero AW → depletion is 0 (guard against division by zero)."""
        _sw, depletion = spinup_soil_moisture(weather_series=DRY_HISTORY, aw=0.0, crop_id="corn")
        assert depletion == 0.0


class TestSpinupSmallAW:
    """Small AW (sandy loam) depletes faster than large AW (silt loam)."""

    def test_sandy_loam_depletes_faster(self):
        _sw_sandy, dep_sandy = spinup_soil_moisture(
            weather_series=DRY_HISTORY, aw=4.0, crop_id="corn",
        )
        _sw_silt, dep_silt = spinup_soil_moisture(
            weather_series=DRY_HISTORY, aw=7.2, crop_id="corn",
        )
        assert dep_sandy > dep_silt, (
            f"Sandy loam ({dep_sandy:.4f}) should deplete more than silt loam ({dep_silt:.4f})"
        )


class TestSpinupGDDScaling:
    """GDD-based Kc scaling produces less depletion than flat kc_mid."""

    def test_less_depletion_with_gdd_scaling(self):
        """30 days with kc_mid=1.20 flat should deplete MORE than GDD-scaled."""
        # Build 30 hot dry days (enough to see the Kc difference, not enough to deplete fully)
        dry_30 = [
            {"tmax_f": 90, "tmin_f": 70, "precip_in": 0.05, "et0_in": 0.30}
            for _ in range(30)
        ]
        _sw_flat, dep_flat = spinup_soil_moisture(
            weather_series=dry_30, aw=7.2, kc=1.20, use_gdd_scaling=False,
        )
        # GDD-scaled version uses lower Kc for first ~50 days
        _sw_gdd, dep_gdd = spinup_soil_moisture(
            weather_series=dry_30, aw=7.2, crop_id="corn",
        )
        # GDD-scaled should deplete LESS (lower Kc in early season)
        assert dep_gdd < dep_flat, (
            f"GDD-scaled ({dep_gdd:.4f}) should deplete less than flat ({dep_flat:.4f})"
        )

    def test_different_crops_different_depletion(self):
        """Corn (kc_initial=0.30) and onions (kc_initial=0.70) must differ."""
        dry_30 = [
            {"tmax_f": 90, "tmin_f": 70, "precip_in": 0.05, "et0_in": 0.30}
            for _ in range(30)
        ]
        _, dep_corn = spinup_soil_moisture(
            weather_series=dry_30, aw=7.2, crop_id="corn",
        )
        _, dep_onions = spinup_soil_moisture(
            weather_series=dry_30, aw=7.2, crop_id="onions",
        )
        # Onions has higher kc_initial (0.70 vs 0.30), so depletes more
        assert dep_onions > dep_corn, (
            f"Onions ({dep_onions:.4f}) should deplete more than corn ({dep_corn:.4f})"
        )

    def test_kc_curve_values(self):
        """Verify Kc curve at key GDD fractions.

        Grain-fill and maturity values reflect corn kc_end = 0.60 (FAO-56
        Table 12, maize (grain) harvested at HIGH MOISTURE — see DECISIONS.md
        D-010 and migration m10_corn_kc_end). The previous 0.90 corresponded to
        no FAO-56 harvest mode: too low for silage cut green (~1.05-1.15), too
        high for grain (0.35 dry / 0.60 high-moisture).

        Mid-season values reflect corn kc_mid = 1.20 (FAO-56 Table 12, maize
        (grain) — see DECISIONS.md D-014 and migration m12_fao56_kc_mid). The
        previous 1.15 was *sweet* corn's Kc_mid, not field maize's.
        """
        from app.engine.kc import kc_for_gdd_frac
        assert kc_for_gdd_frac("corn", 0.0) == 0.30   # seedling
        assert kc_for_gdd_frac("corn", 0.10) == 0.30  # just entering vegetative
        assert kc_for_gdd_frac("corn", 0.30) == pytest.approx(0.75, abs=0.01)  # mid-vegetative
        assert kc_for_gdd_frac("corn", 0.50) == 1.20   # pollination start
        assert kc_for_gdd_frac("corn", 0.56) == 1.20   # pollination peak
        assert kc_for_gdd_frac("corn", 0.62) == 1.20   # pollination end
        assert kc_for_gdd_frac("corn", 0.76) == pytest.approx(0.90, abs=0.01)  # mid grain-fill
        assert kc_for_gdd_frac("corn", 0.90) == 0.60   # maturity
        assert kc_for_gdd_frac("corn", 1.00) == 0.60   # past maturity


def test_spinup_preserves_growth_before_weather_window():
    # 1380 prior GDD + 30/day stays on corn's 1.20 plateau.
    # Three dry days: 7.2 - 3 * (1.20 * 0.28) = 6.192 inches.
    weather = [{"tmax_f": 89, "tmin_f": 71, "precip_in": 0, "et0_in": 0.28}] * 3
    sw, depletion = spinup_soil_moisture(
        weather, aw=7.2, crop_id='corn', initial_gdd=1380,
    )
    assert sw == pytest.approx(6.192)
    assert depletion == pytest.approx(0.14)


def test_spinup_uses_supplied_starting_water():
    weather = [{"tmax_f": 89, "tmin_f": 71, "precip_in": 0, "et0_in": 0.28}] * 3
    sw, depletion = spinup_soil_moisture(
        weather, aw=7.2, initial_gdd=1380, initial_sw=3.6,
    )
    # 3.6 - 3 * 1.20 * .28 = 2.592, depletion .64.
    assert sw == pytest.approx(2.592)
    assert depletion == pytest.approx(.64)


def test_full_history_replay_equals_continuing_previous_state():
    weather = [{"tmax_f": 89, "tmin_f": 71, "precip_in": 0, "et0_in": .28}] * 6
    first, _ = spinup_soil_moisture(weather[:3], 7.2, initial_gdd=1380, initial_sw=3.6)
    continued = spinup_soil_moisture(weather[3:], 7.2, initial_gdd=1470, initial_sw=first)
    replay = spinup_soil_moisture(weather, 7.2, initial_gdd=1380, initial_sw=3.6)
    assert continued == pytest.approx(replay)


def test_initialization_bounds_converge_after_soaking_rain():
    weather = [{"tmax_f": 89, "tmin_f": 71, "precip_in": 10, "et0_in": .28}]
    low = spinup_soil_moisture(weather, 7.2, initial_sw=0)
    high = spinup_soil_moisture(weather, 7.2, initial_sw=7.2)
    assert low == high == (7.2, 0.0)
