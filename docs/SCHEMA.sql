-- SCHEMA.sql — furrowcast v1.6 (M6: Farmer Dashboard + Farm Model)
-- Source of truth for the database schema.
-- SQLAlchemy models in app/db/models.py must match this file exactly.

CREATE EXTENSION IF NOT EXISTS postgis;

-- ─────────────────────────────────────────────────────────────────────
-- counties — all 359 counties across NY, NE, IA, KS
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE counties (
    fips            VARCHAR(5)   PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    state           VARCHAR(2)   NOT NULL,     -- NY, NE, IA, KS
    latitude        DOUBLE PRECISION NOT NULL,
    longitude       DOUBLE PRECISION NOT NULL,
    frost_kill_10   INTEGER,                   -- Julian day, 10th-percentile first frost
    frost_kill_50   INTEGER,                   -- Julian day, 50th-percentile first frost
    frost_kill_90   INTEGER,                   -- Julian day, 90th-percentile first frost
    grid_id         VARCHAR(10),               -- NWS grid office (e.g. OAX)
    grid_x          INTEGER,                   -- NWS grid X coordinate
    grid_y          INTEGER                    -- NWS grid Y coordinate
);

-- ─────────────────────────────────────────────────────────────────────
-- crops — FAO-56 coefficients + agronomy parameters
-- v1.5: expanded to 9 crops (corn, soy, alfalfa, cover + cotton, sorghum,
--        potatoes, peanuts, sunflower). New crops are FAO-56 reference
--        values pending agronomist sign-off.
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE crops (
    id              VARCHAR(20)  PRIMARY KEY,   -- corn, soy, alfalfa, cover
    base_temp_f     DOUBLE PRECISION NOT NULL,  -- base temperature for GDD
    gdd_total       INTEGER      NOT NULL,      -- GDD to maturity
    root_depth_in   DOUBLE PRECISION NOT NULL,  -- effective root depth (inches)
    mad_fraction    DOUBLE PRECISION NOT NULL,  -- management-allowed depletion (fraction)
    kc_initial      DOUBLE PRECISION NOT NULL,  -- Kc at initial stage
    kc_mid          DOUBLE PRECISION NOT NULL,  -- Kc at mid-season
    kc_end          DOUBLE PRECISION NOT NULL,  -- Kc at end season
    stage_days      VARCHAR(30)  NOT NULL       -- CSV: initial,development,mid,late (days)
);

-- ─────────────────────────────────────────────────────────────────────
-- soils — dominant soil type per county (SSURGO simplification)
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE soils (
    county_fips     VARCHAR(5)   NOT NULL REFERENCES counties(fips),
    soil_type       VARCHAR(50)  NOT NULL,
    awc             DOUBLE PRECISION NOT NULL,  -- available water capacity (in/in)
    PRIMARY KEY (county_fips)
);

-- ─────────────────────────────────────────────────────────────────────
-- daily_forecast — 7-day forecast per county (NWS primary, Open-Meteo ET0)
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE daily_forecast (
    county_fips     VARCHAR(5)   NOT NULL REFERENCES counties(fips),
    forecast_date   VARCHAR(10)  NOT NULL,       -- YYYY-MM-DD
    tmax_f          DOUBLE PRECISION,
    tmin_f          DOUBLE PRECISION,
    precip_in       DOUBLE PRECISION,
    et0_in          DOUBLE PRECISION,            -- from Open-Meteo forecast
    source          VARCHAR(20)  NOT NULL DEFAULT 'nws',  -- nws or open-meteo
    PRIMARY KEY (county_fips, forecast_date)
);

-- ─────────────────────────────────────────────────────────────────────
-- daily_historical — historical daily data per county (Open-Meteo archive)
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE daily_historical (
    county_fips     VARCHAR(5)   NOT NULL REFERENCES counties(fips),
    obs_date        VARCHAR(10)  NOT NULL,       -- YYYY-MM-DD
    tmax_f          DOUBLE PRECISION,
    tmin_f          DOUBLE PRECISION,
    precip_in       DOUBLE PRECISION,
    et0_in          DOUBLE PRECISION,            -- FAO-56 reference ET
    PRIMARY KEY (county_fips, obs_date)
);

-- ─────────────────────────────────────────────────────────────────────
-- drought_status — weekly USDM drought classification per county
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE drought_status (
    county_fips     VARCHAR(5)   NOT NULL REFERENCES counties(fips),
    week_ending     VARCHAR(10)  NOT NULL,       -- YYYY-MM-DD (Tuesday ending the USDM week)
    usdm_level      VARCHAR(4)   NOT NULL,       -- NONE, D0, D1, D2, D3, D4
    PRIMARY KEY (county_fips, week_ending)
);

