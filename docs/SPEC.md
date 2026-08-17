# FURROWCAST — PRODUCT SPECIFICATION
<!-- DOC VERSION: v1.9 | LAST UPDATED: 2026-08-17 | OWNER: principal -->

## 1 · Product
County-level planting-window and water-budget advisories for farmers across New York (62 counties),
delivered by SMS with a web dashboard for planning. The farmer gets a 6:30am
text with the 3 numbers that matter today; the web shows the math behind them.
Value before friction; the phone number is the identity.

## 2 · Users
- Farmer — email/password login, dashboard + SMS
- Agronomist — reviews/approves every advisory before send (review queue)
- Admin — ops overview, YubiKey-gated
- Co-op — tenant, roster import, white-label (v1.5)

## 3 · Data sources (all free)
| Source | Provides | Notes |
| NOAA NWS API | 7-day grid forecast | primary; points→gridpoints |
| Open-Meteo | historical 1995–2025 + forecast fallback | archive for GDD/SPI |
| USDM API (drought.gov) | weekly county D0–D4 | authoritative drought |
| SSURGO | soil AWC + texture | county-dominant in v1 |
| NRCS SCAN | measured soil moisture | calibration ground-truth |
| FAO-56 | crop coefficient (Kc) tables | public agronomy standard |

## 4 · Formulas — with worked examples (AUTHORITATIVE)
Tests MUST reproduce these exact numbers.

GDD:  corn, tmax=89, tmin=71 → avg=80 → GDD = 80−50 = 30
ETc:  corn mid-season Kc=1.15, ET0=0.28 → ETc = 1.15×0.28 = 0.322 in/day
AW:   corn root 36in × AWC 0.20 → AW = 7.2 in
Balance: start SW=4.32 (60% of 7.2), depletion=0.40
  Day1 (no rain): 4.32−0.322=4.00 → depletion=0.445 (<0.50, hold)
  Day2: 4.00−0.322=3.68 → depletion=0.489 (hold)
  Day3: 3.68−0.322=3.36 → depletion=0.533 (≥0.50 → IRRIGATE)
  Refill to 0.9×7.2=6.48 → apply 6.48−3.36 = 3.12 in
Window: county frost_50=Oct 12, corn ~120 days → latest safe plant = Jun 14.
  Confidence band from frost_10 (Oct 2) and frost_90 (Oct 22).

### Stage-weighted deficit (v1.1)

Stage weights are defined by GDD fraction of the season (cumulative_gdd / gdd_to_maturity):

| Stage          | GDD fraction | Weight | Rationale |
|----------------|-------------|--------|-----------|
| Vegetative     | 0.00–0.50   | 0.4    | Low sensitivity before tassel |
| Pollination    | 0.50–0.62   | 1.5    | Critical — pollination/grain set |
| Grain fill     | 0.62–0.90   | 1.0    | Moderate — kernel weight |
| Maturity       | 0.90–1.00   | 0.3    | Low — grain dry-down |

Corn gdd_to_maturity = 2700. Pollination window: 0.50×2700 = 1350 GDD → 0.62×2700 = 1674 GDD.

Worked example (corn, start_sw_frac=0.0, 3 days, all in vegetative stage):
  GDD each day = 30, cumulative after 3 days = 90 → gdd_frac = 90/2700 = 0.033
  ETc = 1.15 × 0.28 = 0.322 in/day
  SW starts at 0 → daily deficit = 0.322 in each day
  cumulative_deficit = 3 × 0.322 = 0.966 in
  stage_weighted_deficit = 3 × 0.322 × 0.4 = 0.3864 in  (weight 0.4 for vegetative)

Worked example (45 vegetative + 1 pollination day, start_sw_frac=0.0):
  Vegetative: 44 days × 0.322 × 0.4 = 5.6672
  Pollination: 2 days × 0.322 × 1.5 = 0.966
  stage_weighted_deficit = 6.6332 in

## 5 · Modules
8 modules / 48 submodules — see the Bill of Modules (FC-BM-001).
M1 Ingestion · M2 Engine · M3 Advisor · M4 Delivery · M5 Identity ·
M6 Grower App · M7 Back Office · M8 Commerce.

### M3 — Advisory Composition (v1.2)

M3 builds on M2's engine output. M2 decides IRRIGATE/HOLD; M3 adds SCHEDULE
and produces the final advisory with hash chain integrity.

**Decision logic (build_narrative):**
```
if depletion >= mad:
    decision = "IRRIGATE"
elif depletion >= (mad - SCHEDULE_LOOKAHEAD_MAD) and forecast_rain_7d < SCHEDULE_MIN_RAIN_IN:
    decision = "SCHEDULE"
else:
    decision = "HOLD"
```

Tunable constants:
- `SCHEDULE_LOOKAHEAD_MAD = 0.10` — depletion must be within 0.10 of MAD
- `SCHEDULE_MIN_RAIN_IN = 0.5` — suppress SCHEDULE if forecast rain ≥ 0.5 in

