@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ColorLab Pro Launcher
:: Double-click to start the application.

cd /d "%~dp0"

echo ===========================================
echo   ColorLab Pro Launcher
echo ===========================================
echo.

:: Check virtual environment
set "PYTHON=.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo [ERROR] Virtual environment not found.
    echo.
    echo Please create it first:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

:: Check entry script
if not exist "scripts\run_app.py" (
    echo [ERROR] Entry script not found: scripts\run_app.py
    echo.
    echo Make sure run.bat is in the project root directory.
    echo.
    pause
    exit /b 1
)

:: Show startup info
echo Working dir : %cd%
echo Python      : %PYTHON%
echo Entry       : scripts\run_app.py
echo.
echo Starting ColorLab Pro...
echo ===========================================
echo.

:: Launch
"%PYTHON%" scripts\run_app.py

set "EXITCODE=%errorlevel%"

if %EXITCODE% neq 0 (
    echo.
    echo [ERROR] Application exited with code %EXITCODE%.
    echo.
    pause
)

endlocal
exit /b %EXITCODE%
