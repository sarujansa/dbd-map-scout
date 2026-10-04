"""The overlay window: a borderless, always-on-top, click-through picture."""
from __future__ import annotations

import ctypes
import sys
import tkinter as tk

from PIL import Image, ImageSequence, ImageTk

from .capture import is_above
from .mapimage import floor_frames, floor_view, rotate_frames

IS_WIN = sys.platform == "win32"
KEY = "#ff00fe"                 # colour that Windows makes fully transparent
KEY_RGB = (255, 0, 254)
OFFSCREEN = -32000              # "hidden" = parked far outside every monitor
BACKDROP = (18, 18, 20)         # behind half-transparent picture edges

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008

if IS_WIN:
    from ctypes import wintypes
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        _GetLong = _user32.GetWindowLongPtrW
        _SetLong = _user32.SetWindowLongPtrW
    else:  # pragma: no cover - 32-bit Python
        _GetLong = _user32.GetWindowLongW
        _SetLong = _user32.SetWindowLongW
    _GetLong.argtypes = [wintypes.HWND, ctypes.c_int]
    _GetLong.restype = ctypes.c_ssize_t
    _SetLong.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    _SetLong.restype = ctypes.c_ssize_t
    _user32.GetParent.argtypes = [wintypes.HWND]
    _user32.GetParent.restype = wintypes.HWND
    _user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                     ctypes.c_int, ctypes.c_int, wintypes.UINT]
    _user32.SetWindowPos.restype = wintypes.BOOL
    HWND_TOPMOST = wintypes.HWND(-1)
    HWND_NOTOPMOST = wintypes.HWND(-2)
    SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE, SWP_FRAMECHANGED = 0x1, 0x2, 0x10, 0x20


MAX_LOAD_H = 1440          # the overlay is never taller than the screen (0.9 × 1440): bigger pictures shrink on load


def _fit(img: Image.Image) -> Image.Image:
    if img.height <= MAX_LOAD_H:
        return img
    # BOX: fast and clean for this step; the overlay scales down again with LANCZOS anyway
    return img.resize((max(1, round(img.width * MAX_LOAD_H / img.height)), MAX_LOAD_H), Image.BOX)


def load_frames(path: str, rotation: int = 0):
    """[(PIL RGBA image, duration ms)] – several for animated GIFs; ``rotation``: map turned clockwise (°).
    Pictures taller than MAX_LOAD_H are scaled down (Midwich: 6 × 2000² px = 96 MB otherwise)."""
    im = Image.open(path)
    frames = []
    if getattr(im, "is_animated", False):
        for fr in ImageSequence.Iterator(im):
            d = fr.info.get("duration", 100) or 100
            frames.append((_fit(fr.convert("RGBA")), max(40, int(d))))
    else:
        frames.append((_fit(im.convert("RGBA")), 0))
    return rotate_frames(frames, rotation)


def _prepare(img: Image.Image, height: int, transparent: bool = True) -> Image.Image:
    """Scale to height; fully transparent pixels -> KEY, the rest over a dark backdrop."""
    w = max(1, round(img.width * height / img.height))
    img = img.resize((w, height), Image.LANCZOS)
    alpha = img.getchannel("A")
    base = Image.new("RGBA", img.size, BACKDROP + (255,))
    base.alpha_composite(img)
    out = base.convert("RGB")
    if transparent:
        mask = alpha.point(lambda a: 255 if a < 24 else 0)
        out.paste(KEY_RGB, (0, 0), mask)
    return out


