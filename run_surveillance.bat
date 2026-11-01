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

set PYTHON_BIN=python
if exist ".venv\Scripts\python.exe" (
    set PYTHON_BIN=.\.venv\Scripts\python.exe
)

set TF_ENABLE_ONEDNN_OPTS=0
start "" "http://127.0.0.1:8000"
%PYTHON_BIN% -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Server stopped with exit code %ERRORLEVEL%.
    pause
)
