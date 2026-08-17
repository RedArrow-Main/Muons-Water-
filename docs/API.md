# API.md - API Contracts
<!-- DOC VERSION: v1.2 | LAST UPDATED: 2026-08-17 | OWNER: principal -->

## A.4 Contracts

This file contains the API contracts for the furrowcast project.

## Changelog
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

**Response:** Full advisory for a county, computed on-the-fly from DB data.
The M3 stored advisory (advisories table) is for audit/hash-chain only;
this endpoint always returns the rich dashboard format.

```json
{
  "county": {"fips": "36037", "name": "Genesee", "state": "NY", "lat": 43.0, "lon": -78.2},
  "soil": {"type": "silt loam", "awc": 0.2},
  "crop": {"id": "corn", "aw": 7.2, "mad": 0.5},
  "forecast": [{"date": "2026-08-06", "tmax_f": 89, "tmin_f": 71, ...}],
  "today": {"gdd": 30, "etc": 0.322, "soil_water": 4.32, "soil_pct": 60.0, "depletion": 0.4, "action": "HOLD", "irrigate_amount": 0},
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

**Nulls:** `history.last_7d_rain` and `history.last_7d_et` are `null` when the
county has no `daily_historical` rows in the last 7 days (history backfill not
run yet). They are never `0.0` in that case — the frontend shows
"Setting up data for this county".

**`data_as_of`:** the most recent `nightly_pipeline` run from `ingest_runs`.
`last_pipeline_at` / `last_pipeline_status` are `null` and `last_pipeline_rows`
is `0` when no nightly run has happened yet. The dashboard renders
"Data as of <date>".

**404:** County not found.

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