-- ─────────────────────────────────────────────────────────────────────
-- ingest_runs — pipeline execution log (every connector logs here)
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE ingest_runs (
    id              SERIAL       PRIMARY KEY,
    source          VARCHAR(30)  NOT NULL,       -- county_loader, noaa_nws, open_meteo, etc.
    started_at      TIMESTAMP    NOT NULL DEFAULT now(),
    finished_at     TIMESTAMP,
    rows_upserted   INTEGER      DEFAULT 0,
    status          VARCHAR(10)  NOT NULL DEFAULT 'running',  -- running, success, error
    error_message   TEXT
);

-- ─────────────────────────────────────────────────────────────────────
-- field_cells — individual grid cell within a county+crop combination
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE field_cells (
    id              SERIAL       PRIMARY KEY,
    county_fips     VARCHAR(5)   NOT NULL REFERENCES counties(fips),
    crop_id         VARCHAR(20)  NOT NULL REFERENCES crops(id),
    row             INTEGER      NOT NULL,
    col             INTEGER      NOT NULL,
    soil_type       VARCHAR(50)  NOT NULL,
    awc             DOUBLE PRECISION NOT NULL
);

-- ─────────────────────────────────────────────────────────────────────
-- daily_records — per-cell daily observation / recommendation
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE daily_records (
    id              SERIAL       PRIMARY KEY,
    cell_id         INTEGER      NOT NULL REFERENCES field_cells(id),
    record_date     VARCHAR(10)  NOT NULL,       -- YYYY-MM-DD
    et0_mm          DOUBLE PRECISION,
    rainfall_mm     DOUBLE PRECISION,
    irrigation_mm   DOUBLE PRECISION,
    soil_moisture_pct DOUBLE PRECISION,
    gdd             DOUBLE PRECISION,
    growth_stage    VARCHAR(20)
);

-- ─────────────────────────────────────────────────────────────────────
-- outbox — SMS delivery log
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS outbox (
    id              SERIAL       PRIMARY KEY,
    county_fips     CHAR(5)      NOT NULL,
    phone_to        VARCHAR(20)  NOT NULL,
    body            TEXT         NOT NULL,
    status          VARCHAR(20)  NOT NULL DEFAULT 'sent',
    twilio_sid      VARCHAR(64),
    error_msg       TEXT,
    sent_at         TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_outbox_fips ON outbox(county_fips);
CREATE INDEX IF NOT EXISTS idx_outbox_sent ON outbox(sent_at);

-- ─────────────────────────────────────────────────────────────────────
-- users — authentication (email + password, optional phone)
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              SERIAL       PRIMARY KEY,
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    phone           VARCHAR(20),
    phone_verified  BOOLEAN      NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- ─────────────────────────────────────────────────────────────────────
-- advisories — M3 generated advisory with hash chain integrity
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS advisories (
    id              SERIAL       PRIMARY KEY,
    county_fips     VARCHAR(5)   NOT NULL,
    crop_id         VARCHAR(20)  NOT NULL,
    type            VARCHAR(30)  NOT NULL DEFAULT 'water_budget',
    severity        VARCHAR(10)  NOT NULL,       -- info, watch, action
    headline        VARCHAR(200) NOT NULL,
    body            TEXT         NOT NULL,
    source_data     JSONB,                       -- audit trail
    hash            VARCHAR(64)  NOT NULL,       -- SHA-256
    prev_hash       VARCHAR(64),                 -- chain link
    status          VARCHAR(20)  NOT NULL DEFAULT 'active',
    generated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_advisories_fips_date ON advisories(county_fips, generated_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_advisories_hash ON advisories(hash);
CREATE INDEX IF NOT EXISTS idx_advisories_status ON advisories(status);

-- ─────────────────────────────────────────────────────────────────────
-- farms — one per user per county
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE farms (
    id              SERIAL       PRIMARY KEY,
    user_id         INTEGER      NOT NULL REFERENCES users(id),
    county_fips     VARCHAR(5)   NOT NULL REFERENCES counties(fips),
    name            VARCHAR(200) NOT NULL,
    acres           NUMERIC,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE(user_id, county_fips)
);

-- ─────────────────────────────────────────────────────────────────────
-- farm_crops — which crops a farm grows (M:N)
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE farm_crops (
    farm_id         INTEGER      NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
    crop_id         VARCHAR(20)  NOT NULL REFERENCES crops(id),
    PRIMARY KEY (farm_id, crop_id)
);
