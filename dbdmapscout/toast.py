"""Own small notification window bottom right ("Lobby gefunden").

Windows notifications from the tray icon are swallowed by "Do not disturb", which Windows 11 switches
on by itself while a game or a full-screen app runs. This window does not depend on that: always on
top, never takes the focus (WS_EX_NOACTIVATE), gone after a few seconds or on a click.
"""
from __future__ import annotations

import tkinter as tk

from .overlay import GWL_EXSTYLE, IS_WIN, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW, WS_EX_TOPMOST

BG, FG, DIM, ACCENT = "#1e1f22", "#f2f2f2", "#b5bac1", "#c8102e"


def work_area(root):
    """(left, top, right, bottom) of the primary screen without the taskbar."""
    if IS_WIN:
        try:
            import ctypes
            from ctypes import wintypes
            r = wintypes.RECT()
            if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0):   # SPI_GETWORKAREA
                return r.left, r.top, r.right, r.bottom
        except Exception:
            pass
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


class Toast:
    def __init__(self, root):
        self.root = root
        self.win = None
        self._job = None

    @property
    def shown(self) -> bool:
        return self.win is not None

    def show(self, title: str, text: str, seconds: float = 8.0):
        self.close()
        w = self.win = tk.Toplevel(self.root)
        w.withdraw()
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.configure(bg=ACCENT)                               # 3 px red frame on the left and around
        body = tk.Frame(w, bg=BG, padx=14, pady=10)
        body.pack(fill="both", expand=True, padx=(4, 1), pady=1)
        tk.Label(body, text=title, bg=BG, fg=FG, font=("Segoe UI", 12, "bold"), anchor="w").pack(fill="x")
        tk.Label(body, text=text, bg=BG, fg=DIM, font=("Segoe UI", 10), anchor="w", justify="left",
                 wraplength=320).pack(fill="x", pady=(2, 0))
        for widget in (w, body, *body.winfo_children()):
            widget.bind("<Button-1>", lambda e: self.close())
        w.update_idletasks()
        left, top, right, bottom = work_area(self.root)
        width, height = max(300, w.winfo_reqwidth()), w.winfo_reqheight()
        w.geometry(f"{width}x{height}+{right - width - 16}+{bottom - height - 16}")
        self._no_activate(w)
        w.deiconify()
        self._no_activate(w)
        self._job = self.root.after(int(seconds * 1000), self.close)

    def _no_activate(self, w):
        if not IS_WIN:
            return
        try:
            from .overlay import (HWND_TOPMOST, SWP_NOACTIVATE, SWP_NOMOVE, SWP_NOSIZE, _GetLong, _SetLong,
                                  _user32)
            w.update_idletasks()
            h = int(_user32.GetParent(w.winfo_id()) or 0) or w.winfo_id()
            _SetLong(h, GWL_EXSTYLE, _GetLong(h, GWL_EXSTYLE) | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST)
            _user32.SetWindowPos(h, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        except Exception:
            pass

    def close(self):
        if self._job is not None:
            try:
                self.root.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None
        if self.win is not None:
            try:
                self.win.destroy()
            except tk.TclError:
                pass
            self.win = None
