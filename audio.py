import os
import sys
import shutil
import subprocess
import threading

class SoundPlayer:
    def __init__(self, audio_file=None):
        self.audio_file = audio_file
        self.process = None
        self.lock = threading.RLock()
        self.is_windows = sys.platform == "win32"
        self.is_macos = sys.platform == "darwin"
        
        # Determine available default audio player tool
        self.default_player_cmd = None
        if self.is_windows:
            self.default_player_cmd = "winsound"
        elif self.is_macos:
            if shutil.which("afplay"):
                self.default_player_cmd = "afplay"
        else:
            if shutil.which("paplay"):
                self.default_player_cmd = "paplay"
            elif shutil.which("pw-play"):
                self.default_player_cmd = "pw-play"
            elif shutil.which("aplay"):
                self.default_player_cmd = "aplay"

    def set_audio_file(self, audio_file):
        with self.lock:
            self.stop()
            self.audio_file = audio_file

    def is_playing(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                return True
            return False

    def play(self, custom_path=None):
        target = custom_path or self.audio_file
        if not target or not os.path.exists(target):
            return
            
        with self.lock:
            self.stop()
            try:
                if self.is_windows:
                    if target.lower().endswith(".wav"):
                        import winsound
                        winsound.PlaySound(target, winsound.SND_FILENAME | winsound.SND_ASYNC)
                    else:
                        # Fallback for MP3/other on Windows
                        cmd = f'(New-Object Media.SoundPlayer "{target}").PlaySync()'
                        self.process = subprocess.Popen(
                            ["powershell", "-c", cmd],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                elif self.is_macos:
                    if shutil.which("afplay"):
                        self.process = subprocess.Popen(
                            ["afplay", target],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                else:
                    # Linux playback
                    cmd = None
                    ext = os.path.splitext(target)[1].lower()
                    if ext in (".mp3", ".m4a"):
                        if shutil.which("pw-play"):
                            cmd = ["pw-play", target]
                        elif shutil.which("ffplay"):
                            cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", target]
                        elif shutil.which("mpv"):
                            cmd = ["mpv", "--no-video", target]
                        elif shutil.which("paplay"):
                            cmd = ["paplay", target]
                    else:
                        # WAV, OGG, FLAC
                        if shutil.which("paplay"):
                            cmd = ["paplay", target]
                        elif shutil.which("pw-play"):
                            cmd = ["pw-play", target]
                        elif shutil.which("aplay") and ext == ".wav":
                            cmd = ["aplay", target]
                        elif shutil.which("ffplay"):
                            cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", target]
                            
                    if cmd:
                        self.process = subprocess.Popen(
                            cmd,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
            except Exception as e:
                print(f"[SoundPlayer] Playback error: {e}")

    def stop(self):
        with self.lock:
            if self.is_windows:
                try:
                    import winsound
                    winsound.PlaySound(None, winsound.SND_PURGE)
                except Exception:
                    pass
            if self.process and self.process.poll() is None:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=0.3)
                except Exception:
                    try:
                        self.process.kill()
                    except Exception:
                        pass
                self.process = None
