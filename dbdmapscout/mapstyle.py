"""Map style "Dunkel" (1.66, user's wish: the supplied callout maps in the style of Fallen Refuge / Freddy Fazbear's
Pizza): the lilac floor becomes see-through, a thick black line runs along the outline, the digits get a dark
edge, the M box turns dark red, the S box olive and other boxes (WT, H, P …) and lines inside grey (black would
vanish on black). Pure picture logic – the pictures in maps/ stay as they are, the dark ones are made once and kept
in a cache folder (``styled_path``).

1.66.1 (user: "jede Map prüfen, ob sie identisch ist mit dem alten Bild"): every pixel of these maps is a neutral
grey laid over the lilac floor (``unblend``); the conversion takes the floor off exactly, so the dark picture laid
over lilac again gives back the original wherever no black backing was added – tests/test_mapstyle.py checks that
for every map.

Pictures in another style (Fallen Refuge, Freddy, Trickster's Delusion) stay unchanged; Midwich (animated, floors,
framed) has its own way since 1.66.2 (``restyle_floors``).
"""
from __future__ import annotations

import os
import threading
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageSequence

from .mapimage import FONT, title_split

STYLE_VERSION = 7                     # raise when the conversion changes: the cache is made anew
FILL = np.array([140, 148, 232])      # the lilac floor of the supplied maps
FILL_SHARE = 0.3                      # at least this share of the outline must be lilac, else: another style
M_COLOUR, S_COLOUR = (100, 48, 48), (100, 100, 48)    # as on Fallen Refuge
BOX_GREY = (128, 128, 128)            # other boxes (WT, H, P …) – grey as on Fallen Refuge: black would vanish in the bar
WALL = 110                            # black lines/walls inside the map (RPD, Hawkins …): grey, else they vanish on black
M_MIN, S_MIN = 0.66, 0.75             # letter match needed (measured: M ≈ 0.72, S ≈ 0.88, WT 0.52, H 0.61)
MISFIT, MISFIT_SHARE = 30, 0.002      # pixel off "grey over lilac" by this much = a colour; more than this share: leave it
RING, EDGE, BOX_EDGE = 24, 5, 4       # px at 1280 px picture height: outline, digit edge, box edge


@lru_cache(maxsize=4)
def _letter(letter: str):
    im = Image.new("L", (400, 400), 0)
    ImageDraw.Draw(im).text((50, 50), letter, font=ImageFont.truetype(FONT, 200), fill=255)
    a = np.asarray(im) > 128
    ys, xs = np.nonzero(a)
    return Image.fromarray(a[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.uint8) * 255)


def letter_score(mask, letter: str) -> float:
    """How well the light pixels in a box match the letter (overlap of the two, 0..1)."""
    ys, xs = np.nonzero(mask)
    if not len(ys):
        return 0.0
    mask = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = mask.shape
    t = np.asarray(_letter(letter).resize((w, h))) > 128
    return float((t & mask).sum() / max(1, (t | mask).sum()))


