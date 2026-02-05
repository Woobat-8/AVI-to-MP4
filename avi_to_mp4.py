# ******************************
# AVI To MP4 Converter
# Copyright (C) 2026 Woobat8
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# ******************************

import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import webbrowser
import zipfile
from collections import deque
from datetime import datetime
from urllib.request import Request, urlopen

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from tkinterdnd2 import DND_FILES, TkinterDnD

# ******************************
# App config
# ******************************
APP_NAME = "AVI → MP4"
APP_VERSION = (1, 0, 0, 260205)  # Major.Minor.Patch.YYMMDD

DIR = os.path.join(os.getenv("APPDATA") or os.path.expanduser("~"), "AVI to MP4")
CONFIG_FILE = os.path.join(DIR, "settings.json")
LOG_UI_FILE = os.path.join(DIR, "log.txt")
LOG_FULL_FILE = os.path.join(DIR, "log_full.txt")
DEFAULT_OUTPUT = os.path.join(os.path.expanduser("~"), "Downloads")

ICON_FILENAME = "icon.ico"

BIN_DIR = os.path.join(DIR, "bin")
FFMPEG_EXE_NAME = "ffmpeg.exe"
FFPROBE_EXE_NAME = "ffprobe.exe"

FFMPEG_ZIP_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
FFMPEG_INSTALL_PAGE = "https://www.gyan.dev/ffmpeg/builds/"

os.makedirs(DIR, exist_ok=True)
os.makedirs(BIN_DIR, exist_ok=True)

UI_COLORS = {
    'bg': '#f2f2f2',
    'fg': '#000000',
    'widget_bg': '#f2f2f2',
    'button_bg': '#e0e0e0',
    'log_bg': '#ffffff',
    'combo_bg': '#ffffff',
    'progress_bg': '#4caf50',
}

# ******************************
# PyInstaller things
# ******************************
def resource_path(rel_path: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__)))
    return os.path.join(base, rel_path)

def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.dirname(__file__))

# ******************************
# Logging helpers
# ******************************
def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _safe_append(path: str, text: str):
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        pass

def _log_ui_file(msg: str):
    _safe_append(LOG_UI_FILE, msg + "\n")

def _log_full(msg: str):
    _safe_append(LOG_FULL_FILE, f"[{ts()}] {msg}\n")

_ui_buffer = []

def log(msg: str, full_only=False):
    if not full_only:
        if "log_box" in globals():
            try:
                log_box.insert(tk.END, msg + "\n")
                log_box.see(tk.END)
            except Exception:
                pass
        else:
            _ui_buffer.append(msg)
        _log_ui_file(msg)
    
    _log_full(msg)

_log_ui_file(f"[{ts()}] App Opened")
_log_full("=== App Opened ===")

# ******************************
# Save/load settings
# ******************************
def load_settings():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log(f"Settings load failed: {e}", full_only=True)
            return {}
    return {}

settings = load_settings()

def save_settings():
    try:
        data = {
            "dir_out": dir_out.get() if "dir_out" in globals() else settings.get("dir_out", DEFAULT_OUTPUT),
            "encoder": encode_w.get() if "encode_w" in globals() else settings.get("encoder", "CPU"),
            "startup_notice": settings.get("startup_notice", True),
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        settings.update(data)
        log(f"Settings saved: {data}", full_only=True)
    except Exception as e:
        log(f"Settings save failed: {e}", full_only=True)

# ******************************
# FFmpeg detection / download
# ******************************
FFMPEG_PATH = None
FFPROBE_PATH = None
FFMPEG_VERSION_LINE = "Unknown"

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

def _is_exe(path: str) -> bool:
    return bool(path) and os.path.isfile(path) and path.lower().endswith(".exe")

def _run_capture(cmd, timeout=6):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=CREATE_NO_WINDOW)
        return r.returncode, (r.stdout or ""), (r.stderr or "")
    except Exception as e:
        return -1, "", str(e)

