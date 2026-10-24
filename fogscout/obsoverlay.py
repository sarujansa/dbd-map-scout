"""1.8.89 (user: "nur das DBD-Fenster aufnehmen und das Overlay im Spiel"): the overlay in the recording.

OBS's window capture of DBD does not contain our overlay – it lives in windows of its own. So the visible elements
(map card, lines, system values, "today", music) are composed into one RGBA picture, written as PNG below cache/,
and OBS shows that file through an image source of its own (obsrec.OVERLAY_SOURCE), placed where the elements lie
over the DBD window (``overlay_transform``). Pure: nothing here talks to OBS or Windows; the ``Writer`` only encodes
and writes, off the GUI thread.
"""
from __future__ import annotations

import os
import threading
import time

from PIL import Image

FILE = os.path.join("cache", "obs-overlay.png")   # below the program folder (a runtime file, gitignored)
EMPTY = (1, 1)                                     # written when nothing is shown: OBS draws nothing
COMPRESS = 1                                       # PNG level: fast (a picture a second while the timer runs)
REPLACE_TRIES = 3                                  # os.replace while OBS reads the file (Windows: sharing violation)

ALIGN_LEFT, ALIGN_RIGHT, ALIGN_TOP, ALIGN_BOTTOM = 1, 2, 4, 8     # OBS alignment bits (0 = centre)
TOP_LEFT = ALIGN_TOP | ALIGN_LEFT


def path(root: str) -> str:
    return os.path.join(os.path.abspath(root), FILE)


def compose(elements):
    """``elements``: [(RGBA picture, (x, y) on screen, opacity 0..1)] → (picture, (x, y, w, h)) of their union, or
    None without a visible element. Each element's alpha is scaled by its opacity – the layered windows show them
    so, and an image source has no opacity of its own."""
    items = [(pic, (int(x), int(y)), float(op)) for pic, (x, y), op in elements
             if pic is not None and pic.width > 0 and pic.height > 0 and op > 0]
    if not items:
        return None
    x0 = min(x for _p, (x, _y), _o in items)
    y0 = min(y for _p, (_x, y), _o in items)
    x1 = max(x + p.width for p, (x, _y), _o in items)
    y1 = max(y + p.height for p, (_x, y), _o in items)
    out = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    for pic, (x, y), op in items:
        if pic.mode != "RGBA":
            pic = pic.convert("RGBA")
        if op < 1.0:
            alpha = pic.getchannel("A").point(lambda v, f=min(1.0, op): int(v * f + 0.5))
            pic = pic.copy()
            pic.putalpha(alpha)
        out.alpha_composite(pic, (x - x0, y - y0))
    return out, (x0, y0, x1 - x0, y1 - y0)


def _edge(pos: float, size: float, align: int, low: int, high: int) -> float:
    """Left/top edge of a box of ``size`` whose alignment point is at ``pos``."""
    if align & low:
        return pos
    if align & high:
        return pos - size
    return pos - size / 2.0


def picture_rect(tf: dict):
    """Where OBS draws the (cropped) source of a scene item: (left, top, scale_x, scale_y, crop_left, crop_top)
    on the canvas, from its sceneItemTransform (GetSceneItemList). None while the source has no size yet."""
    sw, sh = float(tf.get("sourceWidth") or 0), float(tf.get("sourceHeight") or 0)
    cl, cr = float(tf.get("cropLeft") or 0), float(tf.get("cropRight") or 0)
    ct, cb = float(tf.get("cropTop") or 0), float(tf.get("cropBottom") or 0)
    cw, ch = sw - cl - cr, sh - ct - cb
    if cw <= 0 or ch <= 0:
        return None
    align = int(tf.get("alignment") or 0)
    px, py = float(tf.get("positionX") or 0), float(tf.get("positionY") or 0)
    bounds = str(tf.get("boundsType") or "OBS_BOUNDS_NONE")
    if bounds == "OBS_BOUNDS_NONE":
        sx, sy = float(tf.get("scaleX") or 1.0), float(tf.get("scaleY") or 1.0)
        left = _edge(px, cw * sx, align, ALIGN_LEFT, ALIGN_RIGHT)
        top = _edge(py, ch * sy, align, ALIGN_TOP, ALIGN_BOTTOM)
        return left, top, sx, sy, cl, ct
    bw, bh = float(tf.get("boundsWidth") or 0), float(tf.get("boundsHeight") or 0)
    if bw <= 0 or bh <= 0:
        return None
    if bounds == "OBS_BOUNDS_STRETCH":
        sx, sy = bw / cw, bh / ch
    elif bounds == "OBS_BOUNDS_SCALE_OUTER":
        sx = sy = max(bw / cw, bh / ch)
    elif bounds == "OBS_BOUNDS_SCALE_TO_WIDTH":
        sx = sy = bw / cw
    elif bounds == "OBS_BOUNDS_SCALE_TO_HEIGHT":
        sx = sy = bh / ch
    elif bounds == "OBS_BOUNDS_MAX_ONLY":
        sx = sy = min(1.0, bw / cw, bh / ch)
    else:                                               # OBS_BOUNDS_SCALE_INNER (obsrec.Recorder._fit)
        sx = sy = min(bw / cw, bh / ch)
    pw, ph = cw * sx, ch * sy
    bl = _edge(px, bw, align, ALIGN_LEFT, ALIGN_RIGHT)
    bt = _edge(py, bh, align, ALIGN_TOP, ALIGN_BOTTOM)
    balign = int(tf.get("boundsAlignment") or 0)
    left = bl + (0.0 if balign & ALIGN_LEFT else bw - pw if balign & ALIGN_RIGHT else (bw - pw) / 2.0)
    top = bt + (0.0 if balign & ALIGN_TOP else bh - ph if balign & ALIGN_BOTTOM else (bh - ph) / 2.0)
    return left, top, sx, sy, cl, ct


