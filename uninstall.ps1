# SnapTray Windows Uninstaller

$ErrorActionPreference = "SilentlyContinue"

$AppName = "SnapcastTray"
$InstallDir = Join-Path $env:APPDATA $AppName
$StartupDir = [Environment]::GetFolderPath("Startup")

Write-Host "=== SnapTray Uninstaller ===" -ForegroundColor Cyan
Write-Host ""

# Stop running instances
Write-Host "Stopping SnapTray..." -ForegroundColor Yellow
Get-Process -Name pythonw, python | Where-Object {
    $_.CommandLine -like "*snapcast_tray*"
} | Stop-Process -Force 2>$null

# Remove startup shortcut
Write-Host "Removing startup shortcut..." -ForegroundColor Yellow
$shortcutPath = Join-Path $StartupDir "SnapTray.lnk"
if (Test-Path $shortcutPath) {
    Remove-Item $shortcutPath -Force
    Write-Host "  Removed: $shortcutPath"
} else {
    Write-Host "  No startup shortcut found"
}

# Remove app files
Write-Host "Removing app files..." -ForegroundColor Yellow
$appFile = Join-Path $InstallDir "snapcast_tray.py"
if (Test-Path $appFile) {
    Remove-Item $appFile -Force
    Write-Host "  Removed: $appFile"
} else {
    Write-Host "  No app file found"
}

Write-Host ""
Write-Host "SnapTray uninstalled." -ForegroundColor Green
Write-Host "Config file preserved at: $InstallDir\snapcast-tray.json"
Write-Host "Delete the folder manually if you want a clean removal:"
Write-Host "  $InstallDir"
Write-Host ""