def best_score(mask, letter: str) -> float:
    """letter_score, also for a box turned by 45° (Pale Rose, Disturbed Ward)."""
    best = letter_score(mask, letter)
    if best >= 0.6:
        return best
    h, w = mask.shape
    size = int((h * h + w * w) ** 0.5) + 2
    pad = np.zeros((size, size), np.uint8)
    pad[(size - h) // 2:(size - h) // 2 + h, (size - w) // 2:(size - w) // 2 + w] = mask
    for angle in (45, -45):
        m = cv2.getRotationMatrix2D((size / 2, size / 2), angle, 1.0)
        best = max(best, letter_score(cv2.warpAffine(pad, m, (size, size)) > 0, letter))
    return best


def _outline(alpha):
    """The map's outline, filled (holes inside the digits closed)."""
    raw = (alpha > 128).astype(np.uint8)
    cnts, _h = cv2.findContours(raw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    filled = np.zeros_like(raw)
    cv2.drawContours(filled, [c for c in cnts if cv2.contourArea(c) > 0.02 * raw.size], -1, 1, -1)
    return filled.astype(bool)


def _disk(r: int):
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def unblend(rgb, fill=None):
    """Every pixel of the supplied maps is a neutral grey g laid over the lilac floor with cover a:
    P = a·g + (1 − a)·FILL (checked on all 52 maps: no pixel off by 30 or more). Solved per pixel (least squares
    over the three channels) → (g, a, misfit). With it the floor comes off exactly – soft edges and the drop
    shadow of the digits included – and the picture laid over lilac again is the original."""
    fill = (FILL if fill is None else np.asarray(fill)).astype(float)
    p = rgb.astype(float) - fill
    basis = np.stack([np.ones(3), fill], axis=1)                  # P − FILL = c0·1 + c1·FILL
    coef = p @ np.linalg.pinv(basis).T
    a = np.clip(-coef[..., 1], 0.0, 1.0)
    g = np.clip(coef[..., 0] / np.maximum(a, 1e-3), 0, 255)
    # g held to 0..255 (the black lines are a little blue: "blacker than black"): the cover again for that grey,
    # then the grey for that cover
    d = g[..., None] - fill
    a = np.clip((p * d).sum(axis=-1) / np.maximum((d * d).sum(axis=-1), 1e-6), 0.0, 1.0)
    g = np.where(a > 1e-3, np.clip((rgb - (1 - a[..., None]) * fill).mean(axis=-1) / np.maximum(a, 1e-3), 0, 255), 0)
    misfit = np.abs(rgb - a[..., None] * g[..., None] - (1 - a[..., None]) * fill).sum(axis=-1)
    return g, a, misfit


# 1.8.16 (user picked them from sample pictures, "zusätzlich", plain names): the dark conversion with a floor under
# the drawing – on the black bar the transparent floor of "dark" leaves little more than digits on black.
# style: (floor RGB, edge RGB or None, edge px at 1280 px height, floor alpha)
FLOORS = {"grey": ((38, 40, 46), None, 0, 255),
          "grey_edge": ((34, 36, 42), (120, 124, 136), 4, 255),
          "lilac": ((40, 42, 72), (110, 118, 200), 4, 255),
          "lilac_glass": ((140, 148, 232), None, 0, 70)}
STYLES = ("dark",) + tuple(FLOORS)        # every style made from the dark conversion ("classic" = the original)


def add_floor(img: Image.Image, top: int, style: str) -> Image.Image:
    """A dark-styled map with the floor of ``style`` under its drawing (and an edge on its outline)."""
    fill, edge, ew, alpha = FLOORS[style]
    a = np.asarray(img.convert("RGBA")).copy()
    body = a[top:]
    shape = _outline(body[..., 3])
    base = np.zeros_like(body)
    base[shape] = (*fill, alpha)
    under = Image.fromarray(base)
    under.alpha_composite(Image.fromarray(body))
    out = np.asarray(under).copy()
    if edge is not None:
        w = max(2, round(ew * a.shape[0] / 1280))
        inner = cv2.erode(shape.astype(np.uint8), _disk(w), borderType=cv2.BORDER_CONSTANT, borderValue=0)
        out[shape & ~inner.astype(bool)] = (*edge, 255)
    a[top:] = out
    return Image.fromarray(a)


def restyle(img: Image.Image, fill=None, style: str = "dark") -> Image.Image:
    """The picture in the dark style (``style`` = one of STYLES: with that floor under it); unchanged if it is not
    one of the lilac callout maps."""
    a = np.asarray(img.convert("RGBA")).copy()
    split = title_split(img)
    top = split[2] if split else 0
    body = a[top:]
    rgb = body[..., :3].astype(int)
    shape = _outline(body[..., 3])
    fill = FILL if fill is None else np.asarray(fill)
    dist = np.abs(rgb - fill).sum(axis=2)
    if not shape.any() or (dist[shape] < 30).mean() < FILL_SHARE:
        return img                                             # another style: leave it
    grey, cover, misfit = unblend(rgb, fill)
    if ((misfit >= MISFIT) & (rgb.max(axis=2) > 80))[shape].mean() > MISFIT_SHARE:   # (blue-black line rims: no colour)
        return img                                             # colours the conversion cannot keep: leave it
    cover = cover * body[..., 3] / 255                         # holes in the original stay holes
    s = a.shape[0] / 1280
    ring = max(2, round(RING * s))
    padded = cv2.copyMakeBorder(shape.astype(np.uint8), ring, ring, ring, ring, cv2.BORDER_CONSTANT, value=0)
    inner = cv2.erode(padded, _disk(ring))[ring:-ring, ring:-ring].astype(bool)
    black = (rgb.max(axis=2) < 40) & shape
    out = body.copy()
    # M and S boxes: black squares with a light letter
    boxes = np.zeros_like(shape)
    n, lab, stats, _c = cv2.connectedComponentsWithStats((black & inner).astype(np.uint8))
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < 1500 * s * s or not 0.4 < w / max(1, h) < 2.5:
            continue
        comp = (lab[y:y + h, x:x + w] == i).astype(np.uint8)
        cs, _h2 = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        area_mask = np.zeros_like(comp)
        cv2.drawContours(area_mask, cs, -1, 1, -1)
        area_mask = area_mask.astype(bool)
        if comp.sum() < 0.45 * area_mask.sum():
            continue                                           # a thin frame round a room, not a filled box
        # smooth the box (its lower edge is frayed on some maps) and take in its soft rim: that gets the black edge
        pad = max(2, round(2 * s))
        y0, x0 = max(0, y - pad), max(0, x - pad)
        y1, x1 = min(shape.shape[0], y + h + pad), min(shape.shape[1], x + w + pad)
        full = np.zeros((y1 - y0, x1 - x0), np.uint8)
        full[y - y0:y - y0 + h, x - x0:x - x0 + w] = area_mask
        # the box's own edge by its cover (> 50 % dark), not by "darker than 40": soft rows of the original's edge
        # are then all in or all out – no teeth (Ormond II); only next to the found box, holes (the letter) filled
        near_box = cv2.dilate(full, _disk(pad)).astype(bool)
        dark_win = ((cover > 0.5) & (grey < 80))[y0:y1, x0:x1] & near_box
        cs2, _h3 = cv2.findContours((dark_win | full.astype(bool)).astype(np.uint8), cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_NONE)
        full = np.zeros_like(full)
        cv2.drawContours(full, cs2, -1, 1, -1)
        full = cv2.morphologyEx(full, cv2.MORPH_CLOSE, _disk(pad), borderType=cv2.BORDER_CONSTANT, borderValue=0)
        full = full.astype(bool)
        if (cover[y0:y1, x0:x1][full] < 0.5).mean() > 0.05:
            continue                                           # floor inside: a room frame (Hawkins "BOT MID")
        grown = cv2.dilate(full.astype(np.uint8), _disk(pad)).astype(bool) & shape[y0:y1, x0:x1]
        boxes[y0:y1, x0:x1] |= grown
        light = (rgb[y:y + h, x:x + w].max(axis=2) >= 60) & area_mask
        sm, ss = best_score(light, "M"), best_score(light, "S")
        colour = np.array(M_COLOUR if sm >= M_MIN and sm > ss else S_COLOUR if ss >= S_MIN else BOX_GREY)
        b = out[y0:y1, x0:x1]
        lum = (grey * cover)[y0:y1, x0:x1, None] / 255           # the letter's brightness, the floor counts as box
        tinted = (colour * (1 - lum) + 255 * lum).astype(np.uint8)
        b[full, :3] = tinted[full]
        b[full, 3] = 255
        bw = max(2, round(BOX_EDGE * s))
        square = cv2.getStructuringElement(cv2.MORPH_RECT, (2 * bw + 1, 2 * bw + 1))   # square: thin bits of the rim stay out
        inside = cv2.erode(full.astype(np.uint8), square, borderType=cv2.BORDER_CONSTANT, borderValue=0).astype(bool)
        rim = grown & ~inside
        b[rim] = (0, 0, 0, 255)
        ink = np.rint(grey * cover).astype(np.uint8)[y0:y1, x0:x1]
        b[rim, 0] = b[rim, 1] = b[rim, 2] = ink[rim]           # digits reaching over the rim stay (Nostromo "12")
    rest = shape & ~boxes
    # the drawing without its floor: grey g with cover a (see-through where the floor was)
    g8 = np.rint(grey).astype(np.uint8)
    out[rest, 0] = out[rest, 1] = out[rest, 2] = g8[rest]
    out[rest, 3] = np.rint(cover[rest] * 255).astype(np.uint8)
    # black behind the light text (dark edge) and along the outline: the drawing laid over black
    light = rest & (cover > 0.5) & (grey > 128)
    edge = max(2, round(EDGE * s))
    halo = cv2.dilate(light.astype(np.uint8), _disk(edge)).astype(bool)
    # walls: dark parts of the drawing away from the light text (the drop shadow of the digits lies closer)
    near = cv2.dilate(light.astype(np.uint8), _disk(2 * edge)).astype(bool)
    walls = (rest & inner & (cover > 0.5) & (grey < 60) & ~near).astype(np.uint8)   # in the outline band: black
    n, lab, stats, _c = cv2.connectedComponentsWithStats(walls)
    big = stats[:, cv2.CC_STAT_AREA] >= 30 * s * s            # single dark pixels at edges are no wall
    big[0] = False
    walls = big[lab]
    out[walls, 0] = out[walls, 1] = out[walls, 2] = WALL
    backed = rest & (halo | ~inner) & ~walls
    on_black = np.rint(grey * cover).astype(np.uint8)
    out[backed, 0] = out[backed, 1] = out[backed, 2] = on_black[backed]
    out[backed, 3] = 255
    a[top:] = out
    res = Image.fromarray(a)
    return add_floor(res, top, style) if style in FLOORS else res


# ------------------------------------------------------------------ Midwich (1.66.2, user: "kann ebenfalls geändert werden")
# A picture of its own kind: an animated GIF (floors), fully opaque, the map in a white frame on a dark patterned
# background, the floor a grey-blue, the name in another font. Each floor is cut out of its frame, the background
# seen through holes in the floor (the top floor's middle) becomes see-through, then it goes the same way as the
# others with its own floor colour; the name is set anew like on every other map. The frames in between only
# fade from one floor to the next – they are made anew from the dark floors.
FRAME_WHITE = 230            # the white frame: all channels above this
HOLE = (52, 52, 58)          # holes in a floor (top floor's middle: a drop) – see-through would look like floor
FLOOR_TITLES = ("Midwich - Bottom", "Midwich - Top")


def framed_floor(img: Image.Image):
    """(map inside the white frame as RGBA with holes see-through, floor colour) or None if it is not that kind."""
    a = np.asarray(img.convert("RGB")).astype(int)
    h, w = a.shape[:2]
    white = a.min(axis=2) > FRAME_WHITE
    rows = np.flatnonzero(white.sum(axis=1) > 0.75 * w)
    cols = np.flatnonzero(white.sum(axis=0) > 0.75 * h)
    if len(rows) < 2 or len(cols) < 2 or rows[-1] - rows[0] < h / 2 or cols[-1] - cols[0] < w / 2:
        return None
    # the frame's own thickness: the white rows/columns next to each outer edge
    def inner(lines, first):
        step = 1 if first else -1
        i = 0 if first else len(lines) - 1
        while 0 <= i + step < len(lines) and lines[i + step] == lines[i] + step:
            i += step
        return lines[i] + step
    y0, y1 = inner(rows, True), inner(rows, False) + 1
    x0, x1 = inner(cols, True), inner(cols, False) + 1
    pad = 2                                               # anti-aliased inner edge of the frame
    body = a[y0 + pad:y1 - pad, x0 + pad:x1 - pad]
    outside = np.concatenate([a[:max(1, rows[0] - 4)].reshape(-1, 3), a[rows[-1] + 4:].reshape(-1, 3)])
    colours, counts = np.unique(body.reshape(-1, 3), axis=0, return_counts=True)
    fill = colours[np.argmax(counts)]
    outside = outside[outside.max(axis=1) < FRAME_WHITE]  # not the name and the frame
    bgc, bgn = np.unique(outside, axis=0, return_counts=True)
    background = bgc[np.argsort(-bgn)[:4]]                # the background and its "+" pattern
    if (counts.max() / counts.sum()) < 0.4 or np.abs(background[0] - fill).sum() < 40:
        return None
    # the background seen through a hole (its colours, not the floor's; "half black over floor" would fit it too)
    near_bg = np.min([np.abs(body - c).sum(axis=2) for c in background], axis=0) < 25
    hole = (near_bg & (np.abs(body - fill).sum(axis=2) > 60)).astype(np.uint8)
    # the whole hole: closed over the soft edges of the "+" pattern, but not into the black walls round it
    wall = body.max(axis=2) < 40
    k = max(3, round(body.shape[0] / 250))
    hole = cv2.morphologyEx(hole, cv2.MORPH_CLOSE, _disk(k)).astype(bool) & ~wall
    n, lab, stats, _c = cv2.connectedComponentsWithStats(hole.astype(np.uint8))
    big = stats[:, cv2.CC_STAT_AREA] >= (k * 4) ** 2     # specks of a soft edge are no hole
    big &= np.minimum(stats[:, cv2.CC_STAT_WIDTH], stats[:, cv2.CC_STAT_HEIGHT]) >= 3 * k   # thin strips at the frame
    big[0] = False
    filled = np.zeros(hole.shape, np.uint8)               # each hole whole (also the "+" inside it)
    cs, _h = cv2.findContours(big[lab].astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(filled, cs, -1, 1, -1)
    hole = filled.astype(bool) & ~wall
    out = np.dstack([body, np.full(body.shape[:2], 255)]).astype(np.uint8)
    out[hole] = (*fill, 255)                              # floor for the conversion, the grey comes on top after it
    return Image.fromarray(out), tuple(int(v) for v in fill), hole


def restyle_floors(frames, style: str = "dark"):
    """[(image, duration)] of an animated map with floors in the dark style, or None if it is not that kind.
    The floors (shown ≥ 1 s) are converted, the fading frames between them made anew from those."""
    from .mapimage import FLOOR_MIN_MS, REF_MAP_H, add_title
    floors = [i for i, (_im, d) in enumerate(frames) if d >= FLOOR_MIN_MS]
    if len(floors) != len(FLOOR_TITLES):
        return None
    dark = {}
    for n, i in enumerate(floors):
        cut = framed_floor(frames[i][0])
        if cut is None:
            return None
        body, fill, hole = cut
        size = (round(body.width * REF_MAP_H / body.height), REF_MAP_H)
        body = body.resize(size, Image.LANCZOS)
        titled = add_title(body, FLOOR_TITLES[n])
        styled = restyle(titled, fill, style)
        if styled is titled:
            return None
        # the holes, dark grey on top (where the conversion made floor of them)
        mask = Image.fromarray(hole.astype(np.uint8) * 255).resize(size, Image.LANCZOS)
        full = Image.new("L", styled.size, 0)
        full.paste(mask, ((styled.width - size[0]) // 2, styled.height - size[1]))
        grey = Image.new("RGBA", styled.size, (*HOLE, 255))
        styled = Image.composite(grey, styled, full)
        dark[i] = styled
    w = max(p.width for p in dark.values())                # one size for all frames (the names differ in width)
    h = max(p.height for p in dark.values())
    for i, pic in dark.items():
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        canvas.paste(pic, ((w - pic.width) // 2, h - pic.height))
        dark[i] = canvas
    out = []
    for i, (_im, d) in enumerate(frames):
        if i in dark:
            out.append((dark[i], d))
            continue
        before = max((f for f in floors if f < i), default=floors[-1])
        after = min((f for f in floors if f > i), default=floors[0])
        span = (after - before) % len(frames)
        t = ((i - before) % len(frames)) / span           # how far from the floor before to the one after
        out.append((Image.blend(dark[before], dark[after], t), d))
    return out


def styled_path(path: str, cache_dir: str, make: bool = True, style: str = "dark") -> str:
    """The dark version of a map picture (made once, kept in ``cache_dir``); the original when the picture is
    cannot be read or is of another style (an animation: Midwich's kind only). ``make=False``: only an existing
    one (thumbnails of the maps page must not wait ~0.5 s per map), else the original."""
    if not path:
        return path
    try:
        st = os.stat(path)
    except OSError:
        return path
    if style not in STYLES:
        return path
    tag = "" if style == "dark" else f"-{style}"            # "dark" keeps its old names (cache made before 1.8.16)
    name = f"{os.path.splitext(os.path.basename(path))[0]}-{int(st.st_mtime)}-{st.st_size}{tag}-v{STYLE_VERSION}.webp"
    sub = os.path.basename(os.path.dirname(path))
    target = os.path.join(cache_dir, sub, name)
    if os.path.exists(target):
        return target
    if not make:
        return path
    try:
        with Image.open(path) as im:
            if getattr(im, "is_animated", False):
                frames = []
                for fr in ImageSequence.Iterator(im):
                    pic = fr.convert("RGBA")
                    frames.append((pic, int(fr.info.get("duration", 100) or 100)))
                dark = restyle_floors(frames, style)
                if dark is None:
                    return path                                # an animation of another kind: as it is
            else:
                im.load()
                src = im.convert("RGBA")
                dark = restyle(src, None, style)
                if dark is src:
                    return path
                dark = [(dark, 0)]
        os.makedirs(os.path.dirname(target), exist_ok=True)
        tmp = f"{target}.{os.getpid()}-{threading.get_ident()}.tmp"     # the warm-up thread may make it too
        first, rest = dark[0][0], [f for f, _d in dark[1:]]
        # exact: also the invisible pixels as they were; several frames: an animated WebP with the same timing
        first.save(tmp, "WEBP", lossless=True, exact=True, save_all=bool(rest), append_images=rest,
                   duration=[d for _f, d in dark] if rest else 0, loop=0)
        os.replace(tmp, target)
        return target
    except Exception:
        return path


def warm(paths, cache_dir: str, stop=lambda: False, style: str = "dark") -> int:
    """Make the dark pictures ahead (thread at start / when the style is switched on), so that showing a map at the
    start of a match does not wait for it. Returns how many pictures are in the dark style."""
    n = 0
    for path in paths:
        if stop():
            break
        n += styled_path(path, cache_dir, style=style) != path
    return n
