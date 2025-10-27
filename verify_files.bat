@echo off
echo ========================================
echo   Verifying Files Before Deploy
echo ========================================
echo.

set "all_exist=true"

echo Checking critical files...
echo.

if exist "config\services_catalog.json" (
    echo [OK] config\services_catalog.json
) else (
    echo [MISSING] config\services_catalog.json
    set "all_exist=false"
)

if exist "app_files\app.py" (
    echo [OK] app_files\app.py
) else (
    echo [MISSING] app_files\app.py
    set "all_exist=false"
)

if exist "app_files\templates\services.html" (
    echo [OK] app_files\templates\services.html
) else (
    echo [MISSING] app_files\templates\services.html
    set "all_exist=false"
)

if exist "app_files\templates\profiles.html" (
    echo [OK] app_files\templates\profiles.html
) else (
    echo [MISSING] app_files\templates\profiles.html
    set "all_exist=false"
)

if exist "app_files\static\script.js" (
    echo [OK] app_files\static\script.js
) else (
    echo [MISSING] app_files\static\script.js
    set "all_exist=false"
)

if exist "app_files\services_catalog.py" (
    echo [OK] app_files\services_catalog.py
) else (
    echo [MISSING] app_files\services_catalog.py
    set "all_exist=false"
)

echo.
if "%all_exist%"=="true" (
    echo ========================================
    echo   All files present! Ready to deploy.
    echo ========================================
    echo.
    echo Run "deploy.bat" to commit and push.
) else (
    echo ========================================
    echo   WARNING: Some files are missing!
    echo ========================================
)

echo.
pause
