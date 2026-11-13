#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke test GUI — instansiasi app, coba semua mode, lalu destroy.

Dipanggil CI di mesin Windows (di mana tkinter tersedia) untuk memastikan
GUI benar-benar bisa dibuka tanpa error sebelum di-bundle jadi .exe.

Yang diuji:
  1. App bisa dibuat & tampil (mainloop jalan sebentar).
  2. Pindah mode Konversi <-> Gabung Audio tidak error dan widget opsi
     gabung muncul/hilang sebagaimana mestinya.
  3. Tombol aksi ikut berganti label sesuai mode.
"""

import m4a2yt_gui as g


def main():
    app = g.M4a2YtApp()

    def _cek_mode():
        assert app.btn_go.cget("text") == "Convert", "label awal harus Convert"

        app._on_mode(g.MODE_STITCH)
        assert app.frame_stitch.winfo_manager() == "grid", \
            "opsi gabung harus tampil di mode Gabung Audio"
        assert app.btn_go.cget("text") == "Gabung Jadi Satu", \
            "tombol harus berubah jadi Gabung Jadi Satu"

        app._on_mode(g.MODE_CONVERT)
        assert app.frame_stitch.winfo_manager() == "", \
            "opsi gabung harus disembunyikan di mode Konversi"
        assert app.btn_go.cget("text") == "Convert", "tombol harus balik Convert"

        app.destroy()

    app.after(300, _cek_mode)
    app.mainloop()
    print("GUI_SMOKE_OK")


if __name__ == "__main__":
    main()