def resolve_ffmpeg_paths_once():
    global FFMPEG_PATH, FFPROBE_PATH, FFMPEG_VERSION_LINE

    p1 = os.path.join(app_dir(), FFMPEG_EXE_NAME)
    q1 = os.path.join(app_dir(), FFPROBE_EXE_NAME)

    p2 = os.path.join(BIN_DIR, FFMPEG_EXE_NAME)
    q2 = os.path.join(BIN_DIR, FFPROBE_EXE_NAME)

    p3 = shutil.which("ffmpeg")
    q3 = shutil.which("ffprobe")

    candidates = [
        (p1, q1, "app_dir"),
        (p2, q2, "bin_dir"),
        (p3, q3, "PATH"),
    ]

    FFMPEG_PATH = None
    FFPROBE_PATH = None

    for ff, fp, src in candidates:
        if _is_exe(ff) and _is_exe(fp):
            FFMPEG_PATH = ff
            FFPROBE_PATH = fp
            log(f"Resolved ffmpeg from {src}: {ff}", full_only=True)
            log(f"Resolved ffprobe from {src}: {fp}", full_only=True)
            break

    if not FFMPEG_PATH or not FFPROBE_PATH:
        log("ffmpeg/ffprobe not found in app_dir, bin_dir, or PATH.", full_only=True)
        FFMPEG_VERSION_LINE = "Missing"
        return False

    rc, out, err = _run_capture([FFMPEG_PATH, "-version"], timeout=6)
    if rc == 0:
        first = (out.splitlines() or [""])[0].strip()
        FFMPEG_VERSION_LINE = first or "Unknown"
        log(f"ffmpeg version: {FFMPEG_VERSION_LINE}", full_only=True)
    else:
        FFMPEG_VERSION_LINE = "Unknown (failed to run)"
        log(f"ffmpeg -version failed: rc={rc} err={err}", full_only=True)

    return True

def open_ffmpeg_install_page():
    webbrowser.open(FFMPEG_INSTALL_PAGE)

def download_and_install_ffmpeg():
    os.makedirs(BIN_DIR, exist_ok=True)
    tmp_zip = os.path.join(DIR, "ffmpeg_download.zip")
    tmp_extract = os.path.join(DIR, "_ffmpeg_extract_tmp")

    try:
        log(f"Downloading FFmpeg zip: {FFMPEG_ZIP_URL}", full_only=True)
        req = Request(FFMPEG_ZIP_URL, headers={"User-Agent": "AVItoMP4/1.0"})
        with urlopen(req, timeout=30) as resp:
            data = resp.read()
        with open(tmp_zip, "wb") as f:
            f.write(data)
        log(f"Downloaded zip bytes={len(data)} to {tmp_zip}", full_only=True)

        if os.path.isdir(tmp_extract):
            shutil.rmtree(tmp_extract, ignore_errors=True)
        os.makedirs(tmp_extract, exist_ok=True)

        with zipfile.ZipFile(tmp_zip, "r") as z:
            z.extractall(tmp_extract)

        found_ffmpeg = None
        found_ffprobe = None
        for root_dir, _, files in os.walk(tmp_extract):
            low = {x.lower(): x for x in files}
            if "ffmpeg.exe" in low and "ffprobe.exe" in low:
                found_ffmpeg = os.path.join(root_dir, low["ffmpeg.exe"])
                found_ffprobe = os.path.join(root_dir, low["ffprobe.exe"])
                break

        if not found_ffmpeg or not found_ffprobe:
            raise RuntimeError("Could not locate ffmpeg.exe/ffprobe.exe inside the downloaded zip.")

        dest_ffmpeg = os.path.join(BIN_DIR, FFMPEG_EXE_NAME)
        dest_ffprobe = os.path.join(BIN_DIR, FFPROBE_EXE_NAME)
        shutil.copy2(found_ffmpeg, dest_ffmpeg)
        shutil.copy2(found_ffprobe, dest_ffprobe)

        log(f"Installed ffmpeg to {dest_ffmpeg}", full_only=True)
        log(f"Installed ffprobe to {dest_ffprobe}", full_only=True)

        try:
            os.remove(tmp_zip)
        except Exception:
            pass
        try:
            shutil.rmtree(tmp_extract, ignore_errors=True)
        except Exception:
            pass

        return True

    except Exception as e:
        log(f"Auto-download/install ffmpeg failed: {e}", full_only=True)
        return False

