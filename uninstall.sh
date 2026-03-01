#!/bin/bash
# SnapTray Uninstaller

set -e

echo "=== SnapTray Uninstaller ==="
echo ""

# Stop and disable service
echo "Stopping service..."
systemctl --user stop snapcast-tray.service 2>/dev/null || true
systemctl --user disable snapcast-tray.service 2>/dev/null || true

# Remove files
echo "Removing files..."
rm -f "$HOME/.local/bin/snapcast_tray.py"
rm -f "$HOME/.config/systemd/user/snapcast-tray.service"
systemctl --user daemon-reload 2>/dev/null || true

echo ""
echo "SnapTray uninstalled."
echo "Config file preserved at: ~/.config/snapcast-tray.json"
echo "Delete it manually if you want a clean removal."
echo ""
