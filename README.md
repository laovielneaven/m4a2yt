# m4a2yt

Ubah rekaman **.m4a** (Windows Voice Recorder) jadi **.mp4** yang bisa di-upload ke YouTube.

YouTube menolak file audio-only. Tool ini membungkus audio jadi video MP4
(layar hitam polos, resolusi kecil) **tanpa menurunkan kualitas audio**
(audio di-copy asli, bukan re-encode).

Ada juga fitur **gabung (stitch)**: beberapa rekaman disambung jadi SATU file,
urut sesuai yang diatur — berguna kalau rekaman rapat terpotong jadi beberapa
bagian dan mau diunggah sebagai satu video.

## Isi folder

| File | Fungsi |
|------|--------|
| `m4a2yt_gui.py` | GUI (klik-klik, untuk orang awam) |
| `m4a2yt.py`     | CLI (ketik perintah di terminal) |
| `core.py`       | Logika konversi + gabung (dipakai berdua) |
| `smoke_test.py` | Uji cepat GUI (dipakai CI sebelum build .exe) |
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

Pilih mode di tombol paling atas: **Konversi** atau **Gabung Audio**.

### Mode Konversi (biasa)

1. Klik **"+ Tambah File"** → pilih satu/lebih file `.m4a`.
2. Pilih lokasi simpan:
   - **Folder yang sama dengan file input** (default), atau
   - **Folder lain** (save as...).
3. Klik **Convert**. Hasil `.mp4` muncul di folder tujuan, siap upload YouTube.

### Mode Gabung Audio (stitch)

1. Pindah ke tab **Gabung Audio**.
2. Tambah file (minimal 2). Urutan di daftar = urutan hasil gabungan.
   Geser dengan tombol **▲ / ▼** kalau urutannya salah.
3. Isi **Nama hasil** (opsional; kalau kosong otomatis `gabungan`).
4. Centang **"Langsung jadikan MP4"** kalau mau hasilnya langsung siap upload
   (kalau tidak dicentang, hasilnya `.m4a` gabungan saja).
5. Klik **Gabung Jadi Satu**.

Hasil gabungan **tidak menimpa** file lama: kalau nama sudah ada, otomatis
jadi `gabungan (2).m4a`.

## Cara pakai (CLI, dari source)

Syarat: Python 3 + ffmpeg (taruh `ffmpeg.exe` di folder `bin/` sebelah script,
atau tambahkan ke PATH).

```
python m4a2yt.py "rekaman.m4a"
python m4a2yt.py "folder-rekaman"
python m4a2yt.py --res 640x360 --cover gambar.jpg "rekaman.m4a"
```

Gabung beberapa rekaman jadi satu:

```
python m4a2yt.py --stitch bagian1.m4a bagian2.m4a bagian3.m4a
python m4a2yt.py --stitch --mp4 --name "rapat-lengkap" a.m4a b.m4a
python m4a2yt.py --stitch --out D:\hasil folder-rekaman
```

| Opsi | Arti |
|------|------|
| `--stitch` | gabung semua file jadi satu (urutan = urutan argumen) |
| `--name NAMA` | nama file hasil gabungan (tanpa ekstensi) |
| `--mp4` | hasil gabungan langsung MP4 (default `.m4a`) |
| `--res 640x360` | ganti resolusi video |
| `--cover gambar.jpg` | pakai gambar sebagai latar video |
| `--out FOLDER` | folder output (default: sama dengan file input) |

## Hasil

- Format MP4, codec H.264 (video) + AAC (audio) — kombinasi yang diterima YouTube.
- Audio **di-copy asli** (bukan re-encode) → suara tetap 100% asli.
- Resolusi kecil (default 240p) → ukuran file kecil, upload cepat.
- Gabung audio: kalau semua file AAC dengan sample rate & channel sama,
  penyambungan **tanpa re-encode** (kualitas asli utuh, cepat). Kalau beda
  parameter, otomatis di-re-encode AAC 192k supaya tidak gagal.

## Build .exe sendiri (opsional)

```
pip install -r requirements-build.txt
pyinstaller --onefile --windowed --name m4a2yt --add-binary "ffmpeg.exe;." --add-binary "ffprobe.exe;." m4a2yt_gui.py
```
