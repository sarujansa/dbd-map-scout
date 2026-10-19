"""Colours and style sheet of the Qt control window (pure, no Qt import: testable without a display).

The palette is the original one of the program (theme.DARK, user's wish 1.51: "Farben wie am Anfang"): greys
#1e1f22 / #2b2d31, gold accent #c9a227, DBD red for selections; the status colours are theme.DOT.
"""
from __future__ import annotations

import colorsys
import os
import tempfile
from functools import lru_cache

from .i18n import N_
from .theme import DARK, DOT

ZOOMS = (0.9, 1.0, 1.1, 1.25, 1.5)        # setting ui_zoom: text size of the window

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


# Colour themes (since 1.62, user's wish): the accent (and for OLED the dark greys) over the palette above. Every
# accent is checked for contrast (tests/test_qt.py): text on cards >= 4.5:1, text on accent buttons >= 4.5:1.
THEMES = {
    "gold": (N_("Gold (Standard)"), {True: {}, False: {}}),
    "red": (N_("Blutrot"), {
        True: {"accent": "#f07a74", "accent_hover": "#f4938e", "on_accent": "#14070a", "select": "#7a1f1f"},
        False: {"accent": "#a8261f", "accent_hover": "#bf3a33", "on_accent": "#ffffff", "select": "#7a1f1f"}}),
    "blue": (N_("Eisblau"), {
        True: {"accent": "#5aaee8", "accent_hover": "#7cc0ee", "on_accent": "#06121c", "select": "#1d4f80"},
        False: {"accent": "#1d5fa6", "accent_hover": "#2a70bd", "on_accent": "#ffffff", "select": "#1d4f80"}}),
    "green": (N_("Giftgrün"), {
        True: {"accent": "#52c48a", "accent_hover": "#72d4a2", "on_accent": "#04140b", "select": "#1b5e3c"},
        False: {"accent": "#1c7a48", "accent_hover": "#258c55", "on_accent": "#ffffff", "select": "#1b5e3c"}}),
    "violet": (N_("Lila"), {
        True: {"accent": "#b48cf0", "accent_hover": "#c3a2f4", "on_accent": "#12081f", "select": "#4e2f86"},
        False: {"accent": "#6b3fb3", "accent_hover": "#7c50c4", "on_accent": "#ffffff", "select": "#4e2f86"}}),
    "custom": (N_("Eigene Farbe"), None),         # 1.63: settings accent_custom, made readable by derive_accent
}
# The palette below the theme list (1.63, user's wish): one click = this colour as own accent (theme "custom").
# Base colours; derive_accent makes each one readable in dark, light and OLED.
SWATCHES = ("#c9a227", "#e08a1e", "#e8692a", "#d93a32", "#b0203a", "#e0508f", "#c040c0", "#8a5cf0",
            "#4f5fe0", "#2f8fe0", "#1fb5c9", "#17a38a", "#3cae4f", "#8cbf26")
CUSTOM_DEFAULT = "#2f8fe0"
MIN_CONTRAST = 4.5
# OLED black (1.62.1, user: "mit OLED mehr Farbkombis"): a switch of its own, true black instead of the dark greys
# – with every accent; the light mode stays as it is
OLED = {"bg": "#000000", "panel": "#0d0d0f", "field": "#0a0a0b", "card": "#0d0d0f", "nav": "#0d0d0f",
        "nav_sel": "#000000", "btn": "#1a1b1e", "btn_hover": "#26282c", "hover": "#1a1b1e", "press": "#26282c",
        "border": "#26282a", "bar": "#141416", "btn_dis": "#0d0d0f"}
_theme, _oled, _custom = "gold", False, CUSTOM_DEFAULT


def set_theme(key: str, oled: bool = False, custom: str | None = None):
    """The colour theme the window uses from now on (settings color_theme, oled_black, accent_custom; unknown =
    gold, a broken own colour = CUSTOM_DEFAULT)."""
    global _theme, _oled, _custom
    _theme = key if key in THEMES else "gold"
    _oled = bool(oled)
    _custom = norm_hex(custom) or CUSTOM_DEFAULT


def colours(dark: bool) -> dict:
    """The palette of the current theme: PALETTE with the theme's accent over it, OLED black when dark."""
    c = dict(PALETTE[bool(dark)])
    if dark and _oled:
        c.update(OLED)
    if _theme == "custom":
        c.update(derive_accent(_custom, bool(dark), c["card"], c["bg"], c["nav"]))
    else:
        c.update(THEMES[_theme][1][bool(dark)])
    return c


