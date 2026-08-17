"""M4: Add advisories table for M3 — hash-chained advisory storage."""

revision = "m4_add_advisories"
down_revision = "m3_add_users"
branch_labels = None
depends_on = None


def upgrade():
    import sqlalchemy as sa
    from alembic import op

    op.create_table(
        "advisories",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("county_fips", sa.String(5), nullable=False),
        sa.Column("crop_id", sa.String(20), nullable=False),
        sa.Column("type", sa.String(30), nullable=False, server_default="water_budget"),
        sa.Column("severity", sa.String(10), nullable=False),  # info, watch, action
        sa.Column("headline", sa.String(200), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("source_data", sa.JSON, nullable=True),      # audit trail
        sa.Column("hash", sa.String(64), nullable=False),      # SHA-256
        sa.Column("prev_hash", sa.String(64), nullable=True),  # chain link
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )

    op.create_index("idx_advisories_fips_date", "advisories",
                    ["county_fips", "generated_at"])
    op.create_index("idx_advisories_hash", "advisories", ["hash"], unique=True)
    op.create_index("idx_advisories_status", "advisories", ["status"])


def downgrade():
    op.drop_index("idx_advisories_status")
    op.drop_index("idx_advisories_hash")
    op.drop_index("idx_advisories_fips_date")
    op.drop_table("advisories")
