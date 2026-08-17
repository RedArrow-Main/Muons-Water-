"""M5: Expand crop library — add cotton, sorghum, potatoes, peanuts, sunflower.

FAO-56 reference values pending agronomist sign-off.
"""

revision = "m5_expand_crops"
down_revision = "m4_add_advisories"
branch_labels = None
depends_on = None


NEW_CROPS = [
    # (id, base_temp_f, gdd_total, root_depth_in, mad_fraction,
    #  kc_initial, kc_mid, kc_end, stage_days)
    ("cotton",    58, 2800, 60, 0.55, 0.35, 1.15, 0.70, "30,60,70,40"),
    ("sorghum",   50, 2200, 48, 0.50, 0.35, 1.10, 0.55, "25,40,45,30"),
    ("potatoes",  45, 1600, 30, 0.45, 0.45, 1.15, 0.75, "25,30,35,25"),
    ("peanuts",   54, 2500, 30, 0.50, 0.40, 1.15, 0.60, "30,40,50,30"),
    ("sunflower", 46, 2000, 50, 0.50, 0.35, 1.10, 0.55, "25,35,40,30"),
]


def upgrade():
    import sqlalchemy as sa
    from alembic import op

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


def downgrade():
    from alembic import op

    crop_ids = [c[0] for c in NEW_CROPS]
    for crop_id in crop_ids:
        op.execute(sa.text("DELETE FROM crops WHERE id = :id").bindparams(id=crop_id))
