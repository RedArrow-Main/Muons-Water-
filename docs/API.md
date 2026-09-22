# API.md - API Contracts
<!-- DOC VERSION: v1.12 | LAST UPDATED: 2026-09-11 | OWNER: principal -->

## A.4 Contracts

This file contains the API contracts for the furrowcast project.

## Changelog
- v1.10 (2026-09-03): No shape change. `today.etc` in the `GET /api/advisory/{fips}`
  sample moves 0.322 → 0.336 because corn `kc_mid` was corrected 1.15 → 1.20
  (SPEC v1.27, DECISIONS D-014); ETc rises ~4% wherever gdd_frac > 0.10 for
  corn, soy and alfalfa. Also fixed a stale sample: it showed
  `growth_stage: "pollination"` with `depletion: 0.4` and `action: "HOLD"`,
  which the stage-adjusted MAD (0.50 × 0.60 = 0.30) makes impossible — now
  `IRRIGATE` with `irrigate_amount: 2.16`. The sample was stale against the
  code, not the reverse.
- v1.9 (2026-09-03): Behaviour change on `GET /api/advisory/{fips}` — response
  SHAPE is unchanged, but values move (SPEC.md v1.25, DECISIONS D-010/D-011):
  - `crop.mad` / `today.action`: the advisor now applies stage-adjusted MAD, so
    the stored advisory and this endpoint agree. Previously the advisor used the
    raw `mad_fraction` while this endpoint used the adjusted value, so a county
    at pollination could show IRRIGATE here and HOLD in the stored advisory.
  - `today.etc`: corn `kc_end` corrected 0.90 → 0.60, lowering ETc by ~15%
    through grain fill (gdd_frac 0.62–0.90). Seedling/vegetative/pollination
    values are unchanged.
  - `crop.planting_date` when NOT supplied: now the region's typical planting
    date (May 15) rather than the latest-safe-plant date, and the year is derived
    from the request date rather than hardcoded to 2026. This shifts
    `cumulative_gdd`, `gdd_pct`, `growth_stage` and therefore `mad` for every
    request that omits `planting_date`.
- v1.8 (2026-08-31): Documented that the stored `advisories` table is corn-only
  in v1 (D-009). The `GET /api/advisory/{fips}` endpoint is crop-aware and
  returns per-request crop data; the durable advisory record always carries
  `crop_id = 'corn'`. No response shape change.
- v1.7 (2026-08-29): Documented the `today` object's internal consistency
  contract on `GET /api/advisory/{fips}` — `soil_water` (inches) and
  `soil_pct` (0–100) describe the same root-zone water content
  (`soil_pct ≈ soil_water / aw × 100`), and `depletion = 1 − soil_water / aw`.
  `soil_water` is the day-0 value, NOT the end-of-forecast value. `action` is
  `IRRIGATE` when `depletion ≥ mad` (the stage-adjusted MAD), else `HOLD`;
  `irrigate_amount` is non-zero only on `IRRIGATE`. Clarification only — no
  field added or removed, response shape unchanged.
- v1.6 (2026-08-18): `GET /api/advisory/{fips}` now sources `soil.type` /
  `soil.awc` from the `soils` table (real per-county SSURGO values). The
  regional estimator is used only when a county has no soils row. Response
  shape is unchanged.
- v1.5 (2026-08-18): Crop Library rotated to NY scope — `cotton`, `sorghum`,
  `peanuts` removed; `cabbage`, `onions`, `sweet corn` added (FAO-56 reference
  values). `GET /api/crops` and `crop_id` validation now cover the NY 9.
- v1.4 (2026-08-18): `GET /api/advisory/{fips}` accepts optional `crop_id`
  and `planting_date` query params and returns the growth stage +
  stage-adjusted MAD in the `crop` object. New `GET /api/crops` crop-library
  endpoint. Farm endpoints persist and return `planting_date` per `farm_crops`.
