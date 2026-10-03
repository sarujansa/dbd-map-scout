"""Column chart for the statistics page "Verlauf" (Tk canvas, no extra package).

One chart per role, each a single series: killer = Ø kills per bucket (axis 0–4), survivor = share escaped
(0–100 %). Thin columns with a rounded top grow from one baseline, hairline grid, only the newest column
carries its value; every column shows its value and the number of rounds on hover. Colours validated
(dataviz palette slots 1/2 against the app's surfaces): blue for killer, orange for survivor.
"""
from __future__ import annotations

import tkinter as tk

COLORS = {True: {"killer": "#3987e5", "survivor": "#d95926", "hover_killer": "#6da7ec", "hover_survivor": "#ec835a",
                 "grid": "#3a3c42", "text": "#e3e5e8", "dim": "#9ba1a9"},
          False: {"killer": "#2a78d6", "survivor": "#d95926", "hover_killer": "#5598e7", "hover_survivor": "#e0703f",
                  "grid": "#d4d4d4", "text": "#1b1b1b", "dim": "#5f6368"}}
BAR_MAX = 24                 # px, columns never fill their slot
RADIUS = 4                   # rounded data end
LEFT, RIGHT, TOP, BOTTOM = 54, 12, 40, 34      # chart margins inside one panel (TOP: title + value label)


def columns(n: int, width: float, left: float = LEFT, right: float = RIGHT):
    """[(x0, x1)] of n columns in a panel ``width`` wide: one slot each, the column at most BAR_MAX and
    at most 60 % of the slot (the rest is air)."""
    if n <= 0:
        return []
    slot = max(1.0, (width - left - right) / n)
    w = max(2.0, min(BAR_MAX, slot * 0.6))
    return [(left + slot * i + (slot - w) / 2, left + slot * i + (slot + w) / 2) for i in range(n)]


class TrendChart:
    """Two stacked panels on one canvas. ``draw(data)``: data = {"killer": panel, "survivor": panel},
    panel = {"title", "empty", "ticks": [(value, label)], "max", "bars": [(value or None, label, tip)],
    "last": label of the newest value}."""
    PANEL_H = 180

    def __init__(self, parent, dark: bool, bg: str):
        self.dark = dark
        self.canvas = tk.Canvas(parent, height=2 * self.PANEL_H + 10, background=bg, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.data = None
        self._hits = []            # (x0, y0, x1, y1, item id, role, tip)
        self._hover = None
        self.canvas.bind("<Configure>", lambda e: self._redraw())
        self.canvas.bind("<Motion>", self._motion)
        self.canvas.bind("<Leave>", lambda e: self._motion(None))

    def draw(self, data):
        self.data = data
        self._redraw()

    def _redraw(self):
        c = self.canvas
        c.delete("all")
        self._hits, self._hover = [], None
        if not self.data:
            return
        width = max(200, c.winfo_width())
        for i, role in enumerate(("killer", "survivor")):
            self._panel(role, self.data[role], i * (self.PANEL_H + 10), width)

    def _panel(self, role, p, top, width):
        c, col = self.canvas, COLORS[self.dark]
        c.create_text(8, top + 2, anchor="nw", text=p["title"], fill=col["text"],
                      font=("Segoe UI", 10, "bold"))
        y0, y1 = top + TOP, top + self.PANEL_H - BOTTOM          # value axis: y1 = 0, y0 = max
        if not any(v is not None for v, _l, _t in p["bars"]):
            c.create_text(LEFT, (y0 + y1) / 2, anchor="w", text=p["empty"], fill=col["dim"])
            return
        scale = (y1 - y0) / p["max"]
        for value, label in p["ticks"]:                        # recessive hairline grid + clean ticks
            y = y1 - value * scale
            c.create_line(LEFT, y, width - RIGHT, y, fill=col["grid"])
            c.create_text(LEFT - 6, y, anchor="e", text=label, fill=col["dim"])
        xs = columns(len(p["bars"]), width)
        every = max(1, -(-len(xs) * 46 // max(1, width - LEFT - RIGHT)))   # x labels must not overlap
        newest = max((i for i, (v, _l, _t) in enumerate(p["bars"]) if v is not None), default=None)
        for i, ((value, label, tip), (x0, x1)) in enumerate(zip(p["bars"], xs)):
            if (len(xs) - 1 - i) % every == 0:
                c.create_text((x0 + x1) / 2, y1 + 6, anchor="n", text=label, fill=col["dim"])
            if value is None:
                continue
            item = self._column(x0, x1, y1, y1 - max(2.0, value * scale), col[role])   # 0 stays visible
            if i == newest:                                    # the one direct label
                c.create_text((x0 + x1) / 2, y1 - value * scale - 4, anchor="s", text=p["last"], fill=col["text"])
            slot = (xs[1][0] - xs[0][0]) if len(xs) > 1 else (x1 - x0) * 2
            mid = (x0 + x1) / 2
            self._hits.append((mid - slot / 2, y0 - 10, mid + slot / 2, y1, item, role, tip))

    def _column(self, x0, x1, base, top, color):
        """Column with a rounded data end (radius ≤ 4 px), square at the baseline."""
        r = min(RADIUS, (x1 - x0) / 2, max(0.0, base - top))
        # a repeated point keeps a sharp corner in a smoothed polygon: square at the baseline, round on top
        pts = [x0, base, x0, base, x0, top + r, x0, top, x0 + r, top, x1 - r, top, x1, top, x1, top + r,
               x1, base, x1, base]
        return self.canvas.create_polygon(pts, fill=color, outline="", smooth=True, splinesteps=4,
                                          joinstyle="round") if r >= 1 else \
            self.canvas.create_rectangle(x0, top, x1, base, fill=color, outline="")

    def _motion(self, event):
        c, col = self.canvas, COLORS[self.dark]
        hit = None
        if event is not None:
            hit = next((h for h in self._hits if h[0] <= event.x <= h[2] and h[1] <= event.y <= h[3]), None)
        if hit is self._hover:
            return
        if self._hover is not None:
            c.itemconfigure(self._hover[4], fill=col[self._hover[5]])
            c.delete("tip")
        self._hover = hit
        if hit is None:
            return
        c.itemconfigure(hit[4], fill=col["hover_" + hit[5]])     # the hovered column lifts
        x = min(max(hit[0], LEFT), c.winfo_width() - 230)
        text = c.create_text(x + 8, hit[1] - 2, anchor="nw", text=hit[6], fill=col["text"], tags="tip",
                             font=("Segoe UI", 9, "bold"))
        bx = c.bbox(text)
        if bx:
            box = c.create_rectangle(bx[0] - 6, bx[1] - 3, bx[2] + 6, bx[3] + 3, fill=c.cget("background"),
                                     outline=col["grid"], tags="tip")
            c.tag_lower(box, text)
