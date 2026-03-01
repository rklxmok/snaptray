# SnapTray Windows Installer
# Installs snapclient + SnapTray app with auto-start on login.

$ErrorActionPreference = "Stop"

$AppName = "SnapcastTray"
$InstallDir = Join-Path $env:APPDATA $AppName
$SnapcastDir = "C:\Program Files\Snapcast"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$StartupDir = [Environment]::GetFolderPath("Startup")
$SnapcastZipUrl = "https://github.com/badaix/snapcast/releases/download/v0.28.0/snapcast_0.28.0_win64.zip"

Write-Host "=== SnapTray Windows Installer ===" -ForegroundColor Cyan
Write-Host ""

# [1/6] Check Python
Write-Host "[1/6] Checking Python..." -ForegroundColor Yellow

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $python) {
    Write-Host "  ERROR: Python not found." -ForegroundColor Red
    Write-Host "  Install with:  winget install Python.Python.3.12" -ForegroundColor Red
    Write-Host "  Then close and reopen PowerShell." -ForegroundColor Red
    exit 1
}

$pyCmd = $python.Name
$pyVersion = & $pyCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
Write-Host "  Python: $pyVersion"

# Check PyQt5
$pyqt5Check = & $pyCmd -c "from PyQt5.QtWidgets import QSystemTrayIcon" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  PyQt5 not found. Installing..." -ForegroundColor Yellow
    & $pyCmd -m pip install PyQt5
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: Failed to install PyQt5. Run: pip install PyQt5" -ForegroundColor Red
        exit 1
    }
}
Write-Host "  PyQt5: OK" -ForegroundColor Green

# [2/6] Install snapclient
Write-Host "[2/6] Checking snapclient..." -ForegroundColor Yellow

$snapclient = Get-Command snapclient.exe -ErrorAction SilentlyContinue
if (-not $snapclient) {
    # Check common install location
    if (Test-Path "$SnapcastDir\snapclient.exe") {
        $snapclient = "$SnapcastDir\snapclient.exe"
    }
}

if (-not $snapclient) {
    Write-Host "  snapclient not found. Downloading..." -ForegroundColor Yellow
    $tempZip = Join-Path $env:TEMP "snapcast_win64.zip"
    $tempExtract = Join-Path $env:TEMP "snapcast_extract"

    # Download
    Write-Host "  Downloading from $SnapcastZipUrl..."
    curl.exe -L -o $tempZip $SnapcastZipUrl --progress-bar
    if (-not (Test-Path $tempZip)) {
        Write-Host "  ERROR: Download failed." -ForegroundColor Red
        exit 1
    }

    # Extract
    if (Test-Path $tempExtract) { Remove-Item $tempExtract -Recurse -Force }
    Expand-Archive $tempZip -DestinationPath $tempExtract -Force

    # Find the snapclient folder (may be nested)
    $snapclientExe = Get-ChildItem -Path $tempExtract -Recurse -Filter "snapclient.exe" | Select-Object -First 1
    if (-not $snapclientExe) {
        Write-Host "  ERROR: snapclient.exe not found in archive." -ForegroundColor Red
        exit 1
    }
    $sourceDir = $snapclientExe.DirectoryName

    # Install VC++ runtime if present
    $vcRedist = Get-ChildItem -Path $sourceDir -Filter "vc_redist*.exe" | Select-Object -First 1
    if ($vcRedist) {
        Write-Host "  Installing Visual C++ runtime..."
        Start-Process $vcRedist.FullName -ArgumentList "/install", "/quiet", "/norestart" -Wait -ErrorAction SilentlyContinue
    }

    # Copy to Program Files
    Write-Host "  Installing to $SnapcastDir..."
    if (-not (Test-Path $SnapcastDir)) {
        New-Item -ItemType Directory -Path $SnapcastDir -Force | Out-Null
    }
    Copy-Item "$sourceDir\*" $SnapcastDir -Force -Exclude "vc_redist*"

    # Add to PATH if not already there
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($currentPath -notlike "*$SnapcastDir*") {
        [Environment]::SetEnvironmentVariable("Path", "$currentPath;$SnapcastDir", "User")
        $env:Path = "$env:Path;$SnapcastDir"
        Write-Host "  Added $SnapcastDir to PATH"
    }

    # Cleanup
    Remove-Item $tempZip -Force -ErrorAction SilentlyContinue
    Remove-Item $tempExtract -Recurse -Force -ErrorAction SilentlyContinue

    Write-Host "  snapclient: installed" -ForegroundColor Green
} else {
    Write-Host "  snapclient: OK" -ForegroundColor Green
}

# Verify snapclient works
$scVer = & "$SnapcastDir\snapclient.exe" --version 2>&1
Write-Host "  Version: $scVer"

# [3/6] Install SnapTray app
Write-Host "[3/6] Installing SnapTray to $InstallDir..." -ForegroundColor Yellow
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}
Copy-Item (Join-Path $ScriptDir "snapcast_tray.py") (Join-Path $InstallDir "snapcast_tray.py") -Force
Write-Host "  Installed: $InstallDir\snapcast_tray.py"

# [4/6] Find pythonw for windowless execution
Write-Host "[4/6] Locating pythonw..." -ForegroundColor Yellow
$pythonw = Get-Command pythonw -ErrorAction SilentlyContinue
if (-not $pythonw) {
    $pythonw = Get-Command pythonw3 -ErrorAction SilentlyContinue
}
if ($pythonw) {
    $pythonwPath = $pythonw.Source
    Write-Host "  Found: $pythonwPath"
} else {
    $pythonwPath = $python.Source
    Write-Host "  pythonw not found, using python (console window may appear briefly)"
}

# [5/6] Create startup shortcut
Write-Host "[5/6] Creating startup shortcut..." -ForegroundColor Yellow
$shortcutPath = Join-Path $StartupDir "SnapTray.lnk"
$wshShell = New-Object -ComObject WScript.Shell
$shortcut = $wshShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonwPath
$shortcut.Arguments = "`"$(Join-Path $InstallDir 'snapcast_tray.py')`""
$shortcut.WorkingDirectory = $InstallDir
$shortcut.Description = "Snapcast Tray - System tray app for Snapcast"
$shortcut.Save()
Write-Host "  Created: $shortcutPath"

# [6/6] Launch now
Write-Host "[6/6] Starting SnapTray..." -ForegroundColor Yellow
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
Write-Host "  snapclient: $SnapcastDir"
Write-Host "  Config: $InstallDir\snapcast-tray.json"
Write-Host ""
