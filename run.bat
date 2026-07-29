@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe scripts\run_pywebview.py
) else (
    python scripts\run_pywebview.py
)
