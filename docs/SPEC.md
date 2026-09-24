# MUONS WATER — PRODUCT SPECIFICATION
<!-- DOC VERSION: v1.38 | LAST UPDATED: 2026-09-24 | OWNER: principal -->

## Changelog (newest first)
- v1.38 (2026-09-24): A county whose soil spin-up fails is marked `advice_uncertain`, so a transient ingest failure can no longer yield confident advice built on a history that was never rebuilt (D-017).
- v1.37 (2026-09-14): Dashboard starts in an explicit loading state and restores saved selections before fetching or persisting them, avoiding a false missing-data flash and default-selection requests; filling the returned planting date does not repeat a successful request.
- v1.36 (2026-09-14): Refine reference typography and spacing; compact header, crop artwork and controls for narrow embedded previews while preserving uncertainty messaging in the green advice card.
- v1.35 (2026-09-14): Overview follows the supplied photo-led reference with inline field controls, paired crop/advice cards, three metrics, growth/range cards and compact forecast/status panels; range graphics show actual bounds, and field checks link to the saved checklist.
- v1.34 (2026-09-12): Local API defaults match the browser hostname; launcher wires chosen ports and CORS, and connection failures show a retryable service error instead of missing-data text.
- v1.33 (2026-09-12): Ten-page workspace shares a responsive dark-green shell; analysis uses advisory APIs, journal/preferences/checklists persist locally, reports export available data with explicit missing-data states.
- v1.32 (2026-09-12): Visual dashboard adds clearly labelled crop artwork, switchable growth diagram, model-stage timeline, daily rain/use comparison, advice explanation and session-only field checklist.
- v1.31 (2026-09-12): Dashboard adds a rotatable schematic 3D growth view, soil-water and growth progress, and plain-language actions; uncertain advice suppresses irrigation doses.
- v1.29 (2026-09-09): Nightly spin-up preserves seasonal GDD before the 14-day window; requires complete history and replaces same-day estimates on rerun.
- v1.27 (2026-09-03): **`kc_mid` corrected for corn (1.15 → 1.20), soy
  (1.10 → 1.15) and alfalfa (1.05 → 0.95)** (D-014) — the coordinated change
  v1.25 and v1.26 both deferred. Re-verified against FAO-56 Table 12 at the time
  of the change. Corn's old 1.15 was *sweet* maize's coefficient, understating
  peak ETc by ~4% through pollination (STAGE_WEIGHTS 1.5, MAD factor 0.60) —
  the yield-losing direction. Sunflower's 1.10 left alone: Table 12 prints a
  range of 1.0–1.15 and 1.10 is inside it. §4's AUTHORITATIVE examples
  regenerated through the real code paths: ETc 0.322 → 0.336; balance walk
  4.00/3.68/3.36 → 3.984/3.648/3.312, depletion 0.445/0.489/0.533 →
  0.447/0.493/0.540, refill 3.12 → 3.168; 46-day example cumulative_deficit
  8.505 → 8.778 and stage_weighted_deficit 4.1104 → 4.2504. The 3-day
  vegetative example is unchanged — at gdd_frac 0.033 it reads `kc_initial`.
  Applied in `seed.py`, `engine/kc.py` and migration `m12_fao56_kc_mid`
  (upgrade/downgrade verified). Every Kc in `crops` now matches FAO-56 Table 12
  for the eight crops it covers; `cover` remains the sole unsourced crop.
