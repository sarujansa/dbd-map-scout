"""Overlay styles (1.3, user: "mir gefallen alle 3" of the mock-ups): the cards of the system values, "today" and
the music drawn as glass cards, chips & icons or minimal line art – pure Pillow, nothing here touches the screen.
"classic" stays in overlay_win32 (render_hud / render_music); the HUD windows and the preview call ``card()`` /
``music()`` for every other style.

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
from .overlay_win32 import _draw_run, _run_len, fira

STYLES = ("classic", "glass", "chips", "line")
STYLE_LABELS = [("classic", N_("Klassisch")), ("glass", N_("Glas-Karten")), ("chips", N_("Chips & Icons")),
                ("line", N_("Minimal Line"))]
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
WEIGHTS = ("Regular", "Medium", "SemiBold", "Bold")

GOLD = (212, 166, 58, 255)              # accent when the window's theme is not known
WHITE = (255, 255, 255, 255)
GREY = (160, 166, 180, 255)             # secondary text
DIMG = (120, 126, 140, 255)             # labels
GLASS_FILL = (16, 17, 22, 205)
GLASS_EDGE = (255, 255, 255, 40)
LINE_EDGE = (255, 255, 255, 80)
HAIRLINE = (255, 255, 255, 28)
TRACK = (255, 255, 255, 35)             # the empty part of a bar
CHIP_FILL = (20, 21, 27, 215)
CHIP_EDGE = (255, 255, 255, 50)
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
def _panel(w: int, h: int, radius: int, fill, edge, width: int = 1) -> Image.Image:
    im = Image.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=max(1, radius), fill=fill,
                                         outline=edge, width=max(1, width))
    return im


def shadowed(card: Image.Image, u: float) -> Image.Image:
    """The card on its soft drop shadow (glass and chips); the margin belongs to the picture."""
    blur = max(2, int(8 * u))
    off = max(1, int(4 * u))
    out = Image.new("RGBA", (card.width + 4 * blur, card.height + 4 * blur), (0, 0, 0, 0))
    sh = Image.new("RGBA", out.size, (0, 0, 0, 0))
    a = card.getchannel("A").point(lambda v: v * 120 // 255)
    sh.paste((0, 0, 0, 255), (2 * blur, 2 * blur + off), a)
    out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))
    out.alpha_composite(card, (2 * blur, 2 * blur))
    return out


def _text(im, x, y, text, font, fill, track: float = 0) -> float:
    return _draw_run(im, x, y, text, font, fill, 0, None, track)


def _width(font, text, track: float = 0) -> float:
    return _run_len(font, text) + track * max(0, len(text) - 1)


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
    art = cover.convert("RGBA").resize((side, side), Image.LANCZOS)
    mask = Image.new("L", (side, side), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, side - 1, side - 1), radius=radius, fill=255)
    art.putalpha(mask)
    return art


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


# ------------------------------------------------------------------ the cards (system values, today)
def card(rows, height: int, style: str, accent=None, title=None, dim=None) -> Image.Image:
    """System values / "today" in ``style`` (glass | chips | line) from the classic rows of sysinfo.hud_rows /
    today_rows; ``title`` for the header ("SYSTEM" for the values; None = the first row's label, "today")."""
    from .sysinfo import DIM
    dim = dim or DIM
    u = max(0.25, height / 1440)
    acc = accent_rgba(accent)
    head, lines = card_model(rows, dim, title)
    if not lines:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    if style == "chips":
        return _card_chips(head, lines, u, acc)
    if style == "line":
        return _card_line(head, lines, u, acc)
    return _card_glass(head, lines, u, acc)


def _card_glass(head, lines, u, acc) -> Image.Image:
    pad = int(18 * u)
    hf, lf, vf, ff = inter("SemiBold", int(14 * u)), inter("Medium", int(19 * u)), inter("SemiBold", int(22 * u)), \
        inter("SemiBold", int(20 * u))
    row_h, gap = int(34 * u), int(8 * u)
    top = int(48 * u) if head else pad
    w = max([_width(hf, head.upper(), 2.2 * u) + int(30 * u) + pad] +
            [(_width(lf, nice(lab)) + int(24 * u) if lab else 0) + _values_width(vals, vf if lab else ff, gap) + 2 * pad
             for lab, vals, _f in lines])
    w = int(max(w, 160 * u))
    h = top + len(lines) * row_h + int(10 * u)
    im = _panel(w, h, int(20 * u), GLASS_FILL, GLASS_EDGE)
    d = ImageDraw.Draw(im)
    if head:
        d.rounded_rectangle((pad, int(17 * u), pad + int(4 * u), int(31 * u)), radius=int(2 * u), fill=acc)
        _text(im, pad + int(12 * u), int(14 * u), head.upper(), hf, GREY, 2.2 * u)
    y = top
    for lab, vals, _f in lines:
        if lab:
            _text(im, pad, y, nice(lab), lf, DIMG)
            _values_right(im, w - pad, y - int(2 * u), [(nice(t), c) for t, c in vals], vf, gap)
        else:
            _text(im, pad, y - int(2 * u), "  ·  ".join(nice(t) for t, _c in vals), ff, WHITE)
        y += row_h
    return shadowed(im, u)


def _card_line(head, lines, u, acc) -> Image.Image:
    pad = int(18 * u)
    cf, vf, ff = int(13 * u), inter("Regular", int(21 * u)), inter("Regular", int(19 * u))
    row_h = int(40 * u)
    top = int(44 * u) if head else int(16 * u)
    capw = lambda t: _width(inter("Medium", cf), t.upper(), 3 * u)          # noqa: E731
    w = max([capw(head) + 2 * pad] + [(capw(nice(lab)) + int(24 * u) if lab else 0) +
                                      _values_width(vals, vf if lab else ff, int(8 * u)) + 2 * pad
                                      for lab, vals, _f in lines])
    w = int(max(w, 160 * u))
    h = top + len(lines) * row_h + int(4 * u)
    im = _panel(w, h, int(10 * u), (0, 0, 0, 0), LINE_EDGE, max(1, int(u)))
    d = ImageDraw.Draw(im)
    if head:
        _caps(im, pad, int(16 * u), head, cf, DIMG, u)
    y = top
    for i, (lab, vals, _f) in enumerate(lines):
        if lab:
            _caps(im, pad, y + int(4 * u), nice(lab), cf, DIMG, u)
            _values_right(im, w - pad, y - int(2 * u), [(nice(t), c) for t, c in vals], vf, int(8 * u))
        else:
            _text(im, pad, y - int(2 * u), "  ·  ".join(nice(t) for t, _c in vals), ff, WHITE)
        if i < len(lines) - 1:
            d.line((pad, y + int(32 * u), w - pad, y + int(32 * u)), fill=HAIRLINE)
        y += row_h
    return im


def chip(text, u, font=None, colour=WHITE, dot=None, edge=CHIP_EDGE, pad=None, h=None) -> Image.Image:
    font = font or inter("SemiBold", int(16 * u))
    pad = int(14 * u) if pad is None else pad
    h = int(38 * u) if h is None else h
    w = int(_width(font, text)) + 2 * pad + (int(18 * u) if dot else 0)
    im = _panel(w, h, h // 2, CHIP_FILL, edge)
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


def _card_chips(head, lines, u, acc) -> Image.Image:
    if any(lab and lab.upper().split()[0] in ICONS for lab, _v, _f in lines):   # the system values: icon, bar
        return _chips_table(lines, u, acc)
    # "today" and anything else: one chip per pair
    f = inter("SemiBold", int(16 * u))
    chips = []
    for lab, vals, _fr in lines:
        text = "  ·  ".join(nice(t) for t, _c in vals)
        if lab and lab.upper() != (head or "").upper():
            text = f"{nice(lab)} {text}"
        colour = vals[-1][1] if vals else WHITE
        chips.append(chip(text, u, f, colour if colour != WHITE else WHITE))
    return shadowed(chip_rows(chips, int(WRAP_SHARE * 1440 * u), int(8 * u)), u)


def _chips_table(lines, u, acc) -> Image.Image:
    pad = int(16 * u)
    lf, vf = inter("Medium", int(16 * u)), inter("SemiBold", int(18 * u))
    col = int(max(100 * u, pad + 30 * u + max((_width(lf, nice(lab)) for lab, _v, _f in lines if lab), default=0)
                  + 12 * u))
    row_h, slim = int(46 * u), int(30 * u)
    w = int(max(300 * u, max(col + _values_width(vals, vf, int(8 * u)) + 2 * pad for _l, vals, _f in lines)))
    h = int(16 * u) + sum(row_h if fr is not None else slim for _l, _v, fr in lines)
    im = _panel(w, h, int(16 * u), GLASS_FILL, GLASS_EDGE)
    d = ImageDraw.Draw(im)
    y = int(14 * u)
    for lab, vals, fr in lines:
        if lab:
            kind = ICONS.get(lab.upper().split()[0]) if lab else None
            if kind:
                _icon(d, kind, pad, y, u)
            _text(im, pad + int(30 * u), y - u, nice(lab), lf, DIMG)
        if vals:
            first, rest = vals[0], vals[1:]
            _text(im, col, y - 3 * u, nice(first[0]), vf, first[1])
            if rest:
                _values_right(im, w - pad, y - u, [(nice(t), c) for t, c in rest], lf, int(8 * u))
        if fr is not None:
            hot = any(c != WHITE and c != DIMG for _t, c in vals[:1])
            _bar(d, col, y + int(24 * u), w - col - pad, fr, acc if fr >= 0.85 or hot else WHITE, u)
            y += row_h
        else:
            y += slim
    return shadowed(im, u)


# ------------------------------------------------------------------ the music card
def music(rows, cover, height: int, style: str, progress=None, look=(), accent=None) -> Image.Image:
    """"Läuft gerade" in ``style``: ``rows`` as media.rows gives them ([[(title, white)], [(artist, dim)]]),
    ``progress`` = (elapsed, total) s or None, ``look`` as media.look (``remaining`` = time left on the right,
    ``accent`` = bar in the cover's colour – else the theme's accent)."""
    u = max(0.25, height / 1440)
    acc = accent_rgba(accent)
    if "accent" in look and cover is not None:
        from .media import accent as cover_accent
        acc = accent_rgba(cover_accent(cover)) if cover_accent(cover) else acc
    texts = ["".join(t for t, _c in row) for row in rows]
    title = texts[0] if texts else ""
    artist = texts[1] if len(texts) > 1 else ""
    if style == "chips":
        return _music_chips(title, artist, cover, u, acc, progress, look)
    if style == "line":
        return _music_line(title, artist, cover, u, acc, progress, look)
    return _music_glass(title, artist, cover, u, acc, progress, look)


def _clock(seconds: float) -> str:
    from .media import clock
    return clock(seconds)


def _progress_text(progress, look) -> str:
    if not progress:
        return ""
    el, total = progress
    return "−" + _clock(total - el) if "remaining" in look else _clock(el) + " / " + _clock(total)


def _music_glass(title, artist, cover, u, acc, progress, look) -> Image.Image:
    pad, side = int(16 * u), int(64 * u) if cover is not None else 0
    text_x = pad + side + (int(14 * u) if cover is not None else 0)
    max_w = int(WRAP_SHARE * 1440 * u) - text_x - pad
    tf, title = _fit_text(title, "SemiBold", int(20 * u), max_w)
    af, artist = _fit_text(artist, "Medium", int(16 * u), max_w) if artist else (inter("Medium", int(16 * u)), "")
    w = text_x + int(max(_width(tf, title), _width(af, artist), 120 * u)) + pad
    h = max(side + 2 * pad, int(96 * u if progress else 76 * u))
    im = _panel(w, h, int(20 * u), GLASS_FILL, GLASS_EDGE)
    d = ImageDraw.Draw(im)
    if cover is not None:
        im.alpha_composite(_round_cover(cover, side, int(10 * u)), (pad, (h - side) // 2))
    _text(im, text_x, int(18 * u), title, tf, WHITE)
    if artist:
        _text(im, text_x, int(44 * u), artist, af, GREY)
    if progress:
        el, total = progress
        tail = _progress_text(progress, look)
        sf = inter("Medium", int(12 * u))
        tw = int(_width(sf, tail)) + int(8 * u) if tail else 0
        y = int(74 * u)
        _bar(d, text_x, y, w - pad - text_x - tw, min(1.0, el / max(1, total)), acc, u)
        if tail:
            _text(im, w - pad - tw + int(8 * u), y - int(5 * u), tail, sf, GREY)
    return shadowed(im, u)


def _music_chips(title, artist, cover, u, acc, progress, look) -> Image.Image:
    h = int(74 * u)
    side = int(50 * u) if cover is not None else 0
    text_x = int(12 * u) + side + (int(14 * u) if cover is not None else int(8 * u))
    max_w = int(WRAP_SHARE * 1440 * u) - text_x - int(24 * u)
    tf, title = _fit_text(title, "SemiBold", int(18 * u), max_w)
    sub = artist + (" · " + _progress_text(progress, look) if progress and _progress_text(progress, look) else "")
    af, sub = _fit_text(sub, "Medium", int(14 * u), max_w) if sub else (inter("Medium", int(14 * u)), "")
    w = text_x + int(max(_width(tf, title), _width(af, sub), 120 * u)) + int(24 * u)
    im = _panel(w, h, h // 2, GLASS_FILL, GLASS_EDGE)
    d = ImageDraw.Draw(im)
    if cover is not None:
        art = cover.convert("RGBA").resize((side, side), Image.LANCZOS)
        mask = Image.new("L", (side, side), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, side - 1, side - 1), fill=255)
        art.putalpha(mask)
        im.alpha_composite(art, (int(12 * u), (h - side) // 2))
    _text(im, text_x, int(14 * u), title, tf, WHITE)
    if sub:
        _text(im, text_x, int(38 * u), sub, af, GREY)
    if progress:
        el, total = progress
        _bar(d, text_x, int(60 * u), w - text_x - int(24 * u), min(1.0, el / max(1, total)), acc, u)
    return shadowed(im, u)


def _music_line(title, artist, cover, u, acc, progress, look) -> Image.Image:
    pad = int(16 * u)
    side = int(52 * u) if cover is not None else 0
    text_x = pad + side + (int(16 * u) if cover is not None else 0)
    max_w = int(WRAP_SHARE * 1440 * u) - text_x - pad
    tf, title = _fit_text(title, "Regular", int(20 * u), max_w)
    sub = artist + ("  ·  " + _progress_text(progress, look) if progress and _progress_text(progress, look) else "")
    cf = inter("Medium", int(12 * u))
    sub_w = _width(cf, sub.upper(), 3 * u)
    if sub_w > max_w:
        cut = max(4, int(len(sub) * max_w / sub_w) - 1)
        sub = sub[:cut].rstrip() + "…"
    w = text_x + int(max(_width(tf, title), _width(cf, sub.upper(), 3 * u), 120 * u)) + pad
    h = max(side + 2 * pad, int(84 * u))
    im = _panel(w, h, int(10 * u), (0, 0, 0, 0), LINE_EDGE, max(1, int(u)))
    d = ImageDraw.Draw(im)
    if cover is not None:
        im.alpha_composite(cover.convert("RGBA").resize((side, side), Image.LANCZOS), (pad, pad))
        d.rectangle((pad, pad, pad + side - 1, pad + side - 1), outline=LINE_EDGE)
    _text(im, text_x, pad, title, tf, WHITE)
    if sub:
        _caps(im, text_x, int(44 * u), sub, int(12 * u), GREY, u)
    if progress:
        el, total = progress
        y = int(68 * u)
        d.line((text_x, y, w - pad, y), fill=(255, 255, 255, 40))
        d.line((text_x, y, text_x + int((w - pad - text_x) * min(1.0, el / max(1, total))), y), fill=acc,
               width=max(1, int(2 * u)))
    return im
