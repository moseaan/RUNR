@echo off
REM Get the directory where this batch file is located
SET "SCRIPT_DIR=%~dp0"
SET "VENV_PYTHON=%SCRIPT_DIR%.venv\Scripts\python.exe"
SET "APP_FILES_DIR=%SCRIPT_DIR%app_files"
REM *** IMPORTANT: Adjust this line if your Flask app is in main_app.py instead of app.py ***
SET "APP_MODULE=app:app"
SET "HOST=0.0.0.0"
SET "PORT=5000"

ECHO Starting Flask application locally using Waitress from %APP_FILES_DIR% ...

REM Check if venv Python executable exists
IF NOT EXIST "%VENV_PYTHON%" (
    ECHO ERROR: Python executable not found at %VENV_PYTHON%
    ECHO Please ensure the virtual environment exists and is correctly set up in the '.venv' folder.
    PAUSE
    EXIT /B 1
)

REM Check if app file exists inside app_files (use the module name prefix)
SET "APP_FILE_NAME=%APP_MODULE::=:%.py"
IF NOT EXIST "%APP_FILES_DIR%\%APP_FILE_NAME%" (
    ECHO WARNING: Application file %APP_FILES_DIR%\%APP_FILE_NAME% not found. Waitress might fail.
)

REM Set PYTHONPATH - Still needed so waitress running via python can find the module
ECHO Setting PYTHONPATH to include %APP_FILES_DIR%
SET "PYTHONPATH=%APP_FILES_DIR%;%PYTHONPATH%" 

ECHO ============================================================
ECHO  Starting Waitress server for %APP_MODULE% (found in app_files)
ECHO  Using Python: %VENV_PYTHON%
ECHO  Listening on: http://%HOST%:%PORT%
ECHO  Access this from other devices on your network using:
ECHO  http://<Your-Computer-IP-Address>:%PORT%
ECHO  (Find your IP using 'ipconfig' in Command Prompt)
ECHO ============================================================
ECHO.
ECHO Press Ctrl+C in this window to stop the server.
ECHO.

REM Run Waitress server as a module using the venv's Python
"%VENV_PYTHON%" -m waitress --host %HOST% --port %PORT% %APP_MODULE%

ECHO Waitress server stopped.
PAUSE 