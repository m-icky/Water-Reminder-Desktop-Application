import os
import json
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
FRAMES_DIR = os.path.join(ASSETS_DIR, "frames")
SMOKE_DIR = os.path.join(ASSETS_DIR, "smoke")
AUDIO_FILE = os.path.join(BASE_DIR, "reminder.wav")
AUDIO_OGG = os.path.join(BASE_DIR, "reminder.ogg")
PID_FILE = os.path.join(BASE_DIR, "reminder.pid")
SOCKET_FILE = os.path.join(BASE_DIR, "reminder.sock")
PORT_FILE = os.path.join(BASE_DIR, "reminder.port")

DEFAULT_CONFIG = {
    "interval_minutes": 60,
    "snooze_minutes": 10,
    "sound_enabled": True,
    "next_reminder_time": 0,
    "last_reminder_time": 0,
    "last_drank_time": 0,
    "glasses_today": 0,
    "today_date": "",
    "daily_history": {}
}

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