# ******************************
# Encoder Detection (scan ONCE)
# ******************************
ENCODERS = {"CPU": "libx264"}

def test_encoder(enc: str) -> bool:
    if not FFMPEG_PATH:
        return False
    try:
        test_size = "256x144" if enc == "h264_nvenc" else "128x72"
        
        cmd = [
            FFMPEG_PATH, "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", f"testsrc=size={test_size}:rate=30",
            "-t", "0.2", "-an",
        ]
        if enc in ("h264_amf", "h264_qsv"):
            cmd += ["-vf", "format=nv12", "-pix_fmt", "nv12"]
        elif enc == "h264_nvenc":
            cmd += ["-pix_fmt", "yuv420p"]
        else:
            cmd += ["-vf", "format=yuv420p", "-pix_fmt", "yuv420p"]

        cmd += ["-c:v", enc, "-f", "null", "-"]

        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=6, creationflags=CREATE_NO_WINDOW)
        log(f"Test encoder {enc}: returncode={r.returncode}", full_only=True)
        if r.returncode != 0:
            log(f"Test encoder {enc} stderr: {r.stderr.strip()}", full_only=True)
        return r.returncode == 0
    except Exception as e:
        log(f"Test encoder {enc} exception: {e}", full_only=True)
        return False

def detect_encoders_once():
    global ENCODERS

    encoders = {"CPU": "libx264"}

    if test_encoder("h264_amf"):
        encoders["AMF"] = "h264_amf"
    if test_encoder("h264_nvenc"):
        encoders["NVENC"] = "h264_nvenc"
    if test_encoder("h264_qsv"):
        encoders["QSV"] = "h264_qsv"

    ENCODERS = encoders
    log(f"Detected encoders: {list(ENCODERS.keys())}", full_only=True)

def auto_best_encoder():
    for pref in ("AMF", "NVENC", "QSV"):
        if pref in ENCODERS:
            return pref
    return "CPU"

