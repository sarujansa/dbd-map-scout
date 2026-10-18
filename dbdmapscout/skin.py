"""Overlay styles (1.3, user: "mir gefallen alle 3" of the mock-ups; 1.8.27: one card family – user: "A, aber mit
den Dashboards vom GPU CPU"): the cards of the system values, "today", the music, the map and its lines drawn
with pure Pillow, nothing here touches the screen. Every modern style (glass / chips / line) draws the same
cards – rounded frame, caps header with the accent mark, stat tiles in two columns, chips – and differs only in
its surface (``SURFACES``: fill, edge, radius, shadow, icons). "classic" stays in overlay_win32 (render_hud /
render_music / add_info); the HUD windows and the preview call ``card()`` / ``music()`` / ``map_card()`` for
every other style.

Everything scales with ``height`` (the game height, 1440 = the user's screen): ``u = height / 1440`` is one
"design pixel" of the mock-ups. Text is set in Inter (dbdmapscout/fonts/, OFL, subsets of four weights) through the
glyph cache of overlay_win32 (``_draw_run``) – a card costs a few milliseconds, cheap enough once a second.
"""
from __future__ import annotations

import os
import re
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .i18n import N_
from .overlay_win32 import _draw_run, _run_len, cover_radius, fira

STYLES = ("classic", "glass", "chips", "line")
STYLE_LABELS = [("classic", N_("Klassisch")), ("glass", N_("Glas-Karten")), ("chips", N_("Chips & Icons")),
                ("line", N_("Minimal Line"))]
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
WEIGHTS = ("Regular", "Medium", "SemiBold", "Bold")

GOLD = (212, 166, 58, 255)              # accent when the window's theme is not known
WHITE = (255, 255, 255, 255)
GREY = (160, 166, 180, 255)             # secondary text
DIMG = (120, 126, 140, 255)             # labels
# 1.8.29 (user: "ich seh die Umrandung der Map nicht"): on the black bar a (16, 17, 22) card with a 1-px edge
# at alpha 40 vanished – lighter fills, stronger and (at 1440p) 2-px edges
GLASS_FILL = (24, 26, 33, 212)
GLASS_EDGE = (255, 255, 255, 78)
LINE_EDGE = (255, 255, 255, 90)
HAIRLINE = (255, 255, 255, 28)
TRACK = (255, 255, 255, 35)             # the empty part of a bar
CHIP_FILL = (28, 30, 38, 222)
CHIP_EDGE = (255, 255, 255, 96)
WRAP_SHARE = 0.28                       # chips wrap at this share of the game height (≈ the black bar at 1440p)
ICONS = {"CPU": "cpu", "GPU": "gpu", "RAM": "ram", "VRAM": "ram", "HOTSPOT": "gpu", "MEM": "ram"}
_PERCENT = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*%\s*$")
_RATIO = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)")


@lru_cache(maxsize=64)
def inter(weight: str, size: int):
    """Inter in ``weight`` (Regular/Medium/SemiBold/Bold) at ``size`` px; Fira Sans when the file is missing."""
    path = os.path.join(FONT_DIR, f"Inter-{weight}.otf")
    try:
        return ImageFont.truetype(path, max(6, int(size)))
    except OSError:
        return fira(max(6, int(size)))


def accent_rgba(colour) -> tuple:
    """"#rrggbb" / (r, g, b[, a]) / None -> RGBA tuple (None = GOLD)."""
    if colour is None:
        return GOLD
    if isinstance(colour, str):
        c = colour.lstrip("#")
        if len(c) == 6:
            return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
        return GOLD
    c = tuple(int(v) for v in colour)
    return c if len(c) == 4 else c[:3] + (255,)


# ------------------------------------------------------------------ rows -> pairs
def nice(text: str) -> str:
    """Labels and values of the classic rows are set in capitals; the modern styles use mixed case: words in
    capitals longer than four letters become capitalised ("ENTKOMMEN" -> "Entkommen"), short ones stay (CPU, GB)."""
    out = []
    for word in text.split(" "):
        letters = [ch for ch in word if ch.isalpha()]
        if len(letters) > 4 and all(ch.isupper() for ch in letters):
            word = word[:1] + word[1:].lower()
        out.append(word)
    return " ".join(out)


def fraction(values) -> float | None:
    """A bar's share from the values of a row: "38 %" -> 0.38, "7.9 / 12 GB" -> 0.66, else None."""
    for text, _c in values:
        m = _PERCENT.match(text)
        if m:
            return max(0.0, min(1.0, float(m.group(1).replace(",", ".")) / 100))
        m = _RATIO.match(text)
        if m:
            total = float(m.group(2).replace(",", "."))
            return max(0.0, min(1.0, float(m.group(1).replace(",", ".")) / total)) if total > 0 else None
    return None


def pairs(row, dim) -> list:
    """One classic row [(text, colour), ...] -> [(label, [(value, colour), ...]), ...]: a dim segment opens a
    pair, " · " separators fall away, values keep their colour (temperatures are coloured)."""
    out = []
    label, values = "", []
    for text, colour in row:
        if colour == dim and text.strip() in ("·", "-", "–", ""):
            continue
        if colour == dim:
            if values or label:
                out.append((label, values))
            label, values = text.strip().rstrip(":"), []
        else:
            values.append((text.strip(), colour))
    if values or label:
        out.append((label, values))
    return out


