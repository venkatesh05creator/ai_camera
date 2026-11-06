@echo off
REM Aegis AI - one-command start (Windows).
REM 1. ensures a venv with pinned deps   2. kills any stale server on :8000
REM 3. runs alembic migrations           4. serves API+PWA on 127.0.0.1:8000
setlocal
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
  echo [aegis] creating Python 3.13 venv...
  py -3.13 -m venv .venv || goto :fail
  echo [aegis] installing pinned dependencies...
  .venv\Scripts\python.exe -m pip install --upgrade pip >nul
  .venv\Scripts\python.exe -m pip install -r requirements-server.txt || goto :fail
)

REM kill anything already holding the port (stale server from a previous run)
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:"TCP .*127.0.0.1:8000.*LISTENING"') do (
  echo [aegis] stopping stale process %%p on port 8000
  taskkill /PID %%p /F >nul 2>&1
)

echo [aegis] running database migrations...
.venv\Scripts\python.exe -m alembic upgrade head || goto :fail

echo [aegis] starting on http://127.0.0.1:8000  (Ctrl+C to stop)
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
goto :eof

:fail
exit /b 1
