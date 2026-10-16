"""Native Windows overlay: a layered, click-through, always-on-top popup window.

The picture is pushed with UpdateLayeredWindow (per-pixel alpha), so the
transparent parts of a map really are transparent; Qt's window handling is not involved.
The window never takes the keyboard focus
(WS_EX_NOACTIVATE, shown with SW_SHOWNOACTIVATE) and lets every click through
to the game (WS_EX_TRANSPARENT) – except in edit mode, where it can be dragged.
"""
from __future__ import annotations

import ctypes
import re
import sys
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .capture import is_above
from .mapimage import FONT as FIRA, floor_frames, floor_view
from .overlay import BACKDROP, MAX_LOAD_H, load_frames

IS_WIN = sys.platform == "win32"

WS_POPUP = 0x80000000
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
GWL_EXSTYLE = -20
GWLP_WNDPROC = -4
SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE, SWP_FRAMECHANGED = 0x1, 0x2, 0x10, 0x20
ULW_ALPHA = 2
WM_NCHITTEST = 0x0084
WM_MOUSEWHEEL = 0x020A
WM_EXITSIZEMOVE = 0x0232
HTCAPTION = 2
BORDER = (224, 176, 0, 255)

if IS_WIN:
    from ctypes import wintypes

    _u = ctypes.WinDLL("user32", use_last_error=True)
    _g = ctypes.WinDLL("gdi32", use_last_error=True)
    _k = ctypes.WinDLL("kernel32", use_last_error=True)
    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD)]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]

    class BLENDFUNCTION(ctypes.Structure):
        _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                    ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]

    _k.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    _k.GetModuleHandleW.restype = wintypes.HMODULE
    _u.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
    _u.CreateWindowExW.restype = wintypes.HWND
    _u.DestroyWindow.argtypes = [wintypes.HWND]
    _u.DestroyWindow.restype = wintypes.BOOL
    _u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    _u.ShowWindow.restype = wintypes.BOOL
    _u.IsWindowVisible.argtypes = [wintypes.HWND]
    _u.IsWindowVisible.restype = wintypes.BOOL
    _u.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, wintypes.UINT]
    _u.SetWindowPos.restype = wintypes.BOOL
    _u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    _u.GetWindowRect.restype = wintypes.BOOL
    _u.UpdateLayeredWindow.argtypes = [wintypes.HWND, wintypes.HDC, ctypes.POINTER(wintypes.POINT),
                                       ctypes.POINTER(wintypes.SIZE), wintypes.HDC, ctypes.POINTER(wintypes.POINT),
                                       wintypes.DWORD, ctypes.POINTER(BLENDFUNCTION), wintypes.DWORD]
    _u.UpdateLayeredWindow.restype = wintypes.BOOL
    _u.GetDC.argtypes = [wintypes.HWND]
    _u.GetDC.restype = wintypes.HDC
    _u.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    _u.ReleaseDC.restype = ctypes.c_int
    _u.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    _u.CallWindowProcW.restype = LRESULT
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        _GetLong, _SetLong = _u.GetWindowLongPtrW, _u.SetWindowLongPtrW
    else:  # pragma: no cover
        _GetLong, _SetLong = _u.GetWindowLongW, _u.SetWindowLongW
    _GetLong.argtypes = [wintypes.HWND, ctypes.c_int]
    _GetLong.restype = ctypes.c_ssize_t
    _SetLong.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    _SetLong.restype = ctypes.c_ssize_t
    _g.CreateCompatibleDC.argtypes = [wintypes.HDC]
    _g.CreateCompatibleDC.restype = wintypes.HDC
    _g.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.POINTER(BITMAPINFO), wintypes.UINT,
                                    ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD]
    _g.CreateDIBSection.restype = wintypes.HBITMAP
    _g.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    _g.SelectObject.restype = wintypes.HGDIOBJ
    _g.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    _g.DeleteObject.restype = wintypes.BOOL
    _g.DeleteDC.argtypes = [wintypes.HDC]
    _g.DeleteDC.restype = wintypes.BOOL
    HWND_TOPMOST = wintypes.HWND(-1)
    HWND_NOTOPMOST = wintypes.HWND(-2)