def card_model(rows, dim, title=None) -> tuple:
    """(title, lines) of a card from classic rows: ``lines`` = [(label, values, frac)], ``title`` the given one or
    the first row's label when it has no values of its own in the other pairs ("HEUTE 4 Runden · 1:12 h" -> title
    HEUTE, first line the values without label)."""
    lines = []
    for row in rows:
        for label, values in pairs(row, dim):
            lines.append((label, values, fraction(values)))
    if title is None and lines and lines[0][0]:
        title = lines[0][0]
        lines[0] = ("", lines[0][1], lines[0][2])
    return (title or ""), lines


# ------------------------------------------------------------------ drawing helpers
SHADOW_STEP = 4                   # the drop shadow is blurred this many times smaller (1.3.5)

def _panel(w: int, h: int, radius: int, fill, edge, width: int = 1) -> Image.Image:
    im = Image.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=max(1, radius), fill=fill,
                                         outline=edge, width=max(1, width))
    return im


SHADOWS_KEPT = 48                 # 1.8.31: shadows by card frame – blurred once, not on every redraw
_SHADOWS: dict = {}


def shadowed(card: Image.Image, u: float, key=None, shape=None) -> Image.Image:
    """The card on its soft drop shadow (glass and chips); the margin belongs to the picture. ``key`` (1.8.31): the
    shadow depends only on the card's frame – with a key it is blurred once per (size, key) and kept, made from
    ``shape()`` (the frame's alpha) instead of the card's own alpha (whose text changes every second)."""
    blur = max(2, int(8 * u))
    off = max(1, int(4 * u))
    ck = (card.size, round(u, 4), key) if key is not None else None
    sh = _SHADOWS.get(ck) if ck is not None else None
    if sh is None:
        sh = _shadow(card.size, shape() if shape is not None else card.getchannel("A"), blur, off)
        if ck is not None:
            _SHADOWS[ck] = sh
            while len(_SHADOWS) > SHADOWS_KEPT:
                _SHADOWS.pop(next(iter(_SHADOWS)))
    out = sh.copy()
    out.alpha_composite(card, (2 * blur, 2 * blur))
    return out


