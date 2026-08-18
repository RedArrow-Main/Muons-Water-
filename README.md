# FURROWCAST

County-level planting-window and water-budget advisories for New York farmers — delivered by SMS, explained on a web dashboard.

> The farmer gets a 6:30am text with the 3 numbers that matter today; the web shows the math behind them. Value before friction; the phone number is the identity.

**Scope (v1):** 9 crops (corn, soy, alfalfa, cover, cotton, sorghum, potatoes, peanuts, sunflower) × New York (62 counties). SMS is the alarm clock; the web is the planning desk.

## Stack

- **Backend:** Python 3.12 · FastAPI · SQLAlchemy 2 · Pydantic v2 · Alembic
- **Database:** PostgreSQL 16 + PostGIS (local: docker-compose)
- **Frontend:** Next.js 15 · TypeScript · Tailwind (frontend only — no API routes)
- **SMS:** Twilio (only through `app/delivery/sender.py`)
- **Auth:** Email + password (Argon2id). Dev bypass: `FURROWCAST_DEV_PUBLIC=1`
- **Cron:** GitHub Actions scheduled workflow + local `scripts/nightly.sh`

## Quickstart

Prereqs: Docker, Python 3.12, Node 18+.

```bash
# 1. Database up
docker compose up -d db

# 2. Backend venv + deps
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. Migrate + seed
.venv/bin/alembic upgrade head
.venv/bin/python -m app.db.seed

# 4. Run backend
DATABASE_URL="postgresql+psycopg2://user:password@127.0.0.1:5432/furrowcast" \
  .venv/bin/uvicorn app.main:app --reload --port 8000

# 5. Run frontend (separate terminal)
cd ../web
npm install
npm run dev        # http://localhost:3000
```

Or use the all-in-one launcher: `./start.sh` (starts DB, backend, frontend, picks free ports).

## Nightly pipeline

Runs automatically (GitHub Actions cron `0 5 * * *` UTC, or local crontab via `scripts/nightly.sh`):

1. NWS forecast + Open-Meteo forecast/history + USDM drought for all 62 NY counties
2. Soil spin-up (field_cells + daily_records)
3. Advisory regeneration
4. Optional SMS send (`--sms`)
5. Every run is logged to `ingest_runs` — surfaced on the dashboard as **"Data as of \<date\>"**

On-demand trigger: `POST /api/admin/refresh` (auth-protected). Manual run: `make nightly DATE=2026-08-17`.

## Make targets

| Target | Purpose |
|---|---|
| `make dev` | DB + backend (reload) |
| `make test` | pytest suite |
| `make lint` | ruff check |
| `make db-reset` | drop/recreate DB + migrate + seed |
| `make migrate` | Alembic upgrade |
| `make seed` | seed DB |
| `make ingest DATE=2026-08-01` | full ingest for a date |
| `make ingest-range FROM=2026-08-01 TO=2026-08-17` | historical backfill |
| `make nightly DATE=2026-08-17` | nightly pipeline (no SMS) |
| `make nightly-sms DATE=2026-08-17` | nightly pipeline + SMS |
| `make sms FIPS=36037 PHONE=+15551234567` | dry-run SMS for a county |

## Tests

Every agronomy function has a unit test with hand-computed expected values (the worked examples in `docs/SPEC.md`); every API endpoint has a contract test matching `docs/API.md`.

```bash
make test    # backend pytest
cd web && npx tsc --noEmit   # frontend types
```

## Repo layout

```
backend/app/{ingest,engine,advisor,delivery,auth,api,db,farm,dashboard,sms}
web/src/{app,components,lib}
docs/SPEC.md · SCHEMA.sql · API.md · DECISIONS.md · sprints/
scripts/nightly.sh
.github/workflows/{ci.yml,nightly-ingest.yml}
```

## Docs (source of truth)

- **`docs/SPEC.md`** — product spec, authoritative agronomy formulas with worked examples
- **`docs/SCHEMA.sql`** — database schema
- **`docs/API.md`** — API contracts
- **`docs/DECISIONS.md`** — architecture decisions (D-xxx)

## Key formulas

```
GDD_day      = max(0, (tmax + tmin)/2 − base_temp)      # base: corn/soy 50°F, wheat 32°F
ETc          = Kc × ET0                                 # Kc from FAO-56
SW(t+1)      = min(AW, SW(t) + rain + irr − ETc)        # AW = root_depth_in × awc
IRRIGATE     when depletion = 1 − SW/AW ≥ crop.mad      # refill to 0.9 × AW
Window close = first_frost_50pct − maturity_days        # band from frost_10/90
```
