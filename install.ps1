# SnapTray Windows Installer
# Installs Snapcast Tray app with auto-start on login.

$ErrorActionPreference = "Stop"

$AppName = "SnapcastTray"
$InstallDir = Join-Path $env:APPDATA $AppName
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$StartupDir = [Environment]::GetFolderPath("Startup")

Write-Host "=== SnapTray Windows Installer ===" -ForegroundColor Cyan
Write-Host ""

# [1/5] Check Python
Write-Host "[1/5] Checking dependencies..." -ForegroundColor Yellow

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $python) {
    Write-Host "  ERROR: Python not found. Install Python 3.8+ from https://python.org" -ForegroundColor Red
    Write-Host "  Make sure to check 'Add Python to PATH' during install." -ForegroundColor Red
    exit 1
}

$pyCmd = $python.Name
$pyVersion = & $pyCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
Write-Host "  Python: $pyVersion"

# Check PyQt5
$pyqt5Check = & $pyCmd -c "from PyQt5.QtWidgets import QSystemTrayIcon" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  PyQt5 not found. Installing..." -ForegroundColor Yellow
    & $pyCmd -m pip install PyQt5
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: Failed to install PyQt5. Run: pip install PyQt5" -ForegroundColor Red
        exit 1
    }
}
Write-Host "  PyQt5: OK" -ForegroundColor Green

# Check snapclient
$snapclient = Get-Command snapclient.exe -ErrorAction SilentlyContinue
if (-not $snapclient) {
    # Check common install locations
    $commonPaths = @(
        "C:\Program Files\Snapcast\snapclient.exe",
        "C:\Program Files (x86)\Snapcast\snapclient.exe",
        "$env:LOCALAPPDATA\Snapcast\snapclient.exe"
    )
    foreach ($p in $commonPaths) {
        if (Test-Path $p) {
            $snapclient = $p
            break
        }
    }
}
if (-not $snapclient) {
    Write-Host ""
    Write-Host "  WARNING: snapclient.exe not found." -ForegroundColor Yellow
    Write-Host "  SnapTray can still control volume via the server API,"
    Write-Host "  but connect/disconnect won't work without snapclient installed."
    Write-Host "  Download: https://github.com/badaix/snapcast/releases"
    Write-Host ""
} else {
    Write-Host "  snapclient: OK" -ForegroundColor Green
}

# [2/5] Install app
Write-Host "[2/5] Installing to $InstallDir..." -ForegroundColor Yellow
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}
Copy-Item (Join-Path $ScriptDir "snapcast_tray.py") (Join-Path $InstallDir "snapcast_tray.py") -Force
Write-Host "  Installed: $InstallDir\snapcast_tray.py"

# [3/5] Find pythonw for windowless execution
Write-Host "[3/5] Locating pythonw..." -ForegroundColor Yellow
$pythonw = Get-Command pythonw -ErrorAction SilentlyContinue
if (-not $pythonw) {
    $pythonw = Get-Command pythonw3 -ErrorAction SilentlyContinue
}
if ($pythonw) {
    $pythonwPath = $pythonw.Source
    Write-Host "  Found: $pythonwPath"
} else {
    # Fall back to python (will show console window briefly)
    $pythonwPath = $python.Source
    Write-Host "  pythonw not found, using python (console window may appear briefly)"
}

# [4/5] Create startup shortcut
Write-Host "[4/5] Creating startup shortcut..." -ForegroundColor Yellow
$shortcutPath = Join-Path $StartupDir "SnapTray.lnk"
$wshShell = New-Object -ComObject WScript.Shell
$shortcut = $wshShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonwPath
$shortcut.Arguments = "`"$(Join-Path $InstallDir 'snapcast_tray.py')`""
$shortcut.WorkingDirectory = $InstallDir
$shortcut.Description = "Snapcast Tray - System tray app for Snapcast"
$shortcut.Save()
Write-Host "  Created: $shortcutPath"

# [5/5] Launch now
Write-Host "[5/5] Starting SnapTray..." -ForegroundColor Yellow
Start-Process $pythonwPath -ArgumentList "`"$(Join-Path $InstallDir 'snapcast_tray.py')`"" -WorkingDirectory $InstallDir
Start-Sleep -Seconds 2

$proc = Get-Process -Name pythonw -ErrorAction SilentlyContinue
if (-not $proc) {
    $proc = Get-Process -Name python -ErrorAction SilentlyContinue
}
if ($proc) {
    Write-Host "  SnapTray is running!" -ForegroundColor Green
} else {
    Write-Host "  Process started. Check system tray for the speaker icon."
}

Write-Host ""
Write-Host "=== Installation Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Tray icon should appear in your system tray."
Write-Host "  Right-click for volume, mute, server, and connect/disconnect."
Write-Host ""
Write-Host "  SnapTray will auto-start on login."
Write-Host "  Config saved to: $InstallDir\snapcast-tray.json"
Write-Host ""
