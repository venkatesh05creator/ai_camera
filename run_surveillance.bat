@echo off
title AI Surveillance Platform - Privacy-First Security Center
cd /d "%~dp0"

echo =======================================================
echo    FULL-STACK PRIVACY-FIRST AI SURVEILLANCE PLATFORM    
echo =======================================================
echo.
echo Starting FastAPI Backend + React TS Dashboard...
echo Dashboard URL: http://127.0.0.1:8000
echo Auth:          Owner credentials configured in .env
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found in .venv.
    echo Please install dependencies or run: py -3.13 -m venv .venv
    pause
    exit /b 1
)

set TF_ENABLE_ONEDNN_OPTS=0
start "" "http://127.0.0.1:8000"
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Server stopped with exit code %ERRORLEVEL%.
    pause
)
