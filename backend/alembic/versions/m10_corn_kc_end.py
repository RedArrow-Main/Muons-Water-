"""m10_corn_kc_end — correct corn kc_end from 0.90 to 0.60 (FAO-56).

Agronomist sign-off, DECISIONS.md D-010.

FAO-56 Table 12 gives maize three distinct end-of-season coefficients depending
on how the crop is harvested, because Kc_end reflects whether the canopy is
still transpiring:

    field (grain), dry harvest             Kc_end 0.35
    field (grain), high-moisture harvest   Kc_end 0.60   <- adopted
    silage (cut green)                     Kc_end ~1.05-1.15
    sweet corn                             Kc_end 1.05

The previous 0.90 corresponds to none of these — it sits between "dried down"
and "cut green". 0.60 is the correct row for New York, where a large share of
grain corn is harvested at high moisture for on-farm storage rather than
field-dried (drying is expensive here).

Effect: the grain-fill ramp interpolates toward Kc_end across gdd_frac
0.62-0.90, where STAGE_WEIGHTS is 1.0 and the MAD factor is 0.80. At
gdd_frac 0.76 the coefficient moves 1.025 -> 0.875, roughly 15% lower modelled
crop water use through grain fill.

NOT changed here: kc_mid stays 1.15 even though FAO-56 gives 1.20 for field
maize, because SPEC.md §4's authoritative worked example is built on
1.15 x 0.28 = 0.322 and changing it would cascade through every worked example.
Logged as a separate open question.
"""
import sqlalchemy as sa

from alembic import op

revision = "m10_corn_kc_end"
down_revision = "m9_subscribers_and_units"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text("UPDATE crops SET kc_end = 0.60 WHERE id = 'corn'")
    )


def downgrade() -> None:
    op.execute(
        sa.text("UPDATE crops SET kc_end = 0.90 WHERE id = 'corn'")
    )