# ******************************
# ffprobe
# ******************************
def get_file_info(f):
    try:
        cmd = [
            FFPROBE_PATH, "-v", "error",
            "-show_entries", "format=duration:stream=codec_name,codec_type,profile,pix_fmt",
            "-of", "json", f
        ]
        log(f"ffprobe: {' '.join(cmd)}", full_only=True)
        r = subprocess.run(cmd, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
        
        if r.returncode != 0:
            log(f"ffprobe failed: {r.stderr}", full_only=True)
            return {'duration': 0.0, 'video': {}, 'audio': ''}
        
        data = json.loads(r.stdout)
        
        duration = float(data.get('format', {}).get('duration', 0))
        video_info = {}
        audio_codec = ''
        
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video' and not video_info:
                video_info = {
                    'codec_name': stream.get('codec_name', ''),
                    'profile': stream.get('profile', ''),
                    'pix_fmt': stream.get('pix_fmt', ''),
                }
            elif stream.get('codec_type') == 'audio' and not audio_codec:
                audio_codec = stream.get('codec_name', '')
        
        log(f"Parsed file info: duration={duration}, video={video_info}, audio={audio_codec}", full_only=True)
        
        return {
            'duration': duration,
            'video': video_info,
            'audio': audio_codec
        }
    except Exception as e:
        log(f"get_file_info exception: {e}", full_only=True)
        return {'duration': 0.0, 'video': {}, 'audio': ''}

# ******************************
# Globals
# ******************************
current_process = None
pause_event = threading.Event()
cancel_event = threading.Event()
pause_event.set()

# ******************************
# UI helpers
# ******************************
def ui(fn, *args, **kwargs):
    root.after(0, lambda: fn(*args, **kwargs))

def set_ui_state(status=None, progress=None, pause_btn_text=None):
    try:
        if status is not None:
            status_label.config(text=status)
        if progress is not None:
            progress_bar["value"] = max(0, min(100, float(progress)))
        if pause_btn_text is not None:
            pause_btn.config(text=pause_btn_text)
            if pause_btn_text == "Pause":
                pause_event.set()
    except Exception:
        pass

def format_date(build: int) -> str:
    try:
        s = f"{build:06d}"
        year = 2000 + int(s[:2])
        month = int(s[2:4])
        day = int(s[4:6])
        return datetime(year, month, day).strftime("%B %d, %Y")
    except Exception:
        return "Unknown"

# ******************************
# UI Things
# ******************************
def apply_ui_style():
    root.configure(bg=UI_COLORS['bg'])
    for w in themed_widgets:
        try:
            w.configure(bg=UI_COLORS['widget_bg'], fg=UI_COLORS['fg'])
        except Exception:
            pass

    style.configure(".", background=UI_COLORS['bg'], foreground=UI_COLORS['fg'])
    style.configure("TButton", background=UI_COLORS['button_bg'], foreground=UI_COLORS['fg'])
    style.configure("TLabel", background=UI_COLORS['widget_bg'], foreground=UI_COLORS['fg'])
    style.configure("TCombobox", fieldbackground=UI_COLORS['combo_bg'], foreground=UI_COLORS['fg'])
    style.configure("Horizontal.TProgressbar", background=UI_COLORS['progress_bg'])

    log_box.configure(bg=UI_COLORS['log_bg'], fg=UI_COLORS['fg'], insertbackground=UI_COLORS['fg'])

# ******************************
# Popup GUIs
# ******************************
def show_about():
    major, minor, patch, build = APP_VERSION
    version_str = f"{major}.{minor}.{patch}.{build}"
    release_date = format_date(build)

    win = tk.Toplevel(root)
    win.title("About")
    try:
        icon_path = resource_path(ICON_FILENAME)
        if os.path.exists(icon_path):
            win.iconbitmap(icon_path)
    except Exception:
        pass
    win.resizable(False, False)
    win.transient(root)
    win.grab_set()
    win.configure(bg=root["bg"])

    fg = UI_COLORS['fg']

    tk.Label(win, text=APP_NAME, font=("Segoe UI", 12, "bold"), bg=win["bg"], fg=fg).pack(padx=16, pady=(12, 4))
    tk.Label(win, text=f"Version {version_str}", bg=win["bg"], fg=fg).pack(pady=2)
    tk.Label(win, text=f"Released: {release_date}", bg=win["bg"], fg=fg).pack(pady=2)
    tk.Label(win, text="© 2026 Woobat8", bg=win["bg"], fg=fg).pack(pady=2)

    def open_latest():
        webbrowser.open("https://github.com/Woobat-8/AVI-to-MP4/releases/latest")

    get_latest = tk.Label(
        win,
        text="Get the latest version here.",
        bg=win["bg"],
        fg="#4da6ff",
        cursor="hand2",
        font=("Segoe UI", 9, "underline"),
    )

    get_latest.pack(pady=(2, 10))
    get_latest.bind("<Button-1>", lambda _: open_latest())

    def open_gpl():
        webbrowser.open("https://www.gnu.org/licenses/gpl-3.0.html")

    gpl_link = tk.Label(
        win,
        text="Licensed under the GNU GPL v3",
        bg=win["bg"],
        fg="#4da6ff",
        cursor="hand2",
        font=("Segoe UI", 9, "underline"),
    )
    gpl_link.pack(pady=(2, 10))
    gpl_link.bind("<Button-1>", lambda _: open_gpl())

    tk.Button(win, text="OK", width=10, command=win.destroy).pack(pady=(0, 12))

def startup_notice(force_show=False):
    show = settings.get("startup_notice", True)
    if not show and not force_show:
        log("Startup notice skipped (user preference)", full_only=True)
        return
    log("Startup notice displayed", full_only=True)

    fg = UI_COLORS['fg']

    win = tk.Toplevel(root)
    win.title("Important Information")
    try:
        icon_path = resource_path(ICON_FILENAME)
        if os.path.exists(icon_path):
            win.iconbitmap(icon_path)
    except Exception:
        pass
    win.resizable(False, False)
    win.transient(root)
    win.grab_set()
    win.configure(bg=root["bg"])

    msg = (
        "This application requires FFmpeg to function.\n"
        "If FFmpeg cannot be found or you encounter an FFmpeg-related error, the app may offer to download FFmpeg automatically, or you can install it manually and add it to your system PATH.\n\n"
        "This software is licensed under the GNU General Public License v3.\n"
        "You are free to use, modify, and redistribute it under the terms of that license.\n\n"
        "This software is free. If you paid for it, you may have been misled.\n\n"
        "This software is provided \"as is\", without warranty or liability."
    )

    tk.Label(win, text=msg, justify="left", wraplength=430, bg=win["bg"], fg=fg).pack(padx=16, pady=(16, 8))

    link = tk.Label(
        win,
        text="Install ffmpeg here.",
        bg=win["bg"],
        fg="#4da6ff",
        cursor="hand2",
        font=("Segoe UI", 9, "underline"),
    )
    link.pack(pady=(0, 10))
    link.bind("<Button-1>", lambda _: open_ffmpeg_install_page())

    dont_show_var = tk.BooleanVar(value=False)
    tk.Checkbutton(
        win,
        text="Don't show this again",
        variable=dont_show_var,
        bg=win["bg"],
        fg=fg,
        activebackground=win["bg"],
        activeforeground=fg,
        selectcolor=win["bg"],
    ).pack(pady=(0, 8))

    def close_notice():
        if dont_show_var.get():
            settings["startup_notice"] = False
            log("Startup notice disabled by user", full_only=True)
        else:
            log("Startup notice left enabled", full_only=True)
        save_settings()
        win.destroy()

    tk.Button(win, text="OK", width=10, command=close_notice).pack(pady=(0, 16))

# ******************************
# stderr drain
# ******************************
def drain_stderr(proc, tail):
    try:
        for line in proc.stderr:
            line = line.rstrip()
            if line:
                tail.append(line)
                log(f"ffmpeg stderr: {line}", full_only=True)
    except Exception as e:
        log(f"drain_stderr exception: {e}", full_only=True)

# ******************************
# Conversion worker
# ******************************
def convert_file(input_file):
    global current_process

    log(f"convert_file called with: {input_file}", full_only=True)

    if FFMPEG_PATH is None or FFPROBE_PATH is None:
        ui(log, "❌ FFmpeg/FFprobe not found.")
        ui(startup_notice, True)
        return

    if not input_file.lower().endswith(".avi"):
        ui(log, f"Skipped (not AVI): {input_file}")
        return
    if not os.path.exists(input_file):
        ui(log, f"Missing file: {input_file}")
        return

    cancel_event.clear()
    pause_event.set()

    out_dir = dir_out.get() or DEFAULT_OUTPUT
    os.makedirs(out_dir, exist_ok=True)

    out_path = os.path.join(out_dir, os.path.splitext(os.path.basename(input_file))[0] + ".mp4")

    file_info = get_file_info(input_file)
    
    duration = file_info['duration']
    video = file_info['video']
    audio = file_info['audio']

    if duration == 0:
        ui(log, f"❌ Could not read file info")
        return

    ui(log, f"\nInput: {os.path.basename(input_file)}")
    ui(set_ui_state, status="Working...")

    cmd = [
        FFMPEG_PATH, "-hide_banner", "-loglevel", "error",
        "-y", "-i", input_file,
        "-progress", "pipe:1", "-nostats",
    ]

    chosen = encode_w.get()
    if chosen not in ENCODERS:
        chosen = auto_best_encoder()
        ui(log, "⚠️ Encoder unavailable; switching.")
        ui(lambda: encode_w.set(chosen))
        ui(save_settings)

    safe_copy = (
        video.get("codec_name") == "h264"
        and video.get("pix_fmt") == "yuv420p"
        and video.get("profile") in ("Baseline", "Main", "High")
        and chosen == "CPU"
    )

    if safe_copy:
        cmd += ["-c:v", "copy"]
        ui(log, "Video: stream copy")
    else:
        enc = ENCODERS[chosen]
        cmd += ["-c:v", enc, "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1"]

        if enc == "libx264":
            cmd += ["-preset", "medium", "-crf", "18"]
        elif enc == "h264_amf":
            cmd += ["-rc", "cqp", "-qp_i", "18", "-qp_p", "18", "-qp_b", "18"]
        elif enc == "h264_nvenc":
            cmd += ["-rc", "vbr", "-cq", "18", "-b:v", "0"]
        elif enc == "h264_qsv":
            cmd += ["-global_quality", "18"]

        ui(log, f"Video: {chosen}")

    if audio in ("aac", "mp3"):
        cmd += ["-c:a", "copy"]
    else:
        cmd += ["-c:a", "aac", "-b:a", "192k"]

    cmd += ["-movflags", "+faststart", out_path]

    stderr_tail = deque(maxlen=10)

    try:
        current_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            creationflags=CREATE_NO_WINDOW,
        )
    except Exception as e:
        ui(log, f"❌ ffmpeg start failed: {e}")
        ui(set_ui_state, status="Idle", progress=0, pause_btn_text="Pause")
        return

    threading.Thread(target=drain_stderr, args=(current_process, stderr_tail), daemon=True).start()

    start = time.time()
    last_bytes = None
    last_bytes_time = None

    def output_kbps():
        nonlocal last_bytes, last_bytes_time
        try:
            if not os.path.exists(out_path):
                return 0.0
            b = os.path.getsize(out_path)
            t = time.time()
            if last_bytes is None:
                last_bytes, last_bytes_time = b, t
                return 0.0
            dt = max(0.001, t - (last_bytes_time or t))
            db = max(0, b - (last_bytes or 0))
            last_bytes, last_bytes_time = b, t
            return (db / dt) / 1024.0
        except Exception:
            return 0.0

    try:
        for raw in current_process.stdout:
            if cancel_event.is_set():
                try:
                    current_process.terminate()
                    current_process.wait(timeout=2)
                except Exception:
                    try:
                        current_process.kill()
                    except Exception:
                        pass

                if os.path.exists(out_path):
                    try:
                        os.remove(out_path)
                        ui(log, "❌ Cancelled (partial output deleted)")
                    except Exception:
                        ui(log, "❌ Cancelled (could not delete output)")
                else:
                    ui(log, "❌ Cancelled")

                ui(set_ui_state, status="Idle", progress=0, pause_btn_text="Pause")
                return

            pause_event.wait()

            line = raw.strip()
            if line.startswith("out_time_ms"):
                val = line.split("=", 1)[1].strip()
                if not val.isdigit():
                    continue

                out_time = int(val) / 1_000_000
                pct = (out_time / duration) * 100 if duration else 0.0
                ui(set_ui_state, progress=pct)

                elapsed = max(0.001, time.time() - start)
                speed = out_time / elapsed if out_time > 0 else 0.0
                eta = (duration - out_time) / speed if speed > 0 else 0.0

                kbps = output_kbps()
                ui(set_ui_state, status=f"{pct:5.1f}% | ETA {eta:5.1f}s | {kbps:,.0f} KB/s")

        rc = current_process.wait()

    except Exception as e:
        ui(log, f"❌ Progress read error: {e}")
        rc = -1

    if cancel_event.is_set():
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except Exception:
                pass
        ui(set_ui_state, status="Idle", progress=0, pause_btn_text="Pause")
        return

    if rc != 0:
        ui(log, "❌ ffmpeg failed")
        if stderr_tail:
            ui(log, "Last stderr:\n" + "\n".join(stderr_tail))
        try:
            if os.path.exists(out_path) and os.path.getsize(out_path) == 0:
                os.remove(out_path)
        except Exception:
            pass
        ui(set_ui_state, status="Idle", progress=0, pause_btn_text="Pause")
        return

    if not (os.path.exists(out_path) and os.path.getsize(out_path) > 0):
        ui(log, "❌ Output missing/empty")
        ui(set_ui_state, status="Idle", progress=0, pause_btn_text="Pause")
        return

    ui(set_ui_state, progress=100, status="Done")
    ui(log, f"✅ Output: {out_path}")

    log(f"UI reset to Idle", full_only=True)
    root.after(800, lambda: set_ui_state(status="Idle", progress=0, pause_btn_text="Pause"))

