#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m4a2yt GUI (CustomTkinter dark mode) — bungkus M4A jadi MP4 untuk YouTube.

Alur pakai:
  1. Klik "+  Tambah File" -> pilih satu/lebih file .m4a
  2. Pilih lokasi simpan (default: folder yang sama dengan input)
  3. Klik "Convert" -> hasil .mp4 muncul di folder tujuan

Butuh:  customtkinter  (pip install customtkinter)
"""

import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk

import core

ACCENT = "#2ea043"        # hijau tombol convert
ACCENT_HOVER = "#3fb950"
DANGER = "#f85149"


class M4a2YtApp(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        super().__init__()

        self.title("m4a2yt — M4A ke YouTube")
        self.geometry("760x640")
        self.minsize(640, 560)

        self.files = []          # list path (string)
        self.out_choice = tk.StringVar(value="same")
        self.out_dir = tk.StringVar(value="")
        self._q = queue.Queue()
        self._running = False

        self._build_ui()
        self._check_ffmpeg()

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)   # baris file list membesar

        # --- Header ---
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 8))
        title = ctk.CTkLabel(
            header, text="m4a2yt",
            font=ctk.CTkFont(size=28, weight="bold"))
        title.pack(anchor="w")
        sub = ctk.CTkLabel(
            header, text="Rekaman M4A  →  Video MP4 siap upload YouTube",
            font=ctk.CTkFont(size=13), text_color="#8b949e")
        sub.pack(anchor="w", pady=(2, 0))

        # --- File list ---
        frame_files = ctk.CTkFrame(self, corner_radius=12)
        frame_files.grid(row=3, column=0, sticky="nsew", padx=24, pady=8)
        frame_files.grid_columnconfigure(0, weight=1)
        frame_files.grid_rowconfigure(1, weight=1)

        top_files = ctk.CTkFrame(frame_files, fg_color="transparent")
        top_files.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        lbl_files = ctk.CTkLabel(
            top_files, text="File Audio (.m4a)",
            font=ctk.CTkFont(size=14, weight="bold"))
        lbl_files.pack(side="left")
        self.btn_add = ctk.CTkButton(
            top_files, text="+  Tambah File", width=140, height=30,
            command=self.pick_files)
        self.btn_add.pack(side="right")

        self.scroll = ctk.CTkScrollableFrame(frame_files, corner_radius=8,
                                             fg_color="#11151c")
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=12, pady=8)
        self.scroll.grid_columnconfigure(0, weight=1)

        self.lbl_empty = ctk.CTkLabel(
            self.scroll, text="Belum ada file.\nKlik \u201c+ Tambah File\u201d "
                               "untuk memilih rekaman.",
            font=ctk.CTkFont(size=13), text_color="#6e7681",
            justify="center", anchor="center")
        self.lbl_empty.grid(row=0, column=0, sticky="ew", pady=36)

        # --- Lokasi simpan ---
        frame_out = ctk.CTkFrame(self, corner_radius=12)
        frame_out.grid(row=4, column=0, sticky="ew", padx=24, pady=8)
        lbl_out = ctk.CTkLabel(
            frame_out, text="Lokasi Simpan",
            font=ctk.CTkFont(size=14, weight="bold"))
        lbl_out.grid(row=0, column=0, columnspan=3, sticky="w",
                     padx=12, pady=(10, 2))

        self.rb_same = ctk.CTkRadioButton(
            frame_out, text="Folder yang sama dengan file input (default)",
            variable=self.out_choice, value="same", command=self._toggle_out)
        self.rb_same.grid(row=1, column=0, columnspan=3, sticky="w",
                          padx=12, pady=(2, 2))

        self.rb_custom = ctk.CTkRadioButton(
            frame_out, text="Folder lain:", variable=self.out_choice,
            value="custom", command=self._toggle_out)
        self.rb_custom.grid(row=2, column=0, sticky="w", padx=12, pady=(2, 6))

        self.ent_out = ctk.CTkEntry(
            frame_out, textvariable=self.out_dir, state="disabled",
            placeholder_text="Pilih folder tujuan...")
        self.ent_out.grid(row=2, column=1, sticky="ew", padx=(2, 8), pady=(2, 6))
        frame_out.grid_columnconfigure(1, weight=1)
        self.btn_browse = ctk.CTkButton(
            frame_out, text="Browse", width=90, height=30,
            command=self.pick_outdir, state="disabled")
        self.btn_browse.grid(row=2, column=2, sticky="e", padx=(0, 12), pady=(2, 6))

        # --- Convert + progress ---
        self.btn_go = ctk.CTkButton(
            self, text="Convert", height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self.start)
        self.btn_go.grid(row=5, column=0, sticky="ew", padx=24, pady=(6, 4))

        self.progress = ctk.CTkProgressBar(self, mode="determinate", height=8)
        self.progress.grid(row=6, column=0, sticky="ew", padx=24, pady=(2, 4))
        self.progress.set(0)

        # --- Log ---
        self.txt = ctk.CTkTextbox(self, height=120, corner_radius=12,
                                  wrap="word", fg_color="#11151c",
                                  border_width=1, border_color="#21262d")
        self.txt.grid(row=7, column=0, sticky="ew", padx=24, pady=(4, 20))
        self.txt.configure(state="disabled")

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
        self._render_files()

    def _render_files(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        if not self.files:
            self.lbl_empty = ctk.CTkLabel(
                self.scroll, text="Belum ada file.\nKlik \u201c+ Tambah File\u201d "
                                   "untuk memilih rekaman.",
                font=ctk.CTkFont(size=13), text_color="#6e7681",
                justify="center", anchor="center")
            self.lbl_empty.grid(row=0, column=0, sticky="ew", pady=36)
            return

        for i, p in enumerate(self.files):
            row = ctk.CTkFrame(self.scroll, corner_radius=8,
                               fg_color="#1b2029")
            row.grid(row=i, column=0, sticky="ew", pady=3)
            row.grid_columnconfigure(0, weight=1)

            name = os.path.basename(p)
            d = os.path.dirname(p)
            txt = ctk.CTkLabel(
                row, text=name, font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w", justify="left")
            txt.grid(row=0, column=0, sticky="w", padx=(12, 8), pady=(8, 0))
            sub = ctk.CTkLabel(
                row, text=d, font=ctk.CTkFont(size=11),
                text_color="#6e7681", anchor="w", justify="left")
            sub.grid(row=1, column=0, sticky="w", padx=(12, 8), pady=(0, 8))

            remove = ctk.CTkButton(
                row, text="✕", width=30, height=30, fg_color="transparent",
                hover_color="#2d333e", text_color=DANGER,
                command=lambda path=p: self._remove_file(path))
            remove.grid(row=0, column=1, rowspan=2, padx=(0, 8), pady=8)

    def _remove_file(self, path):
        if path in self.files:
            self.files.remove(path)
        self._render_files()

    def clear_files(self):
        self.files.clear()
        self._render_files()

    def pick_outdir(self):
        d = filedialog.askdirectory(title="Pilih folder tujuan")
        if d:
            self.out_dir.set(d)

    def _log(self, msg, color=None):
        self.txt.configure(state="normal")
        tag = color if color else "default"
        self.txt.tag_config("ok", foreground=ACCENT)
        self.txt.tag_config("err", foreground=DANGER)
        self.txt.tag_config("default", foreground="#c9d1d9")
        self.txt.insert("end", msg + "\n", tag)
        self.txt.see("end")
        self.txt.configure(state="disabled")

    def _check_ffmpeg(self):
        if not core.find_ffmpeg():
            self._log("⚠ ffmpeg tidak ditemukan. " + core.FFMPEG_DOWNLOAD, "err")

    # ------------------------------------------------------- konversi
    def start(self):
        if self._running:
            return
        if not self.files:
            self._log("Belum ada file. Klik \u201c+ Tambah File\u201d dulu.", "err")
            return
        ffmpeg = core.find_ffmpeg()
        if not ffmpeg:
            self._log("ffmpeg tidak ditemukan — baca README.md.", "err")
            return
        if self.out_choice.get() == "custom" and not self.out_dir.get().strip():
            self._log("Pilih folder tujuan dulu.", "err")
            return

        out_dir = (self.out_dir.get().strip()
                   if self.out_choice.get() == "custom" else None)

        self._running = True
        self.btn_go.configure(state="disabled", text="Memproses...")
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.configure(state="disabled")
        self.progress.set(0)

        t = threading.Thread(target=self._worker, args=(ffmpeg, out_dir),
                             daemon=True)
        t.start()
        self.after(100, self._poll)

    def _worker(self, ffmpeg, out_dir):
        total = len(self.files)
        ok_count = 0
        for i, src in enumerate(self.files, 1):
            ok, dst, info, note = core.convert_one(
                src, ffmpeg, res=core.DEFAULT_RES, out_dir=out_dir)
            name = os.path.basename(src)
            if ok:
                ok_count += 1
                self._q.put(("ok", "[✓] {} → {}\n       ({}, audio {})\n"
                             .format(name, os.path.basename(dst), info, note), i))
            else:
                self._q.put(("err", "[✗] {} GAGAL — {}\n".format(name, info), i))
        self._q.put(("done", ok_count, total))

    def _poll(self):
        try:
            while True:
                kind, payload, i = self._q.get_nowait()
                if kind in ("ok", "err"):
                    self.progress.set(i / len(self.files))
                if kind == "ok":
                    self._log(payload, "ok")
                elif kind == "err":
                    self._log(payload, "err")
                elif kind == "done":
                    total = i
                    ok = payload
                    self.progress.set(1.0)
                    self._running = False
                    self.btn_go.configure(state="normal", text="Convert")
                    self._log("Selesai: {} dari {} file berhasil.".format(ok, total),
                              "ok" if ok else "err")
                    return
        except queue.Empty:
            pass
        self.after(100, self._poll)


def main():
    app = M4a2YtApp()
    app.mainloop()


if __name__ == "__main__":
    main()