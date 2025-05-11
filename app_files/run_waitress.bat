@echo off
ECHO Starting Waitress server...

REM Activate virtual environment
CALL .venv\Scripts\activate

REM Check if activation was successful (optional but good practice)
IF ERRORLEVEL 1 (
    ECHO Failed to activate virtual environment. Make sure .venv exists and is set up correctly.
    PAUSE
    EXIT /B 1
)

REM Run Waitress using python -m
ECHO Running Waitress on http://0.0.0.0:5000
python -m waitress --host=0.0.0.0 --port=5000 app:app

REM Keep the window open after server stops/errors
PAUSE 