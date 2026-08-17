"""initial schema — all tables

Revision ID: m1_data_pipeline
Revises: 
Create Date: 2026-08-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'm1_data_pipeline'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # counties
    op.create_table(
        'counties',
        sa.Column('fips', sa.String(5), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('state', sa.String(2), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('frost_kill_10', sa.Integer(), nullable=True),
        sa.Column('frost_kill_50', sa.Integer(), nullable=True),
        sa.Column('frost_kill_90', sa.Integer(), nullable=True),
        sa.Column('grid_id', sa.String(10), nullable=True),
        sa.Column('grid_x', sa.Integer(), nullable=True),
        sa.Column('grid_y', sa.Integer(), nullable=True),
    )

    # crops
    op.create_table(
        'crops',
        sa.Column('id', sa.String(20), primary_key=True),
        sa.Column('base_temp_f', sa.Float(), nullable=False),
        sa.Column('gdd_total', sa.Integer(), nullable=False),
        sa.Column('root_depth_in', sa.Float(), nullable=False),
        sa.Column('mad_fraction', sa.Float(), nullable=False),
        sa.Column('kc_initial', sa.Float(), nullable=False),
        sa.Column('kc_mid', sa.Float(), nullable=False),
        sa.Column('kc_end', sa.Float(), nullable=False),
        sa.Column('stage_days', sa.String(30), nullable=False),
    )

    # soils
    op.create_table(
        'soils',
        sa.Column('county_fips', sa.String(5), sa.ForeignKey('counties.fips'), primary_key=True),
        sa.Column('soil_type', sa.String(50), nullable=False),
        sa.Column('awc', sa.Float(), nullable=False),
    )

    # daily_forecast
    op.create_table(
        'daily_forecast',
        sa.Column('county_fips', sa.String(5), sa.ForeignKey('counties.fips'), primary_key=True),
        sa.Column('forecast_date', sa.String(10), primary_key=True),
        sa.Column('tmax_f', sa.Float(), nullable=True),
        sa.Column('tmin_f', sa.Float(), nullable=True),
        sa.Column('precip_in', sa.Float(), nullable=True),
        sa.Column('et0_in', sa.Float(), nullable=True),
        sa.Column('source', sa.String(20), nullable=False, server_default='nws'),
    )

    # daily_historical
    op.create_table(
        'daily_historical',
        sa.Column('county_fips', sa.String(5), sa.ForeignKey('counties.fips'), primary_key=True),
        sa.Column('obs_date', sa.String(10), primary_key=True),
        sa.Column('tmax_f', sa.Float(), nullable=True),
        sa.Column('tmin_f', sa.Float(), nullable=True),
        sa.Column('precip_in', sa.Float(), nullable=True),
        sa.Column('et0_in', sa.Float(), nullable=True),
    )

    # drought_status
    op.create_table(
        'drought_status',
        sa.Column('county_fips', sa.String(5), sa.ForeignKey('counties.fips'), primary_key=True),
        sa.Column('week_ending', sa.String(10), primary_key=True),
        sa.Column('usdm_level', sa.String(4), nullable=False),
    )

    # ingest_runs
    op.create_table(
        'ingest_runs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('source', sa.String(30), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('rows_upserted', sa.Integer(), server_default='0'),
        sa.Column('status', sa.String(10), nullable=False, server_default='running'),
        sa.Column('error_message', sa.Text(), nullable=True),
    )

    # field_cells
    op.create_table(
        'field_cells',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('county_fips', sa.String(5), sa.ForeignKey('counties.fips'), nullable=False),
        sa.Column('crop_id', sa.String(20), sa.ForeignKey('crops.id'), nullable=False),
        sa.Column('row', sa.Integer(), nullable=False),
        sa.Column('col', sa.Integer(), nullable=False),
        sa.Column('soil_type', sa.String(50), nullable=False),
        sa.Column('awc', sa.Float(), nullable=False),
    )

    # daily_records
    op.create_table(
        'daily_records',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('cell_id', sa.Integer(), sa.ForeignKey('field_cells.id'), nullable=False),
        sa.Column('record_date', sa.String(10), nullable=False),
        sa.Column('et0_mm', sa.Float(), nullable=True),
        sa.Column('rainfall_mm', sa.Float(), nullable=True),
        sa.Column('irrigation_mm', sa.Float(), nullable=True),
        sa.Column('soil_moisture_pct', sa.Float(), nullable=True),
        sa.Column('gdd', sa.Float(), nullable=True),
        sa.Column('growth_stage', sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('daily_records')
    op.drop_table('field_cells')
    op.drop_table('ingest_runs')
    op.drop_table('drought_status')
    op.drop_table('daily_historical')
    op.drop_table('daily_forecast')
    op.drop_table('soils')
    op.drop_table('crops')
    op.drop_table('counties')
