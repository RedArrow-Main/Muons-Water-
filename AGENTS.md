# FURROWCAST — REPO RULES
<!-- DOC VERSION: v1.2 | LAST UPDATED: 2026-08-15 | OWNER: principal -->
Read this file at the start of EVERY session. Obey it always.

## RULE 0 — THE DOCS ARE THE SOURCE OF TRUTH (highest priority)
SPEC.md, SCHEMA.sql, and API.md define the product. The code must match them.
- If any task changes behavior, schema, an API contract, a formula, or a decision,
  you MUST update the matching doc IN THE SAME COMMIT.
- Bump that doc's version header and add a one-line changelog entry.
- A code change with no doc update is an INCOMPLETE task. Do not mark it done.
- If a doc and the code ever disagree and you did not just change them, STOP and
  report the drift to me. Do not silently "fix" either side.

## What we are building
FurrowCast delivers county-level planting-window + water-budget advisories to
New York farmers via SMS, with a Next.js dashboard. v1: 9 crops
(corn, soy, alfalfa, cover, cotton, sorghum, potatoes, peanuts, sunflower)
× New York (62 counties). SMS is the alarm clock; the web is the planning desk.

## Stack — DECIDED. Do not propose alternatives.
- Backend: Python 3.12 · FastAPI · SQLAlchemy 2 · Pydantic v2 · Alembic
- Database: PostgreSQL 16 + PostGIS (local: docker-compose)
- Frontend: Next.js 15 · TypeScript · Tailwind (frontend ONLY — no API routes here)
- SMS: Twilio, ONLY through app/delivery/sender.py (MessageSender interface)
- Auth: Email + password (Argon2id). M6 frontend login uses email/password —
  OTP/WebAuthn deferred (see DECISIONS.md D-007). Dev bypass: set
  FURROWCAST_DEV_PUBLIC=1 to make protected routes public for local frontend
  work before the login UI exists.
- Payments: Stripe Checkout + webhooks (webhooks hit the BACKEND, not Next.js)
- LLM: may PHRASE templated text. It may NEVER compute a number.
- Cron: GitHub Actions scheduled workflow
- Tests: pytest (backend) · Playwright (web smoke)

## Non-negotiables
1. No new dependency without asking me first, in writing, with the reason.
2. No secrets in code. Env vars only. Never log a phone number or OTP.
3. Every agronomy function has a unit test with a HAND-COMPUTED expected value
   (the worked examples live in SPEC.md — use those exact numbers).
4. Every API endpoint has a contract test matching API.md.
5. Migrations via Alembic only. Never hand-edit production SQL.
6. Modules talk ONLY via API routes and DB tables. M4 never imports M2 internals;
   M2 never knows Twilio exists.
7. Commit format: "M1-1.3: USDM connector + tests". One task per commit.
8. Change only files belonging to the current task. No drive-by refactors.

## Definition of done (every task — all six, or it's not done)
1. Tests written first, seen failing, then passing
2. `make lint` clean
3. The task's demo command runs and its output is shown to me
4. Relevant docs (SPEC/SCHEMA/API) updated + version bumped   ← RULE 0
5. DECISIONS.md touched only if a decision actually changed
6. Nothing else modified

## Key formulas (authoritative — tests must match SPEC.md worked examples)
- GDD_day = max(0, (tmax+tmin)/2 − base_temp)      base: corn/soy 50°F, wheat 32°F
- ETc = Kc × ET0                                    Kc from crop_coefficients (FAO-56)
- SW(t+1) = min(AW, SW(t)+rain+irr−ETc)             AW = root_depth_in × awc
- IRRIGATE WHEN depletion = 1−SW/AW ≥ crop.mad      refill to 0.9 × AW
- Window close = first_frost_50pct − maturity_days  band from frost_10/90 dates
- Stage-weighted deficit = Σ(daily_deficit × stage_weight)
  stages: vegetative(0.0–0.50,w=0.4), pollination(0.50–0.62,w=1.5),
          grain-fill(0.62–0.90,w=1.0), maturity(0.90–1.00,w=0.3)

## Repo layout
backend/app/{ingest,engine,advisor,delivery,auth,api,db,farm}
web/src/{app,components,lib}  (Next.js 14 · TypeScript · Tailwind — frontend only)
docs/: SPEC.md · SCHEMA.sql · API.md · DECISIONS.md · sprints/

## When unsure
Stop and ask. A wrong assumption costs a day; a question costs a minute.

## Changelog
- v1.0 (2026-07-30): Initial foundation issued.
- v1.1 (2026-08-06): M6 — Next.js dashboard, farm model API, Alembic m6_add_farms migration.
- v1.2 (2026-08-15): Scope pivot to NEW YORK ONLY (NE/IA/KS retired as primary target);
  auth updated to email/password; FURROWCAST_DEV_PUBLIC=1 dev bypass documented.
