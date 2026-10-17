"""Program icon (drawn, so no binary file is needed in the repository).

    python -m dbdmapscout.icon PATH.ico     -> writes a multi-size .ico (16 … 256 px)

Styled like the callout maps: lavender blocky map on dark ground with a white marker.
"""
from __future__ import annotations

import sys

from PIL import Image, ImageDraw

BG = (20, 20, 22, 255)
MAP = (140, 147, 232, 255)
MARK = (255, 255, 255, 255)
SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]


def draw(size: int = 256) -> Image.Image:
    s = 4 * size                                  # draw large, scale down (smooth edges)
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    u = s / 16
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(3.2 * u), fill=BG)
    # blocky map made of rooms (like the callout maps), separated by thin dark walls
    for x0, y0, x1, y1 in ((2.5, 3, 9, 8), (9, 3, 13.5, 8), (2.5, 8, 7, 13), (7, 8, 13.5, 13)):
        d.rectangle([x0 * u, y0 * u, x1 * u, y1 * u], fill=MAP)
    wall = max(1, int(0.45 * u))
    d.rectangle([2.5 * u, 8 * u - wall // 2, 13.5 * u, 8 * u + wall // 2], fill=BG)
    d.rectangle([9 * u - wall // 2, 3 * u, 9 * u + wall // 2, 6 * u], fill=BG)       # door gap below
    d.rectangle([7 * u - wall // 2, 10 * u, 7 * u + wall // 2, 13 * u], fill=BG)     # door gap above
    # white marker box like the M/S boxes of the maps
    d.rectangle([10.2 * u, 9.3 * u, 12.6 * u, 11.7 * u], fill=MARK)
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


def save_ico(path: str) -> None:
    draw(256).save(path, format="ICO", sizes=[(n, n) for n in SIZES])


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m dbdmapscout.icon PATH.ico")
    save_ico(sys.argv[1])
