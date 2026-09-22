"""m11_fao56_crop_params — align 6 crops with FAO-56 Tables 12 and 22.

DECISIONS.md D-013. Follows m10, which corrected corn kc_end alone.

Verified against FAO-56 (fao.org/4/x0490e/):
  Table 12 — single crop coefficients Kc_ini / Kc_mid / Kc_end
  Table 22 — max effective rooting depth Zr (m) and depletion fraction p

Corrections applied (field: ours -> FAO-56):

  soy         kc_end       0.80 -> 0.50   Table 12 soybeans
  alfalfa     kc_end       0.85 -> 0.90   Table 12 alfalfa hay, averaged cutting
  sunflower   kc_end       0.55 -> 0.35   Table 12 sunflower
  sweet corn  kc_end       0.90 -> 1.05   Table 12 sweet maize (fresh harvest)
  potatoes    kc_initial   0.45 -> 0.50   Table 12 potato
  potatoes    mad_fraction 0.45 -> 0.35   Table 22 p = 0.35
  potatoes    root_depth_in  30 -> 24     Table 22 Zr max 0.6 m = 23.6 in
  onions      mad_fraction 0.50 -> 0.30   Table 22 p = 0.30 (onion, dry)

Why potatoes' root depth is REDUCED: 30 in exceeded FAO-56's *maximum* Zr of
0.6 m, inflating AW = root_depth x AWC by ~25% and so understating depletion —
under-irrigating a shallow-rooted, stress-sensitive crop.

Why onions' and potatoes' p matter most: both are shallow-rooted and sensitive
to water stress. Waiting for 50% / 45% depletion instead of 30% / 35% delays
irrigation past the no-stress threshold.

NOT changed here (report only, see D-013):
  * kc_mid for ANY crop. corn 1.15 vs FAO 1.20 is load-bearing on SPEC §4's
    authoritative worked example (1.15 x 0.28 = 0.322); correcting the others
    alone would leave the table half-migrated. One coordinated spec-owner
    decision.
  * Root depths that sit BELOW FAO's Zr range (corn 36 vs 39-67, alfalfa 30 vs
    39-79, sweet corn 24 vs 31-47, cabbage 18 vs 20-31). Zr is the MAXIMUM
    effective depth under ideal conditions; using less is defensible for NY
    (shallow soils, hardpan, high water tables in muck land) and errs
    conservative. Raising them would increase AW and make the model LESS likely
    to advise irrigation — not a change to make without local rooting data.
  * corn p 0.50 vs 0.55 and alfalfa p 0.50 vs 0.55: ours are MORE conservative.
  * `cover` has no FAO-56 Table 12 entry at all; its values have no reference.
"""
import sqlalchemy as sa

from alembic import op

revision = "m11_fao56_crop_params"
down_revision = "m10_corn_kc_end"
branch_labels = None
depends_on = None

# (crop_id, column, new_value, old_value)
_CHANGES = [
    ("soy", "kc_end", 0.50, 0.80),
    ("alfalfa", "kc_end", 0.90, 0.85),
    ("sunflower", "kc_end", 0.35, 0.55),
    ("sweet corn", "kc_end", 1.05, 0.90),
    ("potatoes", "kc_initial", 0.50, 0.45),
    ("potatoes", "mad_fraction", 0.35, 0.45),
    ("potatoes", "root_depth_in", 24.0, 30.0),
    ("onions", "mad_fraction", 0.30, 0.50),
]


def _apply(index: int) -> None:
    for crop_id, column, new, old in _CHANGES:
        op.execute(
            sa.text(
                f"UPDATE crops SET {column} = :v WHERE id = :id"
            ).bindparams(v=(new if index == 0 else old), id=crop_id)
        )


def upgrade() -> None:
    _apply(0)


def downgrade() -> None:
    _apply(1)
