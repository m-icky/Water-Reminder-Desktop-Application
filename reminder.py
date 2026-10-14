#!/usr/bin/env python3
import os
import sys
import time
import socket
import json
import signal
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import (
    PID_FILE, SOCKET_FILE, PORT_FILE, LOCK_FILE, load_config, save_config, reset_glasses_count, get_today_str,
    list_available_characters, get_character_metadata, set_active_character, delete_custom_character
)

# Force X11 backend on Linux so overlay can freely position and stay on top
if sys.platform.startswith("linux") and os.environ.get("DISPLAY"):
    os.environ["GDK_BACKEND"] = "x11"

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

# Linux autostart paths
AUTOSTART_DIR = os.path.expanduser("~/.config/autostart")
AUTOSTART_DESKTOP_FILE = os.path.join(AUTOSTART_DIR, "water-reminder.desktop")
SYSTEMD_USER_DIR = os.path.expanduser("~/.config/systemd/user")
SYSTEMD_SERVICE_FILE = os.path.join(SYSTEMD_USER_DIR, "water-reminder.service")

# Windows autostart path
def get_windows_startup_vbs():
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        appdata = os.path.expanduser("~\\AppData\\Roaming")
    startup_dir = os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
    return os.path.join(startup_dir, "WaterReminder.vbs")

def send_socket_command(cmd, timeout=3.0):
    # 1. Try Localhost TCP socket first (preferred cross-platform)
    if os.path.exists(PORT_FILE):
        try:
            with open(PORT_FILE, "r") as f:
                port = int(f.read().strip())
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect(("127.0.0.1", port))
            s.sendall(cmd.encode("utf-8"))
            data = s.recv(4096).decode("utf-8")
            s.close()
            return json.loads(data)
        except Exception:
            pass

    # 2. Try Unix domain socket (POSIX fallback)
    if hasattr(socket, "AF_UNIX") and os.path.exists(SOCKET_FILE):
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect(SOCKET_FILE)
            s.sendall(cmd.encode("utf-8"))
            data = s.recv(4096).decode("utf-8")
            s.close()
            return json.loads(data)
        except Exception:
            pass

    return None

def is_process_running(pid):
    if pid <= 0:
        return False
    if IS_WINDOWS:
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            SYNCHRONIZE = 0x00100000
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid)
            if handle:
                exit_code = ctypes.c_ulong()
                kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                kernel32.CloseHandle(handle)
                return exit_code.value == 259  # STILL_ACTIVE
            return False
        except Exception:
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

