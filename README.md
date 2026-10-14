# 💧 Cross-Platform Water Reminder Desktop Application

A modern, transparent desktop character reminder for **Ubuntu Linux** and **Windows** (also compatible with macOS) that reminds you to drink water at custom intervals (default: every 1 hour) with interactive speech bubbles, daily hydration tracking, smooth cartoon smoke exit animations, smart lock-screen detection, and automatic system startup.

---

## 📑 Table of Contents

1. [Platform Comparison: How It Works](#-platform-comparison-how-it-works)
2. [🐧 How to Work in Ubuntu Linux](#-how-to-work-in-ubuntu-linux)
   - [Prerequisites & System Setup](#1-prerequisites--system-setup-ubuntu)
   - [Step 1: Test the Overlay](#2-test-the-overlay-ubuntu)
   - [Step 2: Start the Background Daemon](#3-start-the-background-daemon-ubuntu)
   - [Step 3: Enable Auto-Start on Boot / Login](#4-enable-auto-start-on-boot--login-ubuntu)
   - [Step 4: Check Status & Daily Hydration](#5-check-status--daily-hydration-ubuntu)
   - [Ubuntu Troubleshooting & Tips](#6-ubuntu-troubleshooting--tips)
3. [🪟 How to Work in Windows](#-how-to-work-in-windows)
   - [Prerequisites & System Setup](#1-prerequisites--system-setup-windows)
   - [Step 1: Test the Overlay](#2-test-the-overlay-windows)
   - [Step 2: Start the Background Daemon (Silent)](#3-start-the-background-daemon-silent-windows)
   - [Step 3: Enable Auto-Start on Windows Logon](#4-enable-auto-start-on-windows-logon)
   - [Step 4: Check Status & Daily Hydration](#5-check-status--daily-hydration-windows)
   - [Windows Troubleshooting & Tips](#6-windows-troubleshooting--tips)
4. [🎮 Interactive Overlay Controls](#-interactive-overlay-controls)
5. [📊 Complete Command Reference](#-complete-command-reference)
6. [⚙️ Configuration (`config.json`)](#️-configuration-configjson)
7. [📁 Project File Structure](#-project-file-structure)

---

## ⚡ Platform Comparison: How It Works

The application detects your operating system automatically and uses the native UI engine and audio system best suited for that platform:

| Feature | 🐧 Ubuntu Linux | 🪟 Windows (10 / 11) |
|---|---|---|
| **GUI Toolkit** | Native **GTK3** (`python3-gi`, Cairo surface) | Native **PyQt6** (`PyQt6` / `PySide6`) |
| **Window Layer** | Frameless, floating X11 overlay (`always-on-top`) | Frameless, translucent Qt window (`WindowStaysOnTopHint`) |
| **Audio Playback** | Native PulseAudio / PipeWire / ALSA (`paplay` / `pw-play` / `aplay`) | Native Windows Multimedia API (`winsound.PlaySound`) |
| **Lock Screen Detection** | DBus (`org.gnome.ScreenSaver` / `org.freedesktop.ScreenSaver`) | Windows Win32 API (`OpenInputDesktop`) |
| **Silent Background Daemon** | Background POSIX process group via `./reminder.sh` | Detached `pythonw.exe` process (no command prompt window) |
| **Autostart Mechanism** | XDG Autostart (`~/.config/autostart`) & Systemd User Service | Startup folder script (`%APPDATA%\...\Startup\WaterReminder.vbs`) |
| **IPC Communication** | Localhost TCP Socket (`127.0.0.1:<port>`) + Unix domain socket | Localhost TCP Socket (`127.0.0.1:<port>`) |

---

## 🐧 How to Work in Ubuntu Linux

Ubuntu desktop includes Python and GTK3 pre-installed. Follow these steps to set up and run the application.

### 1. Prerequisites & System Setup (Ubuntu)

Open your terminal (`Ctrl + Alt + T`) and navigate to the project directory:

```bash
cd ~/Documents/Reminder
```

Install the required GTK3 and imaging bindings (usually already present on Ubuntu Desktop):

```bash
# Update package index and install GTK3 Python bindings & Pillow
sudo apt update
sudo apt install -y python3 python3-gi gir1.2-gtk-3.0 python3-pil pulseaudio-utils
```

*(Optional)* If you prefer running inside a virtual environment using pip:
```bash
pip install -r requirements.txt
```

Ensure the launcher scripts are executable:
```bash
chmod +x reminder.sh reminder.py
```

---

### 2. Test the Overlay (Ubuntu)

Before starting the background service, you can immediately test the character animation, speech bubble, buttons, and sound effect on your screen:

```bash
./reminder.sh test
```
*or directly:*
```bash
python3 reminder.py test
```

> **What happens**: The character will appear floating on the bottom-right corner of your screen. Click **"Yes, I Drank Water"**, **"Snooze"**, or **"Dismiss"** to watch the smooth smoke exit animation.

---

### 3. Start the Background Daemon (Ubuntu)

Start the reminder service in the background:

```bash
./reminder.sh start
```

You will see:
```text
🚀 Starting Water Reminder daemon...
✅ Water Reminder daemon successfully started! (PID: 12345)
   The reminder character will appear every hour on the bottom-right.
```

The daemon runs silently in the background, keeping track of your schedule even while you work.

---

### 4. Enable Auto-Start on Boot / Login (Ubuntu)

To ensure the water reminder starts automatically whenever you turn on your computer or log into Ubuntu:

```bash
./reminder.sh autostart enable
```

This creates:
- **XDG Autostart Desktop Entry**: `~/.config/autostart/water-reminder.desktop` (launches seamlessly when you log into your graphical desktop session).

To disable automatic startup at any time:
```bash
./reminder.sh autostart disable
```

---

### 5. Check Status & Daily Hydration (Ubuntu)

To check if the daemon is running, inspect how many glasses of water you have consumed today, and view the countdown to your next reminder:

```bash
./reminder.sh status
```

**Example output:**
```text
==================================================
           💧 WATER REMINDER STATUS           
==================================================
  ● Platform:       Ubuntu/Linux
  ● Status:         RUNNING (PID: 12345, Engine: GTK)
  ● Today's Date:   2026-10-13 (Resets daily at 00:00)
  ● Glasses Today:  3 🥛
  ● Interval:       Every 60 minutes
  ● Next Reminder:  In 42.5 minutes (2550s)
  ● Screen State:   Active / Unlocked
  ● Sound Effects:  Enabled 🔊
  ● Past Days:      2026-10-12: 8🥛 | 2026-10-11: 7🥛
  ● Auto-start:     Enabled (Starts on boot/login) ✅
==================================================
```

#### Other Handy Ubuntu Commands:
- **Change reminder interval to 45 minutes**:
  ```bash
  ./reminder.sh interval 45
  ```
- **Reset today's water glass count back to 0**:
  ```bash
  ./reminder.sh reset-count
  ```
- **Stop the daemon completely**:
  ```bash
  ./reminder.sh stop
  ```
- **Restart the daemon**:
  ```bash
  ./reminder.sh restart
  ```

---

### 6. Ubuntu Troubleshooting & Tips

- **Wayland vs X11 Display**:
  - The script automatically exports `GDK_BACKEND=x11` inside `reminder.sh` and `reminder.py`. This ensures proper transparent window rendering and borderless `always-on-top` positioning on both standard X11 and GNOME Wayland sessions (via XWayland).
- **Missing GTK Module Error (`ModuleNotFoundError: No module named 'gi'`)**:
  - Run `sudo apt install python3-gi gir1.2-gtk-3.0`.
  - Alternatively, if you use a Python virtualenv where system GTK packages are not linked, install PyQt6 via `pip install PyQt6` and the application will seamlessly switch to the Qt engine on Linux.
- **Audio Output**:
  - Ubuntu uses `paplay` (PulseAudio), `pw-play` (PipeWire), or `aplay` (ALSA) to play `reminder.wav`. Ensure your system volume is unmuted.
- **Logs**:
  - Check `reminder.log` in the project directory if the daemon fails to start:
    ```bash
    tail -f reminder.log
    ```

---

## 🪟 How to Work in Windows

On Windows 10 and 11, the application uses **PyQt6** for crisp floating transparent rendering and native Windows APIs for audio and lock detection.

### 1. Prerequisites & System Setup (Windows)

1. **Install Python**:
   - If you do not have Python installed, download it from [python.org](https://www.python.org/) or install it from the Microsoft Store.
   - ⚠️ **Important**: When installing Python from the installer, make sure to check the box: **"Add Python to PATH"**.

2. **Open Command Prompt or PowerShell**:
   - Press `Win + R`, type `cmd` (or `powershell`), and press Enter.
   - Navigate to the project folder:
     ```cmd
     cd C:\path\to\Reminder
     ```

3. **Install Dependencies**:
   Install the required Python packages (`PyQt6` and `Pillow`):
   ```cmd
   pip install -r requirements.txt
   ```
   *(If `pip` is not recognized, run: `python -m pip install -r requirements.txt`)*

---

### 2. Test the Overlay (Windows)

Test the transparent character animation, dialog bubble, and audio immediately:

In Command Prompt (`cmd`):
```cmd
reminder.bat test
```
*or in PowerShell:*
```powershell
.\reminder.bat test
```
*or using python directly:*
```cmd
python reminder.py test
```

> **What happens**: The animated character will appear at the bottom-right corner of your desktop, playing `reminder.wav` through Windows native audio (`winsound`).

---

### 3. Start the Background Daemon (Silent) (Windows)

To start the reminder background service:

```cmd
reminder.bat start
```

> 💡 **Silent Execution**: The daemon is automatically launched via `pythonw.exe` (Windows Python Windowless Launcher). **No black command prompt window will stay open!** You can close your terminal and the reminder will continue running in the background.

---

### 4. Enable Auto-Start on Windows Logon

To automatically start the reminder whenever you power on or log into your Windows user account:

```cmd
reminder.bat autostart enable
```

**How it works**:
- It creates a silent launcher script `WaterReminder.vbs` inside your personal Windows Startup folder:
  `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\WaterReminder.vbs`
- When you log into Windows, Windows Script Host silently executes `pythonw.exe reminder.py daemon` without flashing any console window.

To disable Windows startup:
```cmd
reminder.bat autostart disable
```

---

### 5. Check Status & Daily Hydration (Windows)

Check the current status and tracker info:

```cmd
reminder.bat status
```

**Example output:**
```text
==================================================
           💧 WATER REMINDER STATUS           
==================================================
  ● Platform:       Windows
  ● Status:         RUNNING (PID: 8412, Engine: QT)
  ● Today's Date:   2026-10-13 (Resets daily at 00:00)
  ● Glasses Today:  4 🥛
  ● Interval:       Every 60 minutes
  ● Next Reminder:  In 38.0 minutes (2280s)
  ● Screen State:   Active / Unlocked
  ● Sound Effects:  Enabled 🔊
  ● Past Days:      2026-10-12: 6🥛 | 2026-10-11: 8🥛
  ● Auto-start:     Enabled (Starts on boot/login) ✅
==================================================
```

#### Other Handy Windows Commands:
- **Change reminder interval to 45 minutes**:
  ```cmd
  reminder.bat interval 45
  ```
- **Reset today's water glass count back to 0**:
  ```cmd
  reminder.bat reset-count
  ```
- **Stop the daemon**:
  ```cmd
  reminder.bat stop
  ```
- **Restart the daemon**:
  ```cmd
  reminder.bat restart
  ```

---

### 6. Windows Troubleshooting & Tips

- **`'python'` or `'pip'` is not recognized**:
  - Python was installed without the "Add Python to PATH" option. Re-run the Python installer, select **Modify**, and check **Add Python to environment variables**.
- **PyQt6 Installation Errors**:
  - Update `pip` before installing:
    ```cmd
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    ```
- **Windows Lock Screen Detection**:
  - When you lock Windows (`Win + L`) or your monitor enters power-saving sleep, the daemon detects that the desktop is inactive via the `OpenInputDesktop` API. It holds off triggering overlays until you unlock your screen.
- **Audio Output**:
  - Audio uses standard Windows `winsound` API. No codecs or additional media players are required. Ensure your Windows sound output device is connected and volume is turned up.
- **Viewing Logs on Windows**:
  - If you encounter issues, view `reminder.log` in the project folder with Notepad:
    ```cmd
    notepad reminder.log
    ```

---

## 🎮 Interactive Overlay Controls

Whenever the reminder character appears on screen:

- **✅ Yes, I Drank Water**:
  - Increments your daily hydration counter (`Today: X 🥛`).
  - Displays quick follow-up buttons asking when to remind you next:
    - **30 mins** | **1 hour** | **2 hours** | **Custom**
  - Triggers a smooth smoke puff animation (`assets/smoke/smoke_01.png` - `smoke_10.png`) as the character vanishes.
- **⏰ Snooze (10 mins)**:
  - Temporarily dismisses the overlay and reminds you again in 10 minutes.
- **⚙️ Settings**:
  - Quick access to adjust reminder frequency or toggle audio alerts.
- **✕ Dismiss**:
  - Closes the overlay immediately until the next scheduled reminder interval.

---

## 📊 Complete Command Reference

| Command | Ubuntu / Linux Syntax | Windows Syntax | Description |
|---|---|---|---|
| **Test** | `./reminder.sh test` | `reminder.bat test` | Immediately shows the floating reminder on screen to verify animations, sound, and buttons. |
| **Status** | `./reminder.sh status` | `reminder.bat status` | Displays running PID, active engine, next reminder countdown, screen lock status, and today's water glasses count. |
| **Start** | `./reminder.sh start` | `reminder.bat start` | Starts the background daemon service. |
| **Stop** | `./reminder.sh stop` | `reminder.bat stop` | Stops the running daemon and releases ports/sockets. |
| **Restart** | `./reminder.sh restart` | `reminder.bat restart` | Restarts the daemon service. |
| **Set Interval** | `./reminder.sh interval <mins>` | `reminder.bat interval <mins>` | Changes reminder interval (e.g., `interval 30` or `interval 60`). |
| **Reset Counter** | `./reminder.sh reset-count` | `reminder.bat reset-count` | Manually resets today's water glasses counter back to 0. |
| **Enable Autostart**| `./reminder.sh autostart enable` | `reminder.bat autostart enable`| Registers the app to start automatically on system boot or user logon. |
| **Disable Autostart**| `./reminder.sh autostart disable`| `reminder.bat autostart disable`| Removes system boot / login startup registration. |

*(Note: On both platforms, you can also run `python reminder.py <command>`.)*

---

## ⚙️ Configuration (`config.json`)

All persistent settings, today's hydration metrics, and history are saved in `config.json` at the root of the project:

```json
{
  "interval_minutes": 60,
  "snooze_minutes": 10,
  "sound_enabled": true,
  "next_reminder_time": 1791868385,
  "last_reminder_time": 1791864768,
  "last_drank_time": 1791864785,
  "glasses_today": 3,
  "today_date": "2026-10-13",
  "daily_history": {
    "2026-10-11": 7,
    "2026-10-12": 5
  }
}
```

- **Daily Auto-Reset**: At midnight (`00:00`), `glasses_today` automatically resets to `0`, and the previous day's count is archived into `daily_history`.
- **⚙️ Gear Icon & Settings**: Click the `⚙️` Gear button at the top-right of the reminder speech bubble (or click `⚙️ Settings & Audio` in the footer) to open settings directly.
- **👤 Custom Character Video Upload**:
  - **Upload Your Own Video**: In Settings, click **`🎬 Upload Video Character...`** and select any video (`.mp4`, `.webm`, `.mov`, `.mkv`, `.avi`, `.gif`).
  - **Automatic Transparent Background Processing**: Automatically converts the video into transparent background frames (`assets/characters/<name>/frames/`) with soft edge anti-aliasing and color despill.
  - **Supported Background Modes**:
    - `✨ Auto-Detect Background`: Analyzes corner and border pixels to automatically detect and key out solid studio backgrounds.
    - `⚪ White / Light Background`: Keys out bright studio/white backgrounds.
    - `🟢 Green Screen (Chroma Key)`: Keys out green screen with despill color neutralization.
    - `🔵 Blue Screen`: Keys out blue screen backgrounds.
    - `⚫ Black / Dark Background`: Keys out dark backgrounds.
    - `🎞️ Native Transparency (Alpha)`: Directly decodes transparent WebM, ProRes 4444, or GIF animations.
  - **Smooth Playback**: Video is scaled and centered into the optimal `270x480` overlay format and smoothly looped.
  - **Character Management**: Switch between the default Hydro Buddy and any custom characters using the dropdown, or delete custom characters with the `🗑️` button.
- **🎵 Custom Audio Selection**:
  - Choose between built-in sounds (`🔔 Default Alert`, `💧 Water Drop`, `🎵 Gentle Chime`) or custom files from the dropdown list.
  - Click **▶ Play / ■ Stop** to preview any sound before selecting it.
  - Click **📁 Add Audio File...** to select any `.wav`, `.mp3`, `.ogg`, or `.flac` audio file from your computer—it is automatically imported and set as your active reminder alert!
- **Sound Toggle**: Toggle `sound_enabled` between `true` and `false` (or click `🔊 Sound: ON / OFF` in Settings) to enable or disable audio.

---

## 🎬 CLI Character Management

You can also manage and import character videos directly from the command line:

```bash
# List all installed characters
python3 reminder.py character list

# Upload a custom video and convert it to transparent animation frames
python3 reminder.py character add my_character.mp4 --name "My Mascot" --mode auto --fps 20

# Switch active character
python3 reminder.py character set "My Mascot"
# or switch back to default:
python3 reminder.py character set default

# Delete a custom character
python3 reminder.py character delete my_mascot_12345
```

---

## 📁 Project File Structure

```text
Reminder/
├── reminder.sh            # Linux launcher script (sets GDK_BACKEND=x11)
├── reminder.bat           # Windows launcher script (CMD & PowerShell compatible)
├── reminder.py            # Main CLI entry point and daemon manager
├── daemon.py              # Background scheduling daemon, IPC server & lock screen monitor
├── overlay.py             # UI switcher: auto-detects GTK (Linux) or Qt (Windows)
├── overlay_gtk.py         # Native GTK3 floating transparent overlay for Ubuntu
├── overlay_qt.py          # Native PyQt6 floating transparent overlay for Windows
├── audio.py               # Cross-platform audio player (winsound / paplay / aplay)
├── video_processor.py     # Video to transparent background frames converter & optimizer
├── config.py              # Configuration manager & daily intake tracker
├── config.json            # Persistent user settings and history
├── requirements.txt       # Python dependencies (Pillow, numpy, PyQt6 on Windows)
├── assets/
│   ├── frames/            # Default character animation frames (f_0001.png - f_0202.png)
│   ├── characters/        # Custom user-uploaded character folders & metadata
│   ├── smoke/             # 10 cartoon smoke frames for smooth exit animation
│   └── sounds/            # Built-in and custom alert audio files
├── reminder.wav           # Reminder audio alert (WAV format)
├── reminder.ogg           # Reminder audio alert (OGG format)
├── reminder.mp4           # Reference reminder animation video
├── reminder.log           # Background service log file
├── reminder.pid           # Running daemon Process ID
└── reminder.port          # TCP IPC communication port
```

---

## 📜 License

MIT License. Feel free to customize the character animations, audio, and intervals to stay healthy and hydrated!
