import os
import sys
import time
import signal
import socket
import json

# Ensure X11 backend for reliable positioning & overlay
os.environ.setdefault("GDK_BACKEND", "x11")

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gio", "2.0")
from gi.repository import Gtk, GLib, Gio

from config import (
    load_config, save_config, reset_glasses_count, PID_FILE, SOCKET_FILE
)
from overlay import WaterReminderOverlay

class ReminderDaemon:
    def __init__(self, test_on_start=False):
        self.test_on_start = test_on_start
        self.config = load_config()
        self.overlay = WaterReminderOverlay(on_action_callback=self.on_overlay_action)
        self.running = True
        
        # Setup IPC server socket
        self.setup_socket()
        
        # Setup signals
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)
        
        # Initialize schedule
        now = int(time.time())
        interval_secs = self.config.get("interval_minutes", 60) * 60
        
        # Check if next_reminder_time is already set in future
        next_time = self.config.get("next_reminder_time", 0)
        last_drank = self.config.get("last_drank_time", 0)
        last_remind = self.config.get("last_reminder_time", 0)
        
        if self.test_on_start:
            # Trigger immediately on test
            self.config["next_reminder_time"] = now
        elif next_time > now:
            # Keep existing scheduled future time
            pass
        else:
            # If system just turned on and it has been more than 30 mins since last drink/reminder
            ref_time = max(last_drank, last_remind)
            if ref_time > 0 and (now - ref_time) >= (30 * 60):
                # Trigger after 10 seconds of desktop startup
                self.config["next_reminder_time"] = now + 10
            else:
                self.config["next_reminder_time"] = now + interval_secs
                
        save_config(self.config)
        
        # Setup periodic check timer (every 5 seconds)
        GLib.timeout_add_seconds(5, self.check_reminder_schedule)
        
        # Setup periodic socket polling (every 200 ms)
        GLib.timeout_add(200, self.poll_socket_clients)
        
        # If test_on_start requested
        if self.test_on_start:
            GLib.timeout_add(500, self.trigger_reminder)

    def is_screen_locked(self):
        """Query DBus to check if GNOME / freedesktop screensaver is active."""
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            proxy = Gio.DBusProxy.new_sync(
                bus,
                Gio.DBusProxyFlags.NONE,
                None,
                "org.gnome.ScreenSaver",
                "/org/gnome/ScreenSaver",
                "org.gnome.ScreenSaver",
                None
            )
            res = proxy.call_sync("GetActive", None, Gio.DBusCallFlags.NONE, 200, None)
            return bool(res.unpack()[0])
        except Exception:
            return False

    def setup_socket(self):
        if os.path.exists(SOCKET_FILE):
            try:
                os.unlink(SOCKET_FILE)
            except OSError:
                pass
        self.server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_sock.setblocking(False)
        self.server_sock.bind(SOCKET_FILE)
        self.server_sock.listen(5)

    def poll_socket_clients(self):
        if not self.running:
            return False
            
        try:
            conn, _ = self.server_sock.accept()
            conn.setblocking(True)
            data = conn.recv(4096).decode("utf-8").strip()
            
            response = {"status": "ok"}
            if data == "test" or data == "trigger":
                GLib.idle_add(self.trigger_reminder)
                response["message"] = "Reminder triggered"
            elif data == "status":
                cfg = load_config()
                now = int(time.time())
                next_rem = cfg.get("next_reminder_time", 0)
                rem_in = max(0, next_rem - now)
                response = {
                    "status": "running",
                    "pid": os.getpid(),
                    "interval_minutes": cfg.get("interval_minutes", 60),
                    "sound_enabled": cfg.get("sound_enabled", True),
                    "glasses_today": cfg.get("glasses_today", 0),
                    "next_reminder_in_seconds": rem_in,
                    "next_reminder_in_minutes": round(rem_in / 60, 1),
                    "is_screen_locked": self.is_screen_locked()
                }
            elif data.startswith("set_interval "):
                try:
                    mins = int(data.split()[1])
                    cfg = load_config()
                    cfg["interval_minutes"] = mins
                    cfg["next_reminder_time"] = int(time.time()) + (mins * 60)
                    save_config(cfg)
                    response["message"] = f"Interval updated to {mins} mins"
                except Exception as e:
                    response = {"status": "error", "message": str(e)}
            elif data == "reset_count":
                reset_glasses_count()
                response["message"] = "Daily water count reset to 0"
            elif data == "stop":
                response["message"] = "Daemon stopping"
                conn.sendall(json.dumps(response).encode("utf-8"))
                conn.close()
                GLib.idle_add(self.stop_daemon)
                return False
            else:
                response = {"status": "error", "message": f"Unknown command: {data}"}
                
            conn.sendall(json.dumps(response).encode("utf-8"))
            conn.close()
        except BlockingIOError:
            pass
        except Exception as e:
            print(f"[Socket Error] {e}")
            
        return True

    def check_reminder_schedule(self):
        if not self.running:
            return False
            
        now = int(time.time())
        self.config = load_config()
        next_time = self.config.get("next_reminder_time", 0)
        
        if next_time > 0 and now >= next_time:
            # Check if screen is locked before triggering
            if self.is_screen_locked():
                # Screen is locked, defer check until unlocked
                return True
                
            self.trigger_reminder()
            
        return True

    def trigger_reminder(self):
        print(f"[{time.strftime('%X')}] Triggering water reminder overlay...")
        self.config = load_config()
        self.config["last_reminder_time"] = int(time.time())
        save_config(self.config)
        self.overlay.show_overlay()
        return False

    def on_overlay_action(self, action_type, value):
        print(f"[Overlay Action] {action_type}: {value}")
        now = int(time.time())
        self.config = load_config()
        
        if action_type == "drank":
            interval = value if value > 0 else self.config.get("interval_minutes", 60)
            self.config["next_reminder_time"] = now + (interval * 60)
            self.config["last_drank_time"] = now
        elif action_type == "snooze":
            snooze_mins = value if value > 0 else self.config.get("snooze_minutes", 10)
            self.config["next_reminder_time"] = now + (snooze_mins * 60)
        elif action_type == "dismiss":
            # Dismiss sets to default interval
            interval = self.config.get("interval_minutes", 60)
            self.config["next_reminder_time"] = now + (interval * 60)
            
        save_config(self.config)

    def handle_signal(self, signum, frame):
        print(f"\nReceived signal {signum}, stopping daemon...")
        self.stop_daemon()

    def stop_daemon(self):
        self.running = False
        try:
            self.overlay.hide_overlay()
        except Exception:
            pass
            
        if os.path.exists(SOCKET_FILE):
            try:
                os.unlink(SOCKET_FILE)
            except OSError:
                pass
                
        if os.path.exists(PID_FILE):
            try:
                os.unlink(PID_FILE)
            except OSError:
                pass
                
        Gtk.main_quit()
        return False

def run_daemon(test=False):
    # Write PID
    pid = os.getpid()
    with open(PID_FILE, "w") as f:
        f.write(str(pid))
        
    daemon = ReminderDaemon(test_on_start=test)
    print(f"💧 Water Reminder Daemon started (PID {pid})")
    Gtk.main()
    print("💧 Water Reminder Daemon stopped.")

if __name__ == "__main__":
    test_mode = "--test" in sys.argv
    run_daemon(test=test_mode)
