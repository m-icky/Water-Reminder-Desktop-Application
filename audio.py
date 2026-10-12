import os
import shutil
import subprocess
import threading

class SoundPlayer:
    def __init__(self, audio_file):
        self.audio_file = audio_file
        self.process = None
        self.lock = threading.RLock()
        
        # Determine available audio player tool
        if shutil.which("paplay"):
            self.player_cmd = "paplay"
        elif shutil.which("pw-play"):
            self.player_cmd = "pw-play"
        elif shutil.which("aplay"):
            self.player_cmd = "aplay"
        else:
            self.player_cmd = None

    def play(self):
        if not self.player_cmd or not os.path.exists(self.audio_file):
            return
            
        with self.lock:
            self.stop()
            try:
                self.process = subprocess.Popen(
                    [self.player_cmd, self.audio_file],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception as e:
                print(f"[SoundPlayer] Playback error: {e}")

    def stop(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=0.5)
                except Exception:
                    try:
                        self.process.kill()
                    except Exception:
                        pass
                self.process = None
