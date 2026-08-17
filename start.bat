@echo off
title FurrowCast - Starting all services...

echo ========================================
echo   FurrowCast - Starting all services
echo ========================================
echo.

:: Navigate to project directory
cd /d "%~dp0"

:: Start PostgreSQL database
echo [1/4] Starting PostgreSQL database...
docker compose up -d
timeout /t 5 /nobreak >nul

:: Wait for database to be ready
echo [2/4] Waiting for database to be ready...
:waitdb
docker compose exec -T db pg_isready -U user -d furrowcast -h 127.0.0.1 >nul 2>&1
if %errorlevel% neq 0 (
    timeout /t 2 /nobreak >nul
    goto waitdb
)
echo       Database is ready!

:: Start backend server
echo [3/4] Starting backend server on port 8000...
set DATABASE_URL=postgresql+psycopg2://user:password@127.0.0.1:5432/furrowcast
start "FurrowCast Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
timeout /t 5 /nobreak >nul

:: Start frontend server
echo [4/4] Starting frontend server on port 3000...
start "FurrowCast Frontend" cmd /k "cd /d %~dp0web && npm run dev"

echo.
echo ========================================
echo   All services started!
echo ========================================
echo.
echo   Backend API:  http://localhost:8000
echo   API Docs:     http://localhost:8000/docs
echo   Frontend:     http://localhost:3000
echo.
echo   Press any key to open the dashboard in your browser...
pause >nul
start http://localhost:3000
