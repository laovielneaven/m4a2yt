# m4a2yt

Ubah rekaman **.m4a** (Windows Voice Recorder) jadi **.mp4** yang bisa di-upload ke YouTube.

YouTube menolak file audio-only. Tool ini membungkus audio jadi video MP4
(layar hitam polos, resolusi kecil) **tanpa menurunkan kualitas audio**
(audio di-copy asli, bukan re-encode).

## Isi folder

| File | Fungsi |
|------|--------|
| `m4a2yt_gui.py` | GUI (klik-klik, untuk orang awam) |
| `m4a2yt.py`     | CLI (ketik perintah di terminal) |
| `core.py`       | Logika konversi (dipakai berdua) |
| `requirements-build.txt` | dependensi untuk build .exe |
| `.github/workflows/build.yml` | build otomatis .exe via GitHub Actions |

## Cara dapat .exe (paling gampang — tanpa install apa pun)

Repo ini sudah dikonfigurasi membangun **satu file `.exe` mandiri**
(Python + GUI + ffmpeg + ffprobe semua di dalam, tidak perlu install apa pun).

1. Buka **Actions** di repo GitHub.
2. Klik **"build-windows-exe"** di kiri → **"Run workflow"** → **"Run workflow"**.
   (Atau dorong tag `v*`, misal `git tag v1.0 && git push --tags`.)
3. Tunggu job selesai (hijau).
4. Buka run itu → scroll ke bawah → **Artifacts** → unduh
   `m4a2yt-windows` (file zip berisi `m4a2yt.exe`).
5. Ekstrak zip → klik 2× `m4a2yt.exe`.

> Windows SmartScreen mungkin muncul saat pertama kali (karena belum
> ditandatangani). Klik **"More info" → "Run anyway"**.

## Cara pakai (GUI)

1. Klik **"Pilih File"** → pilih satu/lebih file `.m4a`.
2. Pilih lokasi simpan:
   - **Folder yang sama dengan file input** (default), atau
   - **Pilih folder lain** (save as...).
3. Klik **Convert**. Hasil `.mp4` muncul di folder tujuan, siap upload YouTube.

## Cara pakai (CLI, dari source)

Syarat: Python 3 + ffmpeg (taruh `ffmpeg.exe` di folder `bin/` sebelah script,
atau tambahkan ke PATH).

```
python m4a2yt.py "rekaman.m4a"
python m4a2yt.py "folder-rekaman"
python m4a2yt.py --res 640x360 --cover gambar.jpg "rekaman.m4a"
```

## Hasil

- Format MP4, codec H.264 (video) + AAC (audio) — kombinasi yang diterima YouTube.
- Audio **di-copy asli** (bukan re-encode) → suara tetap 100% asli.
- Resolusi kecil (default 240p) → ukuran file kecil, upload cepat.

## Build .exe sendiri (opsional)

```
pip install -r requirements-build.txt
pyinstaller --onefile --windowed --name m4a2yt --add-binary "ffmpeg.exe;." --add-binary "ffprobe.exe;." m4a2yt_gui.py
```