def kill_process(pid):
    if IS_WINDOWS:
        try:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass
    else:
        try:
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.3)
        except OSError:
            pass
        if is_process_running(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

def get_running_pid():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                pid = int(f.read().strip())
            if is_process_running(pid):
                return pid
        except Exception:
            pass
    return None

def cmd_status():
    pid = get_running_pid()
    sock_resp = send_socket_command("status")
    
    cfg = load_config()
    print("=" * 50)
    print("           💧 WATER REMINDER STATUS           ")
    print("=" * 50)
    
    today_str = cfg.get("today_date", get_today_str())
    os_name = "Windows" if IS_WINDOWS else ("Ubuntu/Linux" if IS_LINUX else sys.platform)
    print(f"  ● Platform:       {os_name}")
    
    if pid and sock_resp:
        rem_mins = sock_resp.get("next_reminder_in_minutes", 0)
        rem_secs = sock_resp.get("next_reminder_in_seconds", 0)
        locked = sock_resp.get("is_screen_locked", False)
        engine = sock_resp.get("engine", "default").upper()
        print(f"  ● Status:         RUNNING (PID: {pid}, Engine: {engine})")
        print(f"  ● Today's Date:   {today_str} (Resets daily at 00:00)")
        print(f"  ● Interval:       Every {sock_resp.get('interval_minutes')} minutes")
        startup_delay = sock_resp.get("startup_delay_minutes", cfg.get("startup_delay_minutes", 30))
        if startup_delay > 0:
            print(f"  ● Startup Delay:  {startup_delay} minutes after system turn-on ⏱️")
        else:
            print(f"  ● Startup Delay:  Disabled (starts immediately on boot) ⏱️")
        print(f"  ● Next Reminder:  In {rem_mins:.1f} minutes ({rem_secs}s)")
        print(f"  ● Screen State:   {'Locked (Waiting)' if locked else 'Active / Unlocked'}")
        print(f"  ● Sound Effects:  {'Enabled 🔊' if sock_resp.get('sound_enabled') else 'Disabled 🔇'}")
    elif pid:
        print(f"  ● Status:         RUNNING (PID: {pid}) (Socket not responding)")
        print(f"  ● Today's Date:   {today_str} (Resets daily at 00:00)")
        print(f"  ● Glasses Today:  {cfg.get('glasses_today', 0)} 🥛")
    else:
        print("  ○ Status:         STOPPED (Not running)")
        print(f"  ● Today's Date:   {today_str} (Resets daily at 00:00)")
        print(f"  ● Glasses Today:  {cfg.get('glasses_today', 0)} 🥛")
        print(f"  ● Interval:       Configured to {cfg.get('interval_minutes', 60)} minutes")
        startup_delay = cfg.get("startup_delay_minutes", 30)
        if startup_delay > 0:
            print(f"  ● Startup Delay:  {startup_delay} minutes after system turn-on ⏱️")
        else:
            print(f"  ● Startup Delay:  Disabled (starts immediately on boot) ⏱️")
        print(f"  ● Sound Effects:  {'Enabled 🔊' if cfg.get('sound_enabled', True) else 'Disabled 🔇'}")
        
    char_meta = get_character_metadata(config=cfg)
    print(f"  ● Character:      {char_meta.get('name', 'Hydro Buddy')} ({char_meta.get('frame_count', 202)} frames)")
    history = cfg.get("daily_history", {})
    if history:
        recent = sorted(history.items(), reverse=True)[:3]
        history_str = " | ".join([f"{d}: {c}🥛" for d, c in recent])
        print(f"  ● Past Days:      {history_str}")
        
    if IS_WINDOWS:
        autostart_active = os.path.exists(get_windows_startup_vbs())
    else:
        autostart_active = os.path.exists(AUTOSTART_DESKTOP_FILE) or os.path.exists(SYSTEMD_SERVICE_FILE)
    print(f"  ● Auto-start:     {'Enabled (Starts on boot/login) ✅' if autostart_active else 'Disabled ❌'}")
    print("=" * 50)

def cmd_start():
    pid = get_running_pid()
    if pid:
        print(f"💧 Water Reminder is ALREADY running (PID: {pid}).")
        return
        
    print("🚀 Starting Water Reminder daemon...")
    log_file = os.path.join(BASE_DIR, "reminder.log")
    
    with open(log_file, "a") as log:
        if IS_WINDOWS:
            # Use pythonw.exe if available so no command prompt window stays open
            py_dir = os.path.dirname(sys.executable)
            pythonw = os.path.join(py_dir, "pythonw.exe")
            py_exe = pythonw if os.path.exists(pythonw) else sys.executable
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            proc = subprocess.Popen(
                [py_exe, os.path.join(BASE_DIR, "reminder.py"), "daemon"],
                stdout=log,
                stderr=log,
                creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                close_fds=True
            )
        else:
            env = dict(os.environ)
            if os.environ.get("DISPLAY"):
                env["GDK_BACKEND"] = "x11"
            proc = subprocess.Popen(
                [sys.executable, os.path.join(BASE_DIR, "reminder.py"), "daemon"],
                stdout=log,
                stderr=log,
                env=env,
                preexec_fn=os.setpgrp,
                close_fds=True
            )
        
    # Wait up to 2 seconds for PID file & socket initialization
    for _ in range(20):
        time.sleep(0.1)
        if get_running_pid():
            break
            
    running_pid = get_running_pid()
    if running_pid:
        print(f"✅ Water Reminder daemon successfully started! (PID: {running_pid})")
        print("   The reminder character will appear every hour on the bottom-right.")
        print(f"   Use 'python reminder.py test' to see character immediately.")
        print(f"   Use 'python reminder.py stop' to stop it anytime.")
    else:
        print("❌ Failed to start daemon. Check reminder.log for details.")

def cmd_stop():
    pid = get_running_pid()
    if not pid:
        print("○ Water Reminder is not currently running.")
        for fpath in (PID_FILE, SOCKET_FILE, PORT_FILE, LOCK_FILE):
            if os.path.exists(fpath):
                try: os.unlink(fpath)
                except OSError: pass
        return
        
    print(f"🛑 Stopping Water Reminder daemon (PID: {pid})...")
    # 1. Try socket stop first
    send_socket_command("stop", timeout=1.0)
    
    # 2. Wait up to 1.5 seconds for graceful shutdown
    for _ in range(15):
        time.sleep(0.1)
        if not is_process_running(pid):
            break
            
    # 3. Force kill if still lingering
    if is_process_running(pid):
        kill_process(pid)
            
    # Clean files
    for fpath in (PID_FILE, SOCKET_FILE, PORT_FILE, LOCK_FILE):
        if os.path.exists(fpath):
            try: os.unlink(fpath)
            except OSError: pass
        
    print("✅ Water Reminder daemon completely stopped.")

def cmd_restart():
    cmd_stop()
    time.sleep(0.5)
    cmd_start()

def cmd_test():
    pid = get_running_pid()
    if pid:
        print("⚡ Sending trigger command to running daemon...")
        resp = send_socket_command("test")
        if resp and resp.get("status") == "ok":
            print("✅ Reminder overlay triggered on bottom-right of screen!")
            return
            
    # If not running in daemon, run overlay directly
    print("🎬 Launching reminder overlay directly...")
    from overlay import WaterReminderOverlay, ENGINE
    if ENGINE == "gtk":
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk
        overlay = WaterReminderOverlay()
        overlay.show_overlay()
        print("✅ Character reminder is now active on your screen!")
        Gtk.main()
    elif ENGINE == "qt":
        from overlay_qt import run_standalone
        print("✅ Character reminder is now active on your screen!")
        run_standalone()

def cmd_interval(mins):
    try:
        mins = int(mins)
        if mins < 1:
            print("Interval must be at least 1 minute.")
            return
    except ValueError:
        print("Invalid number of minutes.")
        return
        
    cfg = load_config()
    cfg["interval_minutes"] = mins
    save_config(cfg)
    
    resp = send_socket_command(f"set_interval {mins}")
    print(f"✅ Reminder interval set to every {mins} minutes.")

def cmd_startup_delay(mins):
    try:
        mins = int(mins)
        if mins < 0:
            print("Startup delay cannot be negative.")
            return
    except ValueError:
        print("Invalid number of minutes.")
        return
        
    cfg = load_config()
    cfg["startup_delay_minutes"] = mins
    save_config(cfg)
    
    send_socket_command(f"set_startup_delay {mins}")
    if mins == 0:
        print("✅ Startup delay disabled (reminders will start immediately on system boot).")
    else:
        print(f"✅ Startup delay set to {mins} minutes after system turn-on.")

def cmd_autostart(action):
    if IS_WINDOWS:
        vbs_file = get_windows_startup_vbs()
        if action == "enable":
            os.makedirs(os.path.dirname(vbs_file), exist_ok=True)
            script_path = os.path.join(BASE_DIR, "reminder.py").replace("\\", "\\\\")
            py_dir = os.path.dirname(sys.executable)
            pythonw = os.path.join(py_dir, "pythonw.exe")
            py_exe = "pythonw.exe" if os.path.exists(pythonw) else "python.exe"
            
            vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "{py_exe} \"\"\"{script_path}\"\"\" daemon", 0, False
'''
            with open(vbs_file, "w") as f:
                f.write(vbs_content)
            print("✅ Windows Auto-start ENABLED!")
            print(f"   • Created Startup launcher: {vbs_file}")
            print("   The script will start silently in background when you log into Windows!")
        elif action == "disable":
            if os.path.exists(vbs_file):
                os.unlink(vbs_file)
            print("✅ Windows Auto-start DISABLED.")
        else:
            print("Usage: autostart [enable|disable]")
    else:
        # Linux autostart
        script_sh = os.path.join(BASE_DIR, "reminder.sh")
        if action == "enable":
            # 1. Desktop Autostart entry (Official standard for X11 & Wayland graphical desktop sessions)
            os.makedirs(AUTOSTART_DIR, exist_ok=True)
            desktop_content = f"""[Desktop Entry]
Type=Application
Name=Water Reminder
Comment=Character overlay reminder to drink water
Exec={script_sh} daemon
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
StartupNotify=false
Terminal=false
Categories=Utility;
"""
            with open(AUTOSTART_DESKTOP_FILE, "w") as f:
                f.write(desktop_content)
            os.chmod(AUTOSTART_DESKTOP_FILE, 0o755)
            
            # Clean up and disable duplicate systemd service if present so two processes do not run
            if os.path.exists(SYSTEMD_SERVICE_FILE):
                try:
                    subprocess.run(["systemctl", "--user", "stop", "water-reminder.service"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    subprocess.run(["systemctl", "--user", "disable", "water-reminder.service"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    os.unlink(SYSTEMD_SERVICE_FILE)
                    subprocess.run(["systemctl", "--user", "daemon-reload"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass
                
            print("✅ Ubuntu/Linux Auto-start ENABLED!")
            print(f"   • Created XDG Autostart: {AUTOSTART_DESKTOP_FILE}")
            print("   The script will now start automatically when you power on or log in!")
            
        elif action == "disable":
            if os.path.exists(AUTOSTART_DESKTOP_FILE):
                os.unlink(AUTOSTART_DESKTOP_FILE)
            if os.path.exists(SYSTEMD_SERVICE_FILE):
                try:
                    subprocess.run(["systemctl", "--user", "stop", "water-reminder.service"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    subprocess.run(["systemctl", "--user", "disable", "water-reminder.service"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass
                os.unlink(SYSTEMD_SERVICE_FILE)
                try:
                    subprocess.run(["systemctl", "--user", "daemon-reload"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass
            print("✅ Ubuntu/Linux Auto-start DISABLED.")
        else:
            print("Usage: autostart [enable|disable]")

def cmd_character(args):
    if not args:
        print("""🎬 Character Management Commands:
  character list                               List all available characters
  character set <id_or_name>                   Switch active character
  character add <video_path> [--name "Name"]   Import video & convert to transparent animation
  character delete <id>                        Delete a custom character
""")
        return

    subcmd = args[0].lower()
    if subcmd == "list":
        cfg = load_config()
        active_id = cfg.get("active_character", "default")
        chars = list_available_characters(cfg)
        print("🎭 Available Reminder Characters:")
        for c in chars:
            is_active = (c["id"] == active_id)
            status_tag = " ⭐ [ACTIVE]" if is_active else ""
            default_tag = " (Built-in)" if c.get("is_default") else " (Custom)"
            print(f"  • {c['name']} (ID: {c['id']}){default_tag} - {c.get('frame_count', 0)} frames @ {c.get('fps', 20)}fps{status_tag}")
    elif subcmd == "set":
        if len(args) < 2:
            print("Usage: python reminder.py character set <character_id_or_name>")
            return
        target = args[1].strip()
        chars = list_available_characters()
        matched = None
        for c in chars:
            if c["id"].lower() == target.lower() or c["name"].lower() == target.lower() or target.lower() in c["name"].lower():
                matched = c
                break
        if not matched:
            print(f"❌ Character '{target}' not found. Run 'python reminder.py character list' to see available characters.")
            return

        set_active_character(matched["id"])
        pid = get_running_pid()
        if pid:
            send_socket_command(f"set_character {matched['id']}")
        print(f"✅ Active character switched to: {matched['name']} (ID: {matched['id']})")
    elif subcmd == "delete":
        if len(args) < 2:
            print("Usage: python reminder.py character delete <character_id>")
            return
        char_id = args[1].strip()
        if char_id == "default":
            print("❌ Cannot delete default Hydro Buddy character.")
            return
        success = delete_custom_character(char_id)
        if success:
            pid = get_running_pid()
            if pid:
                send_socket_command("set_character default")
            print(f"✅ Character '{char_id}' successfully removed.")
        else:
            print(f"❌ Character '{char_id}' not found.")
    elif subcmd == "add":
        if len(args) < 2:
            print("Usage: python reminder.py character add <video_path> [--name \"Name\"] [--mode auto|white|green|blue|black|alpha] [--fps 20]")
            return
        video_path = args[1]
        if not os.path.exists(video_path):
            print(f"❌ Video file not found: {video_path}")
            return

        name = os.path.splitext(os.path.basename(video_path))[0].replace("_", " ").title()
        bg_mode = "auto"
        fps = 20

        i = 2
        while i < len(args):
            if args[i] == "--name" and i + 1 < len(args):
                name = args[i + 1]
                i += 2
            elif args[i] == "--mode" and i + 1 < len(args):
                bg_mode = args[i + 1].lower()
                i += 2
            elif args[i] == "--fps" and i + 1 < len(args):
                fps = int(args[i + 1])
                i += 2
            else:
                i += 1

        print(f"🎬 Processing video character '{name}'...")
        print(f"   • Source video: {video_path}")
        print(f"   • Background removal mode: {bg_mode}")
        print(f"   • Target FPS: {fps}")

        from video_processor import process_video_character
        def on_prog(pct, msg):
            print(f"   [{pct}%] {msg}")

        try:
            meta = process_video_character(
                video_path=video_path,
                character_name=name,
                bg_mode=bg_mode,
                target_fps=fps,
                progress_callback=on_prog
            )
            set_active_character(meta["id"])
            pid = get_running_pid()
            if pid:
                send_socket_command(f"set_character {meta['id']}")
            print(f"\n🎉 SUCCESS! Custom character '{name}' created with {meta['frame_count']} smooth frames.")
            print(f"   • Character ID: {meta['id']}")
            print(f"   • Active Character: {name}")
            print(f"   Run 'python reminder.py test' to preview your new character on screen!")
        except Exception as e:
            print(f"❌ Video processing failed: {e}")

def print_help():
    launcher = "reminder.bat" if IS_WINDOWS else "./reminder.sh"
    print(f"""💧 WATER REMINDER CLI (Cross-Platform) 💧

Usage: python reminder.py <command> [options]
   or: {launcher} <command> [options]

Commands:
  start                         Start the reminder daemon in background
  stop                          Fully stop the reminder daemon
  restart                       Restart the reminder daemon
  status                        Check status, schedule, active character, and glasses
  test                          Immediately show the character reminder on screen
  interval <minutes>            Set reminder interval (e.g. 60 for 1 hour, 30 for 30 min)
  startup-delay <minutes>       Set delay after system turn-on before 1st reminder (e.g. 30, 0 to disable)
  reset-count                   Reset today's water glasses count back to 0
  character list                List all available characters
  character set <id>            Switch active character
  character add <video> [opts]  Upload & convert video to smooth transparent animation
  character delete <id>         Delete custom character
  autostart enable              Automatically start when you power on/log in
  autostart disable             Remove automatic startup
  help                          Show this help message
""")

def cmd_reset_count():
    pid = get_running_pid()
    if pid:
        send_socket_command("reset_count")
    reset_glasses_count()
    print("✅ Today's water glasses count has been reset to 0 🥛.")

def main():
    if len(sys.argv) < 2:
        print_help()
        sys.exit(0)
        
    cmd = sys.argv[1].lower()
    
    if cmd == "start":
        cmd_start()
    elif cmd == "stop":
        cmd_stop()
    elif cmd == "restart":
        cmd_restart()
    elif cmd == "status":
        cmd_status()
    elif cmd == "test":
        cmd_test()
    elif cmd in ("reset-count", "reset_count", "reset"):
        cmd_reset_count()
    elif cmd in ("character", "char", "characters"):
        cmd_character(sys.argv[2:])
    elif cmd == "interval":
        if len(sys.argv) > 2:
            cmd_interval(sys.argv[2])
        else:
            print("Please specify minutes: e.g. python reminder.py interval 60")
    elif cmd in ("startup-delay", "startup_delay", "delay"):
        if len(sys.argv) > 2:
            cmd_startup_delay(sys.argv[2])
        else:
            cfg = load_config()
            cur = cfg.get("startup_delay_minutes", 30)
            print(f"Current startup delay: {cur} minutes. To change: python reminder.py startup-delay <minutes>")
    elif cmd == "autostart":
        action = sys.argv[2].lower() if len(sys.argv) > 2 else "enable"
        cmd_autostart(action)
    elif cmd == "daemon":
        from daemon import run_daemon
        run_daemon(test=False)
    else:
        print(f"Unknown command: {cmd}\n")
        print_help()

if __name__ == "__main__":
    main()