def _shadow(size, alpha, blur: int, off: int) -> Image.Image:
    """The soft shadow alone, as an RGBA picture the size of the finished card."""
    w, h = size
    mask = Image.new("L", (w + 4 * blur, h + 4 * blur), 0)
    mask.paste(alpha.point(lambda v: v * 120 // 255), (2 * blur, 2 * blur + off))
    # 1.3.5: a soft shadow is blurred on a picture SHADOW_STEP times smaller and scaled back (17 -> 6 ms; it is
    # drawn every second with the timer – at most 5 of 255 apart from the full-size blur)
    k = SHADOW_STEP if blur >= 2 * SHADOW_STEP else 1
    if k > 1:
        mask = mask.resize((max(1, mask.width // k), max(1, mask.height // k)), Image.BOX) \
            .filter(ImageFilter.GaussianBlur(blur / k)).resize(mask.size, Image.BILINEAR)
    else:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    sh = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    sh.putalpha(mask)
    return sh


def _text(im, x, y, text, font, fill, track: float = 0) -> float:
    return _draw_run(im, x, y, text, font, fill, 0, None, track)


def _width(font, text, track: float = 0) -> float:
    return _run_len(font, text) + track * max(0, len(text) - 1)


def _widest(timer: str) -> str:
    """The timer with every digit a "0" (the widest in Inter and Fira): measured with it, the field keeps one
    size and place while the seconds run (1.5.4, user: "wird immer grösser und kleiner")."""
    return re.sub(r"\d", "0", timer or "")


def _caps(im, x, y, text, size, fill, u):
    """Small capitals with wide tracking (headers of "line", labels)."""
    f = inter("Medium", size)
    return _text(im, x, y, text.upper(), f, fill, 3 * u)


def _values_width(values, font, gap) -> float:
    return sum(_width(font, t) for t, _c in values) + gap * max(0, len(values) - 1)


def _values_right(im, right, y, values, font, gap):
    x = right
    for text, colour in reversed(values):
        x -= _width(font, text)
        _text(im, x, y, text, font, colour)
        x -= gap


def _dot(d, x, y, r, colour):
    d.ellipse((x - r, y - r, x + r, y + r), fill=colour)


def _bar(d, x, y, w, frac, colour, u):
    h = max(2, int(5 * u))
    d.rounded_rectangle((x, y, x + w, y + h), radius=h // 2, fill=TRACK)
    d.rounded_rectangle((x, y, x + max(h, int(w * frac)), y + h), radius=h // 2, fill=colour)


def _icon(d, kind, x, y, u, colour=GREY):
    """Little line icons of the chips style (CPU chip, GPU card, RAM bars) in a 20u box."""
    s = lambda v: int(v * u)                                   # noqa: E731
    w = max(1, int(2 * u))
    if kind == "cpu":
        d.rounded_rectangle((x + s(3), y + s(3), x + s(17), y + s(17)), radius=s(3), outline=colour, width=w)
        d.rectangle((x + s(7), y + s(7), x + s(13), y + s(13)), fill=colour)
        for i in (5, 10, 15):
            d.line((x + s(i), y, x + s(i), y + s(3)), fill=colour, width=w)
            d.line((x + s(i), y + s(17), x + s(i), y + s(20)), fill=colour, width=w)
    elif kind == "gpu":
        d.rounded_rectangle((x, y + s(4), x + s(20), y + s(16)), radius=s(3), outline=colour, width=w)
        d.ellipse((x + s(10), y + s(6), x + s(18), y + s(14)), outline=colour, width=w)
        d.line((x + s(2), y + s(16), x + s(2), y + s(20)), fill=colour, width=w)
    else:
        for i in range(4):
            d.rectangle((x + s(i * 5), y + s(4), x + s(i * 5 + 3), y + s(16)), fill=colour)


def _round_cover(cover, side: int, radius: int) -> Image.Image:
    if radius <= 0:                                 # 1.8.24: square corners chosen
        return _square_cover(cover, side)
    memo = cover.info if isinstance(getattr(cover, "info", None), dict) else {}
    key = ("_dbdms_round", side, radius)            # 1.6.1: once per cover and size, not every second
    if key in memo:
        return memo[key]
    art = _square_cover(cover, side).copy()
    mask = Image.new("L", (side, side), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, side - 1, side - 1), radius=radius, fill=255)
    art.putalpha(mask)
    memo[key] = art
    return art


def _square_cover(cover, side: int) -> Image.Image:
    memo = cover.info if isinstance(getattr(cover, "info", None), dict) else {}
    key = ("_dbdms_square", side)
    if key not in memo:
        memo[key] = cover.convert("RGBA").resize((side, side), Image.LANCZOS)
    return memo[key]


def _fit_text(text, weight, size, max_w, min_scale=0.6) -> tuple:
    """(font, text) so that the text is no wider than ``max_w``: smaller first, then cut with an ellipsis."""
    font = inter(weight, size)
    if _width(font, text) <= max_w:
        return font, text
    small = inter(weight, max(6, int(size * min_scale)))
    f = max(min_scale, max_w / max(1, _width(font, text)))
    font = inter(weight, max(6, int(size * f)))
    if _width(font, text) <= max_w:
        return font, text
    while len(text) > 1 and _width(small, text + "…") > max_w:
        text = text[:-1].rstrip()
    return small, text + "…"


# ------------------------------------------------------------------ one card family (1.8.27)
# 1.8.27 (user: "A, aber mit den Dashboards vom GPU CPU" – one card family for every element): every modern style
# draws the same cards – a rounded frame, a small caps header with the accent mark, stat tiles in two columns,
# chips for server / record – and differs only in its surface: fill, edge, radius, shadow (and icons on the system
# tiles for "chips"). ``u`` = design pixel (1 at 1440p).
SURFACES = {
    "glass": dict(fill=GLASS_FILL, edge=GLASS_EDGE, radius=16, tile=(255, 255, 255, 14), tile_edge=(255, 255, 255, 22),
                  tile_radius=10, shadow=True, icons=False),
    "chips": dict(fill=CHIP_FILL, edge=CHIP_EDGE, radius=24, tile=(255, 255, 255, 20), tile_edge=(255, 255, 255, 34),
                  tile_radius=16, shadow=True, icons=True),
    "line": dict(fill=(0, 0, 0, 0), edge=LINE_EDGE, radius=10, tile=(0, 0, 0, 0), tile_edge=(255, 255, 255, 60),
                 tile_radius=6, shadow=False, icons=False),
}
PAD = 16                                # inner margin of every card (design px)
HEAD_H = 20                             # height of the caps header
TILE_GAP = 8                            # between tiles and chips
CARD_MIN_W = 300                        # the tile cards (system values, today) are at least this wide
CARD_MAX_W = int(WRAP_SHARE * 1440)     # … and never wider than the black bar at 1440p (403)
GREEN = (74, 222, 128, 255)             # the server dot
BAR_IDLE = (255, 255, 255, 110)         # a tile's bar below the warning share
BAR_HOT = 0.85                          # a share from here on is drawn in the accent


def surface(style: str) -> dict:
    return SURFACES.get(style, SURFACES["glass"])


EDGE_W = 1.5                            # px of a card's edge at 1440p (2 px there, 1 px on small pictures)


def _frame(w, h, style, u) -> Image.Image:
    s = surface(style)
    return _panel(int(w), int(h), int(s["radius"] * u), s["fill"], s["edge"], max(1, round(EDGE_W * u)))


def _finish(im, style, u) -> Image.Image:
    """The card on its drop shadow where the style has one – the shadow of its frame, kept per size (1.8.31)."""
    if not surface(style)["shadow"]:
        return im
    return shadowed(im, u, ("frame", style), lambda: _frame(im.width, im.height, style, u).getchannel("A"))


def _header_w(text, u, mark=True) -> float:
    return _width(inter("Medium", int(11 * u)), text.upper(), 2.5 * u) + (int(10 * u) if mark else 0)


def _header(im, x, y, text, u, acc, mark=True) -> int:
    """Caps header with the accent mark – the signature every card shares; returns the y below it."""
    if mark:
        ImageDraw.Draw(im).rounded_rectangle((x, y + int(2 * u), x + int(3 * u), y + int(14 * u)),
                                             radius=max(1, int(u)), fill=acc)
        x += int(10 * u)
    _text(im, x, y, text.upper(), inter("Medium", int(11 * u)), GREY, 2.5 * u)
    return y + int(HEAD_H * u)


def _hairline(im, x0, x1, y):
    ImageDraw.Draw(im).line((x0, y, x1, y), fill=HAIRLINE, width=1)


def _fit_caps(text, size, max_w, u) -> tuple:
    """(font, TEXT, tracking) of small capitals no wider than ``max_w``: smaller first, then cut."""
    track = 2 * u
    f = inter("Medium", size)
    t = text.upper()
    if _width(f, t, track) <= max_w:
        return f, t, track
    scale = max(0.7, max_w / max(1, _width(f, t, track)))
    f = inter("Medium", max(6, int(size * scale)))
    while len(t) > 1 and _width(f, t + "…", track) > max_w:
        t = t[:-1].rstrip()
    return f, (t if _width(f, t, track) <= max_w else t + "…"), track


def _tile(w, h, value, label, u, style, acc, frac=None, colour=WHITE, bar_colour=None, icon=None) -> Image.Image:
    """Stat tile: big value, caps label below, optional mini bar (and the style's icon top right)."""
    s = surface(style)
    im = _panel(int(w), int(h), int(s["tile_radius"] * u), s["tile"], s["tile_edge"])
    d = ImageDraw.Draw(im)
    x = int(12 * u)
    inner = w - 2 * x - (int(26 * u) if icon else 0)
    vf, value = _fit_text(value, "SemiBold", int(24 * u), max(10, inner))
    if label:
        _text(im, x, int(8 * u), value, vf, colour)
        lf, lt, tr = _fit_caps(label, int(10 * u), w - 2 * x, u)
        _text(im, x, int(40 * u), lt, lf, GREY, tr)
    else:                                            # a warning: the text alone, centred
        _text(im, x, (h - vf.size) / 2 - 3 * u, value, vf, colour)
    if icon:
        _icon(d, icon, w - x - int(20 * u), int(8 * u), u, DIMG)
    if frac is not None:
        _bar(d, x, h - int(12 * u), w - 2 * x, frac, bar_colour or acc, u)
    return im


def tile_model(label, values, frac, dim) -> dict:
    """What one line of card_model shows as a tile: ``value`` (big), ``label`` (caps), ``frac`` (bar), ``colour``
    of the value, ``warn`` (a warning stands alone across the card), ``hot`` (a coloured value: bar in the accent).
    "CPU 64°C · 38 %" -> 64°C / CPU · 38 % with a bar of 0.38; "VRAM 7.9 / 12 GB" -> 7.9 GB / VRAM / 12 GB;
    "4 RUNDEN · 1:12 h" (no label) -> 4 / Runden · 1:12 h; "GPU DROSSELT (TEMP.)" (coloured, no label) -> warning."""
    if not values:
        return dict(value=nice(label), label="", frac=frac, colour=WHITE, warn=False, hot=False)
    first, rest = values[0], values[1:]
    colour = first[1] if first[1] != dim else WHITE
    hot = colour not in (WHITE, dim)
    if not label:
        text = " · ".join(nice(t) for t, _c in values)
        if len(values) == 1 and hot:
            return dict(value=text, label="", frac=None, colour=colour, warn=True, hot=True)
        head, _sp, tail = text.partition(" ")
        if tail and any(ch.isdigit() for ch in head):
            return dict(value=head, label=tail, frac=frac, colour=colour, warn=False, hot=hot)
        return dict(value=text, label="", frac=frac, colour=colour, warn=False, hot=hot)
    m = _RATIO.match(first[0])
    if m and not rest:
        unit = first[0][m.end():].strip()
        return dict(value=f"{m.group(1)} {unit}".strip(), label=f"{nice(label)} / {m.group(2)} {unit}".strip(),
                    frac=frac, colour=colour, warn=False, hot=hot)
    text = nice(label) + (" · " + " · ".join(nice(t) for t, _c in rest) if rest else "")
    return dict(value=nice(first[0]), label=text, frac=frac, colour=colour, warn=False, hot=hot)


# ------------------------------------------------------------------ the cards (system values, today)
def card(rows, height: int, style: str, accent=None, title=None, dim=None, min_w: int = 0) -> Image.Image:
    """System values / "today" in ``style`` (glass | chips | line) from the classic rows of sysinfo.hud_rows /
    today_rows: a header and one stat tile per value in two columns (1.8.27, the user's pick: "the dashboards
    of GPU / CPU"); ``title`` for the header ("SYSTEM" for the values; None = the first row's label, "today").
    The card is ``CARD_MIN_W`` wide whatever the values say (1.8.28, user: nothing may move when a value gets
    longer or shorter) – texts are fitted into their tiles; ``min_w`` widens it (the App's steady width)."""
    from .sysinfo import DIM
    dim = dim or DIM
    u = max(0.25, height / 1440)
    acc = accent_rgba(accent)
    head, lines = card_model(rows, dim, title)
    if not lines:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    tiles = [tile_model(lab, vals, fr, dim) for lab, vals, fr in lines]
    return _finish(_tiles_card(head, tiles, u, acc, style, min_w), style, u)


def _tiles_card(head, tiles, u, acc, style, min_w=0) -> Image.Image:
    pad, gap = int(PAD * u), int(TILE_GAP * u)
    icons = surface(style)["icons"]
    th = int((64 if any(t["frac"] is not None for t in tiles) else 56) * u)
    head_w = _header_w(head, u) if head else 0
    shadow = 4 * max(2, int(8 * u)) if surface(style)["shadow"] else 0      # min_w counts the finished picture
    w = int(max(CARD_MIN_W * u, min(CARD_MAX_W * u, head_w + 2 * pad), min_w - shadow))
    tw = (w - 2 * pad - gap) // 2
    rows, pair = [], []                              # a warning spans the card, the rest go in pairs
    for t in tiles:
        if t["warn"]:
            if pair:
                rows.append(pair)
                pair = []
            rows.append([t])
        else:
            pair.append(t)
            if len(pair) == 2:
                rows.append(pair)
                pair = []
    if pair:
        rows.append(pair)
    top = pad + (int(HEAD_H * u) + int(6 * u) if head else 0)
    h = top + len(rows) * th + (len(rows) - 1) * gap + pad
    im = _frame(w, h, style, u)
    if head:
        _header(im, pad, pad, head, u, acc)
    y = top
    for row in rows:
        full = len(row) == 1
        for i, t in enumerate(row):
            hot = t["frac"] is not None and (t["frac"] >= BAR_HOT or t["hot"])
            icon = ICONS.get(t["label"].upper().split()[0]) if icons and t["label"] else None
            pic = _tile(w - 2 * pad if full else tw, th, t["value"], t["label"], u, style, acc, t["frac"],
                        t["colour"], acc if hot else BAR_IDLE, icon)
            im.alpha_composite(pic, (pad + i * (tw + gap), y))
        y += th + gap
    return im


def chip(text, u, font=None, colour=WHITE, dot=None, edge=CHIP_EDGE, pad=None, h=None, width_text=None,
         fill=CHIP_FILL) -> Image.Image:
    """``width_text``: size the pill for this text instead (the timer: widest digits – the pill never changes)."""
    font = font or inter("SemiBold", int(16 * u))
    pad = int(14 * u) if pad is None else pad
    h = int(38 * u) if h is None else h
    w = int(_width(font, width_text if width_text is not None else text)) + 2 * pad + (int(18 * u) if dot else 0)
    im = _panel(w, h, h // 2, fill, edge)
    d = ImageDraw.Draw(im)
    x = pad
    if dot:
        _dot(d, x + int(4 * u), h // 2, int(5 * u), dot)
        x += int(18 * u)
    _text(im, x, (h - font.size) / 2 - 3 * u, text, font, colour)
    return im


def chip_rows(chips, max_w: int, gap: int) -> Image.Image:
    """Chips in rows no wider than ``max_w`` (a chip wider than that stands alone), centred."""
    rows, row, w = [], [], 0
    for c in chips:
        if row and w + gap + c.width > max_w:
            rows.append(row)
            row, w = [], 0
        row.append(c)
        w += (gap if len(row) > 1 else 0) + c.width
    if row:
        rows.append(row)
    widths = [sum(c.width for c in r) + gap * (len(r) - 1) for r in rows]
    heights = [max(c.height for c in r) for r in rows]
    im = Image.new("RGBA", (max(widths), sum(heights) + gap * (len(rows) - 1)), (0, 0, 0, 0))
    y = 0
    for r, rw, rh in zip(rows, widths, heights):
        x = (im.width - rw) // 2
        for c in r:
            im.alpha_composite(c, (x, y + (rh - c.height) // 2))
            x += c.width + gap
        y += rh + gap
    return im


# ------------------------------------------------------------------ the music card
BIG_COVER = 200                         # side of the big cover in design pixels (≈ classic "Groß" at 1440p)
SMALL_COVER = 64                        # cover of the compact card


def music(rows, cover, height: int, style: str, progress=None, look=(), accent=None,
          layout: str = "compact", upnext=None, upnext_pos: str = "below", anim=None,
          min_w: int = 0, min_h: int = 0) -> Image.Image:
    """"Läuft gerade" in ``style``: ``rows`` as media.rows gives them ([[(title, white)], [(artist, dim)]]),
    ``progress`` = (elapsed, total) s or None, ``look`` as media.look (``remaining`` = time left on the right,
    ``accent`` = bar in the cover's colour – else the theme's accent). ``layout`` = overlay.media_style:
    "big" (1.3.2, user: the big cover stayed small in the new styles) = cover large on top, text centred below;
    "compact" = cover left. ``upnext`` (1.8) = (label, ((title, artist), …)) of the Spotify queue: below the
    progress inside the card (1.8.27) or as a second panel to its right (``upnext_pos``). ``min_w`` (1.8.28):
    the finished picture is at least this wide – the card (or, with the list on the right, the list's panel)
    fills the width, so a shorter title or queue never moves anything; ``min_h`` (1.8.30) the same for the
    height – a song change without cover or list for a moment keeps the card's size."""
    u = max(0.25, height / 1440)
    acc = accent_rgba(accent)
    if "accent" in look and cover is not None:
        from .media import accent as cover_accent
        acc = accent_rgba(cover_accent(cover)) if cover_accent(cover) else acc
    texts = ["".join(t for t, _c in row) for row in rows]
    title = texts[0] if texts else ""
    artist = texts[1] if len(texts) > 1 else ""
    big = layout == "big" and cover is not None
    items = list(upnext[1]) if upnext and upnext[1] else []
    label = upnext[0] if items else ""
    inside = (label, items, anim) if items and upnext_pos != "right" else None
    right = bool(items and upnext_pos == "right")
    shadow = 4 * max(2, int(8 * u)) if surface(style)["shadow"] else 0
    im = _finish(_music_body(title, artist, cover, u, acc, progress, look, style, big, inside,
                             0 if right else min_w - shadow, min_h - shadow), style, u)
    if right:                                        # 1.8.24: as many rows as fit beside the card
        items = items[:upnext_fit(label, len(items), im.height, u)]
        gap = int(8 * u)
        panel = upnext_panel(label, items, u, style, anim, min_w - im.width - gap - shadow)
        im = _attach(im, panel, "right", gap, centred=big)
    return im


BODIES_KEPT = 6                         # 1.8.31: music cards without their progress, by song and size
_BODIES: dict = {}


def _music_body(title, artist, cover, u, acc, progress, look, style, big, inside, min_w=0, min_h=0) -> Image.Image:
    """The music card without its shadow: cover on top (``big``) or left, title, artist, progress with the time
    left, and the queue (``inside`` = (label, items, anim)) below a hairline; at least ``min_w`` wide. 1.8.31: all
    but the progress is drawn once per song and size (``_BODIES``) – each second only the bar and the time."""
    tail = _progress_text(progress, look)
    sf = inter("Medium", int(12 * u))
    # the field of the time is measured with the widest digits of the song's length: the bar's end never moves
    # while the seconds run or the minutes lose a digit (1.8.28)
    tail_w = int(_width(sf, _widest(_progress_text((progress[1], progress[1]), look)))) + int(8 * u) if tail else 0
    anim = inside[2] if inside else None
    key = (title, artist, id(cover), round(u, 4), acc, tuple(look), style, big,
           (inside[0], tuple(tuple(i) for i in inside[1])) if inside else None, int(min_w), int(min_h),
           bool(progress), tail_w)
    hit = None if anim else _BODIES.get(key)
    if hit is None:
        hit = _music_base(title, artist, cover, u, progress, look, style, big, inside, min_w, min_h, tail_w) + \
            (cover,)                                     # (the cover kept: its id stays unique while cached)
        if not anim:
            _BODIES[key] = hit
            while len(_BODIES) > BODIES_KEPT:
                _BODIES.pop(next(iter(_BODIES)))
    base, bar_x, bar_y, _cover = hit
    if not progress:
        return base if anim else base.copy()
    im = base.copy()
    el, total = progress
    w, pad = im.width, int(PAD * u)
    _bar(ImageDraw.Draw(im), bar_x, bar_y, w - pad - bar_x - tail_w, min(1.0, el / max(1, total)), acc, u)
    if tail:
        _text(im, w - pad - tail_w + int(8 * u), bar_y - int(6 * u), tail, sf, GREY)
    return im


def _music_base(title, artist, cover, u, progress, look, style, big, inside, min_w, min_h, tail_w):
    """(card without the progress, bar x, bar y) – the part of the music card that stays while a song plays."""
    pad = int(PAD * u)
    line = style == "line"
    if big:
        side = int(BIG_COVER * u)
        max_w = max(side, int(WRAP_SHARE * 1440 * u) - 2 * pad)
        tf, title = _fit_text(title, "SemiBold", int(20 * u), max_w)
        af, artist = _fit_text(artist, "Medium", int(15 * u), max_w) if artist else (inter("Medium", int(15 * u)), "")
        w = int(max(side, _width(tf, title), _width(af, artist), 160 * u)) + 2 * pad
        text_x = pad
        body_h = pad + side + int(14 * u) + int(26 * u) + (int(22 * u) if artist else 0) + (int(24 * u) if progress else 0)
    else:
        side = int(SMALL_COVER * u) if cover is not None else 0
        text_x = pad + side + (int(14 * u) if cover is not None else 0)
        max_w = int(WRAP_SHARE * 1440 * u) - text_x - pad
        tf, title = _fit_text(title, "SemiBold", int(20 * u), max_w)
        af, artist = _fit_text(artist, "Medium", int(16 * u), max_w) if artist else (inter("Medium", int(16 * u)), "")
        w = text_x + int(max(_width(tf, title), _width(af, artist), 120 * u)) + pad
        body_h = max(side + pad, int(80 * u if progress else 60 * u))
    queue = _upnext_fitted(*inside[:2], u, style, int(WRAP_SHARE * 1440 * u) - 2 * pad) if inside else None
    if queue:
        w = max(w, queue["w"] + 2 * pad)
        list_h = int(20 * u) + queue["head_h"] + queue["rows_h"]
    else:
        list_h = 0
    w = max(w, int(min_w))
    h = max(body_h + list_h + pad, int(min_h))
    im = _frame(w, h, style, u)
    d = ImageDraw.Draw(im)
    if cover is not None:
        radius = cover_radius(look, side, 0 if line else side // 2 if style == "chips" else int(12 * u))
        cx, cy = ((w - side) // 2, pad) if big else (pad, pad)
        im.alpha_composite(_round_cover(cover, side, radius), (cx, cy))
        if line and not radius:
            d.rectangle((cx, cy, cx + side - 1, cy + side - 1), outline=LINE_EDGE)
    if big:
        y = pad + side + int(14 * u)
        _text(im, (w - _width(tf, title)) / 2, y, title, tf, WHITE)
        y += int(26 * u)
        if artist:
            _text(im, (w - _width(af, artist)) / 2, y, artist, af, GREY)
            y += int(22 * u)
        bar_x, bar_y = pad, y + int(8 * u)
    else:
        _text(im, text_x, pad + int(2 * u), title, tf, WHITE)
        if artist:
            _text(im, text_x, pad + int(28 * u), artist, af, GREY)
        bar_x, bar_y = text_x, pad + int(58 * u)
    if queue:
        y = body_h + int(10 * u)
        _hairline(im, pad, w - pad, y)
        _upnext_draw(im, pad, y + int(10 * u), w - 2 * pad, queue, u, style, inside[2])
    return im, bar_x, bar_y


def _clock(seconds: float) -> str:
    from .media import clock
    return clock(seconds)


def _progress_text(progress, look) -> str:
    if not progress:
        return ""
    el, total = progress
    return "−" + _clock(total - el) if "remaining" in look else _clock(el) + " / " + _clock(total)


# ------------------------------------------------------------------ "Als nächstes" (1.8)
def upnext_fit(label: str, n: int, room: int, u: float) -> int:
    """How many rows of upnext_panel fit into ``room`` px of height (its size is pad + header + rows · row height,
    1.8.24) – at least one."""
    pad, head_h, row_h = int(12 * u), int(16 * u) if label else 0, max(1, int(20 * u))
    fit = (room - 2 * pad - head_h + int(4 * u)) // row_h
    return max(min(n, 1), min(n, int(fit)))


def _upnext_fitted(label, items, u, style, max_w) -> dict:
    """The rows of the queue fitted to ``max_w``: {rows: [(num, font, text, title_len)], num_w, nf, w, head_h,
    rows_h, row_h} – the same metrics as upnext_fit."""
    head_h, row_h = int(16 * u) if label else 0, int(20 * u)
    nf = inter("Medium", int(12 * u))
    num_w = int(_width(nf, "9")) + int(8 * u)

    def fit(num, item):
        title, artist = (tuple(item) + ("", ""))[:2]
        text = f"{title} – {artist}" if artist else title
        tf, text = _fit_text(text, "Regular" if style == "line" else "Medium", int(14 * u), max_w - num_w)
        return num, tf, text, len(title)

    rows = [fit(str(i), item) for i, item in enumerate(items, 1)]
    w = max((int(_width(tf, t)) for _n, tf, t, _k in rows), default=0) + num_w
    w = max(w, int(_header_w(label, u, mark=False)) if label else 0)
    return dict(rows=rows, num_w=num_w, nf=nf, w=w, head_h=head_h, row_h=row_h, fit=fit,
                rows_h=len(rows) * row_h - (int(4 * u) if rows else 0), label=label)


def _upnext_draw(im, x, y, w, q, u, style, anim=None):
    """Header and rows of the queue at (x, y) – ``anim`` (1.8.1) = ((title, artist), shift): the row that became
    the song fades out at the top while the rest slides up from a row below (shift 0 → 1)."""
    if q["label"]:
        _header(im, x, y, q["label"], u, None, mark=False)
    nf, num_w, row_h = q["nf"], q["num_w"], q["row_h"]

    def row(layer, yy, entry, alpha=255):
        num, tf, text, title_len = entry
        white, grey, dim = WHITE[:3] + (alpha,), GREY[:3] + (alpha,), DIMG[:3] + (alpha,)
        _text(layer, 0, yy + int(2 * u), num, nf, dim)
        head, tail = text[:title_len], text[title_len:]      # title bright, artist grey (the fit may cut the tail)
        xx = _text(layer, num_w, yy, head, tf, white)
        if tail:
            _text(layer, xx, yy, tail, tf, grey)

    inner = Image.new("RGBA", (max(1, int(w)), max(1, q["rows_h"])), (0, 0, 0, 0))   # clipped when sliding
    off = 0
    if anim and q["rows"]:
        leaving, shift = anim
        shift = min(1.0, max(0.0, float(shift)))
        off = int(round((1.0 - shift) * row_h))
        row(inner, off - row_h, q["fit"]("", leaving), int(255 * (1.0 - shift)))
    for i, entry in enumerate(q["rows"]):
        row(inner, off + i * row_h, entry)
    im.alpha_composite(inner, (int(x), int(y) + q["head_h"]))


def upnext_panel(label: str, items, u: float, style: str, anim=None, min_w: int = 0) -> Image.Image:
    """"Als nächstes" (1.8) as a small panel of its own in ``style`` (right of the music card): a caps header,
    then number · title – artist per track, each line fitted to the width of the bar (WRAP_SHARE); at least
    ``min_w`` wide (1.8.28: the steady width of the whole music picture)."""
    pad = int(12 * u)
    q = _upnext_fitted(label, items, u, style, int(WRAP_SHARE * 1440 * u) - 2 * pad)
    w = max(q["w"] + 2 * pad, int(120 * u), int(min_w))
    h = pad + q["head_h"] + q["rows_h"] + pad
    im = _frame(w, h, style, u)
    _upnext_draw(im, pad, pad, w - 2 * pad, q, u, style, anim)
    return _finish(im, style, u)


def _attach(card: Image.Image, block: Image.Image, pos: str, gap: int, centred: bool) -> Image.Image:
    """``block`` below ``card`` (centred under it or left-aligned) or to its right (tops aligned)."""
    if pos == "right":
        out = Image.new("RGBA", (card.width + gap + block.width, max(card.height, block.height)), (0, 0, 0, 0))
        out.alpha_composite(card, (0, 0))
        out.alpha_composite(block, (card.width + gap, 0))
        return out
    w = max(card.width, block.width)
    out = Image.new("RGBA", (w, card.height + gap + block.height), (0, 0, 0, 0))
    out.alpha_composite(card, ((w - card.width) // 2 if centred else 0, 0))
    out.alpha_composite(block, ((w - block.width) // 2 if centred else 0, card.height + gap))
    return out


# ------------------------------------------------------------------ the map card (1.3.1)
MAP_U = 518                             # text_h of the map's lines at 1440p and text scale 1 = one design pixel


def frame_pad(style: str, text_h: int) -> int:
    """Edge the card's frame adds around the map in ``style`` (the App lets it use the margin, like the dark
    area's edge – backdrop_pad); 0 for classic. Since 1.8.27 every modern style frames the map."""
    u = max(0.25, text_h / MAP_U)
    return int(PAD * u) if style in SURFACES else 0


def map_card(body, name: str, realm: str, timer: str, note: str, record: str, server: str, ping, status,
             text_h: int, style: str, accent=None, rec=None, lines_top: bool = False) -> Image.Image:
    """The map window in ``style``: ``body`` = the map picture without its drawn name (None: the lines alone –
    the info element – or the waiting card with ``status`` lines); ``name``/``realm`` for the header; ``timer``
    big, ``note`` (amber chip), ``record`` and ``server`` + ``ping`` as chips below a hairline; ``text_h`` sizes
    the text. ``rec``: OBS records – True/False = on/off phase of the blinking "● REC" chip right of the server
    (1.8.33, user: "das Rekord-Zeichen neben Global als REC blinkend"; before: a dot right of the timer), None =
    no chip. ``lines_top`` (1.8.34, user: "mit der Map kombinieren, oben oder unten"): timer and chips between the
    header and the map instead of below it. One drawing for every modern style (1.8.27), the surface comes from
    SURFACES."""
    from .overlay_win32 import INFO_WARN, REC_DOT, ping_colour
    u = max(0.25, text_h / MAP_U)
    acc = accent_rgba(accent)
    s = surface(style)
    pad, gap = int(PAD * u), int(TILE_GAP * u)
    status = tuple(status or ())
    wrap = int(WRAP_SHARE * 1440 * u) - 2 * pad
    nf_max = max(body.width if body is not None else 0, wrap)
    nf, name = _fit_text(name, "SemiBold", int(22 * u), nf_max) if name else (None, "")
    tf, cf = inter("SemiBold", int(44 * u)), inter("Medium", int(14 * u))
    chips = []
    if note:
        chips.append(chip(note, u, cf, colour=INFO_WARN, edge=INFO_WARN, pad=int(12 * u), h=int(30 * u),
                          fill=s["tile"]))
    if server:
        dot = accent_rgba(ping_colour(ping)) if ping is not None else GREEN
        # 1.8.28: the pill is sized for a three-digit ping – "28 ms" → "128 ms" moves nothing
        chips.append(chip(server + (f" · {ping:.0f} ms" if ping is not None else ""), u, cf, dot=dot,
                          edge=s["tile_edge"], pad=int(12 * u), h=int(30 * u), fill=s["tile"],
                          width_text=server + (" · 000 ms" if ping is not None else "")))
    if rec is not None:                                  # 1.8.33: blinks – same size in both phases, nothing moves
        chips.append(chip("REC", u, inter("SemiBold", int(14 * u)), colour=WHITE if rec else (255, 255, 255, 70),
                          dot=REC_DOT if rec else REC_DOT[:3] + (55,),
                          edge=REC_DOT[:3] + (200,) if rec else s["tile_edge"], pad=int(12 * u), h=int(30 * u),
                          fill=s["tile"]))
    if record:
        chips.append(chip(record, u, cf, colour=GREY, edge=s["tile_edge"], pad=int(12 * u), h=int(30 * u),
                          fill=s["tile"]))
    lines = [(inter("SemiBold" if i == 0 else "Medium", int((20 if i == 0 else 16) * u)), t, WHITE if i == 0 else GREY)
             for i, t in enumerate(status)]
    row_pic = chip_rows(chips, max(body.width if body is not None else 0, wrap), gap) if chips else None
    timer_w = _width(tf, _widest(timer).rjust(5, "0")) if timer else 0   # at least "00:00": 9:59 → 10:00 stays
    field_w = timer_w
    parts = [body.width if body is not None else 0, _header_w(realm, u) if realm else 0,
             _width(nf, name) if name else 0, field_w, row_pic.width if row_pic else 0] + \
        [_width(f, t) for f, t, _c in lines]
    w = max(int(max(parts)) + 2 * pad, int(140 * u))
    head = bool(realm or name)
    blocks = []                                      # (kind, height, gap before)
    if realm:
        blocks.append(("realm", int(HEAD_H * u), 0))
    if name:
        blocks.append(("name", int(30 * u), 0))
    top = bool(lines_top and body is not None and (timer or lines or row_pic))
    if body is not None and not top:
        blocks.append(("body", body.height, int(6 * u) if head else 0))
    if timer:
        blocks.append(("timer", int(52 * u), 0 if top else int(10 * u) if body is not None else 0))
    for i in range(len(lines)):
        blocks.append((f"status{i}", int(28 * u), int(8 * u) if i == 0 and body is not None else 0))
    if row_pic:
        blocks.append(("chips", row_pic.height, int(16 * u) if (timer or lines) else int(10 * u) if body is not None else 0))
    if top:                                          # 1.8.34: the map below the lines, a hairline between – the
        blocks.append(("body_below", body.height,   # gaps add up as below the map: switching never resizes the card
                       (int(6 * u) if head else 0) + int(10 * u)))
    h = pad + sum(bh + g for _k, bh, g in blocks) + pad
    im = _frame(w, h, style, u)
    y = pad
    for kind, bh, g in blocks:
        y += g
        if kind == "realm":
            _header(im, pad, y, realm, u, acc)
        elif kind == "name":
            _text(im, pad, y - int(2 * u), name, nf, WHITE)
        elif kind == "body":
            im.alpha_composite(body, ((w - body.width) // 2, y))
        elif kind == "body_below":
            _hairline(im, pad, w - pad, y - g // 2)
            im.alpha_composite(body, ((w - body.width) // 2, y))
        elif kind == "timer":
            x = (w - field_w) / 2 if body is not None else pad
            _text(im, x, y - int(6 * u), timer, tf, WHITE)
        elif kind.startswith("status"):
            f, t, c = lines[int(kind[6:])]
            _text(im, (w - _width(f, t)) / 2, y, t, f, c)
        elif kind == "chips":
            if timer or lines:
                _hairline(im, pad, w - pad, y - g // 2)
            im.alpha_composite(row_pic, ((w - row_pic.width) // 2 if body is not None else pad, y))
        y += bh
    return _finish(im, style, u)
