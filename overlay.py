import os
import sys

# Force X11 backend on Linux for floating overlay & positioning
if sys.platform.startswith("linux") and os.environ.get("DISPLAY"):
    os.environ["GDK_BACKEND"] = "x11"

# Determine UI engine based on OS and installed packages
ENGINE = None
WaterReminderOverlay = None

def _init_engine():
    global ENGINE, WaterReminderOverlay
    
    # On Windows or macOS, Qt is the preferred native cross-platform engine
    if sys.platform in ("win32", "darwin"):
        try:
            from overlay_qt import QtWaterReminderOverlay, QT_AVAILABLE
            if QT_AVAILABLE:
                WaterReminderOverlay = QtWaterReminderOverlay
                ENGINE = "qt"
                return
        except Exception as e:
            print(f"[Overlay] Qt init error: {e}")
            
    # On Linux, try GTK3 first (pre-installed on standard Ubuntu Desktop)
    if sys.platform.startswith("linux") or not ENGINE:
        try:
            from overlay_gtk import WaterReminderOverlay as GtkWaterReminderOverlay, GTK_AVAILABLE
            if GTK_AVAILABLE:
                WaterReminderOverlay = GtkWaterReminderOverlay
                ENGINE = "gtk"
                return
        except Exception:
            pass

    # Fallback to Qt on Linux if GTK is not available
    try:
        from overlay_qt import QtWaterReminderOverlay, QT_AVAILABLE
        if QT_AVAILABLE:
            WaterReminderOverlay = QtWaterReminderOverlay
            ENGINE = "qt"
            return
    except Exception:
        pass

    raise RuntimeError(
        "No supported GUI toolkit found!\n"
        "  - On Ubuntu/Debian: Ensure python3-gi is installed (sudo apt install python3-gi gir1.2-gtk-3.0)\n"
        "  - On Windows/macOS: Install PyQt6 (pip install PyQt6)\n"
    )

_init_engine()

def run_overlay():
    if ENGINE == "gtk":
        from overlay_gtk import run_standalone
        run_standalone()
    elif ENGINE == "qt":
        from overlay_qt import run_standalone
        run_standalone()

if __name__ == "__main__":
    print(f"💧 Starting Water Reminder overlay using engine: {ENGINE.upper()}")
    run_overlay()