def norm_hex(text) -> str | None:
    """'#rrggbb' (lower case) or None for anything else ('#abc' is widened)."""
    t = str(text or "").strip().lower().lstrip("#")
    if len(t) == 3:
        t = "".join(ch * 2 for ch in t)
    if len(t) != 6 or any(ch not in "0123456789abcdef" for ch in t):
        return None
    return "#" + t


def luminance(colour: str) -> float:
    """Relative luminance (WCAG 2)."""
    c = hex_colour(colour).lstrip("#")
    out = []
    for i in (0, 2, 4):
        v = int(c[i:i + 2], 16) / 255
        out.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _hls_hex(h, lum, s) -> str:
    r, g, b = colorsys.hls_to_rgb(h, min(1.0, max(0.0, lum)), s)
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


@lru_cache(maxsize=64)
def derive_accent(base: str, dark: bool, *backgrounds: str) -> dict:
    """accent / accent_hover / on_accent / select from any colour (1.63, own colour + palette): same hue, the
    lightness moved just as far as needed – accent on every background >= 4.5:1, text on the accent button (and
    its hover) >= 4.5:1, white on the selection >= 4.5:1. A colour that is readable already stays as it is."""
    c = norm_hex(base) or CUSTOM_DEFAULT
    r, g, b = (int(c[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, lum, s = colorsys.rgb_to_hls(r, g, b)
    ink = "#000000" if dark else "#ffffff"           # text on the accent button

    def ok(colour):
        return (all(contrast(colour, bg) >= MIN_CONTRAST for bg in backgrounds)
                and contrast(ink, colour) >= MIN_CONTRAST)

    step = 0.01 if dark else -0.01                   # dark: lighter; light: darker – both end at white / black
    accent = _hls_hex(h, lum, s)
    for _n in range(101):
        if ok(accent):
            break
        lum = min(1.0, max(0.0, lum + step))
        accent = _hls_hex(h, lum, s)
    hover_l = lum + 0.07 if dark else lum - 0.06     # hover away from the background: stays readable
    hover = _hls_hex(h, hover_l, s)
    if contrast(ink, hover) < MIN_CONTRAST:
        hover = accent
    sel_l = 0.30
    select = _hls_hex(h, sel_l, min(s, 0.6))
    while contrast("#ffffff", select) < MIN_CONTRAST and sel_l > 0:
        sel_l -= 0.02
        select = _hls_hex(h, sel_l, min(s, 0.6))
    return {"accent": accent, "accent_hover": hover, "on_accent": ink, "select": select}


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


ICON_DIR = os.path.join(tempfile.gettempdir(), "dbdmapscout-ui")


@lru_cache(maxsize=32)
def ui_icon(name: str, colour: str) -> str:
    """1.8.8: a small picture for the style sheet (``check`` = tick of a ticked box, ``arrow`` = the chevron of a
    choice box) in ``colour``, drawn with Pillow at 16 px and 32 px (Qt takes ``@2x`` on a high-DPI screen); the
    path with forward slashes, "" when it cannot be written (Qt then draws nothing there)."""
    try:
        from PIL import Image, ImageDraw
        os.makedirs(ICON_DIR, exist_ok=True)
        base = os.path.join(ICON_DIR, f"{name}-{hex_colour(colour).lstrip('#')}")
        rgb = tuple(int(hex_colour(colour).lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
        for scale, suffix in ((1, ""), (2, "@2x")):
            size, ss = 16 * scale, 8                           # drawn 8× larger, then scaled down: smooth edges
            big = Image.new("RGBA", (size * ss, size * ss), (0, 0, 0, 0))
            d = ImageDraw.Draw(big)
            u = size * ss / 16
            if name == "check":
                d.line([(3.5 * u, 8.5 * u), (6.5 * u, 11.5 * u), (12.5 * u, 4.5 * u)], fill=rgb + (255,),
                       width=round(2.2 * u), joint="curve")
            else:                                              # arrow: a chevron pointing down
                d.line([(4 * u, 6 * u), (8 * u, 10 * u), (12 * u, 6 * u)], fill=rgb + (255,), width=round(1.8 * u),
                       joint="curve")
            big.resize((size, size), Image.LANCZOS).save(base + suffix + ".png")
        return (base + ".png").replace("\\", "/")
    except Exception:
        return ""


def stylesheet(dark: bool, zoom: float = 1.0) -> str:
    """The whole window's QSS. Font sizes in px scale with the setting ui_zoom (Qt adds the screen scaling)."""
    c = colours(dark)

    def px(size):
        return f"{max(8, round(size * zoom))}px"

    return f"""
* {{ font-family: 'Segoe UI Variable Text', 'Segoe UI', 'Inter', sans-serif; font-size: {px(13)}; color: {c['fg']}; }}
QMainWindow, QWidget#page, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {c['bg']}; }}
QListWidget#nav {{ background: {c['nav']}; border: none; padding: 10px 6px; outline: 0; font-size: {px(14)}; }}
QListWidget#nav::item {{ padding: 8px 12px; border-radius: 6px; margin: 1px 0; color: {c['dim']};
    border-left: 3px solid transparent; }}  /* same place selected or not */
QListWidget#nav::item:selected {{ background: {c['nav_sel']}; color: {c['accent']}; border-left: 3px solid {c['accent']}; }}
QListWidget#nav::item:hover:!selected {{ background: {c['hover']}; color: {c['fg']}; }}
QFrame[class="card"] {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 10px; }}
QFrame[class="card"] QLabel {{ background: transparent; }}
QFrame[class="card"][dragging="true"], QFrame[class="card"][found="true"] {{ border: 1px solid {c['accent']}; }}
QWidget#navside {{ background: {c['nav']}; }}
QLineEdit#navsearch {{ margin: 12px 10px 2px 10px; background: {c['field']}; }}
QPushButton#navsearchbtn {{ background: transparent; border: none; margin-top: 10px; padding: 8px; }}
QPushButton#navsearchbtn:hover {{ background: {c['hover']}; }}
QLabel[class="dim"] {{ color: {c['dim']}; font-size: {px(12)}; }}
QLabel[class="h1"] {{ font-size: {px(24)}; font-weight: 700; color: {c['head']}; }}
QLabel[class="map"] {{ font-family: 'Fira Sans ExtraBold', 'Segoe UI'; font-size: {px(26)}; color: {c['head']}; }}
QLabel[class="h2"] {{ font-size: {px(12)}; font-weight: 700; color: {c['accent']}; letter-spacing: 1px; }}
QLabel[class="big"] {{ font-size: {px(16)}; font-weight: 700; color: {c['head']}; }}
QDialog#message {{ background: {c['bg']}; }}  /* 1.8.44: App._ask/_inform */
QTabWidget::pane {{ border: 1px solid {c['border']}; border-radius: 8px; top: -1px; }}
QTabWidget#formtabs::pane {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 10px; top: -1px;
    border-top-left-radius: 0; }}
QTabWidget#formtabs[found="true"]::pane {{ border: 1px solid {c['accent']}; }}
QTabWidget#formtabs QWidget#page {{ background: {c['card']}; }}
QTabWidget#formtabs > QTabBar::tab {{ font-weight: 600; padding: 8px 16px; }}
QTabBar::tab {{ background: transparent; color: {c['dim']}; padding: 7px 14px; border: none; }}
QTabBar[dense="true"]::tab {{ padding: 7px 11px; }}  /* 1.8.46: rows with many tabs (statistics) */
QTabBar::tab:selected {{ color: {c['accent']}; border-bottom: 2px solid {c['accent']}; }}
QTabBar::tab:hover:!selected {{ color: {c['fg']}; }}
QLabel[class="kpi"] {{ font-size: {px(24)}; font-weight: 700; color: {c['head']}; }}
QLabel[class="sub"] {{ color: {c['dim']}; font-size: {px(11)}; font-weight: 700; letter-spacing: 1px; padding-top: 6px; }}
QLabel[class="note"] {{ color: {DOT['warn']}; }}
QLabel#thumb {{ background: {DARK['field']}; border-radius: 8px; }}  /* map pictures need a dark backdrop */
QFrame[class="tile"] {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 8px; }}
QFrame[class="tile"]:hover {{ background: {c['hover']}; }}
QFrame[class="tile"][current="true"] {{ border: 2px solid {c['accent']}; }}
QFrame[class="tile"] QLabel {{ background: transparent; border: none; }}
QFrame[class="tile"] QLabel#tilepic {{ background: {DARK['field']}; border-radius: 6px; }}
QLabel[class="tile"] {{ font-size: {px(12)}; font-weight: 600; color: {c['head']}; }}
QLabel[class="tileinfo"] {{ font-size: {px(11)}; color: {c['dim']}; }}
QListWidget#realms {{ border: 1px solid {c['border']}; border-radius: 8px; padding: 4px; outline: 0; }}
QListWidget#realms::item {{ padding: 7px 0; border-radius: 6px; }}
QListWidget#realms::item:selected {{ background: {c['nav_sel']}; }}
QListWidget#realms::item:hover:!selected {{ background: {c['hover']}; }}
QLabel#pill {{ border-radius: 10px; padding: 3px 12px; font-size: {px(12)}; font-weight: 600; }}
QPushButton {{ background: {c['btn']}; border: 1px solid {c['border']}; border-radius: 6px; padding: 6px 14px; }}
QPushButton:hover {{ background: {c['btn_hover']}; }}
QPushButton:pressed {{ background: {c['press']}; }}
QPushButton:disabled {{ background: transparent; color: {c['fg_dis']}; border-color: {c['border']}; }}  /* keeps its shape */
QPushButton#primary {{ background: {c['accent']}; color: {c['on_accent']}; border: 1px solid {c['accent']}; font-weight: 700; }}
QPushButton#primary:hover {{ background: {c['accent_hover']}; }}
QPushButton[class="seg"]:checked {{ background: {c['accent']}; color: {c['on_accent']}; border-color: {c['accent']}; font-weight: 700; }}  /* 1.3.3 */
QProgressBar {{ background: {c['bar']}; border: none; border-radius: 3px; max-height: 6px; min-height: 6px; }}
QProgressBar::chunk {{ background: {c['accent']}; border-radius: 3px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {c['hover']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar[idle="true"]::handle:vertical {{ background: transparent; }}
QTreeWidget {{ border: 1px solid {c['border']}; border-radius: 8px; padding: 4px; }}
QTreeWidget::item {{ padding: 3px 6px; }}
QHeaderView::section {{ padding: 3px 6px; }}
QTreeWidget::item:selected {{ background: {c['select']}; color: #ffffff; }}
QLineEdit {{ border: 1px solid {c['border']}; border-radius: 6px; padding: 5px 8px; }}
QLineEdit:focus {{ border-color: {c['accent']}; }}
QComboBox {{ background: {c['btn']}; border: 1px solid {c['border']}; border-radius: 6px; padding: 5px 28px 5px 10px; }}
QComboBox:hover {{ background: {c['btn_hover']}; }}
QComboBox:focus, QComboBox:on {{ border-color: {c['accent']}; }}
QComboBox:disabled {{ background: transparent; color: {c['fg_dis']}; }}
QComboBox:editable {{ background: {c['field']}; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right; width: 24px; border: none; }}
QComboBox::down-arrow {{ image: url("{ui_icon('arrow', c['dim'])}"); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{ background: {c['panel']}; border: 1px solid {c['border']}; padding: 4px; outline: 0;
    selection-background-color: {c['select']}; selection-color: #ffffff; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {c['dim']}; border-radius: 4px;
    background: {c['field']}; }}
QCheckBox::indicator:hover {{ border-color: {c['accent']}; }}
QCheckBox::indicator:checked {{ background: {c['accent']}; border-color: {c['accent']};
    image: url("{ui_icon('check', c['on_accent'])}"); }}
QCheckBox::indicator:disabled {{ border-color: {c['fg_dis']}; background: transparent; }}
QCheckBox::indicator:checked:disabled {{ background: {c['border']}; border-color: {c['border']}; }}
QToolTip {{ background: {c['panel']}; color: {c['fg']}; border: 1px solid {c['border']}; padding: 4px; }}
"""


def palette_roles(dark: bool) -> dict:
    """QPalette roles (name -> colour) for what Qt's Fusion style draws itself: check boxes, sliders, choice
    boxes, text fields and lists – the style sheet only covers cards, buttons and labels."""
    c = colours(dark)
    return {"Window": c["bg"], "WindowText": c["fg"], "Base": c["field"], "AlternateBase": c["panel"],
            "Text": c["fg"], "Button": c["btn"], "ButtonText": c["fg"], "Highlight": c["accent"],
            "HighlightedText": c["on_accent"], "ToolTipBase": c["panel"], "ToolTipText": c["fg"],
            "PlaceholderText": c["dim"], "Light": c["hover"], "Midlight": c["border"], "Mid": c["border"],
            "Dark": c["bg"], "Shadow": "#000000", "BrightText": "#ffffff", "Link": c["accent"]}


def bar_style(colour) -> str:
    """Style of one value bar in the colour of its value (temperature, ping)."""
    return f"QProgressBar::chunk {{ background: {hex_colour(colour)}; border-radius: 3px; }}"


def pill_style(style: str) -> str:
    col = dot_colour(style)
    return f"background: {rgba(col, 0.16)}; color: {col};"
