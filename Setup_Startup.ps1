# RUNR Startup Setup Script
# This script adds RUNR to Windows startup so it runs automatically when you log in

$AppName = "RUNR"
$AppPath = $PSScriptRoot
$VbsPath = Join-Path $AppPath "Run_Tray.vbs"
$StartupFolder = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $StartupFolder "$AppName.lnk"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  RUNR Startup Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if VBS file exists
if (-Not (Test-Path $VbsPath)) {
    Write-Host "ERROR: Run_Tray.vbs not found at: $VbsPath" -ForegroundColor Red
    Write-Host "Please ensure you're running this script from the RUNR folder." -ForegroundColor Yellow
    pause
    exit 1
}

# Install required packages first
Write-Host "Installing required packages..." -ForegroundColor Yellow
pip install pystray Pillow --quiet
Write-Host "Packages installed." -ForegroundColor Green
Write-Host ""

# Create shortcut
Write-Host "Creating startup shortcut..." -ForegroundColor Yellow

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "wscript.exe"
$Shortcut.Arguments = "`"$VbsPath`""
$Shortcut.WorkingDirectory = $AppPath
$Shortcut.Description = "RUNR - Auto Promotion Tool"
$Shortcut.Save()

Write-Host ""
Write-Host "SUCCESS!" -ForegroundColor Green
Write-Host "RUNR will now start automatically when you log into Windows." -ForegroundColor Green
Write-Host ""
Write-Host "Shortcut created at:" -ForegroundColor Cyan
Write-Host "  $ShortcutPath" -ForegroundColor White
Write-Host ""
Write-Host "To remove from startup, delete the shortcut from:" -ForegroundColor Yellow
Write-Host "  $StartupFolder" -ForegroundColor White
Write-Host ""
Write-Host "To start RUNR now, run: Run_Tray.bat" -ForegroundColor Cyan
Write-Host ""
pause