# ******************************
# Controls
# ******************************
def start_conversion(f):
    threading.Thread(target=convert_file, args=(f,), daemon=True).start()

def pause_resume():
    if pause_event.is_set():
        pause_event.clear()
        if current_process:
            try:
                current_process.send_signal(signal.SIGSTOP)
            except Exception:
                pass
        log("⏸️ Paused")
        set_ui_state(pause_btn_text="Resume", status="Paused")
    else:
        pause_event.set()
        if current_process:
            try:
                current_process.send_signal(signal.SIGCONT)
            except Exception:
                pass
        log("▶️ Resumed")
        set_ui_state(pause_btn_text="Pause")

def cancel():
    cancel_event.set()
    set_ui_state(progress=0, status="Cancelled")

def choose_output():
    path = filedialog.askdirectory(initialdir=dir_out.get() or DEFAULT_OUTPUT)
    if path:
        dir_out.set(path)
        save_settings()
        log(f"Output folder set to: {path}")

# ******************************
# GUI
# ******************************
root = TkinterDnD.Tk()
root.title(APP_NAME)
root.geometry("860x620")

style = ttk.Style(root)
style.theme_use("default")

try:
    icon_path = resource_path(ICON_FILENAME)
    if os.path.exists(icon_path):
        root.iconbitmap(icon_path)
