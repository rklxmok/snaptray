# SnapTray

System tray app for [Snapcast](https://github.com/badaix/snapcast) clients. Control volume, mute, connect/disconnect, and select audio output — all from your tray.

![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue) ![License: MIT](https://img.shields.io/badge/license-MIT-green) ![Platform: Linux](https://img.shields.io/badge/platform-Linux-orange)

## Features

- **Volume slider** — adjusts Snapcast server-side volume (synced every 3 seconds)
- **Mute/Unmute** toggle
- **Connect/Disconnect** — starts and stops the local snapclient process
- **Server selector** — change server IP and reconnect (saved to config)
- **Audio output selector** — pulse, sysdefault, or specific ALSA device
- **Auto-detects** snapclient version (legacy `-h` vs new URI format)
- **Auto-detects** PulseAudio/PipeWire for audio output
- **Tray icon** changes color: green (connected), grey (disconnected), red (muted)
- **Multi-NIC support** — matches all local MAC addresses against Snapcast clients

## Requirements

- **Python 3.8+**
- **PyQt5** (for system tray / Qt widgets)
- **snapcast** (optional — needed for connect/disconnect)

### Installing dependencies

```bash
# Arch / Manjaro / Garuda
sudo pacman -S python-pyqt5 snapcast

# Debian / Ubuntu
sudo apt install python3-pyqt5 snapcast

# Fedora
sudo dnf install python3-qt5 snapcast
```

## Install

```bash
git clone https://github.com/rklxmok/snaptray.git
cd snaptray
chmod +x install.sh
./install.sh
```

The installer:
1. Checks Python and PyQt5 dependencies
2. Copies `snapcast_tray.py` to `~/.local/bin/`
3. Creates a systemd user service (`snapcast-tray.service`)
4. Enables and starts the service

SnapTray auto-starts with your graphical session on login.

## Uninstall

```bash
./uninstall.sh
```

## Usage

Right-click the tray icon to open the menu:

| Control | Description |
|---------|-------------|
| **Status line** | Shows connection state and server IP |
| **Stream line** | Shows assigned Snapcast stream name |
| **Volume slider** | Drag to set volume (0-100%), debounced 200ms |
| **Mute / Unmute** | Toggle mute on the Snapcast server |
| **Server** | Edit server IP, press Enter to reconnect |
| **Output** | Select audio sink (pulse, sysdefault, hw:X,X) |
| **Connect / Disconnect** | Start or stop the local snapclient process |
| **Quit** | Exit SnapTray (doesn't stop snapclient) |

## Configuration

Settings are saved to `~/.config/snapcast-tray.json`:

```json
{
  "server": "10.10.2.50",
  "sink": "pulse"
}
```

## How it works

SnapTray communicates with the Snapcast server via the [JSON-RPC API](https://github.com/badaix/snapcast/blob/master/doc/json_rpc_api/control.md) on port 1780. It polls `Server.GetStatus` every 3 seconds to sync volume, mute state, and connection status.

For connect/disconnect, it manages the local `snapclient` process directly — detecting the installed version to use the correct CLI format:

- **v0.28+**: `snapclient -s pulse tcp://SERVER:1704`
- **Older**: `snapclient -h SERVER -s pulse`

## Service management

```bash
# Check status
systemctl --user status snapcast-tray

# Restart
systemctl --user restart snapcast-tray

# View logs
journalctl --user -u snapcast-tray -f

# Stop
systemctl --user stop snapcast-tray
```

## License

MIT
