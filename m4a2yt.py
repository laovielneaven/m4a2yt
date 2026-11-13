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

Gabung beberapa rekaman jadi satu:
    python m4a2yt.py --stitch bagian1.m4a bagian2.m4a bagian3.m4a
    python m4a2yt.py --stitch --mp4 --name "rapat-lengkap" a.m4a b.m4a

Opsi:
    --stitch              gabung semua file jadi SATU file (urut sesuai argumen)
    --name NAMA           nama file hasil gabungan (tanpa ekstensi)
    --mp4                 hasil gabungan langsung MP4 (default .m4a)
    --res 640x360         ganti resolusi
    --cover gambar.jpg    pakai gambar sebagai latar
    --out D:\\\\hasil       folder output (default: sama dengan file input)
"""

import argparse
import os
import sys

import core


def collect_files(paths):
    """Kumpulkan file .m4a dari argumen (file atau folder), urut abjad per folder."""
    files = []
    for p in paths:
        if os.path.isdir(p):
            for f in sorted(os.listdir(p)):
                if f.lower().endswith(".m4a"):
                    files.append(os.path.join(p, f))
        elif p.lower().endswith(".m4a"):
            files.append(p)
        else:
            print("  [SKIP] bukan .m4a: " + p)
    return files


def main():
    ap = argparse.ArgumentParser(description="M4A -> MP4 (YouTube-ready).")
    ap.add_argument("paths", nargs="+", help="file .m4a atau folder berisi .m4a")
    ap.add_argument("--res", default=core.DEFAULT_RES)
    ap.add_argument("--cover", default=None)
    ap.add_argument("--out", default=None, help="folder output (default: sama dgn input)")
    ap.add_argument("--stitch", action="store_true",
                    help="gabung semua file jadi satu file")
    ap.add_argument("--name", default=None,
                    help="nama file hasil gabungan (tanpa ekstensi)")
    ap.add_argument("--mp4", action="store_true",
                    help="hasil gabungan langsung MP4 (default .m4a)")
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

    files = collect_files(args.paths)
    if not files:
        print("Tidak ada file .m4a ditemukan.")
        sys.exit(1)

    # ---------------------------------------------------------- mode gabung
    if args.stitch:
        print("Menggabung {} file (urut sesuai argumen)...".format(len(files)))
        for i, f in enumerate(files, 1):
            print("  {}. {}".format(i, os.path.basename(f)))

        state = {"bar": -1}

        def _prog(ratio):
            # progres satu baris, ditimpa terus; hanya gambar ulang kalau berubah
            bar = int(ratio * 30)
            if bar == state["bar"]:
                return
            state["bar"] = bar
            sys.stdout.write("\r  [{}{}] {:3.0f}%".format(
                "#" * bar, "." * (30 - bar), ratio * 100))
            sys.stdout.flush()

        ok, dst, info, note = core.stitch_audio(
            files, ffmpeg, out_dir=args.out, name=args.name,
            make_video=args.mp4, res=args.res, cover=args.cover,
            progress_cb=_prog)
        print()
        if ok:
            print("OK  -> {}  ({}, audio {})".format(dst, info, note))
        else:
            print("GAGAL: {}".format(info))
            sys.exit(1)
        return

    # ------------------------------------------------------- mode konversi
    print("Menemukan {} file. Memproses (res {} , audio asli)...".format(
        len(files), args.res))
    gagal = 0
    for i, f in enumerate(files, 1):
        ok, dst, info, note = core.convert_one(
            f, ffmpeg, res=args.res, out_dir=args.out, cover=args.cover)
        print("[{}/{}] {}".format(i, len(files), os.path.basename(f)))
        if ok:
            print("     OK  -> {}  ({}, audio {})".format(dst, info, note))
        else:
            gagal += 1
            print("     GAGAL: {}".format(info))

    print("Selesai. Hasil ada di: {}{}".format(
        args.out if args.out else "folder masing-masing input",
        "" if not gagal else "  ({} file gagal)".format(gagal)))


if __name__ == "__main__":
    main()
