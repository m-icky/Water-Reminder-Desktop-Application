# 💧 Cross-Platform Water Reminder Desktop Application (Ubuntu Linux & Windows)

A modern, transparent desktop character reminder for **Ubuntu Linux** and **Windows** (also compatible with macOS) that reminds you to drink water at custom intervals (default: every 1 hour) with interactive options, daily hydration tracking, smooth cartoon smoke exit animations, and automatic system startup.

---

## ✨ Features

- **Cross-Platform Compatibility**:
  - **Ubuntu Linux**: Runs natively out-of-the-box using pre-installed GTK3 (`python3-gi`) without needing heavy extra packages.
  - **Windows 10/11**: Runs using PyQt6/PySide6 with standard Windows audio (`winsound`), Windows Lock Screen detection, and silent Startup execution.
  - Automatic UI engine detection: GTK3 on Linux, Qt on Windows.
- **Transparent Character Animation**: Renders your custom character animation (`reminder.mp4`) as a borderless, floating overlay on top of all applications (`always-on-top`) at the bottom-right corner of the screen.
- **Dynamic Speech Bubble**: A frosted-glass cloud dialog with a pointer tail directed at the character.
- **Interactive Action Buttons**:
  - **✅ Yes, I Drank Water**:
    - Tracks your daily hydration count (e.g., `Today: 3 🥛`).
    - Opens a follow-up selector asking when to remind you next: **30 mins**, **1 hour**, **2 hours**, or custom minutes.
    - Displays friendly confirmation and closes with a smooth smoke animation.
  - **⏰ Snooze (10 mins)**:
    - Snoozes the reminder and reminds you again in 10 minutes.
  - **⚙️ Settings**:
    - Easily adjust default intervals or toggle sound on/off.
  - **✕ Dismiss**:
    - Dismisses the reminder window until the next scheduled interval.
- **💨 Smoke Disappearance Animation**:
  - When closing or taking action, a smooth 10-frame cartoon smoke animation (`smoke_01.png` to `smoke_10.png`) plays as the character vanishes.
- **Audio Sound Effect**: Plays the voice/sound effect whenever the reminder appears (using native `winsound` on Windows and PulseAudio/ALSA on Linux).
- **Smart Sleep & Lock Screen Detection**:
  - **Linux**: Queries DBus screensaver to avoid firing when the laptop is locked or asleep.
  - **Windows**: Checks `OpenInputDesktop` API to detect Windows lock screen (Win+L) or screen sleep.
  - Triggers immediately when you unlock your computer if a reminder was due.
- **Auto-Start on Boot/Login**:
  - **Linux**: Configured via XDG Autostart (`~/.config/autostart/water-reminder.desktop`) and Systemd user service.
  - **Windows**: Configured via Windows Startup folder (`WaterReminder.vbs`) to start silently in the background on logon.
- **Daily Hydration Counter & Date Rollover**:
  - Automatically resets the water intake count to `0` at midnight (`00:00`) every day.
  - Archives previous days' totals into history (`config.json`) so you can track your hydration over time.
  - Manual reset option available anytime via `reset-count`.

---

## 🛠️ Installation & Setup

### On Ubuntu Linux
Ubuntu includes GTK3 and Python pre-installed. No pip installations required:
```bash
# Optional: Ensure GTK3 bindings are present (normally already installed on Ubuntu Desktop)
sudo apt update && sudo apt install -y python3-gi gir1.2-gtk-3.0
```

### On Windows
Open PowerShell or Command Prompt in the repository folder:
```cmd
pip install -r requirements.txt
```

---

## 🚀 Usage Commands

### Ubuntu / Linux Commands:
```bash
./reminder.sh test               # Immediately test the character on your screen
./reminder.sh status             # Check daemon status, today's glasses, and next reminder
./reminder.sh start              # Start the background daemon
./reminder.sh stop               # Fully stop the reminder daemon
./reminder.sh restart            # Restart the daemon
./reminder.sh interval 45        # Change reminder interval (in minutes)
./reminder.sh reset-count        # Reset today's water glasses count to 0
./reminder.sh autostart enable   # Enable automatic startup on login
./reminder.sh autostart disable  # Disable automatic startup
```

### Windows Commands:
```cmd
reminder.bat test               rem Immediately test the character on your screen
reminder.bat status             rem Check daemon status, today's glasses, and next reminder
reminder.bat start              rem Start the background daemon (runs silently via pythonw)
reminder.bat stop               rem Fully stop the reminder daemon
reminder.bat restart            rem Restart the daemon
reminder.bat interval 45        rem Change reminder interval (in minutes)
reminder.bat reset-count        rem Reset today's water glasses count to 0
reminder.bat autostart enable   rem Enable automatic startup on Windows boot/logon
reminder.bat autostart disable  rem Disable automatic startup
```

*(You can also run directly with `python reminder.py <command>` on any OS.)*

---

## 📊 Command Reference

| Command | Description |
|---|---|
| `test` | **Immediately show the character reminder on screen** to test animations, audio, and buttons |
| `status` | View running status, today's date, glasses drank today, next reminder countdown, and history |
| `start` | Start the background daemon in the background |
| `stop` | **Fully stop** the reminder daemon and clean up sockets |
| `restart` | Stop and restart the daemon |
| `reset-count` | **Reset today's water count back to 0** manually |
| `interval <mins>` | Change reminder interval (e.g. `interval 60` for 1 hour, `interval 30` for 30 minutes) |
| `autostart enable` | Enable launch on system boot / user login |
| `autostart disable` | Disable automatic launch on boot |

---

## 📁 File Structure

- `reminder.py` — Cross-platform CLI entry point and daemon manager.
- `reminder.sh` — Linux launcher script.
- `reminder.bat` — Windows launcher script.
- `requirements.txt` — Python dependencies (PyQt6 on Windows, Pillow).
- `daemon.py` — Background service managing schedule, localhost TCP IPC socket, and screensaver checks.
- `overlay.py` — Intelligent UI engine switcher (dispatches to GTK on Linux or Qt on Windows).
- `overlay_gtk.py` — Native GTK3 floating transparent overlay for Ubuntu/Linux.
- `overlay_qt.py` — Native PyQt/PySide floating transparent overlay for Windows/macOS.
- `audio.py` — Cross-platform sound player (`winsound` on Windows, `paplay`/`aplay` on Linux).
- `config.py` & `config.json` — Persistent configuration, daily hydration tracking, and date archiving.
- `assets/frames/` — 202 processed transparent animation frames (`f_0001.png` to `f_0202.png`).
- `assets/smoke/` — 10 extracted transparent smoke frames (`smoke_01.png` to `smoke_10.png`) and closing animation sequence.
- `reminder.wav` & `reminder.ogg` — Reminder audio.