- v1.26 (2026-09-03): **Full Crop Library audited against FAO-56 Tables 12 and
  22; six crops corrected** (D-013, extends D-010's corn-only fix). Verified
  against fao.org/4/x0490e/ — read, not recalled.
  - Corrected: soy `kc_end` 0.80→0.50; alfalfa `kc_end` 0.85→0.90; sunflower
    `kc_end` 0.55→0.35; sweet corn `kc_end` 0.90→1.05; potatoes `kc_initial`
    0.45→0.50, `p` 0.45→0.35, `root_depth_in` 30→24. Onions `p` 0.50→0.30.
    Migration `m11_fao56_crop_params` (upgrade + downgrade verified).
  - The depletion fractions matter most: onions and potatoes are shallow-rooted
    and stress-sensitive, so waiting for 50%/45% depletion rather than 30%/35%
    delayed irrigation past FAO-56's no-stress threshold. Potatoes' root depth
    was REDUCED because 30 in exceeded FAO-56's maximum Zr (0.6 m), inflating
    AW ~25% and compounding the same error.
  - Deferred to the spec owner at the time: **`kc_mid` for any crop** — corn
    1.15 vs FAO 1.20 (corn's 1.15 being in fact *sweet corn's* value), soy 1.10
    vs 1.15, alfalfa 1.05 vs 0.95. **Now applied in v1.27 (D-014)**, together
    with the §4 worked examples they are load-bearing on.
  - NOT changed, deliberate: root depths below FAO's Zr range (corn, alfalfa,
    sweet corn, cabbage). Zr is a MAXIMUM under ideal conditions; a shallower
    effective zone suits NY soils and errs conservative.
  - `cover` has no FAO-56 entry at all — its parameters are unsourced and should
    be cited from extension guidance or the crop dropped.
  - Five `test_engine.py` tests named "match FAO-56 reference values" were in
    fact asserting typed-in values that FAO-56 contradicts; retitled and
    re-pointed, with deliberate deviations documented inline.
