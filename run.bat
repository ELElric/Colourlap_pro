@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv not found. Please create venv first.
    pause
    exit /b 1
)

echo Starting ColorLab Pro from %cd% ...
.venv\Scripts\python.exe scripts\run_app.py
if errorlevel 1 (
    echo.
    echo [ERROR] Application exited with error code %errorlevel%.
    pause
)
