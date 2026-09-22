"""m12_fao56_kc_mid — align corn/soy/alfalfa kc_mid with FAO-56 Table 12.

DECISIONS.md D-014. Follows m11, which corrected kc_end / kc_initial / p /
root depth but deliberately left every kc_mid alone pending a coordinated
spec-owner decision. This is that decision, applied.

Verified against FAO-56 Table 12 (fao.org/4/x0490e/x0490e0b.htm):

  corn      kc_mid  1.15 -> 1.20   Maize, Field (grain): 0.30 / 1.20 / 0.60-0.35
  soy       kc_mid  1.10 -> 1.15   Soybeans:              0.40 / 1.15 / 0.50
  alfalfa   kc_mid  1.05 -> 0.95   Alfalfa hay, averaged cutting effects:
                                     0.40 / 0.95 / 0.90

Corn is the significant one: 1.15 is *sweet* maize's Kc_mid (Table 12 lists
Maize, Sweet as 0.30 / 1.15 / 1.05). Field corn was carrying the wrong crop's
mid-season coefficient, understating peak water use by ~4% through the highest-
ETc part of the season — pollination, where STAGE_WEIGHTS is 1.5 and the
stage-adjusted MAD factor is 0.60. Under-irrigating there is the yield-losing
direction.

kc_mid also terminates the vegetative ramp (gdd_frac 0.10-0.50) and originates
the grain-fill ramp (0.62-0.90), so this moves the curve everywhere above
gdd_frac 0.10, not only the 0.50-0.62 plateau.

NOT changed here:
  * sunflower kc_mid 1.10 — Table 12 prints a RANGE of 1.0-1.15; 1.10 is inside
    it, so there is nothing to correct.
  * potatoes 1.15, cabbage 1.05, onions 1.05, sweet corn 1.15 — already
    FAO-exact.
  * `cover` 0.60 — no FAO-56 Table 12 entry exists for it at all; its six
    parameters remain unsourced (D-013). Not something a migration can fix.

With this, every kc_initial / kc_mid / kc_end in `crops` matches FAO-56
Table 12 for the eight crops the table covers.
"""
import sqlalchemy as sa

from alembic import op

revision = "m12_fao56_kc_mid"
down_revision = "m11_fao56_crop_params"
branch_labels = None
depends_on = None

# (crop_id, new_value, old_value)
_CHANGES = [
    ("corn", 1.20, 1.15),
    ("soy", 1.15, 1.10),
    ("alfalfa", 0.95, 1.05),
]


def _apply(index: int) -> None:
    for crop_id, new, old in _CHANGES:
        op.execute(
            sa.text("UPDATE crops SET kc_mid = :v WHERE id = :id").bindparams(
                v=(new if index == 0 else old), id=crop_id
            )
        )


def upgrade() -> None:
    _apply(0)


def downgrade() -> None:
    _apply(1)
