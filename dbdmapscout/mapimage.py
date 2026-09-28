"""Prepare a map picture chosen by the user ("Kartenbild hinzufügen …") – pure image logic.

Same steps as the usual preparation of callout maps (own implementation, Pillow + numpy):
trim the uniform border, make the two background colours of the community maps transparent
(dark blue #282a42, grey violet #535781, 10 % tolerance), scale to 1280 px height, save as WebP.
Animated GIFs are copied unchanged. Works only on the file the user picked – no game files,
no network.
"""
from __future__ import annotations

import os
import re
import shutil

import numpy as np
from PIL import Image

BACKGROUNDS = ((0x28, 0x2A, 0x42), (0x53, 0x57, 0x81))
FUZZ = 0.10                 # colour distance (Euclidean RGB, 0..1) still counted as background
HEIGHT = 1280
USER_DIR = "user_maps"      # own pictures (gitignored: the update on start keeps working)


def trim(img: Image.Image) -> Image.Image:
    """Cut away the border that has exactly the colour of the top-left pixel."""
    img = img.convert("RGBA")
    a = np.asarray(img)
    diff = (a != a[0, 0]).any(axis=2)                # all four channels (getbbox only looks at alpha)
    rows, cols = np.flatnonzero(diff.any(axis=1)), np.flatnonzero(diff.any(axis=0))
    if not len(rows):
        return img
    return img.crop((int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1))


def remove_background(img: Image.Image, colours=BACKGROUNDS, fuzz: float = FUZZ) -> Image.Image:
    """Pixels within ``fuzz`` of one of ``colours`` become fully transparent."""
    a = np.array(img.convert("RGBA"))
    rgb = a[..., :3].astype(np.float32)
    hit = np.zeros(a.shape[:2], bool)
    for c in colours:
        d = np.sqrt(((rgb - np.array(c, np.float32)) ** 2).sum(axis=2)) / 255.0
        hit |= d <= fuzz
    a[hit, 3] = 0
    return Image.fromarray(a, "RGBA")


def convert(img: Image.Image, remove_bg: bool = True, height: int = HEIGHT) -> Image.Image:
    """Trim, (optionally) remove the background, scale to ``height``."""
    out = trim(img)
    if remove_bg:
        out = remove_background(out)
    if out.height != height and out.height > 0:
        out = out.resize((max(1, round(out.width * height / out.height)), height), Image.LANCZOS)
    return out


def is_animated(path: str) -> bool:
    try:
        with Image.open(path) as im:
            return bool(getattr(im, "is_animated", False))
    except OSError:
        return False


def safe_name(text: str) -> str:
    """File/folder name from a map or realm name (Windows-safe)."""
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", text).strip().rstrip(".")
    return re.sub(r"\s+", " ", s)


def target_path(root: str, rel_stem: str, animated: bool) -> str:
    """user_maps/<rel_stem>.webp (or .gif for animations)."""
    return os.path.join(root, USER_DIR, rel_stem + (".gif" if animated else ".webp"))


def save(src: str, dest: str, remove_bg: bool = True) -> str:
    """Convert ``src`` and write it to ``dest`` (older own pictures of the same map are replaced)."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    stem = os.path.splitext(dest)[0]
    for ext in (".webp", ".gif", ".png"):
        if os.path.exists(stem + ext) and stem + ext != dest:
            os.remove(stem + ext)
    if dest.lower().endswith(".gif"):
        shutil.copyfile(src, dest)
    else:
        with Image.open(src) as im:
            convert(im, remove_bg).save(dest, "WEBP", quality=90, method=4)
    return dest


# ------------------------------------------------------------------ rotation (overlay, per map)
ROTATIONS = (0, 90, 180, 270)
TITLE_ZONE = (0.04, 0.25)   # the gap below the map name starts within this share of the height
MIN_GAP = 8                 # px of fully transparent rows between name and map


def title_split(img: Image.Image):
    """Rows (title_top, gap_top, body_top, body_bottom) if the picture has its name on top, separated from
    the map by fully transparent rows (the supplied callout maps); None otherwise (then all of it rotates)."""
    a = np.asarray(img.convert("RGBA"))[..., 3] > 24
    rows = a.any(axis=1)
    filled = np.flatnonzero(rows)
    if not len(filled):
        return None
    h = img.height
    best = None
    i = int(filled[0])
    while i <= int(filled[-1]):
        if rows[i]:
            i += 1
            continue
        j = i
        while j < h and not rows[j]:
            j += 1
        if TITLE_ZONE[0] * h <= i <= TITLE_ZONE[1] * h and j - i >= MIN_GAP and (best is None or j - i > best[1] - best[0]):
            best = (i, j)
        i = j
    if best is None:
        return None
    return int(filled[0]), best[0], best[1], int(filled[-1]) + 1


def _crop_cols(img: Image.Image) -> Image.Image:
    box = img.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
    return img.crop((box[0], 0, box[2], img.height)) if box else img


def rotate(img: Image.Image, degrees: int, split=None) -> Image.Image:
    """Turn the map clockwise by ``degrees`` (multiple of 90); a name above the map stays upright on top.
    ``split``: result of title_split() (computed once for all frames of a GIF, so the frames do not jump)."""
    turns = (int(degrees) // 90) % 4
    if not turns:
        return img
    img = img.convert("RGBA")
    method = {1: Image.ROTATE_270, 2: Image.ROTATE_180, 3: Image.ROTATE_90}[turns]
    if split is None:
        split = title_split(img)
    if split is None:
        return img.transpose(method)
    top, gap, body_top, bottom = split
    title = _crop_cols(img.crop((0, top, img.width, gap)))
    body = img.crop((0, body_top, img.width, bottom)).transpose(method)
    space = body_top - gap
    out = Image.new("RGBA", (max(title.width, body.width), title.height + space + body.height), (0, 0, 0, 0))
    out.alpha_composite(title, ((out.width - title.width) // 2, 0))
    out.alpha_composite(body, ((out.width - body.width) // 2, title.height + space))
    return out


def rotate_frames(frames, degrees: int):
    """[(image, duration)] turned by ``degrees``; the name/map split of the first frame is used for all."""
    if not frames or not (int(degrees) // 90) % 4:
        return frames
    split = title_split(frames[0][0])
    return [(rotate(img, degrees, split), d) for img, d in frames]