- v1.3 (2026-08-17): Session cookie flags are env-configurable for cross-site
  HTTPS deployments: `FURROWCAST_COOKIE_SAMESITE=none` +
  `FURROWCAST_COOKIE_SECURE=1` (requires HTTPS). CORS origins come from the
  comma-separated `CORS_ALLOWED_ORIGINS` env var (plus localhost dev origins).
- v1.2 (2026-08-17): `data_as_of` added to `GET /api/advisory/{fips}` responses
  and `last_pipeline_at`/`last_pipeline_status`/`last_pipeline_rows` added to
  `GET /api/stats` (both from `ingest_runs`, source `nightly_pipeline`). New
  auth-protected `POST /api/admin/refresh` to trigger the nightly pipeline on
  demand.
- v1.1 (2026-08-17): `history.last_7d_rain` / `history.last_7d_et` are now
  `null` (not `0.0`) when a county has no backfilled `daily_historical` rows in
  the last 7 days. Frontend renders "Setting up data for this county" in that
  case. NY-only county scope (62 counties).

### GET /api/advisory/{fips}

**Auth:** Required (session cookie).

**Query params (both optional):**
- `crop_id` — any crop in the Crop Library (`corn`, `soy`, `alfalfa`, `cover`,
  `potatoes`, `sunflower`, `cabbage`, `onions`, `sweet corn`). Default: the
  user's farm crop for that county, else `corn`.
- `planting_date` — `YYYY-MM-DD` the crop was planted. Default: the user's
  farm planting date for that crop/county, else the county's latest safe
  plant date.

**Response:** Full advisory for a county, computed on-the-fly from DB data.
The M3 stored advisory (advisories table) is for audit/hash-chain only;
this endpoint always returns the rich dashboard format. In v1, the stored
advisory is always for `crop_id = 'corn'` (D-009); this endpoint returns
the crop-specific result for the requested `crop_id`.

```json
{
  "county": {"fips": "36037", "name": "Genesee", "state": "NY", "lat": 43.0, "lon": -78.2},
  "soil": {"type": "silt loam", "awc": 0.2},
  "crop": {
    "id": "corn", "aw": 7.2,
    "mad": 0.3, "base_mad": 0.5,
    "planting_date": "2026-05-01",
    "growth_stage": "pollination", "stage_label": "Pollination",
    "gdd_pct": 51.0, "cumulative_gdd": 1377.0, "gdd_to_maturity": 2700
  },
  "forecast": [{"date": "2026-08-06", "tmax_f": 89, "tmin_f": 71, ...}],
  "today": {"gdd": 30, "etc": 0.336, "soil_water": 4.32, "soil_pct": 60.0, "depletion": 0.4, "action": "IRRIGATE", "irrigate_amount": 2.16},
  "history": {
    "july_avg_high": 85.0,
    "july_avg_low": 62.0,
    "july_total_rain": 3.5,
    "last_7d_rain": 1.35,
    "last_7d_et": 1.24
  },
  "drought": {"level": "D1"},
  "planting_window": {"frost_50pct": "2026-10-12", "corn_start": "2026-06-14", ...},
  "outbox": [{"phone": "+1*** *** **12", "body": "...", "status": "sent", "sent_at": "..."}],
  "data_as_of": {
    "last_pipeline_at": "2026-08-17 18:51:05.990846",
    "last_pipeline_status": "success",
    "last_pipeline_rows": 62
  }
}
```

**`crop` object:**
- `mad` is the **stage-adjusted** refill point (see SPEC.md §4 v1.11) —
  `base_mad × stage_mad_factor(stage)`. All IRRIGATE/HOLD decisions in
  `today`/`forecast` use this adjusted value.
- `growth_stage` ∈ `vegetative` · `pollination` · `grain_fill` · `maturity`.
- `cumulative_gdd` is GDD accumulated from `planting_date` through yesterday.