class Overlay:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.win = tk.Toplevel(root)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.configure(bg=KEY)
        self.win.attributes("-topmost", True)
        if IS_WIN:
            self.win.attributes("-transparentcolor", KEY)
        self.caption = tk.Label(self.win, text="", fg="#f2f2f2", bg="#141416", anchor="w",
                                font=("Segoe UI", 10, "bold"), padx=6, pady=1)
        self.pic = tk.Label(self.win, bd=0, bg=KEY, highlightthickness=0)
        self.caption.pack(side="top", anchor="w")
        self.pic.pack(side="top", anchor="w")
        self.timer = tk.Label(self.win, text="", fg="#ffffff", bg="#141416", anchor="center",
                              font=("Segoe UI Black", 24), padx=6, pady=0)
        self.server = tk.Label(self.win, text="", fg="#b2b8f8", bg="#141416", anchor="center",
                               font=("Segoe UI", 11, "bold"), padx=6, pady=2)
        self._timer_text = ""
        self._server_text = ""
        self.ping = tk.Label(self.win, text="", fg="#b2b8f8", bg="#141416", anchor="center",
                             font=("Segoe UI", 11, "bold"), padx=6, pady=1)
        self._ping_text = ""
        self.status = tk.Label(self.win, text="", fg="#ffffff", bg="#141416", anchor="center", justify="center",
                               font=("Segoe UI", 11, "bold"), padx=8, pady=4)
        self._waiting = ()          # lines of the waiting card: shown instead of everything else
        self.note = tk.Label(self.win, text="", fg="#fbbf24", bg="#141416", anchor="center",
                             font=("Segoe UI", 11, "bold"), padx=6, pady=1)
        self._note_text = ""
        self.record = tk.Label(self.win, text="", fg="#b2b8f8", bg="#141416", anchor="center",
                               font=("Segoe UI", 11, "bold"), padx=6, pady=1)
        self._record_text = ""
        self._frames = []           # raw frames
        self._photos = []           # prepared PhotoImages for the current size
        self._frame_i = 0
        self._anim_job = None
        self._floor = None          # frame index of the floor on display; None = all floors one below the other
        self._view = None           # (frames on display, floors stacked) – mapimage.floor_view, cached
        self._height = 0
        self._shown = False
        self._click_through = True
        self._editing = False
        self._drag = None
        self.on_moved = None        # callback(x, y) in screen px after dragging
        self.on_wheel = None        # callback(+1/-1) while editing
        self.opacity = 0.85
        self.transparent = True
        self.last_error = ""
        self._alpha = None
        self.show_caption = True
        self.show_map = True            # off: only timer, server and ping ("nur Infos")
        self._top_job = None
        self.game_hwnd = None           # callable -> HWND of the game (for the Z-order check)
        self.raised_over_game = 0
        self._pos = f"+{OFFSCREEN}+{OFFSCREEN}"
        self.win.geometry(self._pos)
        self.win.deiconify()                  # mapped once now, while our own window has the focus
        self.win.update_idletasks()
        self.root.after(200, self._apply_styles)
        self.root.after(250, lambda: self.root.focus_force())
        self._keep_on_top()
        self.win.bind("<ButtonPress-1>", self._press)
        self.win.bind("<B1-Motion>", self._motion)
        self.win.bind("<ButtonRelease-1>", self._release)
        self.win.bind("<MouseWheel>", self._wheel)

    # ------------------------------------------------------------- content
    def set_map(self, path: str | None, caption: str = "", rotation: int = 0):
        self._stop_anim()
        self._frames = load_frames(path, rotation) if path else []
        self._floor = self._view = None
        self._height = 0
        self.caption.configure(text=caption)
        if self._waiting:
            return                                        # packed again when the waiting card goes
        if self.show_caption and caption and self.show_map:
            self.caption.pack(side="top", anchor="w", before=self.pic)
        else:
            self.caption.pack_forget()

    def set_timer(self, text: str):
        text = text or ""
        if text == self._timer_text:
            return
        self._timer_text = text
        self.timer.configure(text=text)
        self._pack_info()

    def set_server(self, text: str, ping: float | None = None):
        text = text or ""
        ping_text = f"PING {ping:.0f} MS" if ping is not None and text else ""
        if text == self._server_text and ping_text == self._ping_text:
            return
        self._server_text, self._ping_text = text, ping_text
        self.server.configure(text=f"●  {text.upper()}" if text else "")
        if ping is not None:
            from .overlay_win32 import ping_colour
            self.ping.configure(text=ping_text, fg="#%02x%02x%02x" % ping_colour(ping)[:3])
        self._pack_info()

    def set_note(self, text: str):
        """Warning in amber below the timer, e.g. a doubtful detection; "" = none."""
        text = (text or "").upper()
        if text == self._note_text:
            return
        self._note_text = text
        self.note.configure(text=text)
        self._pack_info()

    def set_record(self, text: str):
        """Own results on the map on display ("Ø 2.8 Kills · 12 Runden"); "" = none."""
        text = (text or "").upper()
        if text == self._record_text:
            return
        self._record_text = text
        self.record.configure(text=text)
        self._pack_info()

    def _pack_info(self):
        """Timer (big, centred), server region and ping below the map, in this order."""
        if self._waiting:
            return
        last = self.pic if self.pic.winfo_manager() else None      # info only: no picture above
        for label, shown in ((self.timer, self._timer_text), (self.note, self._note_text),
                             (self.record, self._record_text), (self.server, self._server_text),
                             (self.ping, self._ping_text)):
            label.pack_forget()
            if shown:
                if last is not None:
                    label.pack(side="top", fill="x", after=last)
                else:
                    label.pack(side="top", fill="x")
                last = label

    def set_transparent(self, on: bool):
        """Colour-key transparency around the map (off = dark rectangle behind it)."""
        self.transparent = bool(on)
        self.win.configure(bg=KEY if on else "#%02x%02x%02x" % BACKDROP)
        self.pic.configure(bg=KEY if on else "#%02x%02x%02x" % BACKDROP)
        if IS_WIN:
            self.win.attributes("-transparentcolor", KEY if on else "")
            self._apply_styles()
        self._height = 0                  # re-render with/without key colour

    def set_waiting(self, lines):
        """No map on screen: show only these lines; () = off (map, timer and server come back)."""
        lines = tuple(lines or ())
        if lines == self._waiting:
            return
        was, self._waiting = self._waiting, lines
        if lines:
            for w in (self.caption, self.pic, self.timer, self.note, self.record, self.server, self.ping):
                w.pack_forget()
            self.status.pack(side="top", fill="x")
        elif was:
            self.status.pack_forget()
            self.set_show_map(self.show_map)
            if self.show_caption and self.caption.cget("text") and self.show_map:
                self.caption.pack(side="top", anchor="w", before=self.pic)

    def has_map(self) -> bool:
        return bool(self._frames)

    def floors(self) -> list:
        """Frame indices of the floors of the map (Midwich: bottom, top); [] = one floor."""
        return floor_frames(self._frames)

    def set_floor(self, index):
        """Show this frame (a floor) alone; None = all floors one below the other. The size changes with it:
        applied by the next render()."""
        index = index if index in floor_frames(self._frames) else None
        if index != self._floor:
            self._floor, self._view, self._height = index, None, 0

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
        return bool(self._timer_text or self._server_text or self._note_text or self._record_text)

    def set_show_map(self, on: bool):
        self.show_map = bool(on)
        self._height = 0
        if self._waiting:
            return
        if self.show_map:
            self.pic.pack(side="top", anchor="w")
        else:
            self.pic.pack_forget()
            self.caption.pack_forget()
        self._pack_info()
        self._height = 0

    def _render(self, height: int):
        if height == self._height and self._photos:
            return
        self._height = height
        self._photos = [(ImageTk.PhotoImage(_prepare(img, height, self.transparent)), d)
                        for img, d in self._view_frames()[0]]
        self._frame_i = 0
        self.pic.configure(image=self._photos[0][0])
        self._stop_anim()
        if len(self._photos) > 1:
            self._anim_job = self.root.after(self._photos[0][1], self._next_frame)

    def _next_frame(self):
        if not self._photos:
            return
        self._frame_i = (self._frame_i + 1) % len(self._photos)
        photo, dur = self._photos[self._frame_i]
        self.pic.configure(image=photo)
        self._anim_job = self.root.after(dur, self._next_frame)

    def _stop_anim(self):
        if self._anim_job:
            try:
                self.root.after_cancel(self._anim_job)
            except tk.TclError:
                pass
            self._anim_job = None

    # ------------------------------------------------------------ placement
    def render(self, height: int):
        """Prepare the picture for this height; returns the window size (w, h)."""
        if self._waiting:                     # status lines, then the server once DBD talks to one (lobby)
            extra = [f"●  {self._server_text.upper()}"] if self._server_text else []
            extra += [self._ping_text] if self._ping_text else []
            text = "\n".join([x.upper() for x in self._waiting] + extra)
            if self.status.cget("text") != text:
                self.status.configure(text=text)
            self.win.update_idletasks()
            return self.win.winfo_reqwidth(), self.win.winfo_reqheight()
        if not self._frames:
            return 0, 0
        self._render(max(40, int(height)))
        self.win.update_idletasks()
        return self.win.winfo_reqwidth(), self.win.winfo_reqheight()

    def show_at(self, x: int, y: int):
        if not self._frames and not self._waiting:
            self.hide()
            return
        if self._alpha != self.opacity:
            self.win.attributes("-alpha", self.opacity)
            self._alpha = self.opacity
            self._apply_styles()           # Tk rewrites the extended style on attribute changes
        # The window stays mapped the whole time and is only moved on/off screen:
        # showing a window during the match could otherwise take the keyboard
        # focus away from the game.
        pos = f"+{int(x)}+{int(y)}"
        if pos != self._pos:
            self.win.geometry(pos)
            self._pos = pos
        if not self._shown:
            self._shown = True
            self._apply_styles()

    def hide(self):
        if self._shown:
            self._pos = f"+{OFFSCREEN}+{OFFSCREEN}"
            self.win.geometry(self._pos)
            self._shown = False

    @property
    def shown(self):
        return self._shown

    def hwnd(self) -> int:
        if not IS_WIN:
            return 0
        try:
            return int(self.win.wm_frame(), 16)
        except (tk.TclError, ValueError):
            return int(_user32.GetParent(self.win.winfo_id()) or 0)

    def _apply_styles(self):
        if not IS_WIN:
            return
        h = self.hwnd()
        if not h:
            return
        style = _GetLong(h, GWL_EXSTYLE)
        style |= WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_TOPMOST
        if self._click_through and not self._editing:
            style |= WS_EX_TRANSPARENT | WS_EX_NOACTIVATE      # clicks go to the game
        else:
            style &= ~(WS_EX_TRANSPARENT | WS_EX_NOACTIVATE)   # edit mode: drag + wheel
        _SetLong(h, GWL_EXSTYLE, style)
        _user32.SetWindowPos(h, HWND_TOPMOST, 0, 0, 0, 0,
                             SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED)

    def _keep_on_top(self):
        """Games in borderless mode (and other topmost windows) can end up above
        the overlay; put it back on top once per second."""
        if self._shown and IS_WIN:
            h = self.hwnd()
            if h:
                flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
                _user32.SetWindowPos(h, HWND_TOPMOST, 0, 0, 0, 0, flags)
                game = self.game_hwnd() if self.game_hwnd else None
                if game and is_above(game, h):
                    # the game is topmost itself: re-insert to jump over it
                    _user32.SetWindowPos(h, HWND_NOTOPMOST, 0, 0, 0, 0, flags)
                    _user32.SetWindowPos(h, HWND_TOPMOST, 0, 0, 0, 0, flags)
                    self.raised_over_game += 1
        self._top_job = self.root.after(1000, self._keep_on_top)

    # ------------------------------------------------------------ edit mode
    def set_editing(self, on: bool):
        self._editing = on
        self.win.configure(highlightthickness=3 if on else 0, highlightbackground="#e0b000",
                           highlightcolor="#e0b000")
        self._apply_styles()

    @property
    def editing(self):
        return self._editing

    def _press(self, e):
        if self._editing:
            self.win.focus_force()
            self._drag = (e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y())

    def _motion(self, e):
        if self._editing and self._drag:
            self.win.geometry(f"+{e.x_root - self._drag[0]}+{e.y_root - self._drag[1]}")

    def _release(self, e):
        if self._editing and self._drag:
            self._drag = None
            self._pos = None
            if self.on_moved:
                self.on_moved(self.win.winfo_x(), self.win.winfo_y())

    def _wheel(self, e):
        if self._editing and self.on_wheel:
            self.on_wheel(1 if e.delta > 0 else -1)
