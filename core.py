#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core — logika konversi M4A -> MP4 (YouTube-ready) yang dipakai bersama
oleh CLI (m4a2yt.py) dan GUI (m4a2yt_gui.py).

Aturan kualitas:
  - Video : H.264 (libx264), layar hitam polos, resolusi kecil (default 240p)
  - Audio : di-copy ASLI kalau AAC (tanpa re-encode), kalau bukan AAC -> AAC 192k

Fitur gabung (stitch):
  - Beberapa file audio digabung jadi SATU file, urut sesuai urutan yang
    diberikan. Kalau semua file parameternya sama dan codec-nya AAC ->
    digabung tanpa re-encode (-c copy) = kualitas asli utuh. Kalau beda
    (codec / sample rate / channel) -> re-encode AAC 192k supaya tidak gagal.
  - make_video=True langsung menghasilkan MP4 (video hitam/cover), jadi
    sekali proses tanpa file antara.

Catatan Windows: semua subprocess (ffmpeg/ffprobe) dibungkus flag
CREATE_NO_WINDOW supaya TIDAK memunculkan jendela terminal/console saat
dijalankan dari aplikasi GUI (--windowed).
"""

import os
import shutil
import subprocess
import sys
import tempfile
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


def probe_audio_info(src, ffprobe):
    """
    Info stream audio pertama: dict(codec, sample_rate, channels).
    Return {} kalau gagal. Dipakai untuk memutuskan boleh -c copy atau tidak.
    """
    if not ffprobe:
        return {}
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=codec_name,sample_rate,channels",
             "-of", "csv=p=0", src],
            capture_output=True, text=True, timeout=60,
            **_no_window_kwargs(),
        )
        parts = [p.strip() for p in out.stdout.strip().split(",")]
        if len(parts) < 3 or not parts[0]:
            return {}
        return {"codec": parts[0].lower(),
                "sample_rate": parts[1],
                "channels": parts[2]}
    except Exception:
        return {}


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


def split_res(res):
    """
    '426x240' -> ('426', '240').

    Penting: filter `scale` menerima 'WxH', tapi filter `pad` TIDAK —
    pad butuh 'w:h:x:y'. Dulu kode menulis pad=426x240:... sehingga jalur
    --cover SELALU gagal ("Invalid chars 'x240' at the end of expression").
    """
    try:
        w, h = str(res).lower().replace("*", "x").split("x", 1)
        int(w), int(h)
        return w, h
    except Exception:
        return "426", "240"


def unique_path(dst):
    """
    Jangan timpa file yang sudah ada: 'hasil.mp4' -> 'hasil (2).mp4'.
    Dipakai fitur gabung supaya rekaman lama tidak hilang tanpa sengaja.
    """
    if not os.path.exists(dst):
        return dst
    base, ext = os.path.splitext(dst)
    i = 2
    while os.path.exists("{} ({}){}".format(base, i, ext)):
        i += 1
    return "{} ({}){}".format(base, i, ext)


def _run_ffmpeg(cmd, duration, progress_cb=None):
    """
    Jalankan ffmpeg, parse progres real-time dari stdout ("-progress pipe:1").
    Return tuple (returncode, stderr_text). returncode -1 = gagal start.

    CATATAN: pakai `out_time_us` SAJA (selalu microsecond di semua versi
    ffmpeg). `out_time_ms` tidak bisa diandalkan — di beberapa build nilainya
    sama dengan out_time_us (bukan milidetik), bisa bikin progres melesat 100%.
    """
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True,
                                **_no_window_kwargs())
    except Exception as e:
        return (-1, "gagal mulai ffmpeg: {}".format(e))

    # Baca stderr di thread terpisah agar tidak deadlock (buffer penuh)
    stderr_buf = []

    def _drain_err():
        try:
            stderr_buf.append(proc.stderr.read())
        finally:
            try:
                proc.stderr.close()
            except Exception:
                pass

    t = threading.Thread(target=_drain_err, daemon=True)
    t.start()

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
    return (rc, "".join(stderr_buf))


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
        _w, _h = split_res(res)
        build = ["-loop", "1", "-i", cover, "-i", src,
                 "-map", "0:v", "-map", "1:a",
                 "-vf", "scale={}:force_original_aspect_ratio=decrease,"
                       "pad={}:{}:(ow-iw)/2:(oh-ih)/2".format(res, _w, _h)]
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

    rc, err = _run_ffmpeg(cmd, duration, progress_cb)

    if rc == 0 and os.path.isfile(dst):
        if progress_cb:
            progress_cb(1.0)
        size_mb = os.path.getsize(dst) / (1024 * 1024)
        return (True, dst, "{:.1f} MB".format(size_mb), audio_note)
    return (False, None, (err or "ffmpeg gagal").strip()[-400:], audio_note)


def _write_concat_list(srcs, workdir):
    """
    Tulis daftar file untuk concat demuxer ffmpeg.
    Path absolut, backslash diubah ke '/' (aman di Windows), tanda kutip
    tunggal di-escape sesuai aturan concat demuxer.
    """
    lines = []
    for p in srcs:
        p = os.path.abspath(p).replace("\\", "/")
        p = p.replace("'", "'\\''")
        lines.append("file '{}'".format(p))
    path = os.path.join(workdir, "concat.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def stitch_audio(srcs, ffmpeg, out_dir=None, name=None, make_video=False,
                 res=DEFAULT_RES, cover=None, progress_cb=None):
    """
    Gabung beberapa file audio jadi SATU file, urut sesuai `srcs`.

    Return tuple (ok, dst_path, info, audio_note).

    make_video=False -> hasil .m4a (audio saja)
    make_video=True  -> hasil .mp4 (video hitam/cover + audio gabungan)

    Tanpa re-encode kalau memungkinkan: semua file harus AAC dengan sample
    rate & jumlah channel sama. Selain itu di-re-encode AAC 192k.
    File hasil tidak menimpa file lama (diberi akhiran " (2)" dst).
    """
    srcs = [s for s in srcs if os.path.isfile(s)]
    if not srcs:
        return (False, None, "tidak ada file audio yang valid", "")

    ffprobe = find_ffprobe(ffmpeg)
    infos = [probe_audio_info(s, ffprobe) for s in srcs]
    duration = sum(probe_duration(s, ffprobe) for s in srcs)

    uniform = bool(infos) and all(infos) and len(
        {(i["codec"], i["sample_rate"], i["channels"]) for i in infos}) == 1
    can_copy = uniform and infos[0]["codec"] == "aac"

    if name:
        name = os.path.splitext(os.path.basename(name))[0]
    if not name:
        name = "gabungan"
    ext = ".mp4" if make_video else ".m4a"
    if not out_dir:
        out_dir = os.path.dirname(os.path.abspath(srcs[0]))
    try:
        os.makedirs(out_dir, exist_ok=True)
    except Exception as e:
        return (False, None, "folder tujuan tidak bisa dibuat: {}".format(e), "")
    dst = unique_path(os.path.join(out_dir, name + ext))

    workdir = tempfile.mkdtemp(prefix="m4a2yt-stitch-")
    try:
        inputs = []
        if make_video:
            if cover and os.path.isfile(cover):
                _w, _h = split_res(res)
                inputs += ["-loop", "1", "-i", cover]
                vfilter = ("-vf", "scale={}:force_original_aspect_ratio=decrease,"
                                  "pad={}:{}:(ow-iw)/2:(oh-ih)/2".format(res, _w, _h))
            else:
                inputs += ["-f", "lavfi", "-i",
                           "color=c=black:s={}:r=10".format(res)]
                vfilter = None
            audio_start = 1
        else:
            vfilter = None
            audio_start = 0

        if can_copy:
            # Jalur cepat: semua AAC & parameternya sama -> sambung tanpa decode
            lst = _write_concat_list(srcs, workdir)
            inputs += ["-f", "concat", "-safe", "0", "-i", lst]
            maps = ["-map", "0:v", "-map", "{}:a".format(audio_start)] \
                if make_video else []
            a_opts = ["-c:a", "copy"]
            audio_note = "copy (asli, {} file)".format(len(srcs))
        else:
            # Parameter beda: decode semua, samakan format, sambung via filter.
            # (concat demuxer + re-encode bisa menyisipkan jeda/drift durasi,
            #  concat FILTER presisi karena frame digabung setelah di-decode.)
            ref = infos[0] if all(infos) else {}
            sr = ref.get("sample_rate") or "44100"
            layout = {"1": "mono", "2": "stereo"}.get(
                str(ref.get("channels") or "1"), "stereo")
            chain = []
            for k, p in enumerate(srcs):
                inputs += ["-i", p]
                chain.append("[{k}:a]aresample={sr},aformat=channel_layouts={ly}"
                             "[a{k}]".format(k=k + audio_start, sr=sr, ly=layout))
            pads = "".join("[a{}]".format(k + audio_start)
                           for k in range(len(srcs)))
            chain.append("{}concat=n={}:v=0:a=1[aout]".format(pads, len(srcs)))
            inputs += ["-filter_complex", ";".join(chain)]
            maps = ["-map", "0:v", "-map", "[aout]"] if make_video \
                else ["-map", "[aout]"]
            a_opts = ["-c:a", "aac", "-b:a", "192k"]
            audio_note = "aac 192k ({} file)".format(len(srcs))

        cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
               "-nostats", "-progress", "pipe:1"] + inputs
        if make_video:
            cmd += maps
            if vfilter:
                cmd += list(vfilter)
            cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                    "-shortest"]
        else:
            cmd += maps + ["-movflags", "+faststart"]
        cmd += a_opts
        cmd += [dst]

        rc, err = _run_ffmpeg(cmd, duration, progress_cb)

        if rc == 0 and os.path.isfile(dst):
            if progress_cb:
                progress_cb(1.0)
            size_mb = os.path.getsize(dst) / (1024 * 1024)
            return (True, dst, "{:.1f} MB".format(size_mb), audio_note)
        return (False, None, (err or "ffmpeg gagal").strip()[-400:], audio_note)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
