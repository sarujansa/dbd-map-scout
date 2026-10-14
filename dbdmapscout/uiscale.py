"""Control window that follows its size: long texts wrap at the width there is, table columns stretch, and a
zoom for all fonts (setting ``ui_zoom``).

Before 1.48 every hint had a fixed wrap length (~520 px) and every table fixed column widths: a wider window
left empty space, and the narrowest window was as wide as the widest of those fixed widths.
"""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

ZOOMS = (0.9, 1.0, 1.1, 1.25, 1.5)
NAMED_FONTS = ("TkDefaultFont", "TkTextFont", "TkHeadingFont", "TkMenuFont", "TkFixedFont", "TkTooltipFont",
               "TkCaptionFont", "TkSmallCaptionFont", "TkIconFont")
MIN_WRAP = 300           # px: narrowest wrap length a hint gets (the window's minimum width is measured with it)
ROW_HEIGHT = 20          # ttk default row height of tables at zoom 1.0


def wrap_width(parent_width: int, siblings_width: int, pad: int = 16, minimum: int = MIN_WRAP) -> int:
    """Wrap length for a label: the parent's width minus what stands beside it in the same row."""
    return max(minimum, int(parent_width) - int(siblings_width) - pad)


def apply_zoom(root, zoom: float) -> None:
    """Scale the named Tk fonts and the table row height from their sizes at the first call."""
    base = getattr(root, "_dbdms_font_base", None)
    if base is None:
        base = {}
        for name in NAMED_FONTS:
            try:
                base[name] = tkfont.nametofont(name, root=root).cget("size")
            except tk.TclError:
                continue
        root._dbdms_font_base = base
    for name, size in base.items():
        sign = -1 if size < 0 else 1                     # negative = pixels, positive = points
        tkfont.nametofont(name, root=root).configure(size=sign * max(6, round(abs(size) * zoom)))
    style = ttk.Style(root)
    style.configure("Treeview", rowheight=max(16, round(ROW_HEIGHT * zoom)))
    style.configure("Big.TLabel", font=("Segoe UI", max(9, round(13 * zoom)), "bold"))


def wrap_for(label, right_margin: int = 30) -> int | None:
    """Wrap length that lets ``label`` reach the right edge of its window, minus the widgets standing right
    of it in its row. Measured against the window, not the label's frame: a frame that is only as wide as
    the label would otherwise shrink with it on every round (Tk feedback). None while not on screen."""
    if not label.winfo_viewable():
        return None
    top = label.winfo_toplevel()
    right = top.winfo_rootx() + top.winfo_width() - right_margin
    x = label.winfo_x()
    beside = 0
    for w in label.master.winfo_children():
        if w is not label and w.winfo_manager() and w.winfo_x() > x and abs(w.winfo_y() - label.winfo_y()) < 40:
            beside += w.winfo_reqwidth() + 8                # same row, right of the label (e.g. a choice box)
    return wrap_width(right - label.winfo_rootx(), beside, pad=0)


class AutoWrap:
    """Every label with a wrap length below ``root`` wraps at the width there is from now on: after the
    window was resized and when a tab is shown (bundled, at most every 50 ms)."""

    def __init__(self, root):
        self.root = root
        self.labels = []
        self._job = None
        stack = [root]
        while stack:
            w = stack.pop()
            stack.extend(w.winfo_children())
            if isinstance(w, (ttk.Label, tk.Label)):
                try:
                    wl = int(float(str(w.cget("wraplength"))))
                except (tk.TclError, ValueError):
                    continue
                if wl > 0:
                    self.labels.append(w)
        root.bind("<Configure>", lambda e: self.soon(), add="+")

    def soon(self):
        if self._job is None:
            self._job = self.root.after(50, self.update)

    def narrow(self):
        """All labels at the narrowest wrap length – to measure the window's minimum width."""
        for lbl in self.labels:
            lbl.configure(wraplength=MIN_WRAP)

    def update(self):
        self._job = None
        for lbl in self.labels:
            try:
                want = wrap_for(lbl)
                if want is None:
                    continue
                if abs(int(float(str(lbl.cget("wraplength")))) - want) > 4:   # no jitter on tiny changes
                    lbl.configure(wraplength=want)
            except tk.TclError:
                continue


def stretch_tables(root) -> list:
    """Every table column stretches with the window and may shrink down to its heading. Returns
    [(tree, column, designed width)] so the designed widths can be put back after measuring."""
    out = []
    stack = [root]
    while stack:
        w = stack.pop()
        stack.extend(w.winfo_children())
        if not isinstance(w, ttk.Treeview):
            continue
        font = tkfont.nametofont("TkHeadingFont", root=root)
        for col in ("#0",) + tuple(w["columns"]):
            try:
                text = w.heading(col, "text") or ""
                width = int(w.column(col, "width"))
            except tk.TclError:
                continue
            if col == "#0" and "tree" not in str(w.cget("show")):
                continue
            minimum = min(width, max(40, font.measure(text) + 18))
            w.column(col, stretch=True, minwidth=minimum)
            out.append((w, col, width, minimum))
    return out
