#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Function to check if a port is available
port_available() {
    local port=$1
    if ss -tlnp 2>/dev/null | grep -q ":${port} "; then
        return 1  # Port is in use
    else
        return 0  # Port is available
    fi
}

# Function to find an available port starting from the given port
find_available_port() {
    local port=$1
    while ! port_available $port; do
        port=$((port + 1))
    done
    echo $port
}

echo "========================================"
echo "  FurrowCast - Starting all services"
echo "========================================"
echo ""

# Start PostgreSQL database
echo "[1/4] Starting PostgreSQL database..."
docker compose up -d
sleep 5

# Wait for database to be ready
echo "[2/4] Waiting for database to be ready..."
until docker compose exec -T db pg_isready -U user -d furrowcast -h 127.0.0.1 > /dev/null 2>&1; do
    sleep 2
done
echo "      Database is ready!"

# Find available ports
BACKEND_PORT=$(find_available_port 8000)
FRONTEND_PORT=$(find_available_port 3000)

# Start backend server
echo "[3/4] Starting backend server on port $BACKEND_PORT..."
export DATABASE_URL="postgresql+psycopg2://user:password@127.0.0.1:5432/furrowcast"
cd "$SCRIPT_DIR/backend"
nohup "$SCRIPT_DIR/backend/.venv/bin/python3.12" -m uvicorn app.main:app --reload --host 0.0.0.0 --port $BACKEND_PORT > /tmp/backend.log 2>&1 &
BACKEND_PID=$!
cd "$SCRIPT_DIR"
sleep 3

# Start frontend server
echo "[4/4] Starting frontend server on port $FRONTEND_PORT..."
cd "$SCRIPT_DIR/web"
PORT=$FRONTEND_PORT nohup npm run dev > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!
cd "$SCRIPT_DIR"
sleep 5

echo ""
echo "========================================"
echo "  All services started!"
echo "========================================"
echo ""
echo "  Backend API:  http://localhost:$BACKEND_PORT"
echo "  API Docs:     http://localhost:$BACKEND_PORT/docs"
echo "  Frontend:     http://localhost:$FRONTEND_PORT"
echo ""
echo "  Press Ctrl+C to stop all services"
echo ""

# Handle cleanup on exit
cleanup() {
    echo ""
    echo "Stopping services..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
    echo "Done."
}
trap cleanup EXIT INT TERM

# Keep script running
echo "Services are running. Press Ctrl+C to stop."
while true; do
    sleep 10
done