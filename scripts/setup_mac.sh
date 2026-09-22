#!/usr/bin/env bash
# FURROWCAST — one-command macOS setup (Intel or Apple Silicon).
#
# Installs everything needed for local development and leaves a running stack:
#   Homebrew → Docker (colima) → Python 3.12 → Node 18+ → backend venv → npm deps
#   → database up → migrations → seed
#
# Idempotent: safe to re-run any time (skips what's already installed).
#
# Usage:  ./scripts/setup_mac.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV="$REPO_DIR/backend/.venv"
DATABASE_URL="postgresql+psycopg2://user:password@127.0.0.1:5432/furrowcast"

step() { printf "\n[%s] %s\n" "$STEP_NUM" "$1"; STEP_NUM=$((STEP_NUM + 1)); }

brew_cmd() {
    if [ -x /opt/homebrew/bin/brew ]; then
        /opt/homebrew/bin/brew
    elif [ -x /usr/local/bin/brew ]; then
        /usr/local/bin/brew
    else
        return 1
    fi
}

echo "=============================================="
echo "  FurrowCast — macOS setup"
echo "=============================================="
STEP_NUM=1

# ---------------------------------------------------------------------------
# 1. Homebrew
# ---------------------------------------------------------------------------
step "Homebrew"
if brew_cmd >/dev/null 2>&1; then
    echo "  Already installed."
else
    echo "  Installing Homebrew (may prompt for your password)..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
BREW="$(brew_cmd)"
export PATH="$(dirname "$BREW"):$PATH"

# ---------------------------------------------------------------------------
# 2. Docker engine (colima + docker CLI) with `docker compose` plugin
# ---------------------------------------------------------------------------
step "Docker engine"
if docker info >/dev/null 2>&1; then
    echo "  A Docker engine is already running (Docker Desktop or colima)."
else
    if ! command -v docker >/dev/null 2>&1 || ! command -v colima >/dev/null 2>&1; then
        "$BREW" install docker colima docker-compose
    fi
    if ! docker compose version >/dev/null 2>&1; then
        echo "  Enabling 'docker compose' plugin..."
        mkdir -p "$HOME/.docker/cli-plugins"
        ln -sfn "$("$BREW" --prefix)/opt/docker-compose/bin/docker-compose" \
            "$HOME/.docker/cli-plugins/docker-compose"
    fi
    colima start
    echo "  colima is running."
fi

# ---------------------------------------------------------------------------
# 3. Python 3.12
# ---------------------------------------------------------------------------
step "Python 3.12"
if command -v python3.12 >/dev/null 2>&1; then
    PY="$(command -v python3.12)"
    echo "  Using $PY"
else
    "$BREW" install python@3.12
    PY="$("$BREW" --prefix python@3.12)/bin/python3.12"
    echo "  Using $PY"
fi

# ---------------------------------------------------------------------------
# 4. Node.js 18+
# ---------------------------------------------------------------------------
step "Node.js"
if command -v node >/dev/null 2>&1 && [ "$(node -v | sed 's/^v//' | cut -d. -f1)" -ge 18 ]; then
    echo "  Using $(node -v)"
else
    if ! command -v node >/dev/null 2>&1; then
        "$BREW" install node
    else
        echo "  node found but < 18 — upgrading via 'brew upgrade node'"
        "$BREW" upgrade node
    fi
fi

# ---------------------------------------------------------------------------
# 5. Backend venv + Python deps
# ---------------------------------------------------------------------------
step "Backend venv + deps"
if [ ! -x "$VENV/bin/python" ]; then
    "$PY" -m venv "$VENV"
    echo "  Created venv at $VENV"
fi
"$VENV/bin/pip" install --upgrade pip >/dev/null
"$VENV/bin/pip" install -r "$REPO_DIR/backend/requirements.txt"

# ---------------------------------------------------------------------------
# 6. Frontend npm deps
# ---------------------------------------------------------------------------
step "Frontend npm deps"
(cd "$REPO_DIR/web" && npm install)

# ---------------------------------------------------------------------------
# 7. Database up + migrations + seed
# ---------------------------------------------------------------------------
step "Database (up + migrate + seed)"
(cd "$REPO_DIR" && docker compose up -d db)
until (cd "$REPO_DIR" && docker compose exec -T db pg_isready -U user -d furrowcast -h 127.0.0.1 >/dev/null 2>&1); do
    sleep 2
done
echo "  Database is ready."
export DATABASE_URL="$DATABASE_URL"
(cd "$REPO_DIR/backend" && "$VENV/bin/alembic" upgrade head)
(cd "$REPO_DIR/backend" && "$VENV/bin/python" -m app.db.seed)

# ---------------------------------------------------------------------------
echo ""
echo "=============================================="
echo "  Setup complete. Next steps:"
echo "=============================================="
echo ""
echo "  make dev              # DB + backend with reload"
echo "  cd web && npm run dev # frontend at http://localhost:3000"
echo ""
echo "  Or one-shot: ./start.sh   (DB + backend + frontend)"
echo ""
echo "  All-in-one tests:  make test && make lint"
echo "=============================================="