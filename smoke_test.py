#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke test GUI — instansiasi app, jalan 1.5 detik, destroy.

Dipanggil CI di mesin Windows (di mana tkinter tersedia) untuk memastikan
GUI benar-benar bisa dibuka tanpa error sebelum di-bundle jadi .exe.
"""

import m4a2yt_gui as g


def main():
    app = g.M4a2YtApp()
    app.after(1500, app.destroy)
    app.mainloop()
    print("GUI_SMOKE_OK")


if __name__ == "__main__":
    main()