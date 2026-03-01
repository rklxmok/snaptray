#!/bin/bash
# SnapTray Installer
# Installs Snapcast Tray app with systemd user service and autostart.

set -e

APP_NAME="snapcast_tray"
INSTALL_DIR="$HOME/.local/bin"
SERVICE_DIR="$HOME/.config/systemd/user"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== SnapTray Installer ==="
echo ""

# Check dependencies
echo "[1/5] Checking dependencies..."

if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Install Python 3.8+."
    exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  Python: $PY_VERSION"

# Check PyQt5
if ! python3 -c "from PyQt5.QtWidgets import QSystemTrayIcon" 2>/dev/null; then
    echo ""
    echo "  PyQt5 not found. Attempting to install..."
    if command -v pip3 &>/dev/null; then
        pip3 install --user PyQt5
    elif command -v pip &>/dev/null; then
        pip install --user PyQt5
    else
        echo ""
        echo "  Cannot install PyQt5 automatically. Install it manually:"
        echo "    Arch/Manjaro:  sudo pacman -S python-pyqt5"
        echo "    Debian/Ubuntu: sudo apt install python3-pyqt5"
        echo "    Fedora:        sudo dnf install python3-qt5"
        echo "    pip:           pip3 install --user PyQt5"
        exit 1
    fi
fi
echo "  PyQt5: OK"

# Check snapclient
if ! command -v snapclient &>/dev/null; then
    echo ""
    echo "  WARNING: snapclient not found."
    echo "  SnapTray can still control volume via the server API,"
    echo "  but connect/disconnect won't work without snapclient installed."
    echo "  Install: https://github.com/badaix/snapcast"
    echo ""
fi

# Install app
echo "[2/5] Installing to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
cp "$SCRIPT_DIR/snapcast_tray.py" "$INSTALL_DIR/$APP_NAME.py"
chmod +x "$INSTALL_DIR/$APP_NAME.py"
echo "  Installed: $INSTALL_DIR/$APP_NAME.py"

# Create systemd user service
echo "[3/5] Creating systemd user service..."
mkdir -p "$SERVICE_DIR"
cat > "$SERVICE_DIR/snapcast-tray.service" <<EOF
[Unit]
Description=Snapcast Tray App
After=graphical-session.target

[Service]
ExecStart=/usr/bin/python3 $INSTALL_DIR/$APP_NAME.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical-session.target
EOF
echo "  Created: $SERVICE_DIR/snapcast-tray.service"

# Enable and start
echo "[4/5] Enabling service..."
systemctl --user daemon-reload
systemctl --user enable snapcast-tray.service
echo "  Service enabled (starts with graphical session)"

# Start now if in a graphical session
echo "[5/5] Starting SnapTray..."
if [ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ]; then
    systemctl --user restart snapcast-tray.service
    sleep 2
    if systemctl --user is-active snapcast-tray.service &>/dev/null; then
        echo "  SnapTray is running!"
    else
        echo "  Service started but may not be active yet."
        echo "  Check: systemctl --user status snapcast-tray"
    fi
else
    echo "  No graphical session detected. SnapTray will start on next login."
fi

echo ""
echo "=== Installation Complete ==="
echo ""
echo "  Tray icon should appear in your system tray."
echo "  Right-click for volume, mute, server, and connect/disconnect."
echo ""
echo "  Commands:"
echo "    Status:   systemctl --user status snapcast-tray"
echo "    Restart:  systemctl --user restart snapcast-tray"
echo "    Stop:     systemctl --user stop snapcast-tray"
echo "    Logs:     journalctl --user -u snapcast-tray -f"
echo ""
echo "  Config saved to: ~/.config/snapcast-tray.json"
echo ""
