#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core — logika konversi M4A -> MP4 (YouTube-ready) yang dipakai bersama
oleh CLI (m4a2yt.py) dan GUI (m4a2yt_gui.py).

Aturan kualitas:
  - Video : H.264 (libx264), layar hitam polos, resolusi kecil (default 240p)
  - Audio : di-copy ASLI kalau AAC (tanpa re-encode), kalau bukan AAC -> AAC 192k

Catatan Windows: semua subprocess (ffmpeg/ffprobe) dibungkus flag
CREATE_NO_WINDOW supaya TIDAK memunculkan jendela terminal/console saat
dijalankan dari aplikasi GUI (--windowed).
"""

import os
import shutil
import subprocess
import sys
import threading

DEFAULT_RES = "426x240"          # 240p, kecil

FFMPEG_DOWNLOAD = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

CREATE_NO_WINDOW = 0x08000000    # Windows: jangan buka jendela console


def _no_window_kwargs():
    """Extra kwargs subprocess agar tidak muncul jendela console di Windows."""
    if os.name == "nt":
        return {"creationflags": CREATE_NO_WINDOW}
    return {}


def _frozen_dir():
    """Folder tempat binary ditaruh saat app dibundle PyInstaller (--onefile)."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return None


def find_ffmpeg():
    """Cari ffmpeg, urut: (1) bundle frozen, (2) PATH, (3) bin/ sebelah script."""
    base = _frozen_dir()
    if base:
        for name in ("ffmpeg.exe", "ffmpeg"):
            p = os.path.join(base, name)
            if os.path.isfile(p):
                return p
    p = shutil.which("ffmpeg")
    if p:
        return p
    here = os.path.dirname(os.path.abspath(__file__))
    for name in ("ffmpeg.exe", "ffmpeg"):
        cand = os.path.join(here, "bin", name)
        if os.path.isfile(cand):
            return cand
    return None


def find_ffprobe(ffmpeg):
    """Dapatkan ffprobe di folder yang sama dengan ffmpeg (atau PATH)."""
    if not ffmpeg:
        return None
    base, name = os.path.split(ffmpeg)
    for cand_name in (name.replace("ffmpeg", "ffprobe", 1), "ffprobe", "ffprobe.exe"):
        cand = os.path.join(base, cand_name)
        if os.path.isfile(cand):
            return cand
    return shutil.which("ffprobe")


def probe_audio_codec(src, ffprobe):
    """Nama codec stream audio utama ('' kalau gagal dideteksi)."""
    if not ffprobe:
        return ""
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=codec_name", "-of", "csv=p=0", src],
            capture_output=True, text=True, timeout=60,
            **_no_window_kwargs(),
        )
        return out.stdout.strip().lower()
    except Exception:
        return ""


def probe_duration(src, ffprobe):
    """Durasi media dalam detik (float). Return 0.0 kalau gagal."""
    if not ffprobe:
        return 0.0
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error",
             "-show_entries", "format=duration", "-of", "csv=p=0", src],
            capture_output=True, text=True, timeout=60,
            **_no_window_kwargs(),
        )
        return float(out.stdout.strip())
    except Exception:
        return 0.0


def convert_one(src, ffmpeg, res=DEFAULT_RES, out_dir=None, cover=None,
                progress_cb=None):
    """
    Konversi satu file. Return tuple (ok: bool, dst_path, info, audio_note).

    progress_cb: optional callback yang dipanggil dengan rasio 0.0..1.0
                 secara real-time selama encoding berjalan.
    """
    if not os.path.isfile(src):
        return (False, None, "bukan file: " + src, "")

    ffprobe = find_ffprobe(ffmpeg)
    stem = os.path.splitext(os.path.basename(src))[0]
    if not out_dir:
        out_dir = os.path.dirname(os.path.abspath(src))
    dst = os.path.join(out_dir, stem + ".mp4")
    duration = probe_duration(src, ffprobe)

    # Stream video: layar hitam polos ATAU gambar cover
    if cover and os.path.isfile(cover):
        build = ["-loop", "1", "-i", cover, "-i", src,
                 "-map", "0:v", "-map", "1:a",
                 "-vf", "scale={}:force_original_aspect_ratio=decrease,"
                       "pad={}:(ow-iw)/2:(oh-ih)/2".format(res, res)]
    else:
        build = ["-f", "lavfi", "-i", "color=c=black:s={}:r=10".format(res),
                 "-i", src, "-map", "0:v", "-map", "1:a"]

    # Audio: copy asli kalau AAC (kualitas 100%), re-encode kalau bukan
    codec = probe_audio_codec(src, ffprobe)
    if codec == "aac":
        a_opts = ["-c:a", "copy"]
        audio_note = "copy (asli)"
    else:
        a_opts = ["-c:a", "aac", "-b:a", "192k"]
        audio_note = "aac 192k"

    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
           "-nostats", "-progress", "pipe:1"] + build
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-shortest"]
    cmd += a_opts
    cmd += [dst]

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True,
                                **_no_window_kwargs())
    except Exception as e:
        return (False, None, "gagal mulai ffmpeg: {}".format(e), audio_note)

    # Baca stderr di thread terpisah agar tidak deadlock (buffer penuh)
    stderr_buf = []

    def _drain_err():
        stderr_buf.append(proc.stderr.read())
        proc.stderr.close()

    t = threading.Thread(target=_drain_err, daemon=True)
    t.start()

    # Parse progres real-time dari stdout ("-progress pipe:1")
    # CATATAN: pakai `out_time_us` SAJA (selalu microsecond di semua versi ffmpeg).
    # `out_time_ms` tidak bisa diandalkan — di beberapa build ffmpeg nilainya
    # sama dengan out_time_us (bukan milidetik), bisa bikin progres melesat ke 100%.
    seconds_in = 0.0
    last_ratio = -1.0
    try:
        for line in proc.stdout:
            line = line.strip()
            if line.startswith("out_time_us="):
                try:
                    seconds_in = int(line.split("=", 1)[1]) / 1_000_000.0
                except ValueError:
                    pass

            if progress_cb and duration > 0:
                ratio = max(0.0, min(1.0, seconds_in / duration))
                if ratio - last_ratio >= 0.01 or ratio >= 1.0:
                    last_ratio = ratio
                    progress_cb(ratio)
    except Exception:
        pass
    finally:
        try:
            proc.stdout.close()
        except Exception:
            pass

    rc = proc.wait()
    t.join(timeout=5)

    err = "".join(stderr_buf)

    if rc == 0 and os.path.isfile(dst):
        if progress_cb:
            progress_cb(1.0)
        size_mb = os.path.getsize(dst) / (1024 * 1024)
        return (True, dst, "{:.1f} MB".format(size_mb), audio_note)
    return (False, None, (err or "ffmpeg gagal").strip()[-400:], audio_note)