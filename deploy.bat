@echo off
echo ========================================
echo   Deploying to Render.com
echo ========================================
echo.

echo Step 1: Adding all changes to git...
git add .

echo.
echo Step 2: Showing what will be committed...
git status

echo.
echo Step 3: Committing changes...
git commit -m "Update services config and add import/export features"

echo.
echo Step 4: Pushing to remote repository...
git push

echo.
echo ========================================
echo   Deploy Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Go to Render.com dashboard
echo 2. Wait for automatic deploy to finish
echo 3. Open your app and check Services page
echo 4. Import button should now be visible
echo 5. Services should show correct values
echo.
echo If services are still wrong after deploy:
echo - Click "Export Configs" on local machine
echo - Click "Import Configs" on Render website
echo - Upload the exported file
echo.
pause
