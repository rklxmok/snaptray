#!/usr/bin/env python3
"""
Snapcast Tray — System tray app for Snapcast client control.
Volume slider, mute toggle, server connect/disconnect, now-playing info.
Manages the local snapclient process and talks to snapserver JSON-RPC on :1780.
Cross-platform: Linux and Windows.
"""

import sys
import os
import json
import subprocess
import shutil
import urllib.request
from PyQt5.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QAction, QWidgetAction,
    QWidget, QHBoxLayout, QLabel, QSlider, QLineEdit, QComboBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QPolygon
from PyQt5.QtCore import QPoint

if sys.platform != "win32":
    import signal

VERSION = "2.2.0"
IS_WINDOWS = sys.platform == "win32"
DEFAULT_SERVER = "10.10.2.50"
API_PORT = 1780
SNAPCLIENT_BIN = "snapclient.exe" if IS_WINDOWS else "snapclient"

# Config path: %APPDATA%\SnapcastTray\ on Windows, ~/.config/ on Linux
if IS_WINDOWS:
    _appdata = os.getenv("APPDATA", os.path.expanduser("~/AppData/Roaming"))
    CONFIG_PATH = os.path.join(_appdata, "SnapcastTray", "snapcast-tray.json")
else:
    CONFIG_PATH = os.path.expanduser("~/.config/snapcast-tray.json")


def load_config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f)


def get_macs():
    """Get all local MAC addresses to identify this client in Snapcast."""
    macs = set()
    if IS_WINDOWS:
        try:
            out = subprocess.check_output(
                ["getmac", "/fo", "csv", "/nh"],
                text=True, stderr=subprocess.DEVNULL, timeout=5
            )
            for line in out.strip().splitlines():
                parts = line.split(",")
                if parts:
                    raw = parts[0].strip().strip('"')
                    if raw and raw != "N/A" and len(raw) == 17 and "-" in raw:
                        macs.add(raw.replace("-", ":").lower())
        except Exception:
            pass
    else:
        try:
            out = subprocess.check_output(["ip", "link"], text=True)
            for block in out.split("\n\n"):
                if "state UP" in block or "state UNKNOWN" in block:
                    for line in block.split("\n"):
                        line = line.strip()
                        if line.startswith("link/ether"):
                            macs.add(line.split()[1])
        except Exception:
            pass
    return macs


def detect_audio_sink():
    """Detect the best audio sink for snapclient. Windows uses default device."""
    if IS_WINDOWS:
        return None
    try:
        subprocess.check_output(["pactl", "info"], stderr=subprocess.DEVNULL, timeout=2)
        return "pulse"
    except Exception:
        pass
    try:
        out = subprocess.check_output(["aplay", "-l"], text=True, stderr=subprocess.DEVNULL, timeout=2)
        if "card 0:" in out:
            return "sysdefault"
    except Exception:
        pass
    return None


