@echo off
title OwnerAI Face Recognition Studio
cd /d "%~dp0"

set PYTHON_BIN=python
if exist ".venv\Scripts\python.exe" (
    set PYTHON_BIN=.\.venv\Scripts\python.exe
)

set TF_ENABLE_ONEDNN_OPTS=0
%PYTHON_BIN% main.py %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application exited with code %ERRORLEVEL%.
    pause
)
