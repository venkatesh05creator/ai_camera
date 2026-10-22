@echo off
title OwnerAI Face Recognition Studio
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found in .venv.
    echo Please create it using: py -3.13 -m venv .venv
    pause
    exit /b 1
)

set TF_ENABLE_ONEDNN_OPTS=0
.\.venv\Scripts\python.exe main.py %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application exited with code %ERRORLEVEL%.
    pause
)
