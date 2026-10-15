"""Map style "Dunkel" (1.66, user's wish: the supplied callout maps in the style of Fallen Refuge / Freddy Fazbear's
Pizza): the lilac floor becomes see-through, a thick black line runs along the outline, the digits get a dark
edge, the M box turns dark red and the S box olive; other coloured fields turn grey. Pure picture logic – the
pictures in maps/ stay as they are, the dark ones are made once and kept in a cache folder (``styled_path``).

Pictures in another style (Fallen Refuge, Freddy, Trickster's Delusion) and animated ones (Midwich) stay unchanged.
"""
from __future__ import annotations

import os
import threading
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .mapimage import FONT, title_split

STYLE_VERSION = 1                     # raise when the conversion changes: the cache is made anew
FILL = np.array([140, 148, 232])      # the lilac floor of the supplied maps
FILL_SHARE = 0.3                      # at least this share of the outline must be lilac, else: another style
M_COLOUR, S_COLOUR = (100, 48, 48), (100, 100, 48)    # as on Fallen Refuge
M_MIN, S_MIN = 0.66, 0.75             # letter match needed (measured: M ≈ 0.72, S ≈ 0.88, WT 0.52, H 0.61)
GREY = 0.62                           # other coloured fields: their brightness times this, as grey
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


def restyle(img: Image.Image) -> Image.Image:
    """The picture in the dark style; unchanged if it is not one of the lilac callout maps."""
    a = np.asarray(img.convert("RGBA")).copy()
    split = title_split(img)
    top = split[2] if split else 0
    body = a[top:]
    rgb = body[..., :3].astype(int)
    shape = _outline(body[..., 3])
    dist = np.abs(rgb - FILL).sum(axis=2)
    if not shape.any() or (dist[shape] < 30).mean() < FILL_SHARE:
        return img                                             # another style: leave it
    s = a.shape[0] / 1280
    ring = max(2, round(RING * s))
    padded = cv2.copyMakeBorder(shape.astype(np.uint8), ring, ring, ring, ring, cv2.BORDER_CONSTANT, value=0)
    inner = cv2.erode(padded, _disk(ring))[ring:-ring, ring:-ring].astype(bool)
    black = (rgb.max(axis=2) < 40) & shape
    # where a pixel lies between the floor and white (digits with their soft edges) and how far towards white
    span = 255 - FILL
    t = np.clip(((rgb - FILL) * span).sum(axis=2) / (span ** 2).sum(), 0, 1)
    on_line = np.abs(rgb - (FILL + t[..., None] * span)).sum(axis=2) < 45
    out = body.copy()
    out[shape] = (0, 0, 0, 0)                                  # the floor: see-through
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
        boxes[y:y + h, x:x + w] |= area_mask
        light = (rgb[y:y + h, x:x + w].max(axis=2) >= 60) & area_mask
        sm, ss = best_score(light, "M"), best_score(light, "S")
        colour = np.array(M_COLOUR) if sm >= M_MIN and sm > ss else np.array(S_COLOUR) if ss >= S_MIN else None
        b = out[y:y + h, x:x + w]
        src = body[y:y + h, x:x + w]
        b[area_mask] = src[area_mask]                          # other labels (WT, H, P …) stay as they are
        if colour is None:
            continue
        lum = rgb[y:y + h, x:x + w].mean(axis=2, keepdims=True) / 255
        tinted = (colour * (1 - lum) + 255 * lum).astype(np.uint8)
        b[area_mask, :3] = tinted[area_mask]
        bw = max(2, round(BOX_EDGE * s))
        edge = area_mask & ~cv2.erode(area_mask.astype(np.uint8), _disk(bw)).astype(bool)
        b[edge] = (0, 0, 0, 255)
    rest = shape & ~boxes
    ink = rest & on_line & (t > 0.08)                          # white digits and labels
    other = rest & ~on_line & ~black & (dist >= 30)            # other coloured fields
    keep_black = rest & black                                  # lines and boxes drawn in black
    lum = rgb.mean(axis=2)
    grey = np.clip(lum * GREY, 40, 200).astype(np.uint8)
    out[other, 0] = out[other, 1] = out[other, 2] = grey[other]
    out[other, 3] = 255
    out[keep_black] = (0, 0, 0, 255)
    halo = cv2.dilate((ink & (t > 0.5)).astype(np.uint8), _disk(max(2, round(EDGE * s)))).astype(bool)
    halo &= rest & ~ink & ~other
    out[halo | (shape & ~inner & ~boxes)] = (0, 0, 0, 255)     # digit edges + the black line along the outline
    v = (t * 255).astype(np.uint8)
    out[ink, 0] = out[ink, 1] = out[ink, 2] = v[ink]           # digits on top: whole also at the edge
    out[ink, 3] = 255
    a[top:] = out
    return Image.fromarray(a)


def styled_path(path: str, cache_dir: str) -> str:
    """The dark version of a map picture (made once, kept in ``cache_dir``); the original when the picture is
    animated, cannot be read or is of another style."""
    if not path or path.lower().endswith(".gif"):
        return path
    try:
        st = os.stat(path)
    except OSError:
        return path
    name = f"{os.path.splitext(os.path.basename(path))[0]}-{int(st.st_mtime)}-{st.st_size}-v{STYLE_VERSION}.webp"
    sub = os.path.basename(os.path.dirname(path))
    target = os.path.join(cache_dir, sub, name)
    if os.path.exists(target):
        return target
    try:
        with Image.open(path) as im:
            im.load()
            src = im.convert("RGBA")
        dark = restyle(src)
        if dark is src:
            return path
        os.makedirs(os.path.dirname(target), exist_ok=True)
        tmp = f"{target}.{os.getpid()}-{threading.get_ident()}.tmp"     # the warm-up thread may make it too
        dark.save(tmp, "WEBP", lossless=True)
        os.replace(tmp, target)
        return target
    except Exception:
        return path


def warm(paths, cache_dir: str, stop=lambda: False) -> int:
    """Make the dark pictures ahead (thread at start / when the style is switched on), so that showing a map at the
    start of a match does not wait for it. Returns how many pictures are in the dark style."""
    n = 0
    for path in paths:
        if stop():
            break
        n += styled_path(path, cache_dir) != path
    return n
