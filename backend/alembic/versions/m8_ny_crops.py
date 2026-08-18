"""M8: NY crop rotation — drop cotton/sorghum/peanuts, add cabbage/onions/sweet corn.

Cotton, sorghum, and peanuts are not grown commercially at scale in New York;
they were carried over from the NE/IA/KS scope. New York's major produce acres
are cabbage, onions, and sweet corn. FAO-56 reference values pending
agronomist sign-off (same caveat as M5).
"""

import sqlalchemy as sa

from alembic import op

revision = "m8_ny_crops"
down_revision = "m7_farm_planting_date"
branch_labels = None
depends_on = None

REMOVED_CROPS = ["cotton", "sorghum", "peanuts"]

NEW_CROPS = [
    # (id, base_temp_f, gdd_total, root_depth_in, mad_fraction,
    #  kc_initial, kc_mid, kc_end, stage_days)
    ("cabbage",   45, 2000, 18, 0.45, 0.70, 1.05, 0.95, "20,25,35,25"),
    ("onions",    40, 1800, 14, 0.50, 0.70, 1.05, 0.75, "15,25,35,25"),
    ("sweet corn",50, 2200, 24, 0.50, 0.30, 1.15, 0.90, "20,30,40,25"),
]


def upgrade() -> None:
    # farm_crops crop_id REFERENCES crops(id) (no cascade) — clear orphans first
    for crop_id in REMOVED_CROPS:
        op.execute(
            sa.text("DELETE FROM farm_crops WHERE crop_id = :id").bindparams(id=crop_id)
        )
        op.execute(
            sa.text("DELETE FROM crops WHERE id = :id").bindparams(id=crop_id)
        )
    for (
        crop_id, base_temp, gdd, root_depth, mad,
        kc_ini, kc_mid, kc_end, stage_days,
    ) in NEW_CROPS:
        op.execute(
            sa.text("""
                INSERT INTO crops (
                    id, base_temp_f, gdd_total, root_depth_in, mad_fraction,
                    kc_initial, kc_mid, kc_end, stage_days
                )
                VALUES (
                    :id, :base_temp, :gdd, :root_depth, :mad,
                    :kc_ini, :kc_mid, :kc_end, :stage_days
                )
                ON CONFLICT (id) DO UPDATE SET
                    base_temp_f  = EXCLUDED.base_temp_f,
                    gdd_total    = EXCLUDED.gdd_total,
                    root_depth_in = EXCLUDED.root_depth_in,
                    mad_fraction = EXCLUDED.mad_fraction,
                    kc_initial   = EXCLUDED.kc_initial,
                    kc_mid       = EXCLUDED.kc_mid,
                    kc_end       = EXCLUDED.kc_end,
                    stage_days   = EXCLUDED.stage_days
            """).bindparams(
                id=crop_id, base_temp=base_temp, gdd=gdd,
                root_depth=root_depth, mad=mad,
                kc_ini=kc_ini, kc_mid=kc_mid, kc_end=kc_end,
                stage_days=stage_days,
            )
        )


def downgrade() -> None:
    for crop_id in ["cabbage", "onions", "sweet corn"]:
        op.execute(
            sa.text("DELETE FROM farm_crops WHERE crop_id = :id").bindparams(id=crop_id)
        )
        op.execute(
            sa.text("DELETE FROM crops WHERE id = :id").bindparams(id=crop_id)
        )
    old_crops = [
        ("cotton",    58, 2800, 60, 0.55, 0.35, 1.15, 0.70, "30,60,70,40"),
        ("sorghum",   50, 2200, 48, 0.50, 0.35, 1.10, 0.55, "25,40,45,30"),
        ("peanuts",   54, 2500, 30, 0.50, 0.40, 1.15, 0.60, "30,40,50,30"),
    ]
    for (
        crop_id, base_temp, gdd, root_depth, mad,
        kc_ini, kc_mid, kc_end, stage_days,
    ) in old_crops:
        op.execute(
            sa.text("""
                INSERT INTO crops (
                    id, base_temp_f, gdd_total, root_depth_in, mad_fraction,
                    kc_initial, kc_mid, kc_end, stage_days
                )
                VALUES (
                    :id, :base_temp, :gdd, :root_depth, :mad,
                    :kc_ini, :kc_mid, :kc_end, :stage_days
                )
            """).bindparams(
                id=crop_id, base_temp=base_temp, gdd=gdd,
                root_depth=root_depth, mad=mad,
                kc_ini=kc_ini, kc_mid=kc_mid, kc_end=kc_end,
                stage_days=stage_days,
            )
        )