def _font(size: int, heavy: bool = False):
    names = ("seguibl.ttf",) if heavy else ()             # Segoe UI Black: as heavy as the map titles
    for name in names + ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def compose(img: Image.Image, height: int, caption: str, transparent: bool, border: bool,
            text_h: int = 0, split: int | None = None) -> Image.Image:
    """Scaled map + optional caption bar (+ edit border) as one RGBA picture; ``text_h``: height the
    caption is sized for (stacked floors: one floor), 0 = ``height``. ``split``: first row of the map below the
    name drawn into the picture (mapimage.title_split) – the name is then scaled by ``text_h`` like the lines
    below the map, the map alone by ``height`` (1.65.4, user: the map's size freely, the name stays)."""
    if split and text_h and text_h != height and 0 < split < img.height:
        title = img.crop((0, 0, img.width, split))
        body = img.crop((0, split, img.width, img.height))
        tb = title.getchannel("A").getbbox()        # 1.2.7: the name itself, not the empty strip beside it – the
        if tb:                                      # whole strip made the overlay as wide as the name's size, and
            title = title.crop((tb[0], 0, tb[2], split))     # the lines below were shrunk for nothing
        th = max(1, round(split * text_h / img.height))
        bh = max(1, round(body.height * height / img.height))
        title = title.resize((max(1, round(title.width * text_h / img.height)), th), Image.LANCZOS)
        body = body.resize((max(1, round(img.width * height / img.height)), bh), Image.LANCZOS)
        w = max(title.width, body.width)
        pic = Image.new("RGBA", (w, th + bh), (0, 0, 0, 0))
        pic.alpha_composite(title, ((w - title.width) // 2, 0))
        pic.alpha_composite(body, ((w - body.width) // 2, th))
        height = pic.height
    else:
        w = max(1, round(img.width * height / img.height))
        pic = img.resize((w, height), Image.LANCZOS)
    if not transparent:
        bg = Image.new("RGBA", pic.size, BACKDROP + (255,))
        bg.alpha_composite(pic)
        pic = bg
    if caption:
        size = max(12, (text_h or height) // 34)
        font = _font(size)
        x0, y0, x1, y1 = ImageDraw.Draw(pic).textbbox((0, 0), caption, font=font)
        cap_h = (y1 - y0) + size // 2 + 4
        cap_w = min(w, (x1 - x0) + size + 4)
        canvas = Image.new("RGBA", (w, height + cap_h), (0, 0, 0, 0))
        d = ImageDraw.Draw(canvas)
        d.rectangle([0, 0, cap_w - 1, cap_h - 1], fill=(20, 20, 22, 235))
        d.text((size // 2 + 2 - x0, (cap_h - (y1 - y0)) // 2 - y0), caption, font=font, fill=(242, 242, 242, 255))
        canvas.alpha_composite(pic, (0, cap_h))
        pic = canvas
    if border:
        add_border(pic)
    return pic


def add_border(pic: Image.Image, label: str = "") -> Image.Image:
    """The yellow frame of the edit mode; ``label`` (1.64.7, user: "keinen Plan, was ich verschiebe") names the
    element on a tag inside the frame's top left – size and place stay exactly the same (no jump after "Fertig")."""
    d = ImageDraw.Draw(pic)
    d.rectangle([0, 0, pic.width - 1, pic.height - 1], outline=BORDER, width=3)
    if label:
        size = 15
        try:
            font = ImageFont.truetype(FIRA, size)
        except OSError:
            font = _font(size)
        tw = min(pic.width, int(d.textlength(label, font=font)) + 12)
        asc, desc = font.getmetrics()
        th = min(pic.height, asc + desc + 6)
        d.rectangle([0, 0, tw - 1, th - 1], fill=BORDER)
        d.text((6, 3), label, font=font, fill=(20, 16, 4, 255))
    return pic


INFO_TIMER = (255, 255, 255, 255)
TIMER_GAP = 2.5                    # the gap below the timer, in row gaps (1.2.7, user: too close)
DIM_LABEL = (150, 156, 170, 255)   # = sysinfo.DIM: a row starting with it is "label: values" (column, 1.64.7)
TITLE_SCALE = 1.15                 # the music card's title, a bit larger than the artist below it
INFO_SERVER = (178, 184, 248, 255)     # light tone of the map colour
INFO_DOT = (74, 222, 128, 255)         # "connected"
INFO_WARN = (251, 191, 36, 255)        # doubtful detection
PING_GOOD, PING_OK = 60, 120           # ms: green up to here, amber up to here, red above
PING_COLOURS = ((134, 239, 172, 255), (251, 191, 36, 255), (248, 113, 113, 255))


def ping_colour(ms: float):
    return PING_COLOURS[0] if ms <= PING_GOOD else PING_COLOURS[1] if ms <= PING_OK else PING_COLOURS[2]


def _content_bottom(pic: Image.Image) -> int:
    """Last row with visible map pixels (map pictures often have an empty transparent margin below)."""
    a = np.asarray(pic.getchannel("A"))
    rows = np.flatnonzero((a > 24).any(axis=1))
    return int(rows[-1]) + 1 if rows.size else pic.height


def _tracked_width(d, text, font, track):
    return sum(d.textlength(c, font=font) for c in text) + track * max(0, len(text) - 1)


def add_info(pic: Image.Image, timer: str, server: str, height: int, backdrop: bool = False,
             ping: float | None = None, status=(), note: str = "", record: str = "",
             beside: bool = False) -> Image.Image:
    """Round timer, connected server and its ping below the map, styled like the map title: white heavy
    digits with a soft shadow (no box); below them a green "connected" dot with the region in small
    caps, and the ping coloured by quality. The ping is only shown together with a server.
    ``status``: lines of the waiting card (no map on screen) – first one white, the others dimmer.
    ``note``: a warning in amber right below the timer (doubtful detection).
    ``record``: own results on this map (stats page), dimmer, below the timer/note.
    ``backdrop``: the map sits on a dark rectangle (transparent edge off) – extend it behind the info.
    ``beside``: the block goes right of the map, centred in height (low wide bar above/below the picture)."""
    if not server:
        ping = None
    if not timer and not server and not status and not note and not record:
        return pic
    d0 = ImageDraw.Draw(pic)
    tfont, sfont = _font(max(22, height // 11), heavy=True), _font(max(14, height // 24))
    track = max(1, height // 220)
    dot = max(7, height // 44)
    gap = max(4, height // 64)
    # rows: (kind, [(text, colour), ...] segments, font); small rows are tracked caps
    rows = []
    if timer:
        rows.append(("timer", [(timer, INFO_TIMER)], tfont))
    if note:
        rows.append(("note", [(note.upper(), INFO_WARN)], sfont))
    if record:
        rows.append(("record", [(record.upper(), INFO_SERVER)], sfont))
    for i, line in enumerate(status):          # waiting card: above the server, like the timer on the map
        rows.append(("status", [(line.upper(), INFO_TIMER if i == 0 else INFO_SERVER)], sfont))
    if server:
        rows.append(("server", [(server.upper(), INFO_SERVER)], sfont))
    if ping is not None:
        rows.append(("ping", [("PING ", INFO_SERVER), (f"{ping:.0f} MS", ping_colour(ping))], sfont))
    boxes, widths = [], []
    for kind, segs, font in rows:
        text = "".join(t for t, _ in segs)
        boxes.append(d0.textbbox((0, 0), text if kind == "timer" else text or "0", font=font))
        if kind == "timer":
            widths.append(boxes[-1][2] - boxes[-1][0])
        else:
            widths.append(int(_tracked_width(d0, text, font, track)) + (2 * dot if kind == "server" else 0))
    heights = [b[3] - b[1] for b in boxes]
    # 1.2.7 (user's screenshot: the lines sat right under the timer): more room after the big timer digits
    gaps = [int(TIMER_GAP * gap) if kind == "timer" else gap for kind, _s, _f in rows[:-1]]
    block_h = sum(heights) + sum(gaps)
    width = max([pic.width] + [w + 2 * gap for w in widths])
    # text layer for the info block only (shadow = blurred dark copy, like the title of the map pictures)
    blur = max(2, height // 150)
    pad = 3 * blur
    off = max(1, height // 220)
    layer_w, layer_h = width, block_h + 2 * pad
    top = max(pad, _content_bottom(pic) + 3 * gap)      # right under the visible map, not its empty margin
    left = 0
    halo = max(1, height // 200)                         # dark outline in the shadow: readable over bright game
    if beside:
        layer_w = max(widths) + 2 * gap
        left = pic.width + gap
        canvas_h = max(pic.height, layer_h + 2 * off)
        top = (canvas_h - layer_h) // 2 + pad
        canvas = Image.new("RGBA", (left + layer_w + off, canvas_h), BACKDROP + (255,) if backdrop else (0, 0, 0, 0))
    else:
        canvas = Image.new("RGBA", (width, max(pic.height, top + block_h + pad + 2 * off)),
                           BACKDROP + (255,) if backdrop else (0, 0, 0, 0))
    canvas.alpha_composite(pic, (0, (canvas.height - pic.height) // 2 if beside else 0))
    dark = (0, 0, 0, 230)

    def draw(d, shadow):
        y = pad
        for (kind, segs, font), (x0, y0, x1, y1), w, h in zip(rows, boxes, widths, heights):
            if kind == "timer":
                d.text(((layer_w - w) // 2 - x0, y - y0), segs[0][0], font=font,
                       fill=dark if shadow else segs[0][1],
                       stroke_width=2 * halo if shadow else 0, stroke_fill=dark)
            else:
                x = (layer_w - w) // 2
                if kind == "server":
                    grow = halo if shadow else 0
                    cy = y + h // 2
                    d.ellipse([x - grow, cy - dot // 2 - grow, x + dot + grow, cy - dot // 2 + dot + grow],
                              fill=dark if shadow else INFO_DOT)
                    x += 2 * dot
                for text, colour in segs:
                    for ch in text:
                        d.text((x, y - y0), ch, font=font, fill=dark if shadow else colour,
                               stroke_width=halo if shadow else 0, stroke_fill=dark)
                        x += d.textlength(ch, font=font) + track
            y += h + (int(TIMER_GAP * gap) if kind == "timer" else gap)

    shadow = Image.new("RGBA", (layer_w, layer_h), (0, 0, 0, 0))
    draw(ImageDraw.Draw(shadow), True)
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    text = Image.new("RGBA", (layer_w, layer_h), (0, 0, 0, 0))
    draw(ImageDraw.Draw(text), False)
    canvas.alpha_composite(shadow, (left + off, top - pad + 2 * off))
    canvas.alpha_composite(text, (left, top - pad))
    return canvas


def premultiplied_bgra(img: Image.Image) -> bytes:
    a = np.asarray(img.convert("RGBA"), dtype=np.uint16)
    rgb = (a[:, :, :3] * a[:, :, 3:4] + 127) // 255
    out = np.empty(a.shape, dtype=np.uint8)
    out[:, :, 0] = rgb[:, :, 2]
    out[:, :, 1] = rgb[:, :, 1]
    out[:, :, 2] = rgb[:, :, 0]
    out[:, :, 3] = a[:, :, 3]
    return out.tobytes()


def push_layered(hwnd, data: bytes, w: int, h: int, pos, opacity: float) -> str:
    """Show premultiplied BGRA pixels in a layered window at ``pos``; returns an error text or ""."""
    screen = _u.GetDC(None)
    mem = _g.CreateCompatibleDC(screen)
    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = w
    bmi.bmiHeader.biHeight = -h                   # top-down rows
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bits = ctypes.c_void_p()
    hbmp = _g.CreateDIBSection(screen, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
    err = ""
    try:
        if not hbmp or not bits.value:
            raise OSError(f"CreateDIBSection fehlgeschlagen (Fehler {ctypes.get_last_error()})")
        ctypes.memmove(bits.value, data, len(data))
        old = _g.SelectObject(mem, hbmp)
        blend = BLENDFUNCTION(0, 0, max(1, min(255, int(round(opacity * 255)))), 1)
        ok = _u.UpdateLayeredWindow(hwnd, screen, ctypes.byref(wintypes.POINT(int(pos[0]), int(pos[1]))),
                                    ctypes.byref(wintypes.SIZE(w, h)), mem,
                                    ctypes.byref(wintypes.POINT(0, 0)), 0, ctypes.byref(blend), ULW_ALPHA)
        if not ok:
            err = f"UpdateLayeredWindow Fehler {ctypes.get_last_error()}"
        _g.SelectObject(mem, old)
    finally:
        if hbmp:
            _g.DeleteObject(hbmp)
        _g.DeleteDC(mem)
        _u.ReleaseDC(None, screen)
    return err


def render_hud(rows, height: int) -> Image.Image:
    """System values (sysinfo.hud_rows) in Fira Sans ExtraBold like the map titles (user's choice of five
    variants, 1.49: labels grey, values bright, same font and size, no letter spacing) with the soft shadow of
    the info block, left-aligned; ``height``: game height."""
    size = max(13, height // 60)
    try:
        font = ImageFont.truetype(FIRA, size)
    except OSError:
        font = _font(size)
    track = 0
    gap = max(3, height // 160)
    blur = max(2, height // 300)
    pad = 3 * blur
    halo = max(1, height // 400)
    d0 = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    # 1.64.7 (user: "alles schön untereinander"): rows of label + values start their values in one column
    labelled = [len(row) >= 2 and row[0][1] == DIM_LABEL and row[0][0].strip() for row in rows]
    col = max((int(_tracked_width(d0, row[0][0], font, track)) for row, lab in zip(rows, labelled) if lab),
              default=0)
    texts = ["".join(t for t, _ in (row[1:] if lab else row)) for row, lab in zip(rows, labelled)]
    widths = [int(_tracked_width(d0, t, font, track)) + (col if lab else 0) for t, lab in zip(texts, labelled)]
    asc, desc = font.getmetrics()
    line_h = asc + desc
    w = max(widths, default=0) + 2 * pad
    h = len(rows) * line_h + gap * max(0, len(rows) - 1) + 2 * pad
    dark = (0, 0, 0, 230)

    def draw(d, shadow):
        y = pad
        for row, lab in zip(rows, labelled):
            x = pad
            for i, (text, colour) in enumerate(row):
                if lab and i == 1:
                    x = pad + col                      # the values' column
                for ch in text:
                    d.text((x, y), ch, font=font, fill=dark if shadow else colour,
                           stroke_width=halo if shadow else 0, stroke_fill=dark)
                    x += d.textlength(ch, font=font) + track
            y += line_h + gap

    pic = Image.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 0))
    shadow = Image.new("RGBA", pic.size, (0, 0, 0, 0))
    draw(ImageDraw.Draw(shadow), True)
    pic.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(blur)), (0, 0))
    draw(ImageDraw.Draw(pic), False)
    return pic


def progress_strip(width: int, elapsed: float, total: float, height: int, accent=None,
                   remaining: bool = False) -> Image.Image:
    """The song's progress (1.64.7, user's screenshot of Spotify): "1:10 ──────── 2:56" – times grey, the bar
    white on a faint track, with the soft dark edge of the other text. ``height``: game height. 1.2.4: ``accent``
    = colour of the bar (from the cover), ``remaining`` = time left on the right ("−1:46") instead of the length."""
    from .media import clock
    size = max(11, height // 75)
    try:
        font = ImageFont.truetype(FIRA, size)
    except OSError:
        font = _font(size)
    blur = max(2, height // 300)
    pad = 3 * blur
    halo = max(1, height // 400)
    left, right = clock(elapsed), ("\u2212" + clock(total - elapsed) if remaining else clock(total))
    d0 = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    lw, rw = d0.textlength(left, font=font), d0.textlength(right, font=font)
    asc, desc = font.getmetrics()
    h = asc + desc + 2 * pad
    w = max(int(lw + rw) + 6 * size, width)
    gap = max(6, size // 2)
    x0, x1 = pad + lw + gap, w - pad - rw - gap
    bar = max(3, height // 360)
    cy = h // 2
    frac = 0.0 if total <= 0 else min(1.0, max(0.0, elapsed / total))
    dark = (0, 0, 0, 230)
    pic = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))
    shadow = Image.new("RGBA", pic.size, (0, 0, 0, 0))
    ds = ImageDraw.Draw(shadow)
    for x, t in ((pad, left), (w - pad - rw, right)):
        ds.text((x, pad), t, font=font, fill=dark, stroke_width=halo, stroke_fill=dark)
    ds.rounded_rectangle((x0 - halo, cy - bar / 2 - halo, x1 + halo, cy + bar / 2 + halo), radius=bar, fill=dark)
    pic.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(blur)))
    d = ImageDraw.Draw(pic)
    d.text((pad, pad), left, font=font, fill=DIM_LABEL)
    d.text((w - pad - rw, pad), right, font=font, fill=DIM_LABEL)
    d.rounded_rectangle((x0, cy - bar / 2, x1, cy + bar / 2), radius=bar, fill=(255, 255, 255, 70))
    if frac > 0:
        d.rounded_rectangle((x0, cy - bar / 2, x0 + (x1 - x0) * frac, cy + bar / 2), radius=bar,
                            fill=tuple(accent[:3]) + (235,) if accent else (255, 255, 255, 235))
    return pic


CARD_BACKDROP = (14, 14, 18, 165)    # the music card's own dark area (1.2.4): readable over a bright game picture


def backdrop(pic: Image.Image, height: int, pad: int = 0, radius: int = 0) -> Image.Image:
    """``pic`` on a dark half-transparent area with rounded corners (1.2.4, user's pick: "Hintergrund-Kachel";
    since 1.2.4 also behind the map and the system values, user: "Hintergrund dahinter, für jedes UI-Element").
    ``height``: game height (sets padding and corners unless given)."""
    pad = pad or max(4, height // 160)
    out = Image.new("RGBA", (pic.width + 2 * pad, pic.height + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(out).rounded_rectangle((0, 0, out.width - 1, out.height - 1),
                                          radius=radius or max(6, height // 90), fill=CARD_BACKDROP)
    out.alpha_composite(pic, (pad, pad))
    return out


def map_backdrop(pics, text_h: int) -> list:
    """The map window's pictures (all frames of one map) on the dark area: cut to what all of them show (map
    pictures have empty transparent margins), the same size for every frame; ``text_h``: size of its lines."""
    box = None
    for pic in pics:
        b = pic.getchannel("A").getbbox()
        if b:
            box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
    pad, radius = backdrop_pad(text_h), max(8, text_h // 30)
    return [backdrop(pic.crop(box) if box else pic, 0, pad, radius) for pic in pics]


def backdrop_pad(text_h: int) -> int:
    """Edge of the dark area around the map (map_backdrop)."""
    return max(6, text_h // 45)


def _below(pic: Image.Image, strip: Image.Image, centred: bool) -> Image.Image:
    """``strip`` under ``pic`` (overlapping by the shadow pad, like the text rows)."""
    out = Image.new("RGBA", (max(pic.width, strip.width), pic.height + strip.height), (0, 0, 0, 0))
    out.alpha_composite(pic, ((out.width - pic.width) // 2 if centred else 0, 0))
    out.alpha_composite(strip, ((out.width - strip.width) // 2 if centred else 0, pic.height))
    return out


FIT_MIN = 0.6               # a long title is set down to this share of its size before it wraps (1.65.2)


def fit_lines(rows, height: int, scales=None):
    """Each row as a picture no wider than a line of media.MAX_CHARS characters (1.65.2, user: "lieber die
    Schrift kleiner statt Zeilenumbruch"): a longer row gets smaller text, down to FIT_MIN; only what is still
    too long wraps (media.wrap) at that size. ``scales``: size factor per row (the title is a bit larger)."""
    from .media import ARTIST_LINES, MAX_CHARS, TITLE_LINES, wrap
    out = []
    for i, row in enumerate(rows):
        scale = scales[i] if scales else 1.0
        h = int(height * scale)
        im = render_hud([row], h)
        colour = row[-1][1] if row else (255, 255, 255, 255)
        max_w = render_hud([[("n" * MAX_CHARS, colour)]], h).width
        if im.width <= max_w or len(row) != 1:
            out.append(im)
            continue
        f = max(FIT_MIN, max_w / im.width)
        small = render_hud([row], max(1, int(h * f)))
        if small.width <= max_w * 1.02:
            out.append(small)
            continue
        text = row[0][0]                                 # still too long: wrap at the smallest size
        chars = max(8, int(len(text) * max_w / small.width))
        lines = wrap(text, chars, TITLE_LINES if i == 0 else ARTIST_LINES)
        out += [render_hud([[(line, colour)]], max(1, int(h * f))) for line in lines]
    return out


def _stack(lines, pad: int, centred: bool) -> Image.Image:
    """Line pictures of render_hud one below the other; ``pad``: their shadow margin (it overlaps)."""
    if not lines:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    w = max(im.width for im in lines)
    h = sum(im.height - pad for im in lines) + pad
    pic = Image.new("RGBA", (w, max(1, h)), (0, 0, 0, 0))
    y = 0
    for im in lines:
        pic.alpha_composite(im, ((w - im.width) // 2 if centred else 0, y))
        y += im.height - pad
    return pic


def render_music_compact(rows, cover, height: int) -> Image.Image:
    """Music card "Kompakt" (1.64): the cover left of the title/artist rows, as tall as the two lines."""
    text = _stack(fit_lines(rows, height), 3 * max(2, height // 300), False)
    if cover is None:
        return text
    size = max(13, height // 60)
    blur = max(2, height // 300)
    pad = 3 * blur
    side = max(16, text.height - 2 * pad)
    art = cover.convert("RGBA").resize((side, side), Image.LANCZOS)
    mask = Image.new("L", (side, side), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, side - 1, side - 1), radius=max(2, size // 4), fill=255)
    art.putalpha(mask)
    gap = max(6, size // 2)
    pic = Image.new("RGBA", (pad + side + gap + text.width - pad, max(text.height, side + 2 * pad)), (0, 0, 0, 0))
    shadow = Image.new("RGBA", pic.size, (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 200), (pad, pad), mask)
    pic.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(blur)))
    pic.alpha_composite(art, (pad, pad))
    pic.alpha_composite(text, (pad + side + gap - pad, 0))
    return pic


def render_music(rows, cover, height: int, style: str = "big", progress=None, look=()) -> Image.Image:
    """"Läuft gerade": style "big" (1.64.7, user's choice "A") = the cover big on top, below it the title (a bit
    larger) and the artist, centred; "compact" = the card of 1.64 (cover left). Text like the system values, the
    cover slightly rounded with the same soft shadow. ``look`` (1.2.4): "accent" = bar in the cover's colour,
    "remaining" = time left, "backdrop" = on a dark area."""
    pic = _render_music(rows, cover, height, style, progress, look)
    return backdrop(pic, height) if "backdrop" in look else pic


def _render_music(rows, cover, height, style, progress, look):
    accent = None
    if progress and "accent" in look:
        from .media import accent as cover_accent
        accent = cover_accent(cover)
    strip = (lambda w: progress_strip(w, *progress, height, accent, "remaining" in look)) if progress else None
    if style == "compact":
        pic = render_music_compact(rows, cover, height)
        if strip:
            pad = 3 * max(2, height // 300)
            pic = _below(pic, strip(pic.width - 2 * pad), False)
        return pic
    blur = max(2, height // 300)
    pad = 3 * blur
    lines = fit_lines(rows, height, [TITLE_SCALE if i == 0 else 1.0 for i in range(len(rows))])
    side = max(32, height // 6) if cover is not None else 0
    gap = max(4, height // 120) if cover is not None else 0
    text_w = max((im.width for im in lines), default=0)
    text_h = sum(im.height - pad for im in lines) + (pad if lines else 0)
    w = max(side + 2 * pad, text_w)
    h = (pad + side + gap - pad if cover is not None else 0) + text_h
    pic = Image.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 0))
    if cover is not None:
        art = cover.convert("RGBA").resize((side, side), Image.LANCZOS)
        mask = Image.new("L", (side, side), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, side - 1, side - 1), radius=max(2, side // 14), fill=255)
        art.putalpha(mask)
        ax = (w - side) // 2
        shadow = Image.new("RGBA", pic.size, (0, 0, 0, 0))
        shadow.paste((0, 0, 0, 200), (ax, pad), mask)
        pic.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(blur)))
        pic.alpha_composite(art, (ax, pad))
    y = pad + side + gap - pad if cover is not None else 0
    for im in lines:
        pic.alpha_composite(im, ((w - im.width) // 2, y))
        y += im.height - pad
    if strip:
        pic = _below(pic, strip(max(side, text_w - 2 * pad)), True)
    return pic


def guide_line(length: int, vertical: bool, dash: int = 14) -> Image.Image:
    """A centre guide line (1.64.5, user: "Mittellinie als Kreuz beim Ausrichten"): 3 px – light dashes on a dark
    edge, visible on bright and dark game pictures alike."""
    w, h = (3, length) if vertical else (length, 3)
    pic = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(pic)
    d.rectangle((0, 0, w - 1, h - 1), fill=(0, 0, 0, 150))
    for i in range(0, length, 2 * dash):
        if vertical:
            d.line([(1, i), (1, min(length - 1, i + dash - 1))], fill=(255, 255, 255, 230))
        else:
            d.line([(i, 1), (min(length - 1, i + dash - 1), 1)], fill=(255, 255, 255, 230))
    return pic


class HudWindow:
    """Small click-through layered window for the system values at the top of a black bar (and, 1.64, the
    music card). In edit mode (the overlay's "Mit der Maus verschieben") it can be dragged like the map:
    ``on_moved(x, y)`` after the drop."""

    def __init__(self, title: str = "DbD Map Scout Systemwerte"):
        ex = WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        self._hwnd = _u.CreateWindowExW(ex, "Static", title, WS_POPUP, 0, 0, 16, 16,
                                        None, None, _k.GetModuleHandleW(None), None)
        if not self._hwnd:
            raise OSError(f"CreateWindowExW fehlgeschlagen (Fehler {ctypes.get_last_error()})")
        self._hwnd = int(self._hwnd)
        self._key = None
        self._data = None
        self._pos = None
        self._shown = False
        self.size = (0, 0)
        self._raised = 0.0
        self.opacity = 0.85
        self.last_error = ""
        self.editing = False
        self.edit_label = ""                   # name on the edit frame ("SYSTEMWERTE", "MUSIK")
        self.fade = 1.0                        # share of the opacity while fading in/out (music card, 1.2.4)
        self.on_moved = None
        self._proc = WNDPROC(self._wndproc)                    # keep a reference!
        self._old_proc = _SetLong(self._hwnd, GWLP_WNDPROC, ctypes.cast(self._proc, ctypes.c_void_p).value)

    def _wndproc(self, hwnd, msg, wp, lp):
        try:
            if self.editing:
                if msg == WM_NCHITTEST:
                    return HTCAPTION                  # drag anywhere on it
                if msg == WM_EXITSIZEMOVE:
                    rc = wintypes.RECT()
                    _u.GetWindowRect(self._hwnd, ctypes.byref(rc))
                    self._pos = (rc.left, rc.top, round(self.opacity, 3))
                    if self.on_moved:
                        self.on_moved(rc.left, rc.top)
        except Exception as e:  # never let an exception escape into Windows
            self.last_error = repr(e)
        return _u.CallWindowProcW(self._old_proc, hwnd, msg, wp, lp)

    def set_editing(self, on: bool):
        """Edit mode: clickable and draggable, with the yellow edit border."""
        if bool(on) == self.editing:
            return
        self.editing = bool(on)
        ex = _GetLong(self._hwnd, GWL_EXSTYLE)
        ex = ex & ~(WS_EX_TRANSPARENT | WS_EX_NOACTIVATE) if on else ex | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
        _SetLong(self._hwnd, GWL_EXSTYLE, ex)
        _u.SetWindowPos(self._hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED)
        self._key = None                                  # re-render with/without border

    def set_picture(self, pic, key):
        """Show a ready picture (the centre guide lines, 1.64.5); ``key`` says when it changed."""
        if key != self._key:
            self._key = key
            self._data, self.size = premultiplied_bgra(pic), pic.size
            self._pos = None
        return self.size

    def render(self, rows, height: int, cover=None, style=None, progress=None, look=()):
        """Prepare the picture; returns its size (0, 0 without rows). ``cover``/``style``/``progress``/``look``: the
        music card (progress = (elapsed, total) seconds; redrawn once a second while a song plays)."""
        progress = (int(progress[0]), int(progress[1])) if progress else None
        look = tuple(sorted(look))
        key = (tuple(tuple(r) for r in rows), int(height), self.editing, id(cover), style, progress, look)
        if key != self._key:
            self._key = key
            if not rows:
                self._data, self.size = None, (0, 0)
            else:
                pic = render_hud(rows, height) if style is None else render_music(rows, cover, height, style,
                                                                                  progress, look)
                if style is None and "backdrop" in look:
                    pic = backdrop(pic, height)
                if self.editing:
                    pic = add_border(pic, self.edit_label)
                self._data, self.size = premultiplied_bgra(pic), pic.size
                self._pos = None                      # push again
        return self.size

    def show_at(self, x: int, y: int):
        if not self._data:
            self.hide()
            return
        pos = (int(x), int(y), round(self.opacity, 3))
        if pos != self._pos:
            self._pos = pos
            err = push_layered(self._hwnd, self._data, self.size[0], self.size[1], pos[:2],
                               self.opacity * self.fade)
            if err:
                self.last_error = err
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
        if not self._shown:
            _u.ShowWindow(self._hwnd, SW_SHOWNOACTIVATE)
            self._shown = True
            self._raised = 0.0
        now = time.monotonic()
        if now - self._raised >= 1.0:                 # stay above DBD; once a second is enough (the UI ticks 4×/s)
            self._raised = now
            _u.SetWindowPos(self._hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)

    def hide(self):
        if self._shown:
            _u.ShowWindow(self._hwnd, SW_HIDE)
            self._shown = False

    def set_fade(self, fade: float):
        """Opacity share 0…1 while fading (1.2.4); pushed again at once when shown."""
        fade = min(1.0, max(0.0, fade))
        if fade == self.fade:
            return
        self.fade = fade
        if self._shown and self._data and self._pos:
            err = push_layered(self._hwnd, self._data, self.size[0], self.size[1], self._pos[:2],
                               self.opacity * fade)
            if err:
                self.last_error = err

    @property
    def shown(self):
        return self._shown

    def hwnd(self) -> int:
        return self._hwnd

    def destroy(self):
        try:
            _u.DestroyWindow(self._hwnd)
        except Exception:
            pass


class PictureOverlay:
    """The overlay's content and logic: map picture (+ caption), timer/server/ping/notes below it, the waiting
    card, floors, animation, edit mode. The window that shows it is a subclass's (Win32Overlay, QtOverlay):
    ``_push(pos)``, ``_show_window()``, ``_hide_window()``, ``_apply_editing()``, ``_raise()``,
    ``_destroy_window()``, ``hwnd()``, ``is_visible()``. ``root`` = mainloop.MainLoop (timers)."""

    def __init__(self, root):
        self.root = root
        self.opacity = 0.85
        self.transparent = True
        self.show_caption = True
        self.show_map = True            # off: only timer, server and ping ("nur Infos")
        self.edit_label = ""            # name on the edit frame (1.64.7: "KARTE · Mausrad = Grösse")
        self.info_beside = False        # timer/server right of the map (low bar above/below the picture)
        self.text_height = 0            # px the timer/name/info are sized for (1.65: not the map's size); 0 = map
        self.backdrop = False           # dark area with rounded corners behind map and lines (1.2.4)
        self.on_moved = None
        self.on_wheel = None
        self.game_hwnd = None
        self.raised_over_game = 0
        self.last_error = ""
        self._frames = []               # [(PIL RGBA, duration)]
        self._caption = ""
        self._timer = ""                # round timer text below the map ("" = none)
        self._server = ""               # connected server region below the timer ("" = none)
        self._ping = None               # ping to that region in ms, below the region
        self._waiting = ()              # lines of the waiting card: shown instead of everything else
        self._note = ""                 # warning below the timer ("" = none)
        self._record = ""               # own results on this map below the timer ("" = none)
        self._base = []                 # [(PIL RGBA, duration)] scaled map (+ caption), cached per size
        self._base_key = None
        self._prepared = []             # [(bytes, w, h, duration)]
        self._key = None
        self._pushed_key = None         # _key of the picture last put on the screen
        self._fit = None                # fit_width(): (content key, text height, map height)
        self._frame_i = 0
        self._anim_job = None
        self._floor = None              # frame index of the floor on display; None = all floors one below the other
        self._view = None               # (frames on display, floors stacked) – mapimage.floor_view, cached
        self._shown = False
        self._editing = False
        self._pos = None
        self._size = (0, 0)

    def _start(self):
        """End of a subclass's __init__ (window made): stay on top from now on."""
        self._keep_on_top()

    # ------------------------------------------------------------ content
    def set_map(self, path, caption: str = "", rotation: int = 0):
        self._stop_anim()
        self._frames = load_frames(path, rotation) if path else []
        self._floor = self._view = None
        self._caption = caption
        self._base_key = self._key = None

    def set_timer(self, text: str):
        """Round timer shown below the map; only re-renders when the text changes."""
        self._timer = text or ""

    def set_server(self, text: str, ping: float | None = None):
        """Connected server region (and its ping) shown below the timer."""
        self._server = text or ""
        self._ping = round(ping) if ping is not None and self._server else None

    def set_waiting(self, lines):
        """No map on screen: show only these lines ("Warte auf Map", lobby state); () = off."""
        self._waiting = tuple(lines or ())

    def set_note(self, text: str):
        """Warning in amber below the timer, e.g. a doubtful detection; "" = none."""
        self._note = text or ""

    def set_record(self, text: str):
        """Own results on the map on display ("Ø 2.8 Kills · 12 Runden"); "" = none."""
        self._record = text or ""

    def has_map(self) -> bool:
        return bool(self._frames)

    def _title_split(self, frames):
        """Row where the map starts below its drawn-in name (first picture; GIF floors have none), cached."""
        if not frames:
            return None
        key = (id(frames[0][0]), len(frames))
        if getattr(self, "_split_key", None) != key:
            from .mapimage import title_split
            parts = title_split(frames[0][0]) if len(frames) == 1 or self.stacked() <= 1 else None
            self._split_key, self._split = key, (parts[2] if parts else None)
        return self._split

    def floors(self) -> list:
        """Frame indices of the floors of the map (Midwich: bottom, top); [] = one floor."""
        return floor_frames(self._frames)

    def set_floor(self, index):
        """Show this frame (a floor) alone; None = all floors one below the other. The size changes with it:
        applied by the next render()."""
        index = index if index in floor_frames(self._frames) else None
        if index != self._floor:
            self._floor, self._view = index, None
            self._base_key = self._key = None

    def _view_frames(self):
        if self._view is None:
            self._view = floor_view(self._frames, self._floor, MAX_LOAD_H)
        return self._view

    def stacked(self) -> int:
        """Floors shown one below the other (Midwich: 2), else 1 – the app makes the overlay that much taller."""
        return self._view_frames()[1] if self._frames and self.show_map and not self._waiting else 1

    def map_size(self):
        """Size of the map picture as loaded (w, h) – to fit it without rendering it first."""
        return self._view_frames()[0][0][0].size if self._frames and self.show_map and not self._waiting else (0, 0)

    def has_info(self) -> bool:
        return bool(self._timer or self._server or self._note or self._record)

    def set_show_map(self, on: bool):
        self.show_map = bool(on)
        self._base_key = self._key = None

    def set_transparent(self, on: bool):
        self.transparent = bool(on)
        self._key = None

    def set_backdrop(self, on: bool):
        self.backdrop = bool(on)
        self._key = None

    def backdrop_pad(self, text_h: int) -> int:
        """Edge the dark area adds around the map (0 without it) – the App lets it use the margin, so the map
        stays as big as without the area (1.2.5, user: "Warum wird die Map kleiner?")."""
        return backdrop_pad(text_h) if self.backdrop else 0

    def render(self, height: int, push: bool = True):
        """Prepare pictures for this height; returns (w, h) of the overlay. ``push=False``: only measure – the
        screen keeps the picture it has (the App tries sizes before it settles; pushing each one made the
        overlay grow and shrink on every tick)."""
        if self._waiting:
            return self._render_waiting(max(40, int(self.text_height) or int(height)))
        if not self._frames:
            return 0, 0
        height = max(40, int(height))
        if not self.show_map and not self.has_info():
            return 0, 0                   # nothing to show without the map
        # text below/above the map is sized for one floor: stacked floors would double it; since 1.65 the App
        # gives it its own size (user: a bigger map, the same text)
        text_h = max(40, int(self.text_height) or height // self.stacked())
        base_key = (height, self._caption if self.show_caption else "", self.transparent, self.show_map, text_h)
        new_base = base_key != self._base_key
        if new_base:                      # scaling is the slow part: done once per size, not per timer tick
            if self.show_map:
                frames = self._view_frames()[0]
                split = self._title_split(frames)
                self._base = [(compose(img, height, base_key[1], self.transparent, False, text_h, split), dur)
                              for img, dur in frames]
            else:                         # info only: an empty picture, the info block is drawn below it
                self._base = [(Image.new("RGBA", (1, 1), (0, 0, 0, 0)), 0)]
            self._base_key = base_key
        key = (base_key, self._editing, self._timer, self._server, self._ping, self._note, self._record,
               self.info_beside, self.backdrop)
        if key != self._key:
            self._prepared = []
            pics = []
            for pic, dur in self._base:
                if self.has_info():
                    pic = add_info(pic, self._timer, self._server, text_h, backdrop=not self.transparent,
                                   ping=self._ping, note=self._note, record=self._record,
                                   beside=self.info_beside and self.show_map)
                pics.append(pic)
            if self.backdrop:
                pics = map_backdrop(pics, text_h)
            for pic, (_b, dur) in zip(pics, self._base):
                if self._editing:
                    pic = add_border(pic.copy(), self.edit_label)
                self._prepared.append((premultiplied_bgra(pic), pic.width, pic.height, dur))
            self._key = key
            self._size = (self._prepared[0][1], self._prepared[0][2])
            if new_base or self._frame_i >= len(self._prepared):
                self._frame_i = 0
                if push:
                    self._restart_anim()
            # else: timer text changed – same frame, the animation keeps running
        if push and self._shown and self._pushed_key != self._key:
            self._push()
            self._pushed_key = self._key
            if self._anim_job is None:
                self._restart_anim()
        return self._size

    def fit_width(self, height: int, text_h: int, avail: float) -> int:
        """Map height and ``text_height`` at which the overlay is at most ``avail`` wide (a black bar): the lines
        below the map get smaller text first, the map only when that is not enough. Measured without putting
        anything on the screen, with the widest digits in the timer, and kept until the content changes – before,
        the App rendered big, showed it, then smaller: the map grew and shrank on every tick."""
        key = (height, text_h, avail, re.sub(r"\d", "0", self._timer), self._server, self._ping, self._note,
               self._record, self.info_beside, self._editing, self.show_map, self.show_caption, self._caption,
               self.transparent, self.backdrop, self._floor, id(self._frames[0][0]) if self._frames else None)
        if self._fit is None or self._fit[0] != key:
            timer, self._timer = self._timer, key[3]
            try:
                self.text_height = text_h
                w, _h = self.render(height, push=False)
                iw, ih = self.map_size()
                map_w = (round(iw * height / ih) if ih else 0) + 2 * self.backdrop_pad(text_h)
                for _try in range(3):           # the lines below are wider than the bar: smaller text, same map
                    if w <= avail or w <= map_w or self.text_height <= 40:    # (the area's edge does not scale)
                        break
                    self.text_height = max(40, int(self.text_height * avail / w))
                    w, _h = self.render(height, push=False)
                for _try in range(6):           # still too wide (the map with the area's edge): the map too
                    if w <= avail or height <= 80:
                        break
                    height = max(80, min(height - 1, int(height * avail / w)))
                    w, _h = self.render(height, push=False)
            finally:
                self._timer = timer
            self._fit = (key, self.text_height, height)
        self.text_height = self._fit[1]
        return self._fit[2]

    def _render_waiting(self, height: int):
        key = ("waiting", height, self.transparent, self._editing, self._waiting, self._server, self._ping,
               self.backdrop)
        if key != self._key:
            self._stop_anim()
            pic = add_info(Image.new("RGBA", (1, 1), (0, 0, 0, 0)), "", self._server, height,
                           backdrop=not self.transparent, ping=self._ping, status=self._waiting)
            if self.backdrop:
                pic = map_backdrop([pic], height)[0]
            if self._editing:
                pic = add_border(pic.copy(), self.edit_label)
            self._prepared = [(premultiplied_bgra(pic), pic.width, pic.height, 0)]
            self._key, self._base_key, self._frame_i = key, None, 0     # the map is rebuilt afterwards
            self._size = (pic.width, pic.height)
            if self._shown:
                self._push()
        return self._size

    # ----------------------------------------------------------- animation
    def _restart_anim(self):
        self._stop_anim()
        if len(self._prepared) > 1:
            self._anim_job = self.root.after(self._prepared[self._frame_i][3], self._next_frame)

    def _next_frame(self):
        if not self._prepared:
            return
        self._frame_i = (self._frame_i + 1) % len(self._prepared)
        if self._shown:
            self._push()
        self._anim_job = self.root.after(self._prepared[self._frame_i][3], self._next_frame)

    def _stop_anim(self):
        if self._anim_job:
            try:
                self.root.after_cancel(self._anim_job)
            except Exception:
                pass
            self._anim_job = None

    # ----------------------------------------------------------- placement
    def show_at(self, x: int, y: int):
        if not self._prepared:
            self.hide()
            return
        pos = (int(x), int(y))
        opacity_key = round(self.opacity, 3)
        if not self._shown or pos != self._pos or opacity_key != getattr(self, "_pushed_opacity", None):
            self._pos = pos
            self._push(pos)
            self._pushed_key = self._key
            self._pushed_opacity = opacity_key
        if not self._shown:
            self._show_window()
            self._shown = True

    def hide(self):
        if self._shown:
            self._hide_window()
            self._shown = False

    @property
    def shown(self):
        return self._shown

    def _keep_on_top(self):
        try:
            if self._shown:
                self._raise()
        except Exception as e:
            self.last_error = repr(e)
        self.root.after(1000, self._keep_on_top)

    # ----------------------------------------------------------- edit mode
    def set_editing(self, on: bool):
        self._editing = bool(on)
        self._apply_editing()
        self._key = None                                  # re-render with/without border

    @property
    def editing(self):
        return self._editing

    @property
    def dragging(self) -> bool:
        """The user is moving it right now (the native window: Windows' own move loop, nothing to wait for)."""
        return False

    def destroy(self):
        self._stop_anim()
        try:
            self._destroy_window()
        except Exception:
            pass


class Win32Overlay(PictureOverlay):
    """The overlay as a layered Win32 popup: per-pixel alpha (UpdateLayeredWindow), click-through, never active."""

    def __init__(self, root):
        super().__init__(root)
        ex = WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        self._hwnd = _u.CreateWindowExW(ex, "Static", "DbD Map Scout Overlay", WS_POPUP, 0, 0, 16, 16,
                                        None, None, _k.GetModuleHandleW(None), None)
        if not self._hwnd:
            raise OSError(f"CreateWindowExW fehlgeschlagen (Fehler {ctypes.get_last_error()})")
        self._hwnd = int(self._hwnd)
        self._proc = WNDPROC(self._wndproc)                    # keep a reference!
        self._old_proc = _SetLong(self._hwnd, GWLP_WNDPROC, ctypes.cast(self._proc, ctypes.c_void_p).value)
        self._start()

    def _wndproc(self, hwnd, msg, wp, lp):
        try:
            if self._editing:
                if msg == WM_NCHITTEST:
                    return HTCAPTION                  # drag anywhere on the picture
                if msg == WM_EXITSIZEMOVE:
                    rc = wintypes.RECT()
                    _u.GetWindowRect(self._hwnd, ctypes.byref(rc))
                    self._pos = (rc.left, rc.top)
                    if self.on_moved:
                        self.on_moved(rc.left, rc.top)
                if msg == WM_MOUSEWHEEL and self.on_wheel:
                    delta = ctypes.c_short((wp >> 16) & 0xFFFF).value
                    self.on_wheel(1 if delta > 0 else -1)
                    return 0
        except Exception as e:  # never let an exception escape into Windows
            self.last_error = repr(e)
        return _u.CallWindowProcW(self._old_proc, hwnd, msg, wp, lp)

    def _push(self, pos=None):
        """Hand the current frame to Windows (UpdateLayeredWindow)."""
        if not self._prepared:
            return
        data, w, h, _ = self._prepared[self._frame_i]
        err = push_layered(self._hwnd, data, w, h, pos or self._pos or (0, 0), self.opacity)
        if err:
            self.last_error = err

    def _show_window(self):
        _u.ShowWindow(self._hwnd, SW_SHOWNOACTIVATE)
        _u.SetWindowPos(self._hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

    def _hide_window(self):
        _u.ShowWindow(self._hwnd, SW_HIDE)

    def _raise(self):
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
        _u.SetWindowPos(self._hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
        game = self.game_hwnd() if self.game_hwnd else None
        if game and is_above(game, self._hwnd):
            _u.SetWindowPos(self._hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, flags)
            _u.SetWindowPos(self._hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
            self.raised_over_game += 1

    def _apply_editing(self):
        ex = _GetLong(self._hwnd, GWL_EXSTYLE)
        if self._editing:
            ex &= ~(WS_EX_TRANSPARENT | WS_EX_NOACTIVATE)
        else:
            ex |= WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
        _SetLong(self._hwnd, GWL_EXSTYLE, ex)
        _u.SetWindowPos(self._hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED)

    def _destroy_window(self):
        _u.DestroyWindow(self._hwnd)

    def hwnd(self) -> int:
        return self._hwnd

    def is_visible(self) -> bool:
        return bool(_u.IsWindowVisible(self._hwnd))


def make_overlay(root, prefer_native: bool = True):
    """Native overlay on Windows (fallback, and elsewhere: a Qt window)."""
    from .overlay_qt import QtOverlay
    if IS_WIN and prefer_native:
        try:
            return Win32Overlay(root)
        except Exception as e:
            ov = QtOverlay(root)
            ov.last_error = f"natives Overlay nicht verfügbar: {e}"
            return ov
    return QtOverlay(root)

