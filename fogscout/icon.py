"""Program icon (drawn, so no binary file is needed in the repository).

    python -m fogscout.icon PATH.ico     -> writes a multi-size .ico (16 … 256 px)

1.9.1 (user: "ändere ruhig auch das Logo"): a compass star – the scout – over layers of fog, on the dark ground
of the UI; the needle that points is gold (the theme's accent). Until 1.9 a lavender blocky callout map with a
white marker. The file carries ICON_VERSION in its name: Windows caches shortcut and taskbar icons by path and
would keep showing the old picture out of a replaced file; the old files go with the old shortcuts
(autostart.install).
"""
from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw, ImageFilter

ICON_VERSION = 2
FILE = f"fogscout-{ICON_VERSION}.ico"
OLD_FILES = ("fogscout.ico", "dbdmapscout.ico")       # icons of earlier versions (1.9 / until 1.8.91)
BG = (20, 20, 22, 255)
FOG = (176, 182, 228)              # the lavender of the old icon, pale, layered with alpha
NORTH = (201, 162, 39, 255)        # theme accent: the needle that points
STAR = (236, 238, 243, 255)
SOUTH = (200, 203, 212, 255)
SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]


def draw(size: int = 256) -> Image.Image:
    s = 4 * size                                  # draw large, scale down (smooth edges)
    u = s / 16
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    radius = int(3.2 * u)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=radius, fill=BG)
    # fog: soft bands in the lower half, denser towards the bottom, kept inside the rounded ground
    fog = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fog)
    for x0, y0, x1, y1, a in ((-2.0, 10.2, 11.0, 12.4, 60), (4.0, 10.8, 18.0, 13.2, 75), (-3.0, 12.0, 12.0, 14.8, 105),
                              (3.0, 12.6, 19.0, 15.6, 125), (-2.0, 13.8, 18.0, 17.5, 150)):
        fd.ellipse([x0 * u, y0 * u, x1 * u, y1 * u], fill=FOG + (a,))
    fog = fog.filter(ImageFilter.GaussianBlur(radius=0.7 * u))
    ground = Image.new("L", (s, s), 0)
    ImageDraw.Draw(ground).rounded_rectangle([0, 0, s - 1, s - 1], radius=radius, fill=255)
    fog.putalpha(Image.composite(fog.getchannel("A"), Image.new("L", (s, s), 0), ground))
    img.alpha_composite(fog)
    # compass star: four points, the north one long and gold, the south one sinking into the fog
    cx, cy = 8 * u, 7.4 * u
    long_n, long_s, short, w = 5.6 * u, 4.2 * u, 3.3 * u, 1.55 * u
    points = {"n": [(cx, cy - long_n), (cx + w, cy), (cx, cy), (cx - w, cy)],
              "s": [(cx, cy + long_s), (cx - w, cy), (cx, cy), (cx + w, cy)],
              "e": [(cx + short, cy), (cx, cy - w), (cx, cy), (cx, cy + w)],
              "w": [(cx - short, cy), (cx, cy + w), (cx, cy), (cx, cy - w)]}
    shadow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    for k in points:
        sd.polygon(points[k], fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=0.35 * u))
    img.alpha_composite(shadow, (int(0.1 * u), int(0.25 * u)))
    d = ImageDraw.Draw(img)
    d.polygon(points["e"], fill=STAR)
    d.polygon(points["w"], fill=STAR)
    d.polygon(points["s"], fill=SOUTH)
    d.polygon(points["n"], fill=NORTH)
    r = 0.8 * u
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=BG)
    r = 0.38 * u
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=STAR)
    return img.resize((size, size), Image.LANCZOS)


REC = (229, 83, 75, 255)      # 1.4.1: recording dot top right (theme.DOT "err" red)


def draw_status(size: int, colour: str | None, rec: bool = False) -> Image.Image:
    """1.3.6: the icon with a status dot bottom right (tray), ringed in the icon's dark ground; 1.4.1: a red
    dot top right while a round is being recorded."""
    img = draw(size)
    if not colour and not rec:
        return img
    s = 4 * size
    over = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    if colour:
        r, ring = 0.25 * s, 0.06 * s
        cx = cy = s - r - ring
        d.ellipse([cx - r - ring, cy - r - ring, cx + r + ring, cy + r + ring], fill=BG)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=colour)
    if rec:
        r, ring = 0.19 * s, 0.06 * s
        cx, cy = s - r - ring, r + ring
        d.ellipse([cx - r - ring, cy - r - ring, cx + r + ring, cy + r + ring], fill=BG)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=REC)
    img.alpha_composite(over.resize((size, size), Image.LANCZOS))
    return img


def ico_bytes() -> bytes:
    from io import BytesIO
    buf = BytesIO()
    draw(256).save(buf, format="ICO", sizes=[(n, n) for n in SIZES])
    return buf.getvalue()


def save_ico(path: str) -> None:
    with open(path, "wb") as fh:
        fh.write(ico_bytes())


def ensure_ico(root: str) -> str:
    """The icon file for the taskbar and the shortcuts in ``root`` (FILE): written once when missing or empty
    (the picture's version is in the name, so an existing file is this picture; drawing the nine sizes takes
    ~180 ms, not spent at every start). Written through a temporary file, so a crash leaves no half file."""
    path = os.path.join(root, FILE)
    try:
        if os.path.getsize(path) > 0:
            return path
    except OSError:
        pass
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(ico_bytes())
    os.replace(tmp, path)
    return path


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m fogscout.icon PATH.ico")
    save_ico(sys.argv[1])
