"""m6_add_farms — Add farms and farm_crops tables for M6 dashboard."""
from alembic import op
import sqlalchemy as sa

revision = "m6_add_farms"
down_revision = "m5_expand_crops"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "farms",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("county_fips", sa.String(5), sa.ForeignKey("counties.fips"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("acres", sa.Numeric, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "county_fips", name="uq_farm_user_county"),
    )
    op.create_table(
        "farm_crops",
        sa.Column("farm_id", sa.Integer, sa.ForeignKey("farms.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("crop_id", sa.String(20), sa.ForeignKey("crops.id"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("farm_crops")
    op.drop_table("farms")
