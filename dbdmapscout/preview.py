"""The overlay tab's preview (since 1.61; 1.64, user: "jedes UI-Element in der Vorschau, Regler sofort sichtbar"):
everything the game will show – the map with timer/record/server, the system values with "today", the music
card – rendered with the very functions the overlay windows use, as layers in screen pixels. Pure (PIL only)."""
from __future__ import annotations

import time
from functools import lru_cache

from PIL import Image, ImageDraw

from . import layout, media, sysinfo
from .overlay_win32 import add_info, compose, render_hud, render_music

SAMPLE_SNAPSHOT = dict(cpu_load=38, cpu_temp=64, gpu_temp=71, gpu_load=92, gpu_name="GPU",
                       vram_used=7.1, vram_total=16, ram_used=17.2, ram_total=32, gpu_power=241)


RENDER_H = 1440              # pictures at this game height at most: smaller ones distort (fonts have a minimum size)


@lru_cache(maxsize=1)
def sample_cover() -> Image.Image:
    """A made-up cover for the preview while nothing plays."""
    c = Image.new("RGBA", (96, 96))
    d = ImageDraw.Draw(c)
    for y in range(96):
        t = y / 96
        d.line([(0, y), (96, y)], fill=(int(200 - 150 * t), int(30 + 20 * t), int(60 + 120 * t), 255))
    d.ellipse((24, 24, 72, 72), outline=(255, 230, 120, 255), width=5)
    return c


def sample_snapshot():
    return sysinfo.Snapshot(t=time.time(), **SAMPLE_SNAPSHOT)


def overlay_picture(pic, map_h: int, caption: str, transparent: bool, timer: str, server: str, ping, record: str,
                    text_h: int = 0):
    """The map window's picture (PictureOverlay.render for one frame); ``pic`` None = info only; ``text_h``: size
    of the name and the lines below (1.65: its own, not the map's)."""
    text_h = max(40, text_h or map_h)
    base = compose(pic, map_h, caption, transparent, False, text_h) if pic is not None \
        else Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    if timer or server or record:
        base = add_info(base, timer, server, text_h, backdrop=not transparent, ping=ping, record=record)
    return base


_CACHE: dict = {}             # one picture per layer: a slider that moves the map does not redraw the others


def fitted(render, height: int, avail_w: float, key=None):
    """render(height) once more smaller when it is wider than ``avail_w`` (like App._hud_place); ``key``: the
    layer's name and inputs – the same inputs give the same picture without drawing it again."""
    if key is not None:
        hit = _CACHE.get(key[0])
        if hit is not None and hit[0] == (key[1:], height, avail_w):
            return hit[1]
    img = render(height)
    if avail_w > 0 and img.width > avail_w:
        img = render(max(200, int(height * avail_w / img.width)))
    if key is not None:
        _CACHE[key[0]] = ((key[1:], height, avail_w), img)
    return img


def music_rows(now: media.NowPlaying, wall: float):
    """Rows and cover of the music card: what plays, else a sample (so the preview always shows the card)."""
    if media.playing(now, wall):
        p = media.progress(now, wall)
        return media.rows(now, wall, "", sysinfo.DIM, sysinfo.WHITE), now.cover, \
            (int(p[0]), int(p[1])) if p else None
    sample = media.NowPlaying("Blinding Lights", "The Weeknd", True, wall)
    return media.rows(sample, wall, "", sysinfo.DIM, sysinfo.WHITE), sample_cover(), (70, 176)


