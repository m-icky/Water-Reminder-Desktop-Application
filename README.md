# 💧 Water Reminder Desktop Application for Ubuntu

A modern, transparent desktop character reminder for Ubuntu Linux that reminds you to drink water at custom intervals (default: every 1 hour) with interactive options and automatic system startup.

---

## ✨ Features

- **Transparent Character Animation**: Renders your custom character animation (`reminder.mp4`) as a borderless, floating overlay on top of all applications (`always-on-top`) at the bottom-right corner of the screen.
- **Dynamic Speech Bubble**: A frosted-glass cloud dialog with a pointer tail directed at the character.
- **Interactive Action Buttons**:
  - **✅ Yes, I Drank Water**:
    - Tracks your daily hydration count (e.g., `Today: 3 🥛`).
    - Opens a follow-up selector asking when to remind you next: **30 mins**, **1 hour**, **2 hours**, or custom minutes.
    - Displays friendly confirmation and automatically hides the character.
  - **⏰ Snooze (10 mins)**:
    - Snoozes the reminder and reminds you again in 10 minutes.
  - **⚙️ Settings**:
    - Easily adjust default intervals or toggle sound on/off.
  - **✕ Dismiss**:
    - Dismisses the reminder window until the next interval.
- **Audio Sound Effect**: Plays the voice/sound from your video whenever the reminder appears.
- **Smart Sleep & Lock Screen Detection**:
  - Uses DBus screensaver detection to avoid firing when the laptop screen is locked or asleep.
  - Triggers immediately when you unlock your laptop if a reminder was due.
- **Auto-Start on Boot/Login**:
  - Automatically configured with Ubuntu XDG Autostart (`~/.config/autostart/water-reminder.desktop`) and Systemd user service.
  - Automatically stops when you shut down the laptop, and resumes when you power it on.

- **Daily Hydration Counter & Date Rollover**:
  - Automatically resets the water intake count to `0` at the start of each new day (`00:00`).
  - Archives previous days' totals into history (`config.json`) so you can look back at past days.
  - Manual reset option available anytime via `./reminder.sh reset-count`.

---

## 🚀 Quick Usage Commands

All actions can be managed using `./reminder.sh` or `python3 reminder.py`:

| Command | Description |add a wter botton in the hand

|---|---|
| `./reminder.sh test` | **Immediately show the character reminder on screen** to test animations and buttons |
| `./reminder.sh status` | Check running state, today's date, glasses drank today, and past days history |
| `./reminder.sh reset-count` | **Reset today's water count back to 0** manually |
| `./reminder.sh start` | Start the background daemon |
| `./reminder.sh stop` | **Fully stop** the reminder daemon |
| `./reminder.sh restart` | Restart the background daemon |
| `./reminder.sh interval <minutes>` | Change default reminder interval (e.g. `./reminder.sh interval 45` or `60`) |
| `./reminder.sh autostart enable` | Enable automatic launch when turning on / logging into Ubuntu |
| `./reminder.sh autostart disable` | Disable automatic launch on boot |

---

## 📁 File Structure

- `reminder.sh` — Convenient shell script launcher with executable permissions.
- `reminder.py` — Main CLI controller and entry point.
- `daemon.py` — Background service handling timer scheduling, IPC socket, and screensaver checks.
- `overlay.py` — GTK3 floating transparent window with custom Cairo speech bubble and 20 FPS animation loop.
- `audio.py` — Asynchronous audio player for reminder audio.
- `config.py` & `config.json` — Persistent configuration and hydration tracking.
- `assets/frames/` — 202 processed transparent frames from `reminder.mp4`.
- `assets/smoke/` — 10 extracted transparent smoke frames (`smoke_01.png` to `smoke_10.png`) and aligned closing animation frames (`close_anim_01.png` to `close_anim_10.png`).
- `reminder.wav` & `reminder.ogg` — Extracted audio from `reminder.mp4`.
