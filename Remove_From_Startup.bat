@echo off
:: Removes RUNR from Windows Startup

set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_NAME=RUNR Tray.lnk"

echo Removing RUNR from Windows startup...

if exist "%STARTUP_FOLDER%\%SHORTCUT_NAME%" (
    del "%STARTUP_FOLDER%\%SHORTCUT_NAME%"
    echo.
    echo SUCCESS! RUNR removed from Windows startup.
) else (
    echo.
    echo RUNR was not in the startup folder.
)
echo.
pause
