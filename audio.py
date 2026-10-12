import os
import sys
import shutil
import subprocess
import threading

class SoundPlayer:
    def __init__(self, audio_file):
        self.audio_file = audio_file
        self.process = None
        self.lock = threading.RLock()
        self.is_windows = sys.platform == "win32"
        self.is_macos = sys.platform == "darwin"
        
        # Determine available audio player tool
        self.player_cmd = None
        if self.is_windows:
            self.player_cmd = "winsound"
        elif self.is_macos:
            if shutil.which("afplay"):
                self.player_cmd = "afplay"
        else:
            if shutil.which("paplay"):
                self.player_cmd = "paplay"
            elif shutil.which("pw-play"):
                self.player_cmd = "pw-play"
            elif shutil.which("aplay"):
                self.player_cmd = "aplay"

    def play(self):
        if not os.path.exists(self.audio_file):
            return
            
        with self.lock:
            self.stop()
            try:
                if self.player_cmd == "winsound":
                    import winsound
                    winsound.PlaySound(self.audio_file, winsound.SND_FILENAME | winsound.SND_ASYNC)
                elif self.player_cmd:
                    self.process = subprocess.Popen(
                        [self.player_cmd, self.audio_file],
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
            elif self.process and self.process.poll() is None:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=0.5)
                except Exception:
                    try:
                        self.process.kill()
                    except Exception:
                        pass
                self.process = None
