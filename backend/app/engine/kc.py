"""Crop coefficient (Kc) curve — FAO-56 style."""
from __future__ import annotations

CROP_PARAMS = {
    "corn":      (50.0, 36.0, 0.50, 0.30, 1.15, 0.90, 2700),
    "soy":       (50.0, 24.0, 0.50, 0.40, 1.10, 0.80, 2500),
    "alfalfa":   (41.0, 30.0, 0.50, 0.40, 1.05, 0.85, 1800),
    "cover":     (40.0, 10.0, 0.45, 0.30, 0.60, 0.55, 1200),
    "potatoes":  (45.0, 30.0, 0.45, 0.45, 1.15, 0.75, 1600),
    "sunflower": (46.0, 50.0, 0.50, 0.35, 1.10, 0.55, 2000),
    "cabbage":   (45.0, 18.0, 0.45, 0.70, 1.05, 0.95, 2000),
    "onions":    (40.0, 14.0, 0.50, 0.70, 1.05, 0.75, 1800),
    "sweet corn":(50.0, 24.0, 0.50, 0.30, 1.15, 0.90, 2200),
}
_CROP_PARAMS_DEFAULT = (50.0, 36.0, 0.5, 0.30, 1.15, 0.90, 2700)


def kc_for_gdd_frac(crop_id: str, gdd_frac: float) -> float:
    """Return crop coefficient for a given crop and GDD fraction of maturity.

    FAO-56-style curve:
      0.00–0.10: kc_initial (seedling)
      0.10–0.50: ramp initial → mid (vegetative)
      0.50–0.62: kc_mid (pollination, peak water use)
      0.62–0.90: ramp mid → end (grain fill)
      0.90–1.00: kc_end (maturity, dry-down)
    """
    params = CROP_PARAMS.get(crop_id, _CROP_PARAMS_DEFAULT)
    _, _, _, kc_initial, kc_mid, kc_end, _ = params
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


def _kc_for_gdd_frac(gdd_frac: float, kc_initial: float = 0.30,
                     kc_mid: float = 1.15, kc_end: float = 0.60) -> float:
    """Return crop coefficient based on GDD fraction (legacy signature)."""
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