def snap_rpc(server, method, params=None):
    """Call Snapcast JSON-RPC API."""
    payload = {"jsonrpc": "2.0", "method": method, "id": 1}
    if params:
        payload["params"] = params
    try:
        req = urllib.request.Request(
            f"http://{server}:{API_PORT}/jsonrpc",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def create_icon(color="#3fb950", muted=False):
    """Generate a speaker icon pixmap."""
    px = QPixmap(64, 64)
    px.fill(QColor(0, 0, 0, 0))
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    c = QColor(color)
    p.setBrush(c)
    p.setPen(Qt.NoPen)
    p.drawRect(12, 22, 14, 20)
    poly = QPolygon([QPoint(26, 22), QPoint(42, 10), QPoint(42, 54), QPoint(26, 42)])
    p.drawPolygon(poly)
    if muted:
        p.setPen(QColor("#f7768e"))
        pen = p.pen()
        pen.setWidth(4)
        p.setPen(pen)
        p.drawLine(46, 20, 60, 44)
        p.drawLine(60, 20, 46, 44)
    else:
        p.setPen(QColor(color))
        pen = p.pen()
        pen.setWidth(3)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawArc(44, 22, 12, 20, -60 * 16, 120 * 16)
        p.drawArc(50, 16, 16, 32, -60 * 16, 120 * 16)
    p.end()
    return px


def snapclient_version():
    """Get snapclient version to determine CLI format."""
    try:
        out = subprocess.check_output(
            [SNAPCLIENT_BIN, "--version"], text=True, stderr=subprocess.STDOUT
        )
        for part in out.split():
            if part.startswith("v") or (part[0:1].isdigit()):
                ver = part.lstrip("v")
                major, minor = ver.split(".")[:2]
                return (int(major), int(minor))
    except Exception:
        pass
    return (0, 28)


class SnapcastTray(QSystemTrayIcon):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.cfg = load_config()
        self.server = self.cfg.get("server", DEFAULT_SERVER)
        self.audio_sink = self.cfg.get("sink", detect_audio_sink() or "pulse") if not IS_WINDOWS else None
        self.my_macs = get_macs()
        self.my_client_id = None
        self.my_group_id = None
        self.volume = 100
        self.muted = False
        self.connected = False
        self.client_connected = False
        self.stream_name = ""
        self.snapclient_proc = None
        self._vol_send_timer = None
        self._slider_dragging = False

        self.setIcon(QIcon(create_icon("#787c99")))
        self.setToolTip("Snapcast Tray")

        self.build_menu()

        # Debounce timer for volume changes
        self._vol_send_timer = QTimer()
        self._vol_send_timer.setSingleShot(True)
        self._vol_send_timer.setInterval(200)
        self._vol_send_timer.timeout.connect(self._do_send_volume)

        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self.poll_status)
        self.poll_timer.start(3000)

        # Auto-connect on startup if snapclient is installed
        if shutil.which(SNAPCLIENT_BIN):
            if not self._snapclient_running():
                self.start_snapclient()
            else:
                self.client_connected = True

        self.poll_status()
        self.activated.connect(self.on_activate)
        self.show()

    def _snapclient_running(self):
        try:
            if IS_WINDOWS:
                out = subprocess.check_output(
                    ["tasklist", "/FI", f"IMAGENAME eq {SNAPCLIENT_BIN}", "/NH"],
                    text=True, stderr=subprocess.DEVNULL, timeout=5
                )
                return SNAPCLIENT_BIN.lower() in out.lower()
            else:
                out = subprocess.check_output(["pgrep", "-x", "snapclient"], text=True).strip()
                return bool(out)
        except Exception:
            return False

    def start_snapclient(self):
        """Start snapclient process."""
        self.stop_snapclient(kill_all=True)
        ver = snapclient_version()

        # Linux: pass -s sink, Windows: no sink arg (uses default audio device)
        sink_args = ["-s", self.audio_sink] if self.audio_sink else []

        if ver >= (0, 28):
            cmd = [SNAPCLIENT_BIN] + sink_args + [f"tcp://{self.server}:1704"]
        else:
            cmd = [SNAPCLIENT_BIN, "-h", self.server] + sink_args

        try:
            if IS_WINDOWS:
                self.snapclient_proc = subprocess.Popen(
                    cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                self.snapclient_proc = subprocess.Popen(
                    cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    preexec_fn=os.setsid
                )
            self.client_connected = True
            self.connect_action.setText("Disconnect")
        except Exception as e:
            self.status_action.setText(f"Failed to start: {e}")

    def stop_snapclient(self, kill_all=False):
        """Stop snapclient process."""
        if not IS_WINDOWS:
            # Stop systemd user service first so it doesn't auto-restart
            try:
                subprocess.run(
                    ["systemctl", "--user", "stop", "snapclient.service"],
                    timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            except Exception:
                pass
        # Kill our managed process
        if self.snapclient_proc:
            try:
                if IS_WINDOWS:
                    self.snapclient_proc.terminate()
                else:
                    os.killpg(os.getpgid(self.snapclient_proc.pid), signal.SIGTERM)
            except Exception:
                try:
                    self.snapclient_proc.terminate()
                except Exception:
                    pass
            try:
                self.snapclient_proc.wait(timeout=3)
            except Exception:
                pass
            self.snapclient_proc = None
        # Kill any straggler snapclient processes
        if kill_all:
            try:
                if IS_WINDOWS:
                    subprocess.run(
                        ["taskkill", "/IM", SNAPCLIENT_BIN, "/F"],
                        timeout=3, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                else:
                    subprocess.run(
                        ["pkill", "-x", "snapclient"],
                        timeout=3, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
            except Exception:
                pass
        self.client_connected = False
        self.connected = False
        self.connect_action.setText("Connect")
        self.update_icon()

    def toggle_connection(self):
        if self.client_connected or self._snapclient_running():
            self.stop_snapclient(kill_all=True)
        else:
            self.server = self.srv_input.text().strip() or DEFAULT_SERVER
            self.save_settings()
            self.start_snapclient()

    def build_menu(self):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background: #1a1b26; border: 1px solid #3b4261;
                border-radius: 6px; padding: 6px;
                color: #c0caf5; font-size: 13px;
            }
            QMenu::item { padding: 6px 20px; border-radius: 3px; }
            QMenu::item:selected { background: #2a2f3a; }
            QMenu::separator { height: 1px; background: #3b4261; margin: 4px 8px; }
        """)

        # Status
        self.status_action = QAction("Disconnected")
        self.status_action.setEnabled(False)
        menu.addAction(self.status_action)

        self.stream_action = QAction("")
        self.stream_action.setEnabled(False)
        menu.addAction(self.stream_action)

        menu.addSeparator()

        # Volume slider
        vol_widget = QWidget()
        vol_widget.setStyleSheet("background: transparent;")
        vol_layout = QHBoxLayout(vol_widget)
        vol_layout.setContentsMargins(12, 4, 12, 4)

        vol_lbl = QLabel("Vol:")
        vol_lbl.setStyleSheet("color: #a9b1d6; font-size: 12px;")
        vol_layout.addWidget(vol_lbl)

        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(100)
        self.vol_slider.setFixedWidth(140)
        self.vol_slider.setStyleSheet("""
            QSlider::groove:horizontal { height: 6px; background: #3b4261; border-radius: 3px; }
            QSlider::handle:horizontal { background: #7aa2f7; width: 14px; height: 14px; margin: -4px 0; border-radius: 7px; }
            QSlider::sub-page:horizontal { background: #7aa2f7; border-radius: 3px; }
        """)
        self.vol_slider.valueChanged.connect(self._on_vol_changed)
        vol_layout.addWidget(self.vol_slider)

        self.vol_pct = QLabel("100%")
        self.vol_pct.setStyleSheet("color: #787c99; font-size: 12px; min-width: 32px;")
        vol_layout.addWidget(self.vol_pct)

        vol_action = QWidgetAction(menu)
        vol_action.setDefaultWidget(vol_widget)
        menu.addAction(vol_action)

        # Mute
        self.mute_action = QAction("Mute")
        self.mute_action.triggered.connect(self.toggle_mute)
        menu.addAction(self.mute_action)

        menu.addSeparator()

        # Server input
        srv_widget = QWidget()
        srv_widget.setStyleSheet("background: transparent;")
        srv_layout = QHBoxLayout(srv_widget)
        srv_layout.setContentsMargins(12, 4, 12, 4)

        srv_lbl = QLabel("Server:")
        srv_lbl.setStyleSheet("color: #a9b1d6; font-size: 12px;")
        srv_layout.addWidget(srv_lbl)

        self.srv_input = QLineEdit(self.server)
        self.srv_input.setStyleSheet("""
            QLineEdit { background: #24283b; border: 1px solid #3b4261;
                color: #c0caf5; border-radius: 3px; padding: 3px 6px; font-size: 12px; }
        """)
        self.srv_input.returnPressed.connect(self.reconnect_server)
        srv_layout.addWidget(self.srv_input)

        srv_action = QWidgetAction(menu)
        srv_action.setDefaultWidget(srv_widget)
        menu.addAction(srv_action)

        # Audio output selector — Linux only
        # Windows uses default audio device, change output in Windows Sound Settings
        if not IS_WINDOWS:
            sink_widget = QWidget()
            sink_widget.setStyleSheet("background: transparent;")
            sink_layout = QHBoxLayout(sink_widget)
            sink_layout.setContentsMargins(12, 4, 12, 4)

            sink_lbl = QLabel("Output:")
            sink_lbl.setStyleSheet("color: #a9b1d6; font-size: 12px;")
            sink_layout.addWidget(sink_lbl)

            self.sink_combo = QComboBox()
            self.sink_combo.setStyleSheet("""
                QComboBox { background: #24283b; border: 1px solid #3b4261;
                    color: #c0caf5; border-radius: 3px; padding: 3px 6px; font-size: 12px; }
                QComboBox QAbstractItemView { background: #1a1b26; color: #c0caf5;
                    selection-background-color: #2a2f3a; }
            """)
            self.sink_combo.addItems(["pulse", "sysdefault", "hw:0,0", "hw:1,0", "hw:2,0", "hw:3,0"])
            idx = self.sink_combo.findText(self.audio_sink)
            if idx >= 0:
                self.sink_combo.setCurrentIndex(idx)
            self.sink_combo.currentTextChanged.connect(self._on_sink_change)
            sink_layout.addWidget(self.sink_combo)

            sink_action = QWidgetAction(menu)
            sink_action.setDefaultWidget(sink_widget)
            menu.addAction(sink_action)

        menu.addSeparator()

        # Connect / Disconnect
        self.connect_action = QAction("Connect")
        self.connect_action.triggered.connect(self.toggle_connection)
        menu.addAction(self.connect_action)

        # Quit
        quit_action = QAction("Quit")
        quit_action.triggered.connect(self.app.quit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)

    def on_activate(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.contextMenu().popup(self.geometry().center())

    def _on_vol_changed(self, val):
        """Called on every slider tick — update label and debounce the API call."""
        self.vol_pct.setText(f"{val}%")
        self._vol_send_timer.start()

    def _do_send_volume(self):
        """Actually send volume to Snapcast server (debounced)."""
        vol = self.vol_slider.value()
        if self.my_client_id:
            snap_rpc(self.server, "Client.SetVolume", {
                "id": self.my_client_id,
                "volume": {"percent": vol, "muted": self.muted}
            })

    def toggle_mute(self):
        self.muted = not self.muted
        if self.my_client_id:
            snap_rpc(self.server, "Client.SetVolume", {
                "id": self.my_client_id,
                "volume": {"percent": self.volume, "muted": self.muted}
            })
        self.update_icon()

    def _on_sink_change(self, text):
        if text == self.audio_sink:
            return
        self.audio_sink = text
        self.save_settings()
        # Reconnect with new audio output
        if self.client_connected or self._snapclient_running():
            self.start_snapclient()

    def reconnect_server(self):
        new_server = self.srv_input.text().strip()
        if new_server:
            self.server = new_server
            self.save_settings()
            self.start_snapclient()

    def save_settings(self):
        self.cfg["server"] = self.server
        if not IS_WINDOWS:
            self.cfg["sink"] = self.audio_sink
        save_config(self.cfg)

    def poll_status(self):
        # Check snapclient process
        if self.snapclient_proc and self.snapclient_proc.poll() is not None:
            self.snapclient_proc = None
        self.client_connected = self._snapclient_running()
        self.connect_action.setText("Disconnect" if self.client_connected else "Connect")

        resp = snap_rpc(self.server, "Server.GetStatus")
        if not resp or "result" not in resp:
            self.connected = False
            self.status_action.setText(
                "Server unreachable" if self.client_connected else "Disconnected"
            )
            self.stream_action.setText("")
            self.setIcon(QIcon(create_icon("#787c99")))
            self.setToolTip("Snapcast Tray — Disconnected")
            return

        server_data = resp["result"]["server"]
        self.my_client_id = None
        self.my_group_id = None
        stream_id = "default"

        for g in server_data.get("groups", []):
            for c in g.get("clients", []):
                mac = c.get("host", {}).get("mac", "")
                if mac in self.my_macs:
                    self.my_client_id = c["id"]
                    self.my_group_id = g["id"]
                    self.connected = c.get("connected", False)
                    vol_cfg = c.get("config", {}).get("volume", {})
                    self.volume = vol_cfg.get("percent", 100)
                    self.muted = vol_cfg.get("muted", False)
                    stream_id = g.get("stream_id", "default")
                    break
            if self.my_client_id:
                break

        if not self.my_client_id:
            self.status_action.setText(f"Not registered (MACs: {', '.join(self.my_macs)})")
            self.stream_action.setText("")
            self.setIcon(QIcon(create_icon("#e0af68")))
            return

        # Update slider only when user isn't dragging
        if not self.vol_slider.isSliderDown():
            self.vol_slider.blockSignals(True)
            self.vol_slider.setValue(self.volume)
            self.vol_slider.blockSignals(False)
            self.vol_pct.setText(f"{self.volume}%")

        self.mute_action.setText("Unmute" if self.muted else "Mute")

        # Stream info
        self.stream_name = stream_id
        stream_status = "idle"
        for s in server_data.get("streams", []):
            if s["id"] == stream_id:
                stream_status = s.get("status", "idle")
                break

        conn_str = "Connected" if self.connected else "Registered (offline)"
        self.status_action.setText(f"{conn_str} — {self.server}")

        if stream_status == "playing":
            self.stream_action.setText(f"Stream: {stream_id} (playing)")
        else:
            self.stream_action.setText(f"Stream: {stream_id}")

        mute_str = " [MUTED]" if self.muted else ""
        self.setToolTip(f"Snapcast — {stream_id} — Vol: {self.volume}%{mute_str}")
        self.update_icon()

    def update_icon(self):
        if not self.connected:
            self.setIcon(QIcon(create_icon("#787c99")))
        elif self.muted:
            self.setIcon(QIcon(create_icon("#f7768e", muted=True)))
        else:
            self.setIcon(QIcon(create_icon("#3fb950")))


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Snapcast Tray")

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("System tray not available")
        sys.exit(1)

    tray = SnapcastTray(app)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
