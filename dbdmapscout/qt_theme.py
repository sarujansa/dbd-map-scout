"""Colours and style sheet of the Qt control window (pure, no Qt import: testable without a display).

The palette is the original one of the program (theme.DARK, user's wish 1.51: "Farben wie am Anfang"): greys
#1e1f22 / #2b2d31, gold accent #c9a227, DBD red for selections; the status colours are theme.DOT.
"""
from __future__ import annotations

from .theme import DARK, DOT

PALETTE = {
    True: dict(DARK, card=DARK["panel"], nav=DARK["panel"], nav_sel=DARK["bg"], btn=DARK["hover"],
               btn_hover=DARK["press"], btn_dis="#2b2d31", fg_dis="#6a6e75", on_accent="#1a1406", bar=DARK["field"],
               head="#ffffff", accent_hover="#d8b43a"),
    False: {"bg": "#f3f3f4", "panel": "#ffffff", "field": "#ffffff", "border": "#d6d7da", "fg": "#1b1c1e",
            "dim": "#5f636a", "accent": "#8a6a12", "select": "#7a1f1f", "hover": "#e9eaec", "press": "#dcdde0",
            "card": "#ffffff", "nav": "#e9eaec", "nav_sel": "#f3f3f4", "btn": "#ffffff", "btn_hover": "#e9eaec",
            "btn_dis": "#f3f3f4", "fg_dis": "#a2a5aa", "on_accent": "#ffffff", "bar": "#e4e5e8", "head": "#000000",
            "accent_hover": "#9c7a1a"},
}


def hex_colour(c) -> str:
    """'#rrggbb' from an (r, g, b[, a]) tuple (sysinfo / overlay colours) or a '#rrggbb' string."""
    if isinstance(c, str):
        return c
    return "#{:02x}{:02x}{:02x}".format(*c[:3])


def rgba(colour: str, alpha: float) -> str:
    c = hex_colour(colour).lstrip("#")
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    return f"rgba({r}, {g}, {b}, {round(alpha * 255)})"


def dot_colour(style: str) -> str:
    """Colour of a status kind as used by status.DOT_STYLE ('ok', 'warn', 'err', 'info', 'idle')."""
    return DOT.get(style, DOT["idle"])


def stylesheet(dark: bool, zoom: float = 1.0) -> str:
    """The whole window's QSS. Font sizes in px scale with the setting ui_zoom (Qt adds the screen scaling)."""
    c = PALETTE[bool(dark)]

    def px(size):
        return f"{max(8, round(size * zoom))}px"

    return f"""
* {{ font-family: 'Segoe UI Variable Text', 'Segoe UI', 'Inter', sans-serif; font-size: {px(13)}; color: {c['fg']}; }}
QMainWindow, QWidget#page, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {c['bg']}; }}
QListWidget#nav {{ background: {c['nav']}; border: none; padding: 10px 6px; outline: 0; font-size: {px(14)}; }}
QListWidget#nav::item {{ padding: 8px 12px; border-radius: 6px; margin: 1px 0; color: {c['dim']}; }}
QListWidget#nav::item:selected {{ background: {c['nav_sel']}; color: {c['accent']}; border-left: 3px solid {c['accent']}; }}
QListWidget#nav::item:hover:!selected {{ background: {c['hover']}; color: {c['fg']}; }}
QFrame[class="card"] {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 10px; }}
QFrame[class="card"] QLabel {{ background: transparent; }}
QLabel[class="dim"] {{ color: {c['dim']}; font-size: {px(12)}; }}
QLabel[class="h1"] {{ font-size: {px(24)}; font-weight: 700; color: {c['head']}; }}
QLabel[class="map"] {{ font-family: 'Fira Sans ExtraBold', 'Segoe UI'; font-size: {px(26)}; color: {c['head']}; }}
QLabel[class="h2"] {{ font-size: {px(12)}; font-weight: 700; color: {c['accent']}; letter-spacing: 1px; }}
QLabel[class="kpi"] {{ font-size: {px(24)}; font-weight: 700; color: {c['head']}; }}
QLabel[class="note"] {{ color: {DOT['warn']}; }}
QLabel#thumb {{ background: {DARK['field']}; border-radius: 8px; }}  /* map pictures need a dark backdrop */
QLabel#pill {{ border-radius: 10px; padding: 3px 12px; font-size: {px(12)}; font-weight: 600; }}
QPushButton {{ background: {c['btn']}; border: 1px solid {c['border']}; border-radius: 6px; padding: 6px 14px; }}
QPushButton:hover {{ background: {c['btn_hover']}; }}
QPushButton:pressed {{ background: {c['press']}; }}
QPushButton:disabled {{ background: {c['btn_dis']}; color: {c['fg_dis']}; border-color: {c['btn_dis']}; }}
QPushButton#primary {{ background: {c['accent']}; color: {c['on_accent']}; border: none; font-weight: 700; }}
QPushButton#primary:hover {{ background: {c['accent_hover']}; }}
QProgressBar {{ background: {c['bar']}; border: none; border-radius: 3px; max-height: 6px; min-height: 6px; }}
QProgressBar::chunk {{ background: {c['accent']}; border-radius: 3px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {c['hover']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QToolTip {{ background: {c['panel']}; color: {c['fg']}; border: 1px solid {c['border']}; padding: 4px; }}
"""


def bar_style(colour) -> str:
    """Style of one value bar in the colour of its value (temperature, ping)."""
    return f"QProgressBar::chunk {{ background: {hex_colour(colour)}; border-radius: 3px; }}"


def pill_style(style: str) -> str:
    col = dot_colour(style)
    return f"background: {rgba(col, 0.16)}; color: {col};"
