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
    PID_FILE, SOCKET_FILE, load_config, save_config, reset_glasses_count, get_today_str
)

AUTOSTART_DIR = os.path.expanduser("~/.config/autostart")
AUTOSTART_DESKTOP_FILE = os.path.join(AUTOSTART_DIR, "water-reminder.desktop")
SYSTEMD_USER_DIR = os.path.expanduser("~/.config/systemd/user")
SYSTEMD_SERVICE_FILE = os.path.join(SYSTEMD_USER_DIR, "water-reminder.service")

def send_socket_command(cmd, timeout=3.0):
    if not os.path.exists(SOCKET_FILE):
        return None
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(SOCKET_FILE)
        s.sendall(cmd.encode("utf-8"))
        data = s.recv(4096).decode("utf-8")
        s.close()
        return json.loads(data)
    except Exception:
        return None

def is_process_running(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

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
    print("=" * 48)
    print("           💧 WATER REMINDER STATUS           ")
    print("=" * 48)
    
    today_str = cfg.get("today_date", get_today_str())
    if pid and sock_resp:
        rem_mins = sock_resp.get("next_reminder_in_minutes", 0)
        rem_secs = sock_resp.get("next_reminder_in_seconds", 0)
        locked = sock_resp.get("is_screen_locked", False)
        print(f"  ● Status:         RUNNING (PID: {pid})")
        print(f"  ● Today's Date:   {today_str} (Resets daily at 00:00)")
        print(f"  ● Glasses Today:  {sock_resp.get('glasses_today', 0)} 🥛")
        print(f"  ● Interval:       Every {sock_resp.get('interval_minutes')} minutes")
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
        print(f"  ● Sound Effects:  {'Enabled 🔊' if cfg.get('sound_enabled', True) else 'Disabled 🔇'}")
        
    history = cfg.get("daily_history", {})
    if history:
        recent = sorted(history.items(), reverse=True)[:3]
        history_str = " | ".join([f"{d}: {c}🥛" for d, c in recent])
        print(f"  ● Past Days:      {history_str}")
        
    autostart_active = os.path.exists(AUTOSTART_DESKTOP_FILE) or os.path.exists(SYSTEMD_SERVICE_FILE)
    print(f"  ● Auto-start:     {'Enabled (Starts on login) ✅' if autostart_active else 'Disabled ❌'}")
    print("=" * 48)

def cmd_start():
    pid = get_running_pid()
    if pid:
        print(f"💧 Water Reminder is ALREADY running (PID: {pid}).")
        return
        
    print("🚀 Starting Water Reminder daemon...")
    log_file = os.path.join(BASE_DIR, "reminder.log")
    with open(log_file, "a") as log:
        proc = subprocess.Popen(
            [sys.executable, os.path.join(BASE_DIR, "reminder.py"), "daemon"],
            stdout=log,
            stderr=log,
            preexec_fn=os.setpgrp,
            close_fds=True
        )
        
    # Wait up to 2 seconds for PID file & socket
    for _ in range(20):
        time.sleep(0.1)
        if get_running_pid():
            break
            
    running_pid = get_running_pid()
    if running_pid:
        print(f"✅ Water Reminder daemon successfully started! (PID: {running_pid})")
        print("   The reminder character will appear every hour on the bottom-right.")
        print(f"   Use '{sys.argv[0]} test' to see character immediately.")
        print(f"   Use '{sys.argv[0]} stop' to stop it anytime.")
    else:
        print("❌ Failed to start daemon. Check reminder.log for details.")

def cmd_stop():
    pid = get_running_pid()
    if not pid:
        print("○ Water Reminder is not currently running.")
        # Clean up stale files
        if os.path.exists(PID_FILE): os.unlink(PID_FILE)
        if os.path.exists(SOCKET_FILE): os.unlink(SOCKET_FILE)
        return
        
    print(f"🛑 Stopping Water Reminder daemon (PID: {pid})...")
    # Try socket stop first
    send_socket_command("stop", timeout=1.0)
    
    # Wait or send SIGTERM
    for _ in range(15):
        time.sleep(0.1)
        if not is_process_running(pid):
            break
            
    if is_process_running(pid):
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
            
    # Clean files
    if os.path.exists(PID_FILE):
        try: os.unlink(PID_FILE)
        except OSError: pass
    if os.path.exists(SOCKET_FILE):
        try: os.unlink(SOCKET_FILE)
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
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk
    from overlay import WaterReminderOverlay
    
    overlay = WaterReminderOverlay()
    overlay.show_overlay()
    print("✅ Character reminder is now active on your screen!")
    Gtk.main()

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
    
    # Update running daemon if active
    resp = send_socket_command(f"set_interval {mins}")
    print(f"✅ Reminder interval set to every {mins} minutes.")

def cmd_autostart(action):
    script_sh = os.path.join(BASE_DIR, "reminder.sh")
    
    if action == "enable":
        # 1. Desktop Autostart entry
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
        
        # 2. Systemd user service
        os.makedirs(SYSTEMD_USER_DIR, exist_ok=True)
        service_content = f"""[Unit]
Description=Water Reminder Desktop Application
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
WorkingDirectory={BASE_DIR}
ExecStart=/usr/bin/python3 {BASE_DIR}/reminder.py daemon
Restart=on-failure
RestartSec=5
Environment=DISPLAY=:0
Environment=GDK_BACKEND=x11

[Install]
WantedBy=graphical-session.target
"""
        with open(SYSTEMD_SERVICE_FILE, "w") as f:
            f.write(service_content)
            
        # Try enabling systemd service
        try:
            subprocess.run(["systemctl", "--user", "daemon-reload"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["systemctl", "--user", "enable", "water-reminder.service"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
            
        print("✅ Auto-start ENABLED!")
        print(f"   • Created XDG Autostart: {AUTOSTART_DESKTOP_FILE}")
        print(f"   • Created Systemd User Service: {SYSTEMD_SERVICE_FILE}")
        print("   The script will now start automatically when you power on or log in!")
        
    elif action == "disable":
        if os.path.exists(AUTOSTART_DESKTOP_FILE):
            os.unlink(AUTOSTART_DESKTOP_FILE)
        if os.path.exists(SYSTEMD_SERVICE_FILE):
            try:
                subprocess.run(["systemctl", "--user", "disable", "water-reminder.service"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
            os.unlink(SYSTEMD_SERVICE_FILE)
            try:
                subprocess.run(["systemctl", "--user", "daemon-reload"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        print("✅ Auto-start DISABLED.")
    else:
        print("Usage: autostart [enable|disable]")

def print_help():
    print("""💧 WATER REMINDER CLI 💧

Usage: python3 reminder.py <command> [options]
   or: ./reminder.sh <command> [options]

Commands:
  start                Start the reminder daemon in background
  stop                 Fully stop the reminder daemon
  restart              Restart the reminder daemon
  status               Check status, schedule, and today's water glasses
  test                 Immediately show the character reminder on screen
  interval <minutes>   Set reminder interval (e.g. 60 for 1 hour, 30 for 30 min)
  reset-count          Reset today's water glasses count back to 0
  autostart enable     Automatically start when you power on/log into Ubuntu
  autostart disable    Remove automatic startup
  help                 Show this help message
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
    elif cmd == "interval":
        if len(sys.argv) > 2:
            cmd_interval(sys.argv[2])
        else:
            print("Please specify minutes: e.g. python3 reminder.py interval 60")
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
