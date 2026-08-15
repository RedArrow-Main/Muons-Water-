# DECISIONS LOG
<!-- Append-only. Never delete or overwrite a decision — supersede it. -->
- D-001 (2026-07-30): Single PostgreSQL+PostGIS database. Supersedes: nothing.
- D-002 (2026-07-30): SMS-first, web second; no native app until Jan 2027 gate.
- D-003 (2026-07-30): LLM phrases only, never computes.
- D-004 (2026-08-15): Scope expanded to New York (NY). Web dashboard is NY-first (county selector filtered to NY, default Genesee/36037). Batch pipeline `INSCOPE_STATES` now {NE, IA, KS, NY}; ingest `run.py` supports `--state` scoping. NE/IA/KS retained for backward compatibility.
- D-005 (2026-08-15): USDA Drought Monitor statistics API (`usdmdataservices.unl.edu`) now returns **CSV**, not XML. `app/ingest/usdm.py` rewritten to parse CSV (`_parse_usdm_csv`); the old XML parser was removed. ValidEnd is used as `week_ending`; dominant level = highest D-band with coverage > 0. Unit test `test_usdm_parse` covers NONE/D1/D2 cases.
- D-006 (2026-08-15): Scope superseded — **New York is now the SOLE target state.** Supersedes D-004's NE/IA/KS retention. New work should treat `INSCOPE_STATES` as {NY}; existing NE/IA/KS advisory rows in the DB are legacy/stale and excluded from the dashboard. Reason: product focus narrowed to NY (62 counties) for v1.
- D-007 (2026-08-15): M6 frontend login uses **email + password (Argon2id)** instead of SMS OTP. Reason: the OTP backend (Twilio send/verify + `app/delivery/sender.py`) is not yet built, while `app/auth/routes.py` already exposes working `register`/`login` endpoints that satisfy the secure-dashboard requirement now. OTP/WebAuthn passkeys deferred to a later milestone.
- D-008 (2026-08-15): Dev bypass `FURROWCAST_DEV_PUBLIC=1`. When set, `require_auth` returns a dev user so protected routes (`/api/advisory`, `/api/outbox`, `/api/stats`) are public for local development (frontend login UI not yet wired). MUST NOT be set in CI or production.
