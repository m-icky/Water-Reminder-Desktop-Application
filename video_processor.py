import os
import sys
import json
import time
import re
import shutil
import subprocess
from PIL import Image
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import ASSETS_DIR, CHARACTERS_DIR, FRAMES_DIR, load_config, save_config

TARGET_WIDTH = 270
TARGET_HEIGHT = 480
DEFAULT_FPS = 20
MAX_DURATION_SECS = 12.0  # Limit animation duration for optimal desktop overlay performance

def is_ffmpeg_available():
    """Check if ffmpeg and ffprobe are available in system PATH."""
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None

def probe_video(video_path):
    """
    Probe video properties using ffprobe.
    Returns dict with width, height, fps, duration, nb_frames, pix_fmt, has_alpha.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,duration,pix_fmt,nb_frames",
        "-of", "json",
        video_path
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        data = json.loads(res.stdout)
        streams = data.get("streams", [])
        if not streams:
            raise ValueError("No video stream found in file.")
        
        stream = streams[0]
        w = int(stream.get("width", 0))
        h = int(stream.get("height", 0))
        pix_fmt = stream.get("pix_fmt", "")
        
        # Parse frame rate
        fps_str = stream.get("r_frame_rate", "24/1")
        if "/" in fps_str:
            num, den = fps_str.split("/")
            fps = float(num) / max(1.0, float(den))
        else:
            fps = float(fps_str)
        fps = round(fps, 2)
        
        duration = float(stream.get("duration", 0.0))
        if duration <= 0:
            # Try format duration
            cmd_fmt = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                video_path
            ]
            res_fmt = subprocess.run(cmd_fmt, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            fmt_data = json.loads(res_fmt.stdout)
            duration = float(fmt_data.get("format", {}).get("duration", 5.0))
            
        nb_frames = int(stream.get("nb_frames", 0)) if stream.get("nb_frames") else int(duration * fps)

        # Detect native alpha support in pixel format
        has_alpha = any(a in pix_fmt.lower() for a in ["yuva", "rgba", "bgra", "argb", "abgr", "pal8"])

        return {
            "width": w,
            "height": h,
            "fps": fps,
            "duration": duration,
            "nb_frames": nb_frames,
            "pix_fmt": pix_fmt,
            "has_alpha": has_alpha
        }
    except Exception as e:
        raise RuntimeError(f"Failed to probe video: {e}")

def detect_background_color(video_path, probe_info=None):
    """
    Extract sample frames to detect the dominant background color from the corners and borders.
    Returns:
        dict: {
            "hex_color": "0xRRGGBB",
            "rgb": [r, g, b],
            "description": "White Studio / Light",
            "recommended_similarity": 0.18,
            "recommended_blend": 0.08,
            "has_native_alpha": bool
        }
    """
    if probe_info is None:
        probe_info = probe_video(video_path)

    if probe_info.get("has_alpha"):
        return {
            "hex_color": None,
            "rgb": None,
            "description": "Video with Native Transparency (Alpha Channel)",
            "recommended_similarity": 0.0,
            "recommended_blend": 0.0,
            "has_native_alpha": True
        }

    duration = probe_info.get("duration", 4.0)
    # Sample at 10% and 40% into video
    sample_timestamps = [max(0.1, duration * 0.1), max(0.2, duration * 0.4)]
    corner_pixels = []

    for ts in sample_timestamps:
        cmd = [
            "ffmpeg", "-y", "-ss", str(ts),
            "-i", video_path,
            "-vframes", "1",
            "-f", "image2pipe",
            "-vcodec", "png",
            "-"
        ]
        try:
            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if p.returncode == 0 and len(p.stdout) > 0:
                import io
                img = Image.open(io.BytesIO(p.stdout)).convert("RGB")
                arr = np.array(img, dtype=np.float32)
                h, w, _ = arr.shape
                # Sample corners (12x12 patch in each corner)
                pw = min(12, max(2, w // 10))
                ph = min(12, max(2, h // 10))
                tl = arr[:ph, :pw].reshape(-1, 3)
                tr = arr[:ph, -pw:].reshape(-1, 3)
                bl = arr[-ph:, :pw].reshape(-1, 3)
                br = arr[-ph:, -pw:].reshape(-1, 3)
                corner_pixels.extend([tl, tr, bl, br])
        except Exception:
            pass

    if not corner_pixels:
        # Fallback to white studio background
        return {
            "hex_color": "0xffffff",
            "rgb": [255, 255, 255],
            "description": "Default White (0xffffff)",
            "recommended_similarity": 0.18,
            "recommended_blend": 0.08,
            "has_native_alpha": False
        }

    all_corners = np.vstack(corner_pixels)
    median_rgb = np.median(all_corners, axis=0).astype(int)
    r, g, b = int(median_rgb[0]), int(median_rgb[1]), int(median_rgb[2])
    hex_color = f"0x{r:02x}{g:02x}{b:02x}"

    # Classify color
    if g > 130 and g > (r * 1.3) and g > (b * 1.3):
        desc = f"Chroma Green Screen ({hex_color})"
        similarity = 0.25
        blend = 0.10
    elif b > 130 and b > (r * 1.3) and b > (g * 1.3):
        desc = f"Chroma Blue Screen ({hex_color})"
        similarity = 0.25
        blend = 0.10
    elif r > 210 and g > 210 and b > 210:
        desc = f"White / Light Studio ({hex_color})"
        similarity = 0.18
        blend = 0.08
    elif r < 45 and g < 45 and b < 45:
        desc = f"Black / Dark Background ({hex_color})"
        similarity = 0.20
        blend = 0.08
    else:
        desc = f"Solid Color ({hex_color})"
        similarity = 0.20
        blend = 0.08

    return {
        "hex_color": hex_color,
        "rgb": [r, g, b],
        "description": desc,
        "recommended_similarity": similarity,
        "recommended_blend": blend,
        "has_native_alpha": False
    }

def slugify(text):
    """Generate safe directory / id slug from character name."""
    s = re.sub(r"[^\w\s-]", "", text.strip().lower())
    s = re.sub(r"[-\s]+", "_", s)
    return s or f"char_{int(time.time())}"

def process_video_character(
    video_path,
    character_name="Custom Character",
    bg_mode="auto",
    custom_color="0x00ff00",
    target_fps=DEFAULT_FPS,
    max_duration=MAX_DURATION_SECS,
    progress_callback=None
):
    """
    Process an uploaded video file, convert to transparent background frames,
    smoothly format and scale to 270x480, and save in assets/characters/<char_id>/.

    Parameters:
        video_path (str): Path to input video file.
        character_name (str): Human-readable name.
        bg_mode (str): One of:
            - "auto": Auto-detect solid background color or native alpha
            - "green": Green screen chroma key
            - "blue": Blue screen chroma key
            - "white": White / light studio background
            - "black": Black / dark background
            - "alpha": Native video transparency
            - "custom": Uses `custom_color` (hex string '0xRRGGBB' or '#RRGGBB')
            - "rembg": AI deep matting if rembg package is installed
        custom_color (str): Hex color for custom mode.
        target_fps (int): Target frame rate (15-30, default 20).
        max_duration (float): Max video duration in seconds (default 12.0).
        progress_callback (callable): Optional fn(percentage: int, status: str)

    Returns:
        dict: Character metadata dictionary.
    """
    if not is_ffmpeg_available():
        raise RuntimeError("FFmpeg and FFprobe are required. Please install ffmpeg.")

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Source video not found: {video_path}")

    def update_progress(pct, msg):
        if progress_callback:
            try:
                progress_callback(pct, msg)
            except Exception:
                pass

    update_progress(5, "Analyzing video stream and properties...")
    probe = probe_video(video_path)

    # Determine unique character ID and directory
    char_slug = slugify(character_name)
    timestamp_suffix = int(time.time()) % 100000
    char_id = f"{char_slug}_{timestamp_suffix}"
    char_dir = os.path.join(CHARACTERS_DIR, char_id)
    frames_dir = os.path.join(char_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    # Determine background removal filter
    update_progress(15, "Detecting video background and color key settings...")
    vf_filters = []
    
    # 1. Target frame rate
    vf_filters.append(f"fps={int(target_fps)}")

    # 2. Background removal filter
    actual_bg_mode = bg_mode.lower()
    hex_colorkey = None
    similarity = 0.20
    blend = 0.08

    if actual_bg_mode == "auto":
        bg_info = detect_background_color(video_path, probe)
        if bg_info.get("has_native_alpha"):
            actual_bg_mode = "alpha"
        else:
            hex_colorkey = bg_info["hex_color"]
            similarity = bg_info["recommended_similarity"]
            blend = bg_info["recommended_blend"]
    elif actual_bg_mode == "green":
        hex_colorkey = "0x00ff00"
        similarity = 0.25
        blend = 0.10
    elif actual_bg_mode == "blue":
        hex_colorkey = "0x0000ff"
        similarity = 0.25
        blend = 0.10
    elif actual_bg_mode == "white":
        hex_colorkey = "0xffffff"
        similarity = 0.18
        blend = 0.08
    elif actual_bg_mode == "black":
        hex_colorkey = "0x000000"
        similarity = 0.20
        blend = 0.08
    elif actual_bg_mode == "custom":
        cleaned = custom_color.strip().replace("#", "")
        if not cleaned.startswith("0x"):
            cleaned = "0x" + cleaned
        hex_colorkey = cleaned
        similarity = 0.22
        blend = 0.09

    if hex_colorkey and actual_bg_mode != "alpha" and actual_bg_mode != "rembg":
        vf_filters.append(f"colorkey={hex_colorkey}:{similarity}:{blend}")
        if actual_bg_mode == "green":
            vf_filters.append("despill=type=green")
        elif actual_bg_mode == "blue":
            vf_filters.append("despill=type=blue")

    # 3. Scaling & Transparent Padding to fit 270x480 aspect ratio
    vf_filters.append(
        f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={TARGET_WIDTH}:{TARGET_HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=0x00000000"
    )

    vf_chain = ",".join(vf_filters)
    out_pattern = os.path.join(frames_dir, "f_%04d.png")

    update_progress(30, "Extracting transparent frames with smooth antialiasing...")

    # Build FFmpeg command
    cmd = ["ffmpeg", "-y"]
    if max_duration and max_duration > 0:
        cmd.extend(["-t", str(float(max_duration))])
    cmd.extend([
        "-i", video_path,
        "-vf", vf_chain,
        "-vcodec", "png",
        out_pattern
    ])

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        # Clean up frames dir on failure
        shutil.rmtree(char_dir, ignore_errors=True)
        raise RuntimeError(f"FFmpeg frame extraction failed: {res.stderr}")

    update_progress(75, "Validating and optimizing animation frames...")

    # Verify generated frames
    frame_files = sorted([f for f in os.listdir(frames_dir) if f.startswith("f_") and f.endswith(".png")])
    total_frames = len(frame_files)
    if total_frames == 0:
        shutil.rmtree(char_dir, ignore_errors=True)
        raise RuntimeError("No frames could be extracted from video.")

    # Check if AI rembg matting was requested and rembg is available
    if actual_bg_mode == "rembg":
        try:
            import rembg
            update_progress(80, "Applying AI deep matting to extracted frames...")
            for idx, fname in enumerate(frame_files):
                fpath = os.path.join(frames_dir, fname)
                im = Image.open(fpath)
                out_im = rembg.remove(im)
                out_im.save(fpath)
                if idx % 10 == 0:
                    pct = 80 + int((idx / total_frames) * 15)
                    update_progress(pct, f"AI matting: frame {idx+1}/{total_frames}...")
        except ImportError:
            pass  # Fall back to color keying result

    update_progress(95, "Finalizing character metadata and smooth loop...")

    # Build character metadata
    meta = {
        "id": char_id,
        "name": character_name,
        "frame_count": total_frames,
        "fps": int(target_fps),
        "frame_interval_ms": max(25, int(1000 / target_fps)),
        "loop_start": 0,  # Custom characters loop seamlessly from 0
        "bg_mode": actual_bg_mode,
        "source_file": os.path.basename(video_path),
        "created_at": int(time.time()),
        "width": TARGET_WIDTH,
        "height": TARGET_HEIGHT
    }

    meta_file = os.path.join(char_dir, "metadata.json")
    with open(meta_file, "w") as f:
        json.dump(meta, f, indent=2)

    # Copy source video for backup / reference if size is reasonable (< 35MB)
    try:
        if os.path.getsize(video_path) < 35 * 1024 * 1024:
            dest_video = os.path.join(char_dir, "source" + os.path.splitext(video_path)[1].lower())
            if os.path.abspath(video_path) != os.path.abspath(dest_video):
                shutil.copy2(video_path, dest_video)
    except Exception:
        pass

    update_progress(100, f"Character '{character_name}' ready with {total_frames} smooth frames! 🎉")
    return meta
