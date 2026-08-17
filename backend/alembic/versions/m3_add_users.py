"""M3: Add users table for email/password authentication."""

revision = "m3_add_users"
down_revision = "m2_add_outbox"
branch_labels = None
depends_on = None


def upgrade():
    import sqlalchemy as sa
    from alembic import op

    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("phone_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("idx_users_email", "users", ["email"], unique=True)


def downgrade():
    op.drop_table("users")
