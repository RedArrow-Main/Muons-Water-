"""SQLAlchemy models for the furrowcast schema."""
from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from .connection import Base


class County(Base):
    __tablename__ = "counties"

    fips = Column(String(5), primary_key=True)
    name = Column(String(100), nullable=False)
    state = Column(String(2), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    frost_kill_10 = Column(Integer)
    frost_kill_50 = Column(Integer)
    frost_kill_90 = Column(Integer)
    grid_id = Column(String(10))
    grid_x = Column(Integer)
    grid_y = Column(Integer)

    soil = relationship("Soil", back_populates="county", uselist=False)
    field_cells = relationship("FieldCell", back_populates="county")

    def __repr__(self) -> str:
        return f"<County {self.fips} {self.name}>"


class Crop(Base):
    __tablename__ = "crops"

    id = Column(String(20), primary_key=True)
    base_temp_f = Column(Float, nullable=False)
    gdd_total = Column(Integer, nullable=False)
    root_depth_in = Column(Float, nullable=False)
    mad_fraction = Column(Float, nullable=False)
    kc_initial = Column(Float, nullable=False)
    kc_mid = Column(Float, nullable=False)
    kc_end = Column(Float, nullable=False)
    stage_days = Column(String(30), nullable=False)

    def __repr__(self) -> str:
        return f"<Crop {self.id}>"


class Soil(Base):
    __tablename__ = "soils"

    county_fips = Column(
        String(5), ForeignKey("counties.fips"), primary_key=True
    )
    soil_type = Column(String(50), nullable=False)
    awc = Column(Float, nullable=False)

    county = relationship("County", back_populates="soil")

    def __repr__(self) -> str:
        return f"<Soil {self.county_fips} {self.soil_type}>"


class DailyForecast(Base):
    """7-day forecast per county (NWS primary, Open-Meteo ET0)."""
    __tablename__ = "daily_forecast"

    county_fips = Column(
        String(5), ForeignKey("counties.fips"), primary_key=True
    )
    forecast_date = Column(String(10), primary_key=True)  # YYYY-MM-DD
    tmax_f = Column(Float)
    tmin_f = Column(Float)
    precip_in = Column(Float)
    et0_in = Column(Float)
    source = Column(String(20), nullable=False, default="nws")

    county = relationship("County")

    def __repr__(self) -> str:
        return f"<DailyForecast {self.county_fips} {self.forecast_date}>"


class DailyHistorical(Base):
    """Historical daily data per county (Open-Meteo archive)."""
    __tablename__ = "daily_historical"

    county_fips = Column(
        String(5), ForeignKey("counties.fips"), primary_key=True
    )
    obs_date = Column(String(10), primary_key=True)  # YYYY-MM-DD
    tmax_f = Column(Float)
    tmin_f = Column(Float)
    precip_in = Column(Float)
    et0_in = Column(Float)

    county = relationship("County")

    def __repr__(self) -> str:
        return f"<DailyHistorical {self.county_fips} {self.obs_date}>"


class DroughtStatus(Base):
    """Weekly USDM drought classification per county."""
    __tablename__ = "drought_status"

    county_fips = Column(
        String(5), ForeignKey("counties.fips"), primary_key=True
    )
    week_ending = Column(String(10), primary_key=True)  # YYYY-MM-DD
    usdm_level = Column(String(4), nullable=False)  # NONE, D0–D4

    county = relationship("County")

    def __repr__(self) -> str:
        return f"<DroughtStatus {self.county_fips} {self.week_ending} {self.usdm_level}>"


class IngestRun(Base):
    """Pipeline execution log — every connector logs here."""
    __tablename__ = "ingest_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(30), nullable=False)
    started_at = Column(DateTime, nullable=False, server_default=func.now())
    finished_at = Column(DateTime)
    rows_upserted = Column(Integer, default=0)
    status = Column(String(10), nullable=False, default="running")
    error_message = Column(Text)

    def __repr__(self) -> str:
        return f"<IngestRun {self.source} {self.status}>"


class FieldCell(Base):
    """A grid cell within a field — holds daily irrigation state."""
    __tablename__ = "field_cells"

    id = Column(Integer, primary_key=True, autoincrement=True)
    county_fips = Column(
        String(5), ForeignKey("counties.fips"), nullable=False
    )
    crop_id = Column(
        String(20), ForeignKey("crops.id"), nullable=False
    )
    row = Column(Integer, nullable=False)
    col = Column(Integer, nullable=False)
    soil_type = Column(String(50), nullable=False)
    awc = Column(Float, nullable=False)

    county = relationship("County", back_populates="field_cells")
    crop = relationship("Crop")
    daily_records = relationship("DailyRecord", back_populates="cell")

    def __repr__(self) -> str:
        return f"<FieldCell {self.id} r{self.row}c{self.col}>"


class DailyRecord(Base):
    """Daily observation / recommendation for a field cell."""
    __tablename__ = "daily_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cell_id = Column(
        Integer, ForeignKey("field_cells.id"), nullable=False
    )
    record_date = Column(String(10), nullable=False)  # YYYY-MM-DD
    et0_mm = Column(Float, nullable=True)
    rainfall_mm = Column(Float, nullable=True)
    irrigation_mm = Column(Float, nullable=True)
    soil_moisture_pct = Column(Float, nullable=True)
    gdd = Column(Float, nullable=True)
    growth_stage = Column(String(20), nullable=True)

    cell = relationship("FieldCell", back_populates="daily_records")

    def __repr__(self) -> str:
        return f"<DailyRecord {self.cell_id} {self.record_date}>"


class Outbox(Base):
    """SMS delivery log — tracks every SMS sent."""
    __tablename__ = "outbox"

    id = Column(Integer, primary_key=True, autoincrement=True)
    county_fips = Column(String(5), nullable=False, index=True)
    phone_to = Column(String(20), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="sent")
    twilio_sid = Column(String(64), nullable=True)
    error_msg = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<Outbox {self.county_fips} {self.status}>"


class User(Base):
    """User account — email/password auth, optional phone for SMS."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    phone_verified = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class Advisory(Base):
    """Generated advisory with hash chain integrity (M3)."""
    __tablename__ = "advisories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    county_fips = Column(String(5), nullable=False, index=True)
    crop_id = Column(String(20), nullable=False)
    type = Column(String(30), nullable=False, default="water_budget")
    severity = Column(String(10), nullable=False)  # info, watch, action
    headline = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    source_data = Column(Text, nullable=True)  # JSON as text
    hash = Column(String(64), nullable=False, unique=True)
    prev_hash = Column(String(64), nullable=True)
    status = Column(String(20), nullable=False, default="active")
    generated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<Advisory {self.county_fips} {self.severity} {self.decision}>"
