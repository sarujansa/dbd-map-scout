"""Column chart for the statistics page "Verlauf" (data and geometry; drawn by qt_window.Chart).

One chart per role, each a single series: killer = Ø kills per bucket (axis 0–4), survivor = share escaped
(0–100 %). Thin columns with a rounded top grow from one baseline, hairline grid, only the newest column
carries its value; every column shows its value and the number of rounds on hover. Colours validated
(dataviz palette slots 1/2 against the app's surfaces): blue for killer, orange for survivor.
Temperature (statistics page "System") is a line instead: degrees have no meaningful zero, so the axis starts
near the lowest value – columns from a cut-off baseline would lie about proportions. Aqua (slot 3), validated
against both surfaces (#1e1f22 dark, #f0f0f0 light).
"""
from __future__ import annotations

COLORS = {True: {"killer": "#3987e5", "survivor": "#d95926", "hover_killer": "#6da7ec", "hover_survivor": "#ec835a",
                 "temp": "#199e70", "hover_temp": "#4fc49a", "bp": "#9b7bea", "hover_bp": "#b48cff",
                 "grid": "#3a3c42", "text": "#e3e5e8", "dim": "#9ba1a9"},
          False: {"killer": "#2a78d6", "survivor": "#d95926", "hover_killer": "#5598e7", "hover_survivor": "#e0703f",
                  "temp": "#168f63", "hover_temp": "#1baf7a", "bp": "#6a46c8", "hover_bp": "#7a4fd1",
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


def segments(points):
    """Line pieces between neighbouring points; None (a bucket without rounds) breaks the line."""
    return [(a, b) for a, b in zip(points, points[1:]) if a is not None and b is not None]


class TrendChart:
    """Stacked panels (``panels``: their keys = colour names), drawn by the Qt window (qt_window.Chart).
    ``draw(data)``: data = {key: panel}, panel = {"title", "empty", "ticks": [(value, label)], "max",
    "bars": [(value or None, label, tip)], "last": label of the newest value, optional "kind": "line" with "min"
    (lowest value of the axis)}."""

    def __init__(self, parent, dark: bool, panels=("killer", "survivor")):
        from . import uimodel as ui
        self.dark = dark
        self.panels = tuple(panels)
        self.data = None
        self.widget = ui.Chart(parent, source=self)
        self.widget.pack(fill="both", expand=True)

    def draw(self, data):
        self.data = data
