import os
import json
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
FRAMES_DIR = os.path.join(ASSETS_DIR, "frames")
SMOKE_DIR = os.path.join(ASSETS_DIR, "smoke")
SOUNDS_DIR = os.path.join(ASSETS_DIR, "sounds")
AUDIO_FILE = os.path.join(BASE_DIR, "reminder.wav")
AUDIO_OGG = os.path.join(BASE_DIR, "reminder.ogg")
PID_FILE = os.path.join(BASE_DIR, "reminder.pid")
SOCKET_FILE = os.path.join(BASE_DIR, "reminder.sock")
PORT_FILE = os.path.join(BASE_DIR, "reminder.port")
LOCK_FILE = os.path.join(BASE_DIR, "reminder.lock")

DEFAULT_CONFIG = {
    "interval_minutes": 60,
    "snooze_minutes": 10,
    "sound_enabled": True,
    "audio_file": "reminder.wav",
    "next_reminder_time": 0,
    "last_reminder_time": 0,
    "last_drank_time": 0,
    "glasses_today": 0,
    "today_date": "",
    "daily_history": {}
}

def get_audio_file_path(config=None):
    if config is None:
        config = load_config()
    configured = config.get("audio_file", "reminder.wav")
    if configured:
        # Check absolute path
        if os.path.isabs(configured) and os.path.exists(configured):
            return configured
        # Check in SOUNDS_DIR
        sounds_p = os.path.join(SOUNDS_DIR, configured)
        if os.path.exists(sounds_p):
            return sounds_p
        # Check in BASE_DIR
        base_p = os.path.join(BASE_DIR, configured)
        if os.path.exists(base_p):
            return base_p
    # Fallback to default reminder.wav
    if os.path.exists(AUDIO_FILE):
        return AUDIO_FILE
    if os.path.exists(AUDIO_OGG):
        return AUDIO_OGG
    return AUDIO_FILE

def list_available_sounds(config=None):
    sounds = []
    seen_paths = set()
    
    # 1. Default alert (reminder.wav)
    if os.path.exists(AUDIO_FILE):
        sounds.append({"id": "reminder.wav", "name": "🔔 Default Alert (reminder.wav)", "path": AUDIO_FILE})
        seen_paths.add(os.path.abspath(AUDIO_FILE))
        
    # 2. Check sounds inside assets/sounds
    if os.path.exists(SOUNDS_DIR):
        supported_exts = (".wav", ".mp3", ".ogg", ".flac", ".m4a")
        for fname in sorted(os.listdir(SOUNDS_DIR)):
            if fname.lower().endswith(supported_exts):
                full_p = os.path.join(SOUNDS_DIR, fname)
                abs_p = os.path.abspath(full_p)
                if abs_p not in seen_paths:
                    title = os.path.splitext(fname)[0].replace("_", " ").title()
                    icon = "💧" if "water" in fname.lower() or "drop" in fname.lower() else "🎵"
                    sounds.append({"id": fname, "name": f"{icon} {title} ({fname})", "path": full_p})
                    seen_paths.add(abs_p)

    # 3. Check configured custom file if external
    if config is None:
        config = load_config()
    current_choice = config.get("audio_file")
    if current_choice and os.path.isabs(current_choice) and os.path.exists(current_choice):
        abs_p = os.path.abspath(current_choice)
        if abs_p not in seen_paths:
            fname = os.path.basename(current_choice)
            sounds.append({"id": current_choice, "name": f"📁 Custom ({fname})", "path": current_choice})
            seen_paths.add(abs_p)
            
    return sounds

def get_today_str():
    return time.strftime("%Y-%m-%d")

def load_config():
    config = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                saved = json.load(f)
                config.update(saved)
        except Exception as e:
            print(f"[Warning] Failed to load config: {e}")
            
    # Automatically reset glasses counter if day changed
    today = get_today_str()
    old_date = config.get("today_date", "")
    if old_date and old_date != today:
        history = config.get("daily_history", {})
        if "glasses_today" in config:
            history[old_date] = config.get("glasses_today", 0)
        config["daily_history"] = history
        config["today_date"] = today
        config["glasses_today"] = 0
        save_config(config)
    elif not old_date:
        config["today_date"] = today
        save_config(config)
        
    return config

def save_config(config):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"[Warning] Failed to save config: {e}")

def record_glass_drank(count=1):
    config = load_config()
    today = get_today_str()
    if config.get("today_date") != today:
        config["today_date"] = today
        config["glasses_today"] = 0
    config["glasses_today"] = config.get("glasses_today", 0) + count
    config["last_drank_time"] = int(time.time())
    save_config(config)
    return config["glasses_today"]

def reset_glasses_count():
    config = load_config()
    config["today_date"] = get_today_str()
    config["glasses_today"] = 0
    save_config(config)
    return 0