except Exception as e:
    log(f"iconbitmap failed: {e}", full_only=True)

dir_out = tk.StringVar(value=settings.get("dir_out", DEFAULT_OUTPUT))
encode_w = tk.StringVar(value=settings.get("encoder", "CPU"))

themed_widgets = []

top = tk.Frame(root)
top.pack(pady=6)
themed_widgets.append(top)

tk.Label(top, text="Encoder:").pack(side=tk.LEFT)

encoder_combo = ttk.Combobox(
    top,
    textvariable=encode_w,
    values=["CPU"],
    state="readonly",
    width=10,
)
encoder_combo.pack(side=tk.LEFT, padx=4)

tk.Button(top, text="Output Folder", command=choose_output).pack(side=tk.LEFT, padx=6)

label = tk.Label(root, text="Drag AVI files [Here]", font=("Segoe UI", 12))
label.pack(pady=8)
label.drop_target_register(DND_FILES)
themed_widgets.append(label)

def on_drop(event):
    for f in root.tk.splitlist(event.data):
        start_conversion(f)

label.dnd_bind("<<Drop>>", on_drop)

controls = tk.Frame(root)
controls.pack()
themed_widgets.append(controls)

tk.Button(
    controls,
    text="Select Files",
    command=lambda: [start_conversion(f) for f in filedialog.askopenfilenames(filetypes=[("AVI", "*.avi")])],
).pack(side=tk.LEFT, padx=4)

