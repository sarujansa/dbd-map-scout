"""Light/dark look for the control window (ttk styles + Windows title bar)."""
from __future__ import annotations

import ctypes
import sys
import tkinter as tk
from tkinter import ttk

IS_WIN = sys.platform == "win32"

LOG_COLORS = {
    True: {"ts": "#6f757d", "Erkennung": "#7cc47f", "Overlay": "#6fa8dc", "System": "#b3b8bf", "Fehler": "#e06c6c",
           "text": "#dfe2e6"},
    False: {"ts": "#8a8f96", "Erkennung": "#1e7b34", "Overlay": "#1f5fa8", "System": "#555b63", "Fehler": "#b3261e",
            "text": "#1b1b1b"},
}
DOT = {"ok": "#3fb950", "warn": "#d29922", "err": "#e5534b", "info": "#58a6ff", "idle": "#8b8f98"}

DARK = {
    "bg": "#1e1f22", "panel": "#2b2d31", "field": "#232428", "border": "#3a3c42",
    "fg": "#e3e5e8", "dim": "#9ba1a9", "accent": "#c9a227", "select": "#7a1f1f",
    "hover": "#383a40", "press": "#43464d",
}


def _titlebar(root: tk.Tk, dark: bool):
    """Dark window title bar (Windows 10 2004+ / Windows 11)."""
    if not IS_WIN:
        return
    try:
        from ctypes import wintypes
        hwnd = int(root.wm_frame(), 16)
        dwm = ctypes.WinDLL("dwmapi")
        dwm.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        value = ctypes.c_int(1 if dark else 0)
        for attr in (20, 19):          # DWMWA_USE_IMMERSIVE_DARK_MODE (new / pre-20H1)
            if dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
        u = ctypes.WinDLL("user32")
        u.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, wintypes.UINT]
        u.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x1 | 0x2 | 0x4 | 0x10 | 0x20)   # redraw the frame
    except Exception:
        pass


def apply(root: tk.Tk, dark: bool, text_widgets=()):
    style = ttk.Style(root)
    if not dark:
        style.theme_use("vista" if "vista" in style.theme_names() else "default")
        style.configure("Big.TLabel", font=("Segoe UI", 13, "bold"))
        style.configure("Dim.TLabel", foreground="#666666")
        bg = style.lookup("TFrame", "background") or root.cget("background")
        root.configure(background=bg)
        for key, col in DOT.items():
            style.configure(f"Dot{key.title()}.TLabel", foreground=col)
        for t in text_widgets:
            t.configure(background="white", foreground="black", insertbackground="black")
        _titlebar(root, False)
        return

    c = DARK
    style.theme_use("clam")
    root.configure(background=c["bg"])
    style.configure(".", background=c["bg"], foreground=c["fg"], fieldbackground=c["field"],
                    bordercolor=c["border"], darkcolor=c["bg"], lightcolor=c["bg"], troughcolor=c["panel"],
                    focuscolor=c["accent"], selectbackground=c["select"], selectforeground="#ffffff",
                    insertcolor=c["fg"], arrowcolor=c["fg"])
    style.configure("TFrame", background=c["bg"])
    style.configure("TLabel", background=c["bg"], foreground=c["fg"])
    style.configure("Big.TLabel", background=c["bg"], foreground="#ffffff", font=("Segoe UI", 13, "bold"))
    style.configure("Dim.TLabel", background=c["bg"], foreground=c["dim"])
    style.configure("TLabelframe", background=c["bg"], bordercolor=c["border"], lightcolor=c["bg"], darkcolor=c["bg"])
    style.configure("TLabelframe.Label", background=c["bg"], foreground=c["accent"])
    style.configure("TButton", background=c["panel"], foreground=c["fg"], bordercolor=c["border"],
                    lightcolor=c["panel"], darkcolor=c["panel"], padding=(8, 3))
    style.map("TButton", background=[("pressed", c["press"]), ("active", c["hover"])],
              bordercolor=[("focus", c["accent"])])
    style.configure("TCheckbutton", background=c["bg"], foreground=c["fg"], indicatorbackground=c["field"],
                    indicatorforeground=c["accent"], upperbordercolor=c["border"], lowerbordercolor=c["border"])
    style.map("TCheckbutton", background=[("active", c["bg"])],
              indicatorbackground=[("selected", c["field"]), ("active", c["hover"])],
              indicatorforeground=[("selected", c["accent"])])
    style.configure("TEntry", fieldbackground=c["field"], foreground=c["fg"], insertcolor=c["fg"],
                    bordercolor=c["border"], lightcolor=c["field"], darkcolor=c["field"])
    style.map("TEntry", bordercolor=[("focus", c["accent"])])
    style.configure("TCombobox", fieldbackground=c["field"], background=c["panel"], foreground=c["fg"],
                    arrowcolor=c["fg"], bordercolor=c["border"], lightcolor=c["field"], darkcolor=c["field"])
    style.map("TCombobox", fieldbackground=[("readonly", c["field"])], foreground=[("readonly", c["fg"])],
              selectbackground=[("readonly", c["field"])], selectforeground=[("readonly", c["fg"])],
              background=[("active", c["hover"])])
    root.option_add("*TCombobox*Listbox.background", c["field"])
    root.option_add("*TCombobox*Listbox.foreground", c["fg"])
    root.option_add("*TCombobox*Listbox.selectBackground", c["select"])
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
    style.configure("Treeview", background=c["field"], fieldbackground=c["field"], foreground=c["fg"],
                    bordercolor=c["border"], lightcolor=c["field"], darkcolor=c["field"])
    style.map("Treeview", background=[("selected", c["select"])], foreground=[("selected", "#ffffff")])
    style.configure("Vertical.TScrollbar", background=c["panel"], troughcolor=c["bg"], arrowcolor=c["fg"],
                    bordercolor=c["bg"], lightcolor=c["panel"], darkcolor=c["panel"])
    style.map("Vertical.TScrollbar", background=[("active", c["hover"])])
    style.configure("Horizontal.TScale", background=c["panel"], troughcolor=c["field"], bordercolor=c["border"],
                    lightcolor=c["panel"], darkcolor=c["panel"])
    style.map("Horizontal.TScale", background=[("active", c["accent"])])
    style.configure("TNotebook", background=c["bg"], bordercolor=c["border"], tabmargins=(4, 6, 4, 0),
                    lightcolor=c["bg"], darkcolor=c["bg"])
    style.configure("TNotebook.Tab", background=c["panel"], foreground=c["dim"], padding=(9, 5),
                    bordercolor=c["border"], lightcolor=c["panel"], darkcolor=c["panel"])
    style.map("TNotebook.Tab", background=[("selected", c["bg"]), ("active", c["hover"])],
              foreground=[("selected", c["accent"]), ("active", c["fg"])],
              expand=[("selected", (1, 1, 1, 0))])
    for key, col in DOT.items():
        style.configure(f"Dot{key.title()}.TLabel", background=c["bg"], foreground=col)
    for t in text_widgets:
        t.configure(background=c["field"], foreground=c["fg"], insertbackground=c["fg"])
    _titlebar(root, True)
