"""Where the overlay's elements are and how big (pure, 1.65): snapping while dragging in the preview, undo of the
last changes and one layout per DBD window size (user: "Feinjustieren, Rückgängig, Layout je Fenstergröße")."""
from __future__ import annotations

import copy

# what a layout is: place and size of the map, the system values / "today" and the music card
OVERLAY_KEYS = ("anchor", "pos_x", "pos_y", "height", "map_heights", "text_scale", "hud_scale", "media_scale",
                "media_pos", "media_xy")
TOP_KEYS = ("sysinfo", "sysinfo_pos", "today_side")
UNDO_KEPT = 50
GESTURE_GAP = 0.8      # s: changes closer together than this are one step (a drag, a row of arrow keys)
SNAP_PX = 6            # px in the preview: this close to a line, an element snaps to it (1.65.2: was 8)


def snapshot(data: dict) -> dict:
    """The layout part of the settings (a copy)."""
    o = data.get("overlay", {})
    snap = {"overlay": {k: copy.deepcopy(o[k]) for k in OVERLAY_KEYS if k in o}}
    snap.update({k: copy.deepcopy(data[k]) for k in TOP_KEYS if k in data})
    return snap


def apply(data: dict, snap: dict) -> None:
    """Put a layout back into the settings (only its own keys)."""
    for k, v in (snap.get("overlay") or {}).items():
        if k in OVERLAY_KEYS:
            data.setdefault("overlay", {})[k] = copy.deepcopy(v)
    for k in TOP_KEYS:
        if k in snap:
            data[k] = copy.deepcopy(snap[k])


class UndoStack:
    """The layouts before the last changes. ``mark()`` before every change: the first one of a gesture keeps the
    state before it, the rest of the gesture (closer than GESTURE_GAP) adds nothing."""

    def __init__(self):
        self._states = []
        self._last = -1e9

    def __len__(self):
        return len(self._states)

    def mark(self, snap: dict, now: float) -> None:
        if now - self._last >= GESTURE_GAP and (not self._states or self._states[-1] != snap):
            self._states.append(snap)
            del self._states[:-UNDO_KEPT]
        self._last = now

    def undo(self, current: dict):
        """The newest layout that differs from ``current`` (it leaves the stack), or None."""
        while self._states:
            snap = self._states.pop()
            if snap != current:
                self._last = -1e9                # the next change is a step of its own again
                return snap
        return None

    def clear(self):
        self._states.clear()
        self._last = -1e9


def size_key(w: int, h: int) -> str:
    return f"{int(w)}x{int(h)}"


def snap_rect(x: float, y: float, w: float, h: float, xs, ys, tol: float):
    """Element at (x, y), w × h, moved so that its left/centre/right edge lies on one of the vertical lines ``xs``
    and its top/centre/bottom on one of ``ys`` when it is within ``tol`` (closest wins). Returns (x, y, line_x,
    line_y) – the lines it snapped to, None where it did not."""
    def best(pos, size, lines):
        hit = None
        for line in lines:
            for off in (0, size / 2, size):
                d = abs(pos + off - line)
                if d <= tol and (hit is None or d < hit[0]):
                    hit = (d, line - off, line)
        return (hit[1], hit[2]) if hit else (pos, None)
    nx, lx = best(x, w, xs)
    ny, ly = best(y, h, ys)
    return nx, ny, lx, ly


def snap_lines(screen, bar, layers, moving):
    """(xs, ys) to snap to: screen edges and centre, the edges of the game picture (black bars) and the edges of
    the other elements."""
    sw, sh = screen
    xs, ys = [0, sw / 2, sw], [0, sh / 2, sh]
    if bar:
        xs += [bar, sw - bar, bar / 2, sw - bar / 2]          # bar edges and bar middles (1.65.2)
    for name, lx, ly, lw, lh in layers:
        if name != moving:
            xs += [lx, lx + lw]
            ys += [ly, ly + lh]
    return xs, ys
