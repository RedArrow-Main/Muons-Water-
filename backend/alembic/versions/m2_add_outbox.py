"""M2: Add outbox table for SMS tracking."""

revision = "m2_add_outbox"
down_revision = "m1_data_pipeline"
branch_labels = None
depends_on = None


def upgrade():
    import sqlalchemy as sa
    from alembic import op

    op.create_table(
        "outbox",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("county_fips", sa.String(5), nullable=False),
        sa.Column("phone_to", sa.String(20), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="sent"),
        sa.Column("twilio_sid", sa.String(64), nullable=True),
        sa.Column("error_msg", sa.Text, nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("idx_outbox_fips", "outbox", ["county_fips"])
    op.create_index("idx_outbox_sent", "outbox", ["sent_at"])


def downgrade():
    op.drop_table("outbox")
