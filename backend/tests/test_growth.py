"""Tests for engine.growth — growth-stage + stage-adjusted MAD.

Hand-computed values (SPEC.md §4 authoritative):
  GDD_day(corn, tmax=89, tmin=71) = (89+71)/2 − 50 = 30
  corn gdd_to_maturity = 2700

  Stage bands (GDD fraction):
    Vegetative  0.00–0.50  weight 0.4  MAD factor 1.00
    Pollination 0.50–0.62  weight 1.5  MAD factor 0.60
    Grain fill  0.62–0.90  weight 1.0  MAD factor 0.80
    Maturity    0.90–1.00  weight 0.3  MAD factor 1.00

  Worked example: 3 days × 30 GDD = 90 cumulative → frac = 90/2700 = 0.0333
    → stage 'vegetative', MAD stays 0.50.

  Pollination: frac = 0.50–0.62 → corn MAD = 0.50 × 0.60 = 0.30
  Grain fill:  frac = 0.62–0.90 → corn MAD = 0.50 × 0.80 = 0.40
  Maturity:    frac ≥ 0.90      → corn MAD = 0.50 × 1.00 = 0.50
"""
from __future__ import annotations

import pytest

from app.engine.growth import (
    adjusted_mad,
    cumulative_gdd,
    gdd_fraction,
    growth_stage,
    stage_index,
    stage_label,
    stage_mad_factor,
    stage_weight,
)

# ---------------------------------------------------------------------------
# Hand-computed — GDD accumulation
# ---------------------------------------------------------------------------

def test_cumulative_gdd_worked_example():
    """3 days (89, 71) corn base 50 → 30 GDD/day → 90 total."""
    series = [(89.0, 71.0)] * 3
    assert cumulative_gdd(series, 50.0) == pytest.approx(90.0, abs=0.1)


def test_cumulative_gdd_zero_on_cold():
    """Cold days accumulate no GDD (below base)."""
    series = [(40.0, 30.0)] * 5  # avg 35 < 50 → 0 GDD/day
    assert cumulative_gdd(series, 50.0) == 0.0


def test_gdd_fraction_worked_example():
    """90 / 2700 = 0.0333."""
    assert gdd_fraction(90, 2700) == pytest.approx(0.0333, abs=0.0001)


def test_gdd_fraction_no_maturity_target():
    assert gdd_fraction(100, 0) == 0.0


# ---------------------------------------------------------------------------
# Growth stage boundaries (SPEC §4 bands)
# ---------------------------------------------------------------------------

def test_growth_stage_bands():
    assert growth_stage(0.000) == "vegetative"
    assert growth_stage(0.4999) == "vegetative"
    assert growth_stage(0.5000) == "pollination"   # boundary: low inclusive
    assert growth_stage(0.6199) == "pollination"
    assert growth_stage(0.6200) == "grain_fill"
    assert growth_stage(0.8999) == "grain_fill"
    assert growth_stage(0.9000) == "maturity"
    assert growth_stage(1.0000) == "maturity"
    assert growth_stage(1.5000) == "maturity"      # past maturity clamps


def test_stage_labels():
    assert stage_label(0.03) == "Vegetative"
    assert stage_label(0.55) == "Pollination"
    assert stage_label(0.75) == "Grain Fill"
    assert stage_label(0.95) == "Maturity"


def test_stage_index_weights_match_water_balance():
    assert stage_weight(0.25) == 0.4
    assert stage_weight(0.55) == 1.5
    assert stage_weight(0.75) == 1.0
    assert stage_weight(0.95) == 0.3
    assert stage_index(0.0) == 0
    assert stage_index(1.0) == 3


# ---------------------------------------------------------------------------
# Stage-adjusted MAD (SPEC §4 worked example: corn base_mad = 0.50)
# ---------------------------------------------------------------------------

def test_adjusted_mad_vegetative_unaffected():
    """Vegetative keeps base MAD — 0.50 × 1.00 = 0.50."""
    assert adjusted_mad(0.50, 0.0333) == pytest.approx(0.50, abs=0.001)


def test_adjusted_mad_pollination_tightens():
    """Pollination is critical — 0.50 × 0.60 = 0.30."""
    assert adjusted_mad(0.50, 0.55) == pytest.approx(0.30, abs=0.001)


def test_adjusted_mad_grain_fill():
    """Grain fill — 0.50 × 0.80 = 0.40."""
    assert adjusted_mad(0.50, 0.75) == pytest.approx(0.40, abs=0.001)


def test_adjusted_mad_maturity_restores():
    """Maturity — 0.50 × 1.00 = 0.50."""
    assert adjusted_mad(0.50, 0.95) == pytest.approx(0.50, abs=0.001)


def test_adjusted_mad_other_crops():
    """Other crops use their own base MAD."""
    assert adjusted_mad(0.45, 0.55) == pytest.approx(0.27, abs=0.001)  # potatoes
    assert adjusted_mad(0.55, 0.75) == pytest.approx(0.44, abs=0.001)  # outlook crops
    assert adjusted_mad(0.50, 0.30) == pytest.approx(0.50, abs=0.001)  # soy vegetative


def test_adjusted_mad_matches_cumulative():
    """End-to-end: 90 GDD → vegetative → MAD unchanged."""
    cum = cumulative_gdd([(89.0, 71.0)] * 3, 50.0)
    frac = gdd_fraction(cum, 2700)
    assert growth_stage(frac) == "vegetative"
    assert adjusted_mad(0.50, frac) == pytest.approx(0.50, abs=0.001)


def test_stage_mad_factor_table():
    assert stage_mad_factor(0.25) == 1.00
    assert stage_mad_factor(0.55) == 0.60
    assert stage_mad_factor(0.75) == 0.80
    assert stage_mad_factor(0.95) == 1.00