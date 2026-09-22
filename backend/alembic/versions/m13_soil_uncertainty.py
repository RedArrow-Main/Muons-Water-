"""Track uncertainty from unknown soil-water initialization."""
import sqlalchemy as sa

from alembic import op

revision = 'm13_soil_uncertainty'
down_revision = 'm12_fao56_kc_mid'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('daily_records', sa.Column('soil_min_pct', sa.Float(), nullable=True))
    op.add_column('daily_records', sa.Column('soil_max_pct', sa.Float(), nullable=True))
    op.create_check_constraint('soil_range_valid', 'daily_records',
                               'soil_min_pct >= 0 AND soil_max_pct <= 100 AND soil_min_pct <= soil_max_pct')


def downgrade():
    op.drop_constraint('soil_range_valid', 'daily_records')
    op.drop_column('daily_records', 'soil_max_pct')
    op.drop_column('daily_records', 'soil_min_pct')
