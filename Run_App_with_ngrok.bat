@echo off
REM Get the directory where this batch file is located
SET "SCRIPT_DIR=%~dp0"

REM Define the path to the PowerShell script
SET "PS_SCRIPT=%SCRIPT_DIR%start_and_show_url.ps1"

REM Check if the PowerShell script exists
IF NOT EXIST "%PS_SCRIPT%" (
    ECHO ERROR: PowerShell script not found at %PS_SCRIPT%
    PAUSE
    EXIT /B 1
)

ECHO Starting application, ngrok tunnel, and URL retrieval...
ECHO A PowerShell window will open to manage the processes.

REM Run the PowerShell script, bypassing the execution policy for this process
REM The -NoExit flag might keep the powershell window open after script completes
powershell.exe -ExecutionPolicy Bypass -File "%PS_SCRIPT%"

ECHO Application and tunnel processes are managed by the PowerShell window.
ECHO Closing this launcher window.
REM Removed PAUSE so this launcher window closes quickly once PowerShell takes over. 