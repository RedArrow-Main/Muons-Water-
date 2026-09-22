.PHONY: help dev test test-db lint db-up db-reset seed migrate ingest ingest-range counties sms

DB_URL=postgresql+psycopg2://user:password@127.0.0.1:5432/furrowcast
TEST_DB_URL=postgresql+psycopg2://user:password@127.0.0.1:5432/furrowcast_test

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev:  ## Start development environment
	docker compose up -d
	cd backend && DATABASE_URL="$(DB_URL)" .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test-db:  ## Create + migrate + bootstrap the test DB (idempotent)
	@docker compose up -d db >/dev/null 2>&1
	@until docker compose exec -T db pg_isready -U user -d furrowcast >/dev/null 2>&1; do sleep 1; done
	@docker compose exec -T db psql -U user -d postgres -tAc \
		"SELECT 1 FROM pg_database WHERE datname='furrowcast_test'" | grep -q 1 || \
		docker compose exec -T db psql -U user -d postgres -c "CREATE DATABASE furrowcast_test"
	@docker compose exec -T db psql -U user -d furrowcast_test \
		-c "CREATE EXTENSION IF NOT EXISTS postgis" >/dev/null
	@cd backend && DATABASE_URL="$(TEST_DB_URL)" .venv/bin/alembic upgrade head 2>&1 | tail -1
	@cd backend && DATABASE_URL="$(TEST_DB_URL)" .venv/bin/python -m app.db.bootstrap

test: test-db  ## Run tests (uses separate test DB by default)
	cd backend && DATABASE_URL="$(TEST_DB_URL)" .venv/bin/python -m pytest -v

lint:  ## Run linter
	cd backend && .venv/bin/ruff check .

db-up:  ## Start DB and print status
	@docker compose up -d db 2>/dev/null
	@until docker compose exec -T db pg_isready -U user -d furrowcast -h 127.0.0.1 2>/dev/null; do sleep 1; done
	@echo "✓ Database ready on localhost:5432"

db-reset:  ## Drop and recreate DB, run migrations + seed
	docker compose down -v
	docker compose up -d db
	@echo "Waiting for DB to be ready..."
	@sleep 5
	@until docker compose exec -T db pg_isready -U user -d furrowcast -h 127.0.0.1 2>/dev/null; do sleep 2; done
	@echo "DB is ready."
	cd backend && DATABASE_URL="$(DB_URL)" .venv/bin/alembic upgrade head
	cd backend && DATABASE_URL="$(DB_URL)" .venv/bin/python -m app.db.seed
	@echo "db-reset complete."

migrate:  ## Run Alembic migrations
	cd backend && DATABASE_URL="$(DB_URL)" .venv/bin/alembic upgrade head

seed:  ## Seed the database
	cd backend && DATABASE_URL="$(DB_URL)" .venv/bin/python -m app.db.seed

counties:  ## Load all US counties (~3,200)
	cd backend && DATABASE_URL="$(DB_URL)" .venv/bin/python -c "from sqlalchemy.orm import Session; from app.db.connection import engine; from app.ingest.county_loader import load_counties; s=Session(engine); print(f'Loaded {load_counties(s)} counties')"

ingest:  ## Run full ingest for DATE (e.g. make ingest DATE=2026-08-01)
	cd backend && DATABASE_URL="$(DB_URL)" .venv/bin/python -m app.ingest.run --date $(DATE)

ingest-range:  ## Backfill historical data from FROM to TO
	cd backend && DATABASE_URL="$(DB_URL)" .venv/bin/python -m app.ingest.run --from $(FROM) --to $(TO)

ingest-source:  ## Run a single connector (e.g. make ingest-source SOURCE=noaa_nws DATE=2026-08-01)
	cd backend && DATABASE_URL="$(DB_URL)" .venv/bin/python -m app.ingest.run --date $(DATE) --source $(SOURCE)

nightly:  ## Run full nightly pipeline (e.g. make nightly DATE=2026-08-02)
	cd backend && DATABASE_URL="$(DB_URL)" .venv/bin/python -m app.nightly --date $(DATE)

nightly-sms:  ## Run nightly pipeline + send SMS advisories
	cd backend && DATABASE_URL="$(DB_URL)" .venv/bin/python -m app.nightly --date $(DATE) --sms

sms:  ## Send dry-run SMS advisory for a county (e.g. make sms FIPS=31027 PHONE=+15551234567)
	cd backend && DATABASE_URL="$(DB_URL)" .venv/bin/python -c "from sqlalchemy.orm import Session; from app.db.connection import engine; from app.sms.gateway import send_sms, TwilioConfig; s=Session(engine); cfg=TwilioConfig(dry_run=True); ok=send_sms(s,'$(PHONE)','Advisory for county $(FIPS) — check dashboard for details',county_fips='$(FIPS)',config=cfg); print('SMS sent (dry_run)' if ok else 'SMS blocked (rate limit or error)')"
