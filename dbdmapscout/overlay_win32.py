"""Native Windows overlay: a layered, click-through, always-on-top popup window.

The picture is pushed with UpdateLayeredWindow (per-pixel alpha), so the
transparent parts of a map really are transparent, and nothing depends on
Tk's window handling. The window never takes the keyboard focus
(WS_EX_NOACTIVATE, shown with SW_SHOWNOACTIVATE) and lets every click through
to the game (WS_EX_TRANSPARENT) – except in edit mode, where it can be dragged.
"""
from __future__ import annotations

import ctypes
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .capture import is_above
from .overlay import BACKDROP, load_frames

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


def _font(size: int):
    for name in ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def compose(img: Image.Image, height: int, caption: str, transparent: bool, border: bool) -> Image.Image:
    """Scaled map + optional caption bar (+ edit border) as one RGBA picture."""
    w = max(1, round(img.width * height / img.height))
    pic = img.resize((w, height), Image.LANCZOS)
    if not transparent:
        bg = Image.new("RGBA", pic.size, BACKDROP + (255,))
        bg.alpha_composite(pic)
        pic = bg
    if caption:
        size = max(12, height // 34)
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


def add_border(pic: Image.Image) -> Image.Image:
    ImageDraw.Draw(pic).rectangle([0, 0, pic.width - 1, pic.height - 1], outline=BORDER, width=3)
    return pic


def add_info(pic: Image.Image, timer: str, server: str, height: int) -> Image.Image:
    """Dark strip below the (composed) map: big centred round timer, connected server region below it."""
    lines = [(t, _font(max(size, 1)), fill) for t, size, fill in
             ((timer, max(22, height // 11), (242, 242, 242, 255)),
              (server, max(14, height // 24), (170, 200, 235, 255))) if t]
    if not lines:
        return pic
    d = ImageDraw.Draw(pic)
    boxes = [d.textbbox((0, 0), t, font=f) for t, f, _ in lines]
    pad = max(6, height // 60)
    gap = pad
    bar_h = sum(b[3] - b[1] for b in boxes) + gap * (len(lines) - 1) + 2 * pad
    width = max(pic.width, max(b[2] - b[0] for b in boxes) + 2 * pad)
    canvas = Image.new("RGBA", (width, pic.height + bar_h), (0, 0, 0, 0))
    canvas.alpha_composite(pic, (0, 0))
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, pic.height, width - 1, pic.height + bar_h - 1], fill=(20, 20, 22, 235))
    y = pic.height + pad
    for (text, font, fill), (x0, y0, x1, y1) in zip(lines, boxes):
        d.text(((width - (x1 - x0)) // 2 - x0, y - y0), text, font=font, fill=fill)
        y += (y1 - y0) + gap
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


class Win32Overlay:
    """Same interface as overlay.Overlay, implemented with plain Win32 calls."""

    def __init__(self, root):
        self.root = root
        self.opacity = 0.85
        self.transparent = True
        self.show_caption = True
        self.on_moved = None
        self.on_wheel = None
        self.game_hwnd = None
        self.raised_over_game = 0
        self.last_error = ""
        self._drag = None               # kept for interface compatibility (native drag blocks Tk anyway)
        self._frames = []               # [(PIL RGBA, duration)]
        self._caption = ""
        self._timer = ""                # round timer text below the map ("" = none)
        self._server = ""               # connected server region below the timer ("" = none)
        self._base = []                 # [(PIL RGBA, duration)] scaled map (+ caption), cached per size
        self._base_key = None
        self._prepared = []             # [(bytes, w, h, duration)]
        self._key = None
        self._frame_i = 0
        self._anim_job = None
        self._shown = False
        self._editing = False
        self._pos = None
        self._size = (0, 0)
        ex = WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        self._hwnd = _u.CreateWindowExW(ex, "Static", "DbD Map Scout Overlay", WS_POPUP, 0, 0, 16, 16,
                                        None, None, _k.GetModuleHandleW(None), None)
        if not self._hwnd:
            raise OSError(f"CreateWindowExW fehlgeschlagen (Fehler {ctypes.get_last_error()})")
        self._hwnd = int(self._hwnd)
        self._proc = WNDPROC(self._wndproc)                    # keep a reference!
        self._old_proc = _SetLong(self._hwnd, GWLP_WNDPROC, ctypes.cast(self._proc, ctypes.c_void_p).value)
        self._keep_on_top()

    # ------------------------------------------------------------- window proc
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

    # ------------------------------------------------------------ content
    def set_map(self, path, caption: str = ""):
        self._stop_anim()
        self._frames = load_frames(path) if path else []
        self._caption = caption
        self._base_key = self._key = None

    def set_timer(self, text: str):
        """Round timer shown below the map; only re-renders when the text changes."""
        self._timer = text or ""

    def set_server(self, text: str):
        """Connected server region shown below the timer."""
        self._server = text or ""

    def has_map(self) -> bool:
        return bool(self._frames)

    def set_transparent(self, on: bool):
        self.transparent = bool(on)
        self._key = None

    def render(self, height: int):
        """Prepare pictures for this height; returns (w, h) of the overlay."""
        if not self._frames:
            return 0, 0
        height = max(40, int(height))
        base_key = (height, self._caption if self.show_caption else "", self.transparent)
        new_base = base_key != self._base_key
        if new_base:                      # scaling is the slow part: done once per size, not per timer tick
            self._base = [(compose(img, height, base_key[1], self.transparent, False), dur)
                          for img, dur in self._frames]
            self._base_key = base_key
        key = (base_key, self._editing, self._timer, self._server)
        if key != self._key:
            self._prepared = []
            for pic, dur in self._base:
                if self._timer or self._server:
                    pic = add_info(pic, self._timer, self._server, height)
                if self._editing:
                    pic = add_border(pic.copy())
                self._prepared.append((premultiplied_bgra(pic), pic.width, pic.height, dur))
            self._key = key
            self._size = (self._prepared[0][1], self._prepared[0][2])
            if new_base or self._frame_i >= len(self._prepared):
                self._frame_i = 0
                if self._shown:
                    self._push()
                self._restart_anim()
            elif self._shown:
                self._push()              # timer text changed: same frame, keep the animation running
        return self._size

    def _push(self, pos=None):
        """Hand the current frame to Windows (UpdateLayeredWindow)."""
        if not self._prepared:
            return
        data, w, h, _ = self._prepared[self._frame_i]
        pos = pos or self._pos or (0, 0)
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
        try:
            if not hbmp or not bits.value:
                raise OSError(f"CreateDIBSection fehlgeschlagen (Fehler {ctypes.get_last_error()})")
            ctypes.memmove(bits.value, data, len(data))
            old = _g.SelectObject(mem, hbmp)
            blend = BLENDFUNCTION(0, 0, max(1, min(255, int(round(self.opacity * 255)))), 1)
            ok = _u.UpdateLayeredWindow(self._hwnd, screen, ctypes.byref(wintypes.POINT(int(pos[0]), int(pos[1]))),
                                        ctypes.byref(wintypes.SIZE(w, h)), mem,
                                        ctypes.byref(wintypes.POINT(0, 0)), 0, ctypes.byref(blend), ULW_ALPHA)
            if not ok:
                self.last_error = f"UpdateLayeredWindow Fehler {ctypes.get_last_error()}"
            _g.SelectObject(mem, old)
        finally:
            if hbmp:
                _g.DeleteObject(hbmp)
            _g.DeleteDC(mem)
            _u.ReleaseDC(None, screen)

    # ----------------------------------------------------------- animation
    def _restart_anim(self):
        self._stop_anim()
        if len(self._prepared) > 1:
            self._anim_job = self.root.after(self._prepared[0][3], self._next_frame)

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
            self._pushed_opacity = opacity_key
        if not self._shown:
            _u.ShowWindow(self._hwnd, SW_SHOWNOACTIVATE)
            _u.SetWindowPos(self._hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
            self._shown = True

    def hide(self):
        if self._shown:
            _u.ShowWindow(self._hwnd, SW_HIDE)
            self._shown = False

    @property
    def shown(self):
        return self._shown

    def hwnd(self) -> int:
        return self._hwnd

    def is_visible(self) -> bool:
        return bool(_u.IsWindowVisible(self._hwnd))

    def _keep_on_top(self):
        try:
            if self._shown:
                flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
                _u.SetWindowPos(self._hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
                game = self.game_hwnd() if self.game_hwnd else None
                if game and is_above(game, self._hwnd):
                    _u.SetWindowPos(self._hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, flags)
                    _u.SetWindowPos(self._hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
                    self.raised_over_game += 1
        except Exception as e:
            self.last_error = repr(e)
        self.root.after(1000, self._keep_on_top)

    # ----------------------------------------------------------- edit mode
    def set_editing(self, on: bool):
        self._editing = bool(on)
        ex = _GetLong(self._hwnd, GWL_EXSTYLE)
        if on:
            ex &= ~(WS_EX_TRANSPARENT | WS_EX_NOACTIVATE)
        else:
            ex |= WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
        _SetLong(self._hwnd, GWL_EXSTYLE, ex)
        _u.SetWindowPos(self._hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED)
        self._key = None                                  # re-render with/without border

    @property
    def editing(self):
        return self._editing

    def destroy(self):
        self._stop_anim()
        try:
            _u.DestroyWindow(self._hwnd)
        except Exception:
            pass


def make_overlay(root, prefer_native: bool = True):
    """Native overlay on Windows (fallback: Tk overlay)."""
    from .overlay import Overlay
    if IS_WIN and prefer_native:
        try:
            return Win32Overlay(root)
        except Exception as e:
            ov = Overlay(root)
            ov.last_error = f"natives Overlay nicht verfügbar: {e}"
            return ov
    return Overlay(root)