**`today` object:** a snapshot of the **current/forecast-day-0** state for the
crop. Its fields are mutually consistent: `soil_water` (inches) and `soil_pct`
(0–100) describe the same root-zone water content (`soil_pct ≈ soil_water / aw ×
100`), and `depletion = 1 − soil_water / aw`. `soil_water` is the day-0 value
(i.e. the same reference as `soil_pct`/`depletion`), NOT the end-of-forecast
value. `action` is `IRRIGATE` when `depletion ≥ mad`, else `HOLD`;
`irrigate_amount` is non-zero only on `IRRIGATE`.

**Nulls:** `history.last_7d_rain` and `history.last_7d_et` are `null` when the
county has no `daily_historical` rows in the last 7 days (history backfill not
run yet). They are never `0.0` in that case — the frontend shows
"Setting up data for this county".

**`data_as_of`:** the most recent `nightly_pipeline` run from `ingest_runs`.
`last_pipeline_at` / `last_pipeline_status` are `null` and `last_pipeline_rows`
is `0` when no nightly run has happened yet. The dashboard renders
"Data as of <date>".

**404:** County not found. **404:** unknown `crop_id`.

### GET /api/crops

**Auth:** None (public catalog).

**Response:** The 9-crop Crop Library from the `crops` table.

```json
[
  {"id": "corn", "base_temp_f": 50.0, "gdd_total": 2700, "root_depth_in": 36.0,
   "mad_fraction": 0.5, "kc_initial": 0.3, "kc_mid": 1.15, "kc_end": 0.9},
  ...
]
```

### GET /api/farm

**Auth:** Required (session cookie).

**Response:** All farms for the current user. `crops` now includes each
crop's optional `planting_date`.

```json
[
  {"id": 1, "county_fips": "36037", "name": "Springfield", "acres": 120,
   "created_at": "...",
   "crops": [{"crop_id": "corn", "planting_date": "2026-05-01"}]}
]
```

### POST /api/farm

**Auth:** Required (session cookie).

**Body:**
```json
{"county_fips": "36037", "name": "Springfield", "acres": 120,
 "crops": [{"crop_id": "corn", "planting_date": "2026-05-01"}]}
```
Legacy `crop_ids: ["corn", "soy"]` still accepted (planting_date `null`).

**Response:** Created farm with its `crops` (including `planting_date`).

**Errors:** 400 missing county/name/crop; 404 unknown county or crop;
409 farm already exists for user + county.

### DELETE /api/farm/{farm_id}

**Auth:** Required. **Response:** `{"ok": true}` (404 if not owned).

### GET /api/stats

**Auth:** Required (session cookie).

**Response:**
```json
{
  "counties": 69,
  "forecast_rows": 434,
  "ingests": 4,
  "last_pipeline_at": "2026-08-17 18:51:05.990846",
  "last_pipeline_status": "success",
  "last_pipeline_rows": 62
}
```

### POST /api/admin/refresh

**Auth:** Required (session cookie).

**Body (optional):**
```json
{"date": "2026-08-17", "states": ["NY"], "sms": false}
```
`date` defaults to today, `states` to `["NY"]`, `sms` to `false`.

**Response:** Full run summary of the nightly pipeline (counts per connector,
spin-up and advisory generation). Logs a `nightly_pipeline` row to
`ingest_runs`, which updates `data_as_of` / `last_pipeline_at`.

## Dashboard water-state correction (2026-09-08)

Changelog: Preserve planting-to-yesterday GDD in crop metadata and initialize forecast Kc from that accumulated growth, advancing it after each forecast day. Initialize soil water from the latest matching county/crop record for the first forecast date (start-of-day spin-up); stale records are not used. Without a matching record, use an explicit 60% assumption. The additive `soil.water_source` field is `stored` or `assumed`; stored values are model outputs, not sensor observations.

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
No field-calibration claim is made. The full-capacity default remains only for
legacy direct callers of the pure simulator; the nightly path supplies both
endpoints explicitly. Lint cleanup removes dead bindings, sorts imports, uses
UTC-aware timestamps, and documents intentional exception boundaries and FastAPI
dependency declarations locally; checks remain enabled repository-wide.