- v1.25 (2026-09-03): Agronomy + calendar corrections (DECISIONS D-010/D-011/D-012).
  - **Corn `kc_end` 0.90 → 0.60** (D-010). VERIFIED against FAO-56 Table 12
    (fao.org/4/x0490e/x0490e0b.htm): Maize, Field (grain) is Kc_ini 0.30 /
    Kc_mid 1.20 / Kc_end 0.60–0.35, the first value "for harvest at high grain
    moisture", the second "after complete field drying of the grain (to about
    18% moisture)". 0.90 appears in no row. 0.60 adopted — much NY grain corn is
    harvested wet for on-farm storage. Grain-fill Kc at gdd_frac 0.76 moves
    1.025 → 0.875 (~15% lower ETc through grain fill). Applied in `seed.py`,
    `engine/kc.py` and migration `m10_corn_kc_end` (upgrade/downgrade verified
    against a pre-seeded DB). Corn removed from the "pending agronomist
    sign-off" list.
  - **Two discrepancies the verification exposed, deferred at the time** (see
    D-010): corn `kc_mid` 1.15 vs FAO-56's 1.20 for field maize, and `sweet
    corn` `kc_end` 0.90 vs 1.05. **Both are now fixed** — sweet corn's
    `kc_end` in v1.26 (D-013), corn's `kc_mid` in v1.27 (D-014).
  - **Default planting date is now the TYPICAL regional date (May 15), not the
    latest-safe-plant date** (D-011). Latest-safe modelled every farmer as
    planting as late as possible, understating GDD by ~10–20 days and yielding a
    lower Kc and a less conservative MAD — the yield-losing direction at
    pollination. Clamped so it can never exceed latest-safe. New module
    `app/engine/season.py`; latest-safe retained for planting-window advice.
  - **The hardcoded 2026 epoch is gone.** `_fmt_julian` was duplicated in
    `advisor/service.py` and `dashboard/routes.py` with the year pinned to 2026,
    so from January 2027 both produced planting dates a full year early —
    silently, feeding gdd_frac → Kc → MAD → the irrigate decision. Both now call
    `season.julian_to_date`, which derives the year from the run date.
  - **`SECRET_KEY` fails fast** rather than defaulting to
    `"CHANGE_ME_IN_PRODUCTION"` (D-012, §6). Other §6 gaps (plaintext phone,
    flat 30-day JWT) remain open and are documented as such.
  - Test fixes: the two stage-adjusted-MAD tests were asserting a pollination
    scenario that actually computed to gdd_frac 0.463 (vegetative) and required a
    live Open-Meteo call to run at all — both corrected and made hermetic. The
    SMS regression test pinned `generated_at` so it no longer passes only on the
    date it was written.
- v1.24 (2026-09-01): Reference-data guard hardened — now compares full
  seed sets (counties, crops, soils) against source-of-truth files and runs
  last in the test suite. `_preserve_reference_data` fixture extended to
  snapshot/restore NY counties; cleanup deletes child rows in FK order.
  Contaminated Albany weather rows purged and re-fetched at correct
  coordinates (gdd_frac shift < 0.001 — Open-Meteo grid resolution makes
  ~10 km immaterial).
- v1.23 (2026-09-01): Reverted corn maturity fallback from 145 to 130 days
  (seed.py `25,35,45,25`). The 145 figure was test residue from
  `test_advisor.py` upserting corn with `'30,40,50,25'` — it was never the
  seed source of truth. Extension preservation fixture (`_preserve_reference_data`)
  now snapshots and restores both `soils` and `crops` across the test module.
- v1.22 (2026-08-31): Corn-only advisory generation documented as deliberate v1
  choice (D-009). Advisory GENERATION and SMS are county-level and corn-only;
  the web dashboard (`/api/advisory/{fips}`) is crop- and stage-aware via its
  `crop_id`/`planting_date` query params. Fixed `nightly.py` SMS query
  referencing nonexistent `decision` and `date` columns on `advisories`.
- v1.21 (2026-08-31): Stage-adjusted MAD documented in §4 (MAD scaled by
  growth-stage factor). `generate_advisory` enriches `source_data` with
  `decision` for SMS audit trail. Nightly SMS reads stored advisory's
  `source_data` JSON instead of recomputing inline.

## 1 · Product
County-level planting-window and water-budget advisories for farmers across New York (62 counties),
delivered by SMS with a web dashboard for planning. The farmer gets a 6:30am
text with the 3 numbers that matter today; the web shows the math behind them.
Value before friction; the phone number is the identity.

**v1 scope note (D-009):** Advisory GENERATION and SMS are county-level and
corn-only — the `advisories` table always carries `crop_id = 'corn'`, and the
6:30am text describes corn water-budget status for the subscriber's county. The
web dashboard (`/api/advisory/{fips}`) is crop- and stage-aware: it accepts
`crop_id` and `planting_date` query params and computes advisories for any of
the 9 in-scope crops on the fly. Per-crop SMS is deferred (see DECISIONS.md
D-009).

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
| SSURGO (via SoilWeb) | soil AWC + texture | real per-county NY snapshot in `soils` (41/62 counties captured 2026-08-18, dominant map-unit texture + AWS(0-100cm)/100); rest use state defaults. Live refresh: `refresh_county_soils()` |
| NRCS SCAN | measured soil moisture | calibration ground-truth |
| FAO-56 | crop coefficient (Kc) tables | public agronomy standard |

## 4 · Formulas — with worked examples (AUTHORITATIVE)
Tests MUST reproduce these exact numbers.

GDD:  corn, tmax=89, tmin=71 → avg=80 → GDD = 80−50 = 30
ETc:  corn mid-season Kc=1.20, ET0=0.28 → ETc = 1.20×0.28 = 0.336 in/day
AW:   corn root 36in × AWC 0.20 → AW = 7.2 in
Balance: start SW=4.32 (60% of 7.2), depletion=0.40
  Day1 (no rain): 4.32−0.336=3.984 → depletion=0.447 (<0.50, hold)
  Day2: 3.984−0.336=3.648 → depletion=0.493 (hold)
  Day3: 3.648−0.336=3.312 → depletion=0.540 (≥0.50 → IRRIGATE)
  Refill to 0.9×7.2=6.48 → apply 6.48−3.312 = 3.168 in
Window: Albany frost_kill_50=275 (Oct 2), corn ~130 days → latest safe plant = May 25.
  Derivation: 275 − 130 = julian 145 = May 25. Confidence band from frost_10 (255 = Sep 12) and frost_90 (300 = Oct 27).

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
  Kc = 0.30 (gdd_frac < 0.10 → kc_initial, NOT mid-season kc_mid)
  ETc = 0.30 × 0.28 = 0.084 in/day
  SW starts at 0 → daily deficit = 0.084 in each day
  cumulative_deficit = 3 × 0.084 = 0.252 in
  stage_weighted_deficit = 3 × 0.084 × 0.4 = 0.1008 in  (weight 0.4 for vegetative)

Worked example (44 vegetative + 2 pollination days, start_sw_frac=0.0):
  46 days × 30 GDD = 1,380 GDD → gdd_frac runs 0.011 → 0.511
  Kc follows the FAO-56 curve: kc_initial 0.30 for the first 9 days
  (gdd_frac < 0.10), ramping 0.30 → 1.20 across gdd_frac 0.10–0.50,
  then kc_mid 1.20 from day 45 (gdd_frac = 1350/2700 = 0.50).
  cumulative_deficit = 8.778 in
  stage_weighted_deficit = 4.2504 in

### Growth stage + stage-adjusted MAD (v1.11)

The crop's current growth stage is derived from GDD accumulated since planting:

```
cumulative_gdd = Σ GDD_day from planting_date to yesterday
gdd_frac       = cumulative_gdd / gdd_to_maturity   (crop's GDD to maturity)
stage          = band lookup of gdd_frac (table above)
```

The dashboard computes `cumulative_gdd` from backfilled `daily_historical`
temps (authoritative) with a live Open-Meteo archive fetch filling any gaps
before the backfill window. The advisory endpoint accepts `crop_id` and
`planting_date` query params; absent that, it defaults to the user's farm
crop + planting date for that county (or corn at the county's latest safe
plant date).

**Stage-adjusted MAD (refill point):** MAD is scaled by stage so the refill
decision is more conservative during yield-critical windows.

| Stage          | MAD factor | Rationale |
|----------------|-----------|-----------|
| Vegetative     | 1.00      | Normal management |
| Pollination    | 0.60      | Critical — refill earlier to protect grain set |
| Grain fill     | 0.80      | Sensitive — keep root zone wetter |
| Maturity       | 1.00      | Normal; dry-down tolerated |

```
adjusted_mad = base_mad × stage_mad_factor(stage)
```

Worked example (corn, base_mad = 0.50):
  Planted May 1; by Aug 17 it has accumulated 1,377 GDD (base 50°F).
  gdd_frac = 1377 / 2700 = 0.51 → Pollination → factor 0.60
  adjusted_mad = 0.50 × 0.60 = 0.30  → irrigate when depletion ≥ 0.30

Engine: `app/engine/growth.py` (band table mirrors water_balance.STAGE_WEIGHTS).

## 5 · Modules
8 modules / 48 submodules — see the Bill of Modules (FC-BM-001).
M1 Ingestion · M2 Engine · M3 Advisor · M4 Delivery · M5 Identity ·
M6 Grower App · M7 Back Office · M8 Commerce.

### M3 — Advisory Composition (v1.3)

M3 builds on M2's engine output. M2 decides IRRIGATE/HOLD; M3 adds SCHEDULE
and produces the final advisory with hash chain integrity.

**v1 scope (D-009):** `generate_all()` iterates all 62 NY counties and produces
one advisory per county per night, always for `crop_id = 'corn'`. The crop
params lookup, Kc curve call, GDD accumulation, and soil moisture spin-up all
use the corn crop. The `advisories` table — the hash-chained, tamper-evident
audit record — always describes corn, even for farms growing other crops. The
web dashboard computes per-crop advisories on the fly from `daily_historical`
and `crops` data; these are not persisted to `advisories`.

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
3. Soil spin-up (`field_cells` + `daily_records`) from fetched history — corn only
4. `generate_all(date)` — produces one advisory per county (corn only, D-009)
5. Store to `advisories` table
6. Optionally send SMS (`--sms` / `FURROWCAST_NIGHTLY_SMS=1`) — corn advisory per subscriber county
7. Log the run to `ingest_runs` (source `nightly_pipeline`, status, row counts)
   — the dashboard surfaces this as "Data as of <date>" and `/api/admin/refresh`
   triggers the same pipeline on demand (auth-protected).

## 6 · Security (summary — full: Addendum 06-2)
Login: email + password (Argon2id) for the M6 frontend — OTP/WebAuthn deferred
(see DECISIONS.md D-007). Local dev bypass: FURROWCAST_DEV_PUBLIC=1 makes
protected routes public.
Sessions: 15-min access, 30-day rotating refresh, device-bound, revocable.
Production cookies: set `FURROWCAST_COOKIE_SAMESITE=none` +
`FURROWCAST_COOKIE_SECURE=1` so the session cookie survives cross-site fetches
(frontend and API on different hosts, e.g. Render). Requires HTTPS.
Audit: advisories hash-chained (SHA-256), daily Merkle root anchored to Bitcoin.
PII: phone encrypted at rest, never logged. Admin: YubiKey only.

## 7 · Deployment (public demo)
Deploy configs live in `render.yaml` (Render blueprint), `backend/Dockerfile`
(migrate + bootstrap + uvicorn), `web/Dockerfile` (Next.js standalone).
- DB: external Postgres (e.g. Neon free tier) — `DATABASE_URL` env.
- CORS: comma-separated `CORS_ALLOWED_ORIGINS` env (frontend host) + localhost.
- Bootstrap: `python -m app.db.bootstrap` loads 62 NY counties, 9 crops, 62
  soils on first boot (idempotent). Weather + advisories come from the nightly
  pipeline (`POST /api/admin/refresh` or `python -m app.nightly`).
- `FURROWCAST_DEV_PUBLIC` MUST NOT be set in production.

## 7 · SMS rules
3 lines max per digest · quiet hours respected · STOP honored in one cycle ·
TCPA consent captured at signup · 10DLC registered before beta (2–4 wk lead).

## 8 · Out of scope (v1)
No native app (gated Jan 2027) · no field polygons (v2) · no MMS · no blog ·
no standalone chatbot · no payments at signup (free tier first).

## Changelog
- v1.21 (2026-08-31): Stage-adjusted MAD in advisor, SMS single source of truth.
  - **TASK 2 (MAD divergence fix):** `_build_water_state` now applies
    `adjusted_mad(base_mad, gdd_frac)` per SPEC.md §4, returning `mad`
    (stage-adjusted) and `base_mad` (raw). At pollination the MAD tightens
    from 0.50 to 0.30 (×0.60 factor), so a county at 35% depletion now
    correctly triggers IRRIGATE in the stored advisory — matching the
    dashboard. Previously the advisor used raw MAD and could say HOLD while
    the dashboard said IRRIGATE for the same county/crop/date. This is a
    user-visible behavior change: stored advisories and SMS for counties in
    pollination or grain-fill stages will trigger irrigation at lower
    depletion thresholds than before.
  - **TASK 3 (SMS dedup):** `_send_sms_advisories` no longer recomputes the
    water balance inline with hardcoded corn constants. It reads the advisory
    that `generate_all` already stored (source_data JSON) and formats it for
    SMS. SMS and dashboard now share one computation path. The `decision`
    field is now included in `source_data` for audit trail completeness.
  - Removed dead `SSURGO_URL` constant from `dashboard/routes.py` (host does
    not exist; real SSURGO ingestion lives in `app/ingest/ssurgo.py`).
  - Verified `nightly.py` field_cells insert: `soil_type` from column 0
    (text), `awc` from column 1 (numeric) — correct after earlier fix.
- v1.20 (2026-08-31): Coverage-guard fix, tz hardcode removal, archive-URL dedup.
  - **TASK 1 (critical):** `_build_water_state` now checks coverage (MIN(obs_date)
    <= planting_date) instead of row count. A county with 14 recent rows where
    the live fetch fails is now correctly skipped instead of producing a
    seedling-band advisory from a truncated window.
  - **TASK 2:** `_ensure_history_coverage` now receives the caller-supplied `tz`
    parameter (`tz_for_state(state)`) instead of defaulting to `America/New_York`.
  - **TASK 3:** Duplicate archive URL constants (`_ARCHIVE_URL` in advisor,
    `OPEN_METEO_HISTORY` in dashboard) consolidated into shared helpers
    `fetch_archive_daily()` and `tz_for_state()` in `app/ingest/open_meteo.py`.
    Both advisor and dashboard import from this single source. Dashboard's
    in-memory merge behavior unchanged.
  - `_ensure_history_coverage` now returns `bool` (coverage achieved) instead
    of `int` (rows upserted), aligning the return value with the guard's intent.
- v1.19 (2026-08-31): Live archive fetch for complete GDD accumulation.
  - `_build_water_state` now calls `_ensure_history_coverage()` before
    computing cumulative GDD. When `daily_historical` has gaps between
    planting_date and yesterday, a live Open-Meteo archive fetch fills them
    (same mechanism the dashboard already uses in `_historical_temps`).
    This ensures the advisor and dashboard agree on gdd_frac for the same
    county/crop/planting date.
  - Partial-coverage guard: zero rows still returns None (skip); partial
    rows trigger the live fetch to complete the window. Counties where the
    archive API is unreachable gracefully fall back to whatever DB rows exist.
  - Advisory and dashboard now compute identical gdd_frac values.
- v1.18 (2026-08-31): Pipeline history-fetch fix + data-sufficiency guard.
  - Open-Meteo archive request now ends at `run_date - 1` (archive API lags
    ~1 day; requesting today's date fails all 62 counties). Timezone changed
    from hardcoded `America/Chicago` to per-state (`America/New_York` for NY).
  - `_build_water_state` now counts `daily_historical` rows in the
    planting→date window; returns `None` (skip advisory) when zero rows are
    found, preventing seedling-Kc advisories built on absent data. New
    `counties_skipped` counter in `generate_all` results.
  - Advisory errors and history fetch errors are now logged with county FIPS.
- v1.17 (2026-08-31): `spinup_soil_moisture()` made genuinely crop-aware — new
  `crop_id` parameter replaces discarded `kc`/`kc_initial`/`kc_end`; crop
  params (`base_temp_f`, `gdd_to_maturity`, Kc curve) now resolved from
  `CROP_PARAMS` inside spinup. Callers in nightly.py, backfill_spinup.py,
  rerun_spinup.py, backfill_all.py updated to pass `crop_id="corn"`.
  Computed soil-moisture values change for non-corn crops (previously all
  used corn's Kc curve regardless of crop_id).
- v1.16 (2026-08-30): Fixed §4 stage-weighted worked examples — ETc was computed with flat kc_mid (1.15) instead of kc_for_gdd_frac; at gdd_frac=0.033 the Kc curve returns kc_initial=0.30. Corrected 3-day example (cumulative_deficit 0.966→0.252, stage_weighted_deficit 0.3864→0.1008) and 46-day example (cumulative_deficit 14.812→8.505, stage_weighted_deficit 6.6332→4.1104); fixed heading (45+1→44+2).
- v1.15 (2026-08-30): Schema + correctness pass (SCHEMA.sql v1.15,
  migration `m9_subscribers_and_units`).
  - **`subscribers` table added.** `nightly.py::_send_sms_advisories` queried
    a `subscribers` table that had never existed in the schema, so the
    optional SMS step (§5 M3 nightly flow step 6, `--sms` /
    `FURROWCAST_NIGHTLY_SMS=1`) crashed on every run. Table + index created;
    `Subscriber` model added.
  - **`daily_records` units corrected.** `et0_mm` / `rainfall_mm` /
    `irrigation_mm` renamed to `*_in`: the engine computes and stores inches
    throughout (§4), and the columns never held mm. Pure rename — no data
    conversion — bringing the schema contract in line with the engine.
  - **Open-Meteo timezone is now per-state.** Forecast/archive URLs were
    pinned to `America/Chicago`, so NY counties' daily tmax/tmin/precip
    buckets were cut on Central time. `_STATE_TZ` / `_tz_for_state()` in
    `app/dashboard/routes.py` now send `America/New_York` for NY.
  - **ORM caught up to the schema.** `Farm`, `FarmCrop` and `Subscriber`
    models added to `app/db/models.py` (SCHEMA.sql requires models.py to
    match it exactly); `Advisory.__repr__` no longer references a
    nonexistent `decision` column.
  - **`INSCOPE_STATES` narrowed to `{NY}`** in `app/advisor/service.py`,
    completing DECISIONS.md D-006 in code. Legacy NE/IA/KS advisory tests
    now skip (not fail) when those counties aren't seeded, since
    `app.db.bootstrap` is NY-only.
- v1.14 (2026-08-28): Bug fix — `app/dashboard/routes.py::_get_soil_awc`
  (the last-resort soil fallback for a county with no `soils` row) previously
  used lat/lon-only quadrant buckets built for KS/NE/IA; since NY latitudes
  (~41–45°N) fell into the `lat >= 41.0` branch labeled "Nebraska," any
  unseeded NY county would have silently received Nebraska soil values. The
  fallback now takes `state` and, for any state outside {KS, NE, IA}, returns
  `app.ingest.ssurgo.STATE_DEFAULTS[state]` — the same per-state default
  `load_soils`/`bootstrap`/`refresh_county_soils` already use, matching this
  doc's existing "rest use state defaults" line in §3. No API or schema
  change; `GET /api/advisory/{fips}` response shape is unchanged.
- v1.13 (2026-08-18): Real per-county NY soils — `app/ingest/ssurgo.py`
  carries a 41/62-county SSURGO snapshot captured 2026-08-18 via SoilWeb
  (dominant map-unit texture + Available Water Storage 0-100cm / 100),
  with state-default fallback for the rest. `load_soils` + raw bootstrap
  seed the `soils` table from it. `/api/advisory/{fips}` now sources
  `soil.type`/`soil.awc` from the `soils` table (DB is the source of truth);
  the regional estimator is reached only for unseeded counties.
  `refresh_county_soils()` re-pulls live SSURGO when needed.
- v1.12 (2026-08-18): Crop Library rotated to the New York scope — `cotton`,
  `sorghum`, `peanuts` retired (not grown commercially in NY); `cabbage`,
  `onions`, `sweet corn` added — all now verified against FAO-56 Tables 12/22
  (D-013). Migration M8 + seed + engine fallback params updated; still 9
  crops total.
- v1.11 (2026-08-18): Growth stage + stage-adjusted MAD wired end-to-end —
  `/api/advisory/{fips}` accepts `crop_id` + `planting_date`, computes the
  current stage from accumulated GDD (backfilled `daily_historical` + live
  Open-Meteo archive) and scales MAD by stage (Pollination ×0.60, Grain fill
  ×0.80) so the refill point reacts to the season. Farm crops gain
  `planting_date`; dashboard shows crop selector, planting date, and the
  current Growth Stage. Engine `app/engine/growth.py`.
- v1.10 (2026-08-17): Production deploy prep — `render.yaml` blueprint
  (backend + frontend web services), Dockerfiles for backend (migrate +
  bootstrap + uvicorn) and web (Next.js standalone), `app/db/bootstrap.py`
  NY-only first-boot loader (62 counties, 9 crops, 62 soils). CORS origins now
  env-driven (`CORS_ALLOWED_ORIGINS`); session cookie configurable for
  cross-site HTTPS (`FURROWCAST_COOKIE_SAMESITE=none` + `FURROWCAST_COOKIE_SECURE=1`).
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

## Dashboard water-state correction (2026-09-08)

Changelog: Preserve planting-to-yesterday GDD in crop metadata and initialize forecast Kc from that accumulated growth, advancing it after each forecast day. Initialize soil water from the latest matching county/crop record for the first forecast date (start-of-day spin-up); stale records are not used. Without a matching record, use an explicit 60% assumption. The additive `soil.water_source` field is `stored` or `assumed`; stored values are model outputs, not sensor observations.

### Seasonal spin-up initialization (v1.29)
Nightly corn spin-up still assumes field capacity at the start of its 14-day
rain-fed simulation. Its initial GDD is now the sum from the default planting
date to the day before that window. The crop coefficient uses that carried
accumulation plus each weather day's GDD, as in the existing spin-up convention.
History is fetched back to planting (or the window start, whichever is earlier).
Missing days or temperatures, or missing rain/ET0 inside the window, cause a
skip rather than an early-season assumption. Same-cell/date records are replaced
and store cumulative GDD and growth stage. Legacy historical backfill scripts
are not the nightly path and retain their existing calendar assumptions.
Worked regression: 1380 initial GDD, three days at 89/71 F, ET0 0.28 in,
zero rain and AW 7.2 in: Kc stays 1.20; SW = 7.2 - 3*1.20*0.28 = 6.192 in,
depletion = 0.14. This fixes growth initialization, not field calibration or
the full-capacity initial soil-water assumption.

## Moisture initialization uncertainty (2026-09-11)
Changelog: Nightly corn moisture replays complete daily history from the default
planting date through yesterday. Replaying each day's ending water as the next
day's starting water is equivalent to continuation, without the rolling-window
reset or dependence on obsolete saved parameters. Incomplete weather skips the
record. Initial dry/full endpoints (0 and AW) bound unknown starting water;
their propagated midpoint populates the legacy point estimate. These bounds
cover initialization only, not weather, soil-parameter or model error.
`daily_records.soil_min_pct` and `soil_max_pct` store the unrounded bounds;
legacy records have NULL bounds and are not treated as calibrated observations.
Dashboard `today` adds `soil_min_pct`, `soil_max_pct`, and `advice_uncertain`.
Forecast days add `advice_uncertain`. If the bounds straddle the irrigation
threshold, the UI displays CHECK SOIL rather than the midpoint recommendation.
Missing current-day bounds yield [0,100]% and an explicitly assumed midpoint;
after applying weather, the bounds determine uncertainty. Stored advisory
source_data also includes bounds and the uncertainty flag; automated SMS skips
flagged advice (including uncertainty across the SCHEDULE threshold).
A county whose soil spin-up FAILED for the run is also flagged, regardless of
what its bounds compute to. The spin-up is what rebuilds the water balance from
the planting date; without it the numbers describe an assumed starting state, not
a replayed one. The flag is set per county by the nightly pipeline, which knows
which spin-ups failed, and carries the existing consequences: CHECK SOIL in the
UI and no SMS.
No field-calibration claim is made. The full-capacity default remains only for
legacy direct callers of the pure simulator; the nightly path supplies both
endpoints explicitly. Lint cleanup removes dead bindings, sorts imports, uses
UTC-aware timestamps, and documents intentional exception boundaries and FastAPI
dependency declarations locally; checks remain enabled repository-wide.

### Farmer visual dashboard
The dashboard presents a rotatable, schematic 3D plant whose size and leaf count follow clamped 0–100% GDD progress. It is not a measured height, crop health assessment, or harvest-readiness guarantee. Missing growth has no plant or numeric progress. Crop families vary the diagram shape; these are not botanical models. Rotation supports keyboard input and no animation is automatic. Soil water is shown as percent of available capacity with the refill line at `(1 − MAD) × 100`. Irrigation depth comes only from `today.irrigate_amount` for an unambiguous IRRIGATE action; uncertain advice or assumed starting moisture displays Check your soil first without a dose. Crop water use and forecast rain are separate from irrigation need. Initialization bounds exclude weather and model error.

Dashboard artwork is illustrative maize, not a crop observation. Users can switch to the rotatable growth diagram. The season timeline uses the model stage thresholds (0%, 50%, 62%, 90%); no calendar or harvest date is inferred. The water outlook charts API daily precipitation and ETc in inches, with an explicit empty state when unavailable. Overview links to the saved six-step field checklist; completion never records irrigation or changes a recommendation. Field controls appear within the photo header, update automatically on selection, and can be refreshed with Update. Soil-water uncertainty is shown as an interval using API bounds, without synthetic historical curves or percentage-change claims. Weather history and data freshness are available in an expandable section beneath the forecast.

## MUONS Water workspace (v1.33)

Routes: `/login`, `/dashboard`, `/growth`, `/water`, `/journal`, `/weather`,
`/reports`, `/settings`, `/checklist`, `/help`. The shared shell provides persistent
navigation, page search, date, notification availability panel and account menu.
The sign-in/register/logout API flows remain intact. Authentication errors are
propagated to the page so protected data redirects to sign-in.

Overview is the visual master. Shared cards, metric cards, tables, trend charts,
buttons, fields and empty states use the same green/white design tokens. Content
is capped at 1680px and the 250px sidebar becomes a drawer below 1024px. Existing
county/crop/planting controls persist the selection used by analysis pages.

Growth shows current model data and accumulated forecast heat, never inferred
historical measurements. Maturity is shown only if the supplied daily forecast
reaches the crop heat target. This does not indicate harvest readiness. Water
outlook period buttons restrict available forecast rows; 14/30-day gaps are
explicit. No future daily irrigation doses are invented. County map markers are
reference coordinates, not field boundaries. Weather identifies missing live,
hourly, severe-alert and historical-series data; aggregate history remains available.

Journal is browser-local CRUD with optional photo (JPEG/PNG/WebP, max 1.5 MB),
activity, date/time, notes, quantity text, weather, location and author. Search,
activity/date filters, pagination and JSON backup are provided. Notes never update
the model. Browser-storage write failures are shown rather than reported as saves.

Reports offer water use, irrigation, rainfall, growth, weather, field activity and
season snapshot previews, date filtering where applicable, CSV and browser print
PDF. Exports use the preview, preserve unavailable values and neutralize spreadsheet
formula prefixes in user-entered text. Season Summary is explicitly a current
snapshot, not unavailable season history. Field Activity uses browser-local entries
across their recorded locations, clearly distinguished from the selected county API.

Settings persist display name, analysis/report water and temperature units, farm
area units and in-app reminders locally. Overview retains explicit inch labels and
also shows irrigation in millimetres. Area preferences affect displayed farm records;
there is no farm-edit API change. Delivery notifications and account editing are
unavailable rather than simulated. Signing out does not delete local records.

Dedicated six-step checklist completion is saved by local date, county, crop and
planting date under a new versioned storage key. Completion is not authorization
to irrigate; the next step respects model uncertainty. Overview links to this checklist.
Help supplies FAQs and a downloadable support note; no support inbox is invented.

No new frontend dependencies or backend schemas are introduced by this redesign.