**Severity mapping:**
| Decision  | Severity | Color  |
|-----------|----------|--------|
| HOLD      | info     | green  |
| SCHEDULE  | watch    | yellow |
| IRRIGATE  | action   | red    |

**Hash chain:**
Each advisory is SHA-256 hashed with its predecessor's hash, forming a
tamper-evident chain per county. Any mutation breaks all downstream hashes.

```hash = sha256(prev_hash + canonical({county_fips, crop_id, date, decision, severity, headline, body}))```

**Nightly cron flow** (`backend/app/nightly.py`, run by GitHub Actions cron
`0 5 * * *` UTC or local `scripts/nightly.sh`):
1. Span all NY counties (62)
2. Ingestion: NWS forecast, Open-Meteo forecast + 14-day history, USDM drought polygons
3. Soil spin-up (`field_cells` + `daily_records`) from fetched history
4. `generate_all(date)` — produces advisories for all counties with data
5. Store to `advisories` table
6. Optionally send SMS (`--sms` / `FURROWCAST_NIGHTLY_SMS=1`)
7. Log the run to `ingest_runs` (source `nightly_pipeline`, status, row counts)
   — the dashboard surfaces this as "Data as of <date>" and `/api/admin/refresh`
   triggers the same pipeline on demand (auth-protected).

## 6 · Security (summary — full: Addendum 06-2)
Login: email + password (Argon2id) for the M6 frontend — OTP/WebAuthn deferred
(see DECISIONS.md D-007). Local dev bypass: FURROWCAST_DEV_PUBLIC=1 makes
protected routes public.
Sessions: 15-min access, 30-day rotating refresh, device-bound, revocable.
Audit: advisories hash-chained (SHA-256), daily Merkle root anchored to Bitcoin.
PII: phone encrypted at rest, never logged. Admin: YubiKey only.

## 7 · SMS rules
3 lines max per digest · quiet hours respected · STOP honored in one cycle ·
TCPA consent captured at signup · 10DLC registered before beta (2–4 wk lead).

## 8 · Out of scope (v1)
No native app (gated Jan 2027) · no field polygons (v2) · no MMS · no blog ·
no standalone chatbot · no payments at signup (free tier first).

## Changelog
- v1.9 (2026-08-17): Nightly pipeline fully automated — `app/nightly.py` rewritten as NY-scoped pipeline (NWS + Open-Meteo + USDM + soil spin-up + advisory regeneration in one run), logging to `ingest_runs` (`nightly_pipeline`). New `POST /api/admin/refresh` (auth-protected on-demand trigger), `data_as_of` on advisory responses and `last_pipeline_at`/status on `/api/stats`; dashboard shows "Data as of <date>". Local cron runner `scripts/nightly.sh`; GitHub Actions workflow bumped to Python 3.12.
- v1.8 (2026-08-17): Dashboard demo fixes — `daily_historical` re-backfilled so all 62 NY counties have real last-7-day rain/ET; `history.last_7d_*` are `null` (not `0.0`) when a county has no backfill, and the dashboard shows "Setting up data for this county". Desktop grid rebalanced (Weather History card no longer leaves dead space). DB restored to NY-only scope (62 NY + legacy seed rows).
- v1.7 (2026-08-15): NEW YORK is now the SOLE product scope — NE/IA/KS retired as primary target. M6 Next.js dashboard complete (email/password login + logout, Drought/History/Soil cards). `daily_historical` backfilled for all 62 NY counties with real 7-day rain/ET.
- v1.6 (2026-08-15): Scope expanded to include New York (NY) alongside NE/IA/KS. `INSCOPE_STATES` in `app/advisor/service.py`, `backfill_spinup.py`, `rerun_spinup.py` now include NY; `run.py` gained a `--state` filter to scope connectors. Web dashboard pivoted to NY-only county selector (default Genesee, 36037).
- v1.5 (2026-08-06): M6 — Farm model API (POST/GET/DELETE /api/farm), Alembic migration m6_add_farms, farm_crops M:N table. Next.js dashboard with Tailwind design system, auth (email+password), onboarding, and live advisory display.
- v1.4 (2026-08-06): Expanded crop library to 9 crops — added cotton, sorghum, potatoes, peanuts, sunflower (FAO-56 reference values, pending agronomist sign-off).
- v1.3 (2026-08-06): API contract: /api/advisory/{fips} always returns on-the-fly dashboard format. M3 stored advisories are audit-only.
- v1.2 (2026-08-04): Added M3 advisory composition — SCHEDULE decision, severity mapping, hash chain.
- v1.1 (2026-08-03): Added stage-weighted deficit formula with GDD-based growth-stage bands.
- v1.0 (2026-07-30): Initial spec issued with worked formula examples.