pause_btn = tk.Button(controls, text="Pause", command=pause_resume)
pause_btn.pack(side=tk.LEFT, padx=4)

tk.Button(controls, text="Cancel", command=cancel).pack(side=tk.LEFT)

progress_bar = ttk.Progressbar(root, length=800)
progress_bar.pack(pady=6)

status_label = tk.Label(root, text="Idle")
status_label.pack()
themed_widgets.append(status_label)

log_box = tk.Text(root, height=18, width=105)
log_box.pack(padx=10, pady=10)

for m in _ui_buffer:
    try:
        log_box.insert(tk.END, m + "\n")
    except Exception:
        pass
try:
    log_box.see(tk.END)
except Exception:
    pass
_ui_buffer.clear()

def on_encoder_change(_=None):
    save_settings()

encoder_combo.bind("<<ComboboxSelected>>", on_encoder_change)

bottom_bar = tk.Frame(root, bg=root["bg"])
bottom_bar.place(x=8, y=580)

major, minor, patch, build = APP_VERSION
version_str_short = f"{major}.{minor}"
version_label = tk.Label(bottom_bar, text=f"v{version_str_short}")
version_label.pack(side=tk.RIGHT)

info_btn = tk.Button(bottom_bar, text="ℹ", width=2, command=lambda: startup_notice(force_show=True))
info_btn.pack(side=tk.LEFT, padx=(0, 4))

