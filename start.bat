@echo off
REM ═══════════════════════════════════════════════════════════════
REM  AML Investigation System - Windows Startup Script
REM  National Bank of Ethiopia
REM  Usage: .\start.bat
REM ═══════════════════════════════════════════════════════════════

set ROOT=%~dp0
set BACKEND_PORT=4000

echo.
echo  AML Investigation System
echo  National Bank of Ethiopia
echo.

REM ── Start FastAPI Backend ─────────────────────────────────────
echo [1/2] Starting FastAPI Backend on port %BACKEND_PORT%...

cd /d "%ROOT%crypto-aml-tracker\backend-py"

REM Create venv if it doesn't exist
if not exist "venv\Scripts\python.exe" (
    echo     Creating Python virtual environment...
    python -m venv venv
)

REM Check and install required packages
echo     Checking required packages...
venv\Scripts\python.exe -c "import fastapi, pandas, aiomysql, motor, neo4j, apscheduler" 2>nul
if errorlevel 1 (
    echo     Installing required packages...
    venv\Scripts\pip.exe install fastapi uvicorn motor neo4j sqlalchemy pymysql aiomysql apscheduler python-dotenv cryptography pandas -q
)

start "AML Backend" cmd /k "cd /d %ROOT%crypto-aml-tracker\backend-py && venv\Scripts\activate.bat && set PORT=%BACKEND_PORT% && python main.py"

cd /d "%ROOT%"
echo     Backend window opened.
timeout /t 5 /nobreak >nul

REM ── Start React Frontend ──────────────────────────────────────
echo [2/2] Starting React Frontend on port 5173...

cd /d "%ROOT%crypto-aml-tracker"

if not exist "node_modules" (
    echo     Installing npm packages...
    npm install
)

start "AML Frontend" cmd /k "cd /d %ROOT%crypto-aml-tracker && npm run dev"
cd /d "%ROOT%"

timeout /t 3 /nobreak >nul

echo.
echo  SYSTEM READY
echo.
echo  Backend  - http://localhost:%BACKEND_PORT%
echo  Frontend - http://localhost:5173
echo  Network  - http://172.20.72.194:5173
echo.
echo  Both services are running in separate windows.
echo  Close those windows to stop the services.
echo.
pause
