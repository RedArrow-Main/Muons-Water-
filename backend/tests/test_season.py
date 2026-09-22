"""Tests for app/engine/season.py — Julian conversion and planting defaults.

Covers the two defects this module was created to fix:

1. The year was hardcoded to 2026 in `_fmt_julian`, duplicated in
   advisor/service.py and dashboard/routes.py, so from January 2027 onward both
   produced planting dates a full year early — silently, feeding
   gdd_frac -> Kc -> stage-adjusted MAD -> the irrigate decision.
2. The default planting date was the LATEST SAFE plant date, which models every
   farmer as having planted as late as possible.
"""
from __future__ import annotations

import pytest

from app.engine.season import (
    NY_TYPICAL_PLANTING,
    default_planting_date,
    julian_to_date,
    latest_safe_planting_date,
    typical_planting_date,
)

# ── julian_to_date: year comes from ref_date, never a constant ──────────────

@pytest.mark.parametrize(("julian", "ref_date", "expected"), [
    (150, "2026-08-31", "2026-05-30"),   # non-leap
    (150, "2027-06-15", "2027-05-30"),   # the year the old code got wrong
    (150, "2028-01-10", "2028-05-29"),   # leap year shifts the calendar date
    (1, "2026-03-01", "2026-01-01"),     # lower bound
    (275, "2026-08-31", "2026-10-02"),   # Albany frost_kill_50
])
def test_julian_to_date_anchors_to_ref_year(julian, ref_date, expected):
    assert julian_to_date(julian, ref_date) == expected


def test_julian_to_date_is_not_pinned_to_2026():
    """The 2027 case is the regression: hardcoded 2026 produced 2026-05-30."""
    assert julian_to_date(150, "2027-06-15").startswith("2027-")


# ── latest_safe_planting_date ──────────────────────────────────────────────

def test_latest_safe_planting_date_albany_corn():
    """Albany frost_kill_50 = 275 (seeded), corn maturity 130 -> julian 145."""
    assert latest_safe_planting_date(275, 130, "2026-08-31") == "2026-05-25"


def test_latest_safe_planting_date_none_without_frost_normal():
    assert latest_safe_planting_date(None, 130, "2026-08-31") is None
    assert latest_safe_planting_date(0, 130, "2026-08-31") is None


# ── typical / default planting date ────────────────────────────────────────

def test_typical_planting_date_tracks_ref_year():
    month, day = NY_TYPICAL_PLANTING
    for year in ("2026", "2027", "2030"):
        assert typical_planting_date(f"{year}-08-31") == f"{year}-{month:02d}-{day:02d}"


def test_default_is_typical_not_latest_safe():
    """The default must be the TYPICAL date, not the latest-safe one.

    Using latest-safe (2026-05-25 here) as the assumed planting date for a
    farmer who did not supply one understates accumulated GDD by ~10 days,
    landing the crop in an earlier stage with a lower Kc and a less
    conservative MAD — an error in the yield-losing direction at pollination.
    """
    latest = latest_safe_planting_date(275, 130, "2026-08-31")
    default = default_planting_date(275, 130, "2026-08-31")
    assert default == "2026-05-15"
    assert default < latest, "default should be earlier than the latest safe date"


def test_default_falls_back_to_typical_without_frost_normal():
    assert default_planting_date(None, 130, "2026-08-31") == "2026-05-15"


def test_default_is_clamped_to_latest_safe_for_long_season_crops():
    """A crop so long that latest-safe precedes the typical date must clamp.

    Otherwise the default would imply a crop planted after the last date it
    could still reach maturity.
    """
    # frost 275, maturity 200 -> latest safe = julian 75 = 2026-03-16
    latest = latest_safe_planting_date(275, 200, "2026-08-31")
    assert latest == "2026-03-16"
    assert default_planting_date(275, 200, "2026-08-31") == latest


def test_default_tracks_ref_year_across_seasons():
    assert default_planting_date(275, 130, "2027-06-15") == "2027-05-15"
    assert default_planting_date(275, 130, "2028-01-10") == "2028-05-15"
