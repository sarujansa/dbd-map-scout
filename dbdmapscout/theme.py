"""Light/dark look for the control window (ttk styles + Windows title bar).

Three designs (setting ``ui_style``, user's wish 1.50): "classic" = the own clam styles below, "fluent" = Windows 11
look of the Sun Valley theme (rdbende, MIT, vendored in ``sv_ttk/``), "fluent_gold" = the same with the gold accent of
the classic design (sprites recoloured at load time, nothing extra on disk).
"""
from __future__ import annotations

import base64
import ctypes
import io
import os
import sys
import tkinter as tk
from tkinter import ttk

from .i18n import N_

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


STYLES = (("fluent_gold", N_("Windows 11, Gold")), ("fluent", N_("Windows 11, Blau")), ("classic", N_("Klassisch")))
DEFAULT_STYLE = "fluent_gold"
SV_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sv_ttk")
GOLD_HUE = 31                  # PIL HSV hue (0..255) of the gold accent, ~#d6ab31
# colours the Sun Valley files hard-code next to their palette; replaced for the gold accent
SV_GOLD = {
    "dark": {'-selbg   "#2f60d8"': '-selbg   "#7a5c12"', '-accent  "#57c8ff"': '-accent  "#d6ab31"',
             '"#25536a"': '"#5a4410"'},
    "light": {'-selbg   "#2f60d8"': '-selbg   "#8a6a12"', '-accent  "#005fb8"': '-accent  "#8a6a12"',
              '"#c1d8ee"': '"#f0e2b8"'},
}
SV_BG = {"dark": "#1c1c1c", "light": "#fafafa"}
SV_DIM = {"dark": "#a0a0a0", "light": "#5f5f5f"}
SV_FIELD = {"dark": "#2b2b2b", "light": "#ffffff"}


def gold_sheet(png: bytes, light: bool) -> bytes:
    """The Sun Valley sprite sheet with its blue accent turned gold (saturated blue pixels only, alpha kept)."""
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGBA")
    alpha = im.getchannel("A")
    h, s, v = im.convert("RGB").convert("HSV").split()
    blue = h.point(lambda x: 255 if 128 <= x <= 179 else 0)
    sat = s.point(lambda x: 255 if x > 64 else 0)
    mask = Image.composite(blue, Image.new("L", im.size, 0), sat)
    h = Image.composite(Image.new("L", im.size, GOLD_HUE), h, mask)
    v = Image.composite(v.point(lambda x: round(x * (0.8 if light else 0.92))), v, mask)
    out = Image.merge("HSV", (h, s, v)).convert("RGB")
    out.putalpha(alpha)
    buf = io.BytesIO()
    out.save(buf, "PNG")
    return buf.getvalue()


def sv_source(mode: str, gold: bool) -> tuple[str, str]:
    """Tcl source of one Sun Valley theme under an own name, loading its sprites from ``$::dbdms_sheet``
    (the files read them next to ``[info script]``, which does not exist when evaluated from a string)."""
    name = f"dbdms-{'gold' if gold else 'blue'}-{mode}"
    ns = name.replace("-", "_")
    with open(os.path.join(SV_DIR, f"{mode}.tcl"), encoding="utf-8") as f:
        src = f.read()
    sprites = os.path.join(SV_DIR, f"sprites_{mode}.tcl").replace("\\", "/")
    reps = {
        f"source [file join [file dirname [info script]] sprites_{mode}.tcl]": f"source {{{sprites}}}",
        f"package provide ttk::theme::sv_{mode} 2.5": "",
        f"ttk::theme::sv_{mode}": f"ttk::theme::{ns}",
        f"sun-valley-{mode}": name,
        "image create photo spritesheet -file $imgfile -format png":
            f"image create photo {ns}_sheet -data $::dbdms_sheet -format png",
        "copy spritesheet": f"copy {ns}_sheet",
        f"load_images [file join [file dirname [info script]] spritesheet_{mode}.png]": "load_images {}",
    }
    if gold:
        reps.update(SV_GOLD[mode])
    for old, new in reps.items():
        if old not in src:
            raise ValueError(f"sun valley {mode}.tcl: {old!r} missing")
        src = src.replace(old, new)
    return name, src


def _sv_theme(root: tk.Tk, dark: bool, gold: bool) -> str:
    """Create the Sun Valley theme once per Tk interpreter, return its name."""
    mode = "dark" if dark else "light"
    name, src = sv_source(mode, gold)
    if name in ttk.Style(root).theme_names():
        return name
    for font, base in (("SunValleyBodyFont", "TkDefaultFont"), ("SunValleyCaptionFont", "TkHeadingFont")):
        if font not in root.tk.splitlist(root.tk.call("font", "names")):
            root.tk.call("font", "create", font, *root.tk.splitlist(root.tk.call("font", "actual", base)))
    with open(os.path.join(SV_DIR, f"spritesheet_{mode}.png"), "rb") as f:
        png = f.read()
    if gold:
        png = gold_sheet(png, light=not dark)
    root.tk.call("set", "::dbdms_sheet", base64.b64encode(png).decode("ascii"))
    root.tk.eval(src)
    return name


def _fluent(root: tk.Tk, dark: bool, gold: bool, text_widgets) -> str:
    mode = "dark" if dark else "light"
    style = ttk.Style(root)
    style.theme_use(_sv_theme(root, dark, gold))
    bg, fg, dim, field = SV_BG[mode], "#fafafa" if dark else "#1c1c1c", SV_DIM[mode], SV_FIELD[mode]
    accent = ("#d6ab31" if dark else "#8a6a12") if gold else ("#57c8ff" if dark else "#005fb8")
    select = ("#7a5c12" if dark else "#8a6a12") if gold else "#2f60d8"
    root.configure(background=bg)
    style.configure(".", background=bg, foreground=fg, troughcolor=bg, selectbackground=select,
                    selectforeground="#ffffff", insertcolor=fg, fieldbackground=bg)
    style.map(".", foreground=[("disabled", "#595959" if dark else "#a0a0a0")])
    style.configure("Big.TLabel", foreground="#ffffff" if dark else "#000000", font=("Segoe UI", 13, "bold"))
    style.configure("Dim.TLabel", foreground=dim)
    style.configure("TLabelframe.Label", foreground=accent)
    style.configure("TNotebook.Tab", foreground=dim)
    style.map("TNotebook.Tab", foreground=[("selected", fg), ("active", fg)])
    for key, col in DOT.items():
        style.configure(f"Dot{key.title()}.TLabel", foreground=col)
    root.option_add("*TCombobox*Listbox.background", field)
    root.option_add("*TCombobox*Listbox.foreground", fg)
    root.option_add("*TCombobox*Listbox.selectBackground", select)
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
    for t in text_widgets:
        t.configure(background=field, foreground=fg, insertbackground=fg)
    _titlebar(root, dark)
    return bg


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


def apply(root: tk.Tk, dark: bool, text_widgets=(), design: str = "classic") -> str:
    """Apply the look; returns the page background (scrolled tab canvases, charts). A design that cannot be
    loaded (Tcl error, files missing) falls back to the classic one."""
    if design in ("fluent", "fluent_gold"):
        try:
            return _fluent(root, dark, design == "fluent_gold", text_widgets)
        except (tk.TclError, OSError, ValueError) as e:
            apply.failed = f"{design}: {e}"
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
        return bg

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
    return c["bg"]


apply.failed = ""