def layers(gw: int, gh: int, o: dict, hud_side: str, hud_rows: list, hud_own, map_pic, caption: str,
           info: dict, height_frac: float, music=None):
    """[(name, picture, x, y)] in screen pixels, bottom to top, + the map's (x, y, w, h) for clicks.
    ``o`` = settings["overlay"], ``hud_side`` = settings["sysinfo"] (or "right" for "today" alone, "" for none),
    ``info`` = timer/server/ping/record lines, ``music`` = (rows, cover) or None."""
    margin = int(gh * o["margin"])
    bar = layout.bar_width(gw, gh)
    avail = layout.max_width(bar, margin) if bar >= layout.MIN_BAR else gw / 3
    out = []
    hud = None
    if hud_side and hud_rows:
        hh = int(gh * min(2.0, max(0.6, float(o.get("hud_scale", 1.0)))))      # its own size (1.64.9)
        hud = fitted(lambda h: render_hud(hud_rows, h), hh, avail, ("hud", repr(hud_rows)))
    drop = hud.height + margin if hud is not None and hud_side != "custom" \
        and layout.below_hud(hud_side, o["anchor"]) else 0
    aspect = map_pic.width / map_pic.height if map_pic is not None else 0.8
    rows = sum(1 for k in ("timer", "server", "record") if info.get(k))
    rows += 1 if info.get("timer") else 0
    _x, _y, _w, _h, mh = layout.preview_rect(gw, gh, o["anchor"], o.get("pos_x", 0.0), o.get("pos_y", 0.0),
                                             height_frac, o["margin"], o.get("keep_in_bar", True), aspect, rows,
                                             drop)
    text_h = int(gh * 0.36 * min(2.0, max(0.5, float(o.get("text_scale", 1.0)))))     # App._text_height
    over = fitted(lambda h: overlay_picture(map_pic, h, caption, o.get("transparent", True), info.get("timer", ""),
                                            info.get("server", ""), info.get("ping"), info.get("record", ""),
                                            text_h),
                  mh, 0, ("map", id(map_pic), caption, o.get("transparent", True), repr(info), text_h))
    x0, _y0 = layout.preview_place(gw, gh, o["anchor"], o.get("pos_x", 0.0), o.get("pos_y", 0.0), margin, False,
                                   over.width, over.height, drop)
    in_bar = (o["anchor"] == "auto" or o.get("keep_in_bar", True)) and \
        layout.bar_side(o["anchor"], x0, over.width, 0, gw, bar)
    if in_bar and over.width > avail:                   # lines wider than the bar: smaller text, like the game
        f = avail / over.width
        over = fitted(lambda h: overlay_picture(map_pic, h, caption, o.get("transparent", True),
                                                info.get("timer", ""), info.get("server", ""), info.get("ping"),
                                                info.get("record", ""), max(40, int(text_h * f))),
                      mh, 0,
                      ("map", id(map_pic), caption, o.get("transparent", True), repr(info), int(text_h * f)))
        if over.width > avail:                          # still too wide: the map too
            g = avail / over.width
            over = fitted(lambda h: overlay_picture(map_pic, h, caption, o.get("transparent", True),
                                                    info.get("timer", ""), info.get("server", ""), info.get("ping"),
                                                    info.get("record", ""), max(40, int(text_h * f * g))),
                          max(80, int(mh * g)), 0,
                          ("map", id(map_pic), caption, o.get("transparent", True), repr(info),
                           int(text_h * f * g)))
    mx, my = layout.preview_place(gw, gh, o["anchor"], o.get("pos_x", 0.0), o.get("pos_y", 0.0), margin,
                                  o.get("keep_in_bar", True), over.width, over.height, drop)
    map_rect = (mx, my, over.width, over.height)
    out.append(("map", over, mx, my))
    hud_rect = None
    if hud is not None:
        hx, hy = layout.hud_preview_xy(hud_side, gw, gh, margin, hud.size, hud_own, map_rect)
        out.append(("hud", hud, hx, hy))
        hud_rect = (hx, hy, hud.width, hud.height)
    if music:
        rows_m, cover, prog = music
        prog = prog if o.get("media_progress", True) else None
        scale = max(60, min(200, o.get("media_scale", 1.0) * 100)) / 100
        spot = o.get("media_pos", "below")
        show_cover = cover if o.get("media_cover", True) else None
        style = o.get("media_style", "big")
        card = fitted(lambda h: render_music(rows_m, show_cover, h, style, prog), int(gh * scale),
                      avail if spot != "custom" else gw / 3, ("music", repr(rows_m), id(show_cover), style, prog))
        cx, cy = layout.media_xy(spot, (0, 0, gw, gh), card.size, margin, hud_rect, o.get("media_xy"))
        out.append(("music", card, int(cx), int(cy)))
    return out, map_rect
