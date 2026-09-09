#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core — logika konversi M4A -> MP4 (YouTube-ready) yang dipakai bersama
oleh CLI (m4a2yt.py) dan GUI (m4a2yt_gui.py).

Aturan kualitas:
  - Video : H.264 (libx264), layar hitam polos, resolusi kecil (default 240p)
  - Audio : di-copy ASLI kalau AAC (tanpa re-encode), kalau bukan AAC -> AAC 192k
"""

import os
import shutil
import subprocess
import sys

DEFAULT_RES = "426x240"          # 240p, kecil

FFMPEG_DOWNLOAD = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


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
        )
        return out.stdout.strip().lower()
    except Exception:
        return ""


def convert_one(src, ffmpeg, res=DEFAULT_RES, out_dir=None, cover=None):
    """Konversi satu file. Return tuple (ok: bool, dst_path, info, audio_note)."""
    if not os.path.isfile(src):
        return (False, None, "bukan file: " + src, "")

    ffprobe = find_ffprobe(ffmpeg)
    stem = os.path.splitext(os.path.basename(src))[0]
    if not out_dir:
        out_dir = os.path.dirname(os.path.abspath(src))
    dst = os.path.join(out_dir, stem + ".mp4")

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

    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"] + build
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-shortest"]
    cmd += a_opts
    cmd += [dst]

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0 and os.path.isfile(dst):
        size_mb = os.path.getsize(dst) / (1024 * 1024)
        return (True, dst, "{:.1f} MB".format(size_mb), audio_note)
    return (False, None, r.stderr.strip()[-400:], audio_note)