import os
import sys
import time
import signal
import socket
import json

# Ensure X11 backend for reliable positioning & overlay on Linux
if sys.platform.startswith("linux") and os.environ.get("DISPLAY"):
    os.environ["GDK_BACKEND"] = "x11"

from config import (
    load_config, save_config, reset_glasses_count, PID_FILE, SOCKET_FILE, PORT_FILE, LOCK_FILE
)
from overlay import WaterReminderOverlay, ENGINE

_lock_file_handle = None

def acquire_instance_lock():
    global _lock_file_handle
    try:
        _lock_file_handle = open(LOCK_FILE, "w")
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(_lock_file_handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(_lock_file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (BlockingIOError, OSError, IOError):
        if _lock_file_handle:
            try:
                _lock_file_handle.close()
            except Exception:
                pass
            _lock_file_handle = None
        return False

def release_instance_lock():
    global _lock_file_handle
    if _lock_file_handle:
        try:
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(_lock_file_handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(_lock_file_handle.fileno(), fcntl.LOCK_UN)
            _lock_file_handle.close()
        except Exception:
            pass
        _lock_file_handle = None
        if os.path.exists(LOCK_FILE):
            try:
                os.unlink(LOCK_FILE)
            except OSError:
                pass

class ReminderDaemon:
    def __init__(self, test_on_start=False):
        self.test_on_start = test_on_start
        self.config = load_config()
        self.engine = ENGINE
        self.running = True

        # Initialize overlay
        self.overlay = WaterReminderOverlay(on_action_callback=self.on_overlay_action)
        
        # Setup IPC sockets (TCP on 127.0.0.1 for cross-platform + Unix domain socket on POSIX)
        self.setup_sockets()
        
        # Setup signals
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)
        
        # Initialize schedule
        now = int(time.time())
        interval_secs = self.config.get("interval_minutes", 60) * 60
        
        next_time = self.config.get("next_reminder_time", 0)
        last_drank = self.config.get("last_drank_time", 0)
        last_remind = self.config.get("last_reminder_time", 0)
        
        if self.test_on_start:
            self.config["next_reminder_time"] = now
        elif next_time > now:
            pass
        else:
            # If system just turned on and it has been more than 30 mins since last drink/reminder
            ref_time = max(last_drank, last_remind)
            if ref_time > 0 and (now - ref_time) >= (30 * 60):
                self.config["next_reminder_time"] = now + 10
            else:
                self.config["next_reminder_time"] = now + interval_secs
                
        save_config(self.config)

        # Setup platform timers
        self.setup_timers()

    def setup_sockets(self):
        # 1. Cross-platform Localhost TCP socket (works on Windows, Linux, macOS)
        self.server_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_tcp.setblocking(False)
        self.server_tcp.bind(("127.0.0.1", 0))
        self.server_tcp.listen(5)
        self.port = self.server_tcp.getsockname()[1]
        try:
            with open(PORT_FILE, "w") as f:
                f.write(str(self.port))
        except Exception as e:
            print(f"[Warning] Failed to write port file: {e}")

        # 2. Unix domain socket on POSIX for backwards compatibility
        self.server_unix = None
        if hasattr(socket, "AF_UNIX") and sys.platform != "win32":
            if os.path.exists(SOCKET_FILE):
                try:
                    os.unlink(SOCKET_FILE)
                except OSError:
                    pass
            try:
                self.server_unix = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.server_unix.setblocking(False)
                self.server_unix.bind(SOCKET_FILE)
                self.server_unix.listen(5)
            except Exception as e:
                print(f"[Warning] Failed to bind Unix socket: {e}")
                self.server_unix = None

    def setup_timers(self):
        if self.engine == "gtk":
            from gi.repository import GLib
            GLib.timeout_add_seconds(5, self.check_reminder_schedule)
            GLib.timeout_add(200, self.poll_socket_clients)
            if self.test_on_start:
                GLib.timeout_add(500, self.trigger_reminder)
        elif self.engine == "qt":
            # Qt timers
            from overlay_qt import QTimer
            self.sched_timer = QTimer()
            self.sched_timer.timeout.connect(self.check_reminder_schedule)
            self.sched_timer.start(5000)

            self.sock_timer = QTimer()
            self.sock_timer.timeout.connect(self.poll_socket_clients)
            self.sock_timer.start(200)

            if self.test_on_start:
                QTimer.singleShot(500, self.trigger_reminder)

    def is_screen_locked(self):
        if sys.platform == "win32":
            try:
                import ctypes
                user32 = ctypes.windll.user32
                # DESKTOP_SWITCHDESKTOP = 0x0100
                desk = user32.OpenInputDesktop(0, False, 0x0100)
                if desk == 0:
                    return True
                user32.CloseDesktop(desk)
                return False
            except Exception:
                return False
        else:
            try:
                import gi
                gi.require_version("Gio", "2.0")
                from gi.repository import Gio
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

    def handle_client(self, conn):
        try:
            conn.setblocking(True)
            data = conn.recv(4096).decode("utf-8").strip()
            response = {"status": "ok"}
            should_stop = False

            if data in ("test", "trigger"):
                self.schedule_ui_callback(self.trigger_reminder)
                response["message"] = "Reminder triggered"
            elif data == "status":
                cfg = load_config()
                now = int(time.time())
                next_rem = cfg.get("next_reminder_time", 0)
                rem_in = max(0, next_rem - now)
                from config import get_character_metadata
                char_meta = get_character_metadata(config=cfg)
                response = {
                    "status": "running",
                    "pid": os.getpid(),
                    "engine": self.engine,
                    "interval_minutes": cfg.get("interval_minutes", 60),
                    "sound_enabled": cfg.get("sound_enabled", True),
                    "glasses_today": cfg.get("glasses_today", 0),
                    "active_character": char_meta.get("id", "default"),
                    "active_character_name": char_meta.get("name", "Hydro Buddy"),
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
            elif data.startswith("set_character ") or data.startswith("set_char "):
                try:
                    char_id = data.split(maxsplit=1)[1].strip()
                    from config import set_active_character
                    set_active_character(char_id)
                    self.schedule_ui_callback(lambda: self.overlay.reload_character(char_id))
                    response["message"] = f"Character set to {char_id}"
                except Exception as e:
                    response = {"status": "error", "message": str(e)}
            elif data in ("reload_character", "reload_char"):
                self.schedule_ui_callback(lambda: self.overlay.reload_character())
                response["message"] = "Character reloaded"
            elif data in ("reset_count", "reset"):
                reset_glasses_count()
                response["message"] = "Daily water count reset to 0"
            elif data == "stop":
                response["message"] = "Daemon stopping"
                should_stop = True
            else:
                response = {"status": "error", "message": f"Unknown command: {data}"}

            conn.sendall(json.dumps(response).encode("utf-8"))
            conn.close()

            if should_stop:
                self.schedule_ui_callback(self.stop_daemon)
                return False
        except Exception as e:
            print(f"[Client Handling Error] {e}")

        return True

    def schedule_ui_callback(self, func):
        if self.engine == "gtk":
            from gi.repository import GLib
            GLib.idle_add(func)
        elif self.engine == "qt":
            from overlay_qt import QTimer
            QTimer.singleShot(0, func)

    def poll_socket_clients(self):
        if not self.running:
            return False

        # 1. Accept from TCP socket
        try:
            conn, _ = self.server_tcp.accept()
            self.handle_client(conn)
        except (BlockingIOError, OSError):
            pass

        # 2. Accept from Unix socket if available
        if self.server_unix:
            try:
                conn, _ = self.server_unix.accept()
                self.handle_client(conn)
            except (BlockingIOError, OSError):
                pass

        return True

    def check_reminder_schedule(self):
        if not self.running:
            return False
            
        now = int(time.time())
        self.config = load_config()
        next_time = self.config.get("next_reminder_time", 0)
        
        if next_time > 0 and now >= next_time:
            if self.is_screen_locked():
                return True
            if hasattr(self.overlay, "is_overlay_visible") and self.overlay.is_overlay_visible():
                return True
            self.trigger_reminder()
            
        return True

    def trigger_reminder(self):
        if hasattr(self.overlay, "is_overlay_visible") and self.overlay.is_overlay_visible():
            return False
        print(f"[{time.strftime('%X')}] Triggering water reminder overlay...")
        self.config = load_config()
        now = int(time.time())
        interval = self.config.get("interval_minutes", 60)
        # Advance next reminder time immediately so check_reminder_schedule does not loop while overlay is open
        self.config["next_reminder_time"] = now + (interval * 60)
        self.config["last_reminder_time"] = now
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
            interval = self.config.get("interval_minutes", 60)
            self.config["next_reminder_time"] = now + (interval * 60)
            
        save_config(self.config)

    def handle_signal(self, signum, frame):
        print(f"\nReceived signal {signum}, stopping daemon...")
        self.stop_daemon()

    def stop_daemon(self):
        self.running = False
        try:
            self.overlay.hide_overlay(animated=False)
        except Exception:
            pass
            
        try:
            self.server_tcp.close()
        except Exception:
            pass
            
        if self.server_unix:
            try:
                self.server_unix.close()
            except Exception:
                pass

        for fpath in (PORT_FILE, SOCKET_FILE, PID_FILE, LOCK_FILE):
            if os.path.exists(fpath):
                try:
                    os.unlink(fpath)
                except OSError:
                    pass

        release_instance_lock()

        if self.engine == "gtk":
            from gi.repository import Gtk
            Gtk.main_quit()
        elif self.engine == "qt":
            from overlay_qt import QApplication
            app = QApplication.instance()
            if app:
                app.quit()

        return False

def run_daemon(test=False):
    # Enforce strict single-instance daemon lock
    if not acquire_instance_lock():
        print("⚠️ Water Reminder Daemon is ALREADY running. Exiting duplicate process.")
        sys.exit(0)

    pid = os.getpid()
    with open(PID_FILE, "w") as f:
        f.write(str(pid))
        
    daemon = ReminderDaemon(test_on_start=test)
    print(f"💧 Water Reminder Daemon started (PID {pid}, Engine: {daemon.engine.upper()})")

    if daemon.engine == "gtk":
        from gi.repository import Gtk
        Gtk.main()
    elif daemon.engine == "qt":
        from overlay_qt import QApplication
        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)
        exec_func = getattr(app, "exec", getattr(app, "exec_", None))
        if exec_func:
            exec_func()

    print("💧 Water Reminder Daemon stopped.")
    release_instance_lock()

if __name__ == "__main__":
    test_mode = "--test" in sys.argv
    run_daemon(test=test_mode)
