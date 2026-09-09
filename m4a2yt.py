#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m4a2yt (CLI) — ubah rekaman M4A jadi video MP4 untuk YouTube.

YouTube menolak file audio-only. Script ini membungkus audio jadi MP4
(layar hitam polos, resolusi kecil 240p) tanpa menurunkan kualitas audio.

Cara pakai:
    python m4a2yt.py "rekaman.m4a"
    python m4a2yt.py "folder-berisi-m4a"
    python m4a2yt.py "a.m4a" "b.m4a"

Opsi:
    --res 640x360         ganti resolusi
    --cover gambar.jpg    pakai gambar sebagai latar
    --out D:\\hasil       folder output (default: sama dengan file input)
"""

import argparse
import os
import sys

import core


def main():
    ap = argparse.ArgumentParser(description="M4A -> MP4 (YouTube-ready).")
    ap.add_argument("paths", nargs="+", help="file .m4a atau folder berisi .m4a")
    ap.add_argument("--res", default=core.DEFAULT_RES)
    ap.add_argument("--cover", default=None)
    ap.add_argument("--out", default=None, help="folder output (default: sama dgn input)")
    args = ap.parse_args()

    ffmpeg = core.find_ffmpeg()
    if not ffmpeg:
        print("ERROR: ffmpeg tidak ditemukan.")
        print("Unduh: " + core.FFMPEG_DOWNLOAD)
        print("Lalu taruh ffmpeg.exe di folder 'bin' sebelah script, "
              "atau tambahkan ke PATH.")
        sys.exit(1)

    if args.cover and not os.path.isfile(args.cover):
        print("ERROR: file cover tidak ditemukan: " + args.cover)
        sys.exit(1)

    # kumpulkan file
    files = []
    for p in args.paths:
        if os.path.isdir(p):
            for f in sorted(os.listdir(p)):
                if f.lower().endswith(".m4a"):
                    files.append(os.path.join(p, f))
        elif p.lower().endswith(".m4a"):
            files.append(p)
        else:
            print("  [SKIP] bukan .m4a: " + p)

    if not files:
        print("Tidak ada file .m4a ditemukan.")
        sys.exit(1)

    print("Menemukan {} file. Memproses (res {} , audio asli)...".format(
        len(files), args.res))
    for i, f in enumerate(files, 1):
        ok, dst, info, note = core.convert_one(
            f, ffmpeg, res=args.res, out_dir=args.out, cover=args.cover)
        print("[{}/{}] {}".format(i, len(files), os.path.basename(f)))
        if ok:
            print("     OK  -> {}  ({}, audio {})".format(dst, info, note))
        else:
            print("     GAGAL: {}".format(info))

    print("Selesai. Hasil ada di: {}".format(
        args.out if args.out else "folder masing-masing input"))


if __name__ == "__main__":
    main()