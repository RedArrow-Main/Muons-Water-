"""m7_farm_planting_date — track planting date per crop on a farm."""
import sqlalchemy as sa

from alembic import op

revision = "m7_farm_planting_date"
down_revision = "m6_add_farms"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "farm_crops",
        sa.Column("planting_date", sa.String(10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("farm_crops", "planting_date")