#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m4a2yt GUI — bungkus M4A (Windows Voice Recorder) jadi MP4 untuk YouTube.

Cara pakai (sangat simpel):
  1. Klik "Pilih File" -> pilih satu/lebih file .m4a
  2. Pilih lokasi simpan (default: folder yang sama dengan file input)
  3. Klik "Convert" -> hasil .mp4 muncul di folder tujuan

Dijalankan langsung:  python m4a2yt_gui.py
"""

import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import core


class App:
    def __init__(self, root):
        self.root = root
        root.title("m4a2yt — M4A ke YouTube")
        root.geometry("720x560")
        root.minsize(620, 480)

        self.files = []           # daftar path file yang dipilih
        self.out_choice = tk.StringVar(value="same")  # 'same' | 'custom'
        self.out_dir = tk.StringVar(value="")
        self._q = queue.Queue()

        self._build_ui()

        # Cek ffmpeg sekali di awal, info jika belum ada
        if not core.find_ffmpeg():
            messagebox.showwarning(
                "ffmpeg tidak ditemukan",
                "ffmpeg tidak ditemukan.\n\n"
                "Kalau kamu pakai versi .exe, tool ini seharusnya sudah "
                "menyertakan ffmpeg — laporkan ke pembuatnya.\n\n"
                "Kalau kamu jalankan dari source, taruh ffmpeg.exe di folder "
                "'bin' sebelah script.\nUnduh: " + core.FFMPEG_DOWNLOAD)

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}

        # Baris 1: pilih file
        frm_top = ttk.Frame(self.root)
        frm_top.pack(fill="x", **pad)
        ttk.Button(frm_top, text="Pilih File (.m4a)", command=self.pick_files)\
            .pack(side="left")
        ttk.Button(frm_top, text="Hapus Semua", command=self.clear_files)\
            .pack(side="left", padx=6)

        # Daftar file
        frm_list = ttk.Frame(self.root)
        frm_list.pack(fill="both", expand=True, **pad)
        self.listbox = tk.Listbox(frm_list, height=8, selectmode="extended")
        sb = ttk.Scrollbar(frm_list, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Baris: lokasi output
        frm_out = ttk.LabelFrame(self.root, text="Lokasi simpan hasil")
        frm_out.pack(fill="x", **pad)

        self.rb_same = ttk.Radiobutton(
            frm_out, text="Folder yang sama dengan file input (default)",
            variable=self.out_choice, value="same", command=self._toggle_out)
        self.rb_same.pack(anchor="w", padx=8, pady=(6, 2))

        self.rb_custom = ttk.Radiobutton(
            frm_out, text="Pilih folder lain (save as...):",
            variable=self.out_choice, value="custom", command=self._toggle_out)
        self.rb_custom.pack(anchor="w", padx=8)

        frm_custom = ttk.Frame(frm_out)
        frm_custom.pack(fill="x", padx=8, pady=(2, 8))
        self.ent_out = ttk.Entry(frm_custom, textvariable=self.out_dir,
                                 state="disabled")
        self.ent_out.pack(side="left", fill="x", expand=True)
        self.btn_browse = ttk.Button(frm_custom, text="Browse...",
                                     command=self.pick_outdir, state="disabled")
        self.btn_browse.pack(side="left", padx=6)

        # Tombol convert + progress
        frm_go = ttk.Frame(self.root)
        frm_go.pack(fill="x", **pad)
        self.btn_go = ttk.Button(frm_go, text="Convert", command=self.start)
        self.btn_go.pack(side="left")
        self.progress = ttk.Progressbar(frm_go, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=8)

        # Log hasil
        frm_log = ttk.LabelFrame(self.root, text="Hasil")
        frm_log.pack(fill="both", expand=True, **pad)
        self.txt = tk.Text(frm_log, height=10, state="disabled", wrap="word")
        sb2 = ttk.Scrollbar(frm_log, orient="vertical", command=self.txt.yview)
        self.txt.configure(yscrollcommand=sb2.set)
        self.txt.pack(side="left", fill="both", expand=True)
        sb2.pack(side="right", fill="y")

    def _toggle_out(self):
        on = self.out_choice.get() == "custom"
        state = "normal" if on else "disabled"
        self.ent_out.configure(state=state)
        self.btn_browse.configure(state=state)

    # ------------------------------------------------------------- aksi
    def pick_files(self):
        paths = filedialog.askopenfilenames(
            title="Pilih file M4A",
            filetypes=[("File audio M4A", "*.m4a"), ("Semua file", "*.*")])
        for p in paths:
            if p not in self.files:
                self.files.append(p)
                self.listbox.insert("end", p)

    def clear_files(self):
        self.files.clear()
        self.listbox.delete(0, "end")

    def pick_outdir(self):
        d = filedialog.askdirectory(title="Pilih folder tujuan")
        if d:
            self.out_dir.set(d)

    def _log(self, msg):
        self.txt.configure(state="normal")
        self.txt.insert("end", msg + "\n")
        self.txt.see("end")
        self.txt.configure(state="disabled")

    # ------------------------------------------------------- konversi
    def start(self):
        if not self.files:
            messagebox.showinfo("Belum ada file", "Klik 'Pilih File' dulu.")
            return
        ffmpeg = core.find_ffmpeg()
        if not ffmpeg:
            messagebox.showerror(
                "ffmpeg tidak ditemukan",
                "Tidak ketemu ffmpeg.\nBaca README.md cara pasangnya: "
                + core.FFMPEG_DOWNLOAD)
            return
        if self.out_choice.get() == "custom" and not self.out_dir.get().strip():
            messagebox.showwarning("Folder belum dipilih",
                                   "Pilih folder tujuan dulu.")
            return

        out_dir = self.out_dir.get().strip() if self.out_choice.get() == "custom" else None

        self.btn_go.configure(state="disabled")
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.configure(state="disabled")
        self.progress.configure(maximum=len(self.files), value=0)

        t = threading.Thread(target=self._worker, args=(ffmpeg, out_dir), daemon=True)
        t.start()
        self.root.after(100, self._poll)

    def _worker(self, ffmpeg, out_dir):
        total = len(self.files)
        for i, src in enumerate(self.files, 1):
            ok, dst, info, note = core.convert_one(
                src, ffmpeg, res=core.DEFAULT_RES, out_dir=out_dir)
            name = os.path.basename(src)
            if ok:
                self._q.put(("ok", "{} -> {}".format(name, dst) +
                                  "  ({}, audio {})".format(info, note), i))
            else:
                self._q.put(("err", "{} GAGAL: {}".format(name, info), i))
        self._q.put(("done", "Selesai. Total {} file.".format(total), total))

    def _poll(self):
        try:
            while True:
                kind, msg, i = self._q.get_nowait()
                self.progress.configure(value=i)
                if kind == "done":
                    self.btn_go.configure(state="normal")
                self._log(msg)
        except queue.Empty:
            pass
        # terus polling sampai proses selesai
        if self.btn_go["state"] == "disabled":
            self.root.after(100, self._poll)


def main():
    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", 1.3)  # font lebih besar, mudah dibaca
    except Exception:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()