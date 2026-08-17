#!/usr/bin/env bash
# FurrowCast nightly pipeline runner for cron.
# Usage: scripts/nightly.sh [YYYY-MM-DD]
# Installed via crontab (see README): 0 5 * * * /path/to/furrowcast/scripts/nightly.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$REPO_DIR/backend/.venv"

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "FurrowCast nightly: venv not found at $VENV" >&2
  exit 1
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "FurrowCast nightly: DATABASE_URL is not set" >&2
  exit 1
fi

RUN_DATE="${1:-$(date -u -d 'yesterday' +%Y-%m-%d)}"
SMS_FLAG=""
if [[ "${FURROWCAST_NIGHTLY_SMS:-0}" == "1" ]]; then
  SMS_FLAG="--sms"
fi

cd "$REPO_DIR/backend"
"$VENV/bin/python" -m app.nightly --date "$RUN_DATE" --state NY $SMS_FLAG