def overlay_transform(window_tf: dict, box):
    """The sceneItemTransform of our overlay picture whose top left lies at ``box`` = (x, y, w, h) relative to
    the DBD window's client area, over the window item drawn with ``window_tf``: same scale, same crop offset.
    None while OBS reports no source size (the capture has not started)."""
    rect = picture_rect(window_tf or {})
    if rect is None:
        return None
    left, top, sx, sy, cl, ct = rect
    return {"positionX": round(left + (float(box[0]) - cl) * sx, 2),
            "positionY": round(top + (float(box[1]) - ct) * sy, 2),
            "scaleX": round(sx, 5), "scaleY": round(sy, 5), "alignment": TOP_LEFT,
            "boundsType": "OBS_BOUNDS_NONE"}


class Writer(threading.Thread):
    """Composes and writes the overlay picture off the GUI thread; the newest request wins. ``on_written(box)``
    runs on this thread after each write with the picture's box relative to the game window, None when nothing
    is shown (a transparent EMPTY picture was written)."""

    def __init__(self, file: str, on_written=None):
        super().__init__(daemon=True, name="obs-overlay")
        self.file = file
        self.on_written = on_written
        self.key = None               # of the last request (equal keys are not written again)
        self.writes = 0
        self.last_error = ""
        self._latest = None
        self._stopping = False       # not _stop: Thread.join() calls self._stop() on Python 3.12
        self._cv = threading.Condition()

    def submit(self, elements, game_xy, key) -> bool:
        """From the GUI thread: the visible elements (see compose) and the game window's origin on screen; ``key``
        says whether anything changed. False = same as last time, nothing to do."""
        if key == self.key:
            return False
        self.key = key
        with self._cv:
            self._latest = (list(elements), (int(game_xy[0]), int(game_xy[1])))
            self._cv.notify()
        return True

    def stop(self):
        with self._cv:
            self._stopping = True
            self._cv.notify()

    def run(self):
        while True:
            with self._cv:
                while self._latest is None and not self._stopping:
                    self._cv.wait()
                if self._stopping:
                    return
                job, self._latest = self._latest, None
            try:
                self._write(*job)
            except Exception as e:                   # never let the thread die; the next change tries again
                self.last_error = f"{type(e).__name__}: {e}"

    def _write(self, elements, game_xy):
        made = compose(elements)
        if made is None:
            pic, box = Image.new("RGBA", EMPTY, (0, 0, 0, 0)), None
        else:
            pic, (x, y, w, h) = made
            box = (x - game_xy[0], y - game_xy[1], w, h)
        os.makedirs(os.path.dirname(self.file) or ".", exist_ok=True)
        tmp = self.file + ".tmp"
        pic.save(tmp, "PNG", compress_level=COMPRESS)
        for i in range(REPLACE_TRIES):
            try:
                os.replace(tmp, self.file)
                break
            except PermissionError:
                if i == REPLACE_TRIES - 1:
                    raise
                time.sleep(0.02)
        self.writes += 1
        if self.on_written is not None:
            self.on_written(box)
