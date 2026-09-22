"""m9_subscribers_and_units — add subscribers table; fix daily_records units.

- Creates `subscribers` so the nightly SMS path (nightly.py::_send_sms_advisories)
  no longer crashes on a missing table. SPEC.md v1.14 §5 step 6 requires the
  optional SMS send to be operational.
- Renames daily_records columns et0_mm/rainfall_mm/irrigation_mm -> *_in because
  the engine computes and stores everything in inches (SPEC §4). The columns were
  never populated with mm, so this is a pure rename correcting the schema contract.
"""
import sqlalchemy as sa

from alembic import op

revision = "m9_subscribers_and_units"
down_revision = "m8_ny_crops"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscribers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("county_fips", sa.String(5), sa.ForeignKey("counties.fips"), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_subscribers_fips", "subscribers", ["county_fips"])

    op.alter_column(
        "daily_records", "et0_mm",
        new_column_name="et0_in", existing_type=sa.Float(), nullable=True,
    )
    op.alter_column(
        "daily_records", "rainfall_mm",
        new_column_name="rainfall_in", existing_type=sa.Float(), nullable=True,
    )
    op.alter_column(
        "daily_records", "irrigation_mm",
        new_column_name="irrigation_in", existing_type=sa.Float(), nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "daily_records", "et0_in",
        new_column_name="et0_mm", existing_type=sa.Float(), nullable=True,
    )
    op.alter_column(
        "daily_records", "rainfall_in",
        new_column_name="rainfall_mm", existing_type=sa.Float(), nullable=True,
    )
    op.alter_column(
        "daily_records", "irrigation_in",
        new_column_name="irrigation_mm", existing_type=sa.Float(), nullable=True,
    )
    op.drop_index("idx_subscribers_fips", table_name="subscribers")
    op.drop_table("subscribers")