about_btn = tk.Button(bottom_bar, text="?", width=2, command=show_about)
about_btn.pack(side=tk.LEFT)

def refresh_encoder_dropdown():
    try:
        encoder_combo["values"] = list(ENCODERS.keys())
        if encode_w.get() not in ENCODERS:
            encode_w.set(auto_best_encoder())
    except Exception as e:
        log(f"refresh_encoder_dropdown failed: {e}", full_only=True)

def reposition_bottom(_=None):
    try:
        bottom_bar.place(x=8, y=root.winfo_height() - 40)
    except Exception:
        pass

root.bind("<Configure>", reposition_bottom)
reposition_bottom()

apply_ui_style()

def ensure_ffmpeg_or_quit():
    ok = resolve_ffmpeg_paths_once()
    if ok:
        return True

    log("FFmpeg missing at startup; prompting user for download permission.", full_only=True)

    answer = messagebox.askyesno(
        "FFmpeg Required",
        "FFmpeg and FFprobe were not found.\n\n"
        "Would you like the app to download and install FFmpeg automatically?\n\n"
        "Click 'No' to quit.",
    )
    if not answer:
        log("User declined FFmpeg download; quitting.", full_only=True)
        try:
            root.destroy()
        except Exception:
            pass
        sys.exit(0)

    log("User approved FFmpeg download; starting download.", full_only=True)
    root.config(cursor="watch")
    root.update_idletasks()

    installed = download_and_install_ffmpeg()

    root.config(cursor="")
    root.update_idletasks()

    if not installed:
        log("FFmpeg download/install failed; quitting.", full_only=True)
        messagebox.showerror(
            "FFmpeg Download Failed",
            "Auto-download failed.\n\n"
            "Please install FFmpeg manually, and add it to your system PATH, then run the app again.\n\n"
            "You can install FFmpeg here:\n"
            f"{FFMPEG_INSTALL_PAGE}",
        )
        try:
            root.destroy()
        except Exception:
            pass
        sys.exit(0)

    ok2 = resolve_ffmpeg_paths_once()
    if not ok2:
        log("FFmpeg still not detected after install; quitting.", full_only=True)
        messagebox.showerror(
            "FFmpeg Not Detected",
            "FFmpeg was downloaded, but could not be detected afterwards.\n\n"
            "Please install FFmpeg manually, and add it to your system PATH, then run the app again.",
        )
        try:
            root.destroy()
        except Exception:
            pass
        sys.exit(0)

    log("FFmpeg detected after download/install.", full_only=True)
    return True

ensure_ffmpeg_or_quit()
detect_encoders_once()
refresh_encoder_dropdown()

if encode_w.get() not in ENCODERS:
    encode_w.set(auto_best_encoder())
    save_settings()

log(f"Startup: ffmpeg={FFMPEG_PATH} ffprobe={FFPROBE_PATH}", full_only=True)
log(f"Startup: ffmpeg_version='{FFMPEG_VERSION_LINE}'", full_only=True)

def on_close():
    _log_ui_file(f"[{ts()}] App Closed")
    _log_full("=== App Closed ===")
    save_settings()
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)
root.after(300, startup_notice)
root.mainloop()