@echo off
cd /d "%~dp0"
set RUNR_PORT=4000
start "" .venv\Scripts\pythonw.exe app_files\tray_app.py
