"""The overlay tab's preview (since 1.61; 1.64, user: "jedes UI-Element in der Vorschau, Regler sofort sichtbar"):
everything the game will show – the map with timer/record/server, the system values with "today", the music
card – rendered with the very functions the overlay windows use, as layers in screen pixels. Pure (PIL only)."""
from __future__ import annotations

import time
from functools import lru_cache

from PIL import Image, ImageDraw

from . import layout, media, sysinfo
from . import skin
from .i18n import _
from .overlay_win32 import (add_info, backdrop, backdrop_pad, body_cols, compose, info_card, map_backdrop, map_body,
                            music_body, music_card, render_hud)

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
                    text_h: int = 0, dark_area: bool = False, style: str = "classic", accent=None, name: str = "",
                    realm: str = ""):
    """The map window's picture (PictureOverlay.render for one frame); ``pic`` None = info only; ``text_h``: size
    of the name and the lines below (1.65: its own, not the map's). ``style`` (1.3.1): glass / chips / line draw
    the card in skin.map_card (``name``/``realm`` for its header)."""
    text_h = max(40, text_h or map_h)
    if style in ("glass", "line"):
        body = map_body(pic, map_h, _split(pic)) if pic is not None else None
        return skin.map_card(body, name, realm, timer, "", record, server, ping, (), text_h, style, accent)
    base = compose(pic, map_h, caption, transparent, False, text_h, _split(pic), _cols(pic)) \
        if pic is not None else Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    if style == "chips":
        return skin.map_card(base if pic is not None else None, name, realm, timer, "", record, server, ping, (),
                             text_h, style, accent)
    if timer or server or record:
        base = add_info(base, timer, server, text_h, backdrop=not transparent, ping=ping, record=record)
    return map_backdrop([base], text_h)[0] if dark_area else base


_SPLITS: dict = {}
_BODY: list = [None, None]                  # [key, body] of the music card: only its progress changes each second


def _music_body(rows, cover, height, style, look):
    """music_body once per song and size (1.3.3, user: the window felt laggy – the preview drew cover, text and
    shadow anew every second although only the progress strip moved; the HUD window splits it since 1.2.13)."""
    key = (repr(rows), id(cover), height, style, "accent" in look, tuple(k for k in look if k.startswith("cover_")))
    if _BODY[0] != key:
        _BODY[0], _BODY[1] = key, (music_body(rows, cover, height, style, look), cover)   # cover kept: id stays
    return _BODY[1][0]


def _cols(pic):
    """overlay_win32.body_cols of the picture (1.8.24), once per picture."""
    key = ("cols", id(pic))
    if key not in _SPLITS:
        _SPLITS[key] = body_cols(pic, _split(pic))
    return _SPLITS[key]


def extent(pic):
    """(w, h) the map's size is fitted by: as wide as what is drawn below its name (1.8.24)."""
    cols = _cols(pic) if _split(pic) else None
    return (cols[1] - cols[0] if cols else pic.width), pic.height


def _split(pic):
    """Row where the map starts below its drawn-in name (mapimage.title_split), once per picture (1.65.4)."""
    key = id(pic)
    if key not in _SPLITS:
        from .mapimage import title_split
        parts = title_split(pic)
        _SPLITS.clear() if len(_SPLITS) > 16 else None
        _SPLITS[key] = parts[2] if parts else None
    return _SPLITS[key]


_CACHE: dict = {}             # {layer: {inputs: picture}}: a slider that moves the map does not redraw the others
CACHE_PER_LAYER = 8           # 1.3.3: the map is tried at a few sizes per refresh (smaller text, smaller map) – with
                              # one slot per layer those evicted each other and the map was scaled anew 4×/s


def fitted(render, height: int, avail_w: float, key=None, fits=None):
    """render(height) once more smaller when it is wider than ``avail_w`` (like App._hud_place); ``key``: the
    layer's name and inputs – the same inputs give the same picture without drawing it again; ``fits`` (1.8.24):
    gets {name: drawn height / asked height} – below 1 the bar holds the element back, a bigger size shows nothing."""
    slot = hit = None
    if key is not None:
        slot = _CACHE.setdefault(key[0], {})
        hit = slot.get((key[1:], height, avail_w))
    if hit is None:
        used = height
        img = render(height)
        if avail_w > 0 and img.width > avail_w:
            used = max(200, int(height * avail_w / img.width))
            img = render(used)
        hit = (img, used)
        if slot is not None:
            if len(slot) >= CACHE_PER_LAYER:
                slot.pop(next(iter(slot)))              # the oldest entry
            slot[(key[1:], height, avail_w)] = hit
    if fits is not None and key is not None:
        fits[key[0]] = hit[1] / max(1, height)
    return hit[0]


def music_rows(now: media.NowPlaying, wall: float):
    """Rows and cover of the music card: what plays, else a sample (so the preview always shows the card)."""
    if media.playing(now, wall):
        p = media.progress(now, wall)
        return media.rows(now, wall, "", sysinfo.DIM, sysinfo.WHITE), now.cover, \
            (int(p[0]), int(p[1])) if p else None
    sample = media.NowPlaying("Blinding Lights", "The Weeknd", True, wall)
    return media.rows(sample, wall, "", sysinfo.DIM, sysinfo.WHITE), sample_cover(), (70, 176)


def layers(gw: int, gh: int, o: dict, hud_side: str, hud_rows: list, hud_own, map_pic, caption: str,
           info: dict, height_frac: float, music=None, today=None, editing: bool = False, accent=None,
           upnext=None, fits=None):
    """[(name, picture, x, y)] in screen pixels, bottom to top, + the map's (x, y, w, h) for clicks.
    ``o`` = settings["overlay"], ``hud_side`` = settings["sysinfo"] ("" for none), ``info`` = timer/server/ping/
    record lines, ``music`` = (rows, cover) or None, ``today`` = rows of "today" (its own card, 1.2.6) or None,
    ``upnext`` = (label, items) of the Spotify queue on the music card (1.8) or None, ``fits`` (1.8.24): a dict
    that gets {element: shown size / asked size} – "map", "text", "hud", "today", "music"."""
    fits = {} if fits is None else fits
    margin = int(gh * o["margin"])
    bar = layout.bar_width(gw, gh)
    avail = layout.max_width(bar, margin) if bar >= layout.MIN_BAR else gw / 3
    align, gap = o.get("bar_align", "centre"), layout.stack_gap(o, gh)        # 1.2.8
    out = []
    hud = None
    if bar < layout.MIN_BAR and not editing:                # like the App: without black bars only own places
        hud_side = hud_side if hud_side == "custom" else ""   # (in the move mode everything shows, to drag it)
        today = today if o.get("today_pos", "below") == "custom" else None
        music = music if o.get("media_pos", "below") == "custom" else None
    style = o.get("style", "classic") if o.get("style", "classic") in skin.STYLES else "classic"   # 1.3
    modern = style != "classic"
    if hud_side and hud_rows:
        hh = int(gh * min(2.0, max(0.6, float(o.get("hud_scale", 1.0)))))      # its own size (1.64.9)
        boxed = bool(o.get("hud_backdrop", False))
        hud = fitted((lambda h: skin.card(hud_rows, h, style, accent, _("SYSTEM"))) if modern else
                     (lambda h: backdrop(render_hud(hud_rows, h), h) if boxed else render_hud(hud_rows, h)), hh, avail,
                     ("hud", repr(hud_rows), boxed, style, accent), fits)
    cards = {}                                              # name: (picture, position setting, own place)
    if today:
        th = int(gh * min(2.0, max(0.6, float(o.get("today_scale", 1.0)))))
        tboxed = bool(o.get("today_backdrop", False))
        tspot = o.get("today_pos", "below")
        cards["today"] = (fitted((lambda h: skin.card(today, h, style, accent)) if modern else
                                 (lambda h: backdrop(render_hud(today, h), h) if tboxed else render_hud(today, h)),
                                 th, avail if tspot != "custom" else gw / 3, ("today", repr(today), tboxed, style, accent),
                                 fits),
                          tspot, o.get("today_xy"))
    if music:
        rows_m, cover, prog = music
        prog = prog if o.get("media_progress", True) else None
        scale = max(60, min(200, o.get("media_scale", 1.0) * 100)) / 100
        spot = o.get("media_pos", "below")
        show_cover = cover if o.get("media_cover", True) else None
        look = media.look(o)
        mstyle = o.get("media_style", "big")
        npos = o.get("media_next_pos", "below")
        cards["music"] = (fitted((lambda h: skin.music(rows_m, show_cover, h, style, prog, look, accent, mstyle,
                                                       upnext, npos)) if modern
                                 else (lambda h: music_card(_music_body(rows_m, show_cover, h, mstyle, look), h,
                                                            mstyle, prog, look, upnext, npos)),
                                 int(gh * scale), avail if spot != "custom" else gw / 3,
                                 ("music", repr(rows_m), id(show_cover), mstyle, prog, look, style, accent,
                                  repr(upnext), npos), fits),
                          spot, o.get("media_xy"))
    # system values and cards first (1.2.11: like the App), the map moves below / above what stands at the
    # top / bottom of its bar – except with the system values right above the map: those follow it afterwards
    hud_rect = None
    placed = {}
    game = (0, 0, gw, gh)
    bands = layout.bar_bands(o, game, margin)               # 1.8.14: the limiter lines of the bars, like the App
    if hud is not None and hud_side != "above":
        hx, hy = layout.hud_preview_xy(hud_side, gw, gh, margin, hud.size, hud_own, None, align, gap)
        hud_rect = layout.clamp_box((hx, hy, hud.width, hud.height), game, bands)
    spots = {n: c[1] for n, c in cards.items()}
    free = {n: (c[0].size, c[1], c[2]) for n, c in cards.items()
            if hud_side != "above" or not layout.hangs_on_hud(n, spots)}  # the rest waits for the values
    placed = layout.place_cards(game, free, hud_rect, margin, align, gap, bands=bands)
    drop = lift = 0
    span = layout.map_bar_range(o["anchor"], o.get("pos_x", 0.0), 0, gw, bar)
    band = bands["left" if span[0] <= 0 else "right"] if bands and span else None
    if span and o["anchor"] != "custom":
        fixed = [hud_rect] + [placed[n] for n in placed if cards[n][1] != "custom"]
        drop, lift = layout.bar_room(fixed, span[0], span[1], 0, gh, margin, gap, band)
        if band and hud is not None and hud_side == "above":     # values + cards above the map (1.8.14)
            drop += layout.follow_reserve(hud.height, {n: c[0].size for n, c in cards.items()}, spots, gap)
    text_h = int(gh * 0.36 * min(2.0, max(0.5, float(o.get("text_scale", 1.0)))))     # App._text_height
    dark = bool(o.get("map_backdrop", False))
    # 1.8.24: the lines as an element of their own ("text") – drawn first, the map makes room for them
    apart = layout.info_apart(o) and map_pic is not None
    ispot = o.get("info_pos", "below")
    lines = {k: v for k, v in info.items() if k in ("name", "realm")} if apart else info
    info_pic = None
    if apart and (info.get("timer") or info.get("server") or info.get("record") or editing):
        timer = info.get("timer", "") or ("0:00" if editing else "")
        info_pic = fitted(lambda hh: info_card(timer, info.get("server", ""), info.get("ping"), "",
                                               info.get("record", ""), hh, style, accent,
                                               o.get("transparent", True), dark),
                          text_h, avail if bar >= layout.MIN_BAR and ispot != "custom" else 0,
                          ("text", repr(info), timer, style, accent, o.get("transparent", True), dark), fits)
        idrop, ilift = layout.info_reserve(o, info_pic.size, gap)
        drop, lift = drop + idrop, lift + ilift
    aspect = extent(map_pic)[0] / map_pic.height if map_pic is not None else 0.8
    rows = sum(1 for k in ("timer", "server", "record") if lines.get(k))
    rows += 1 if lines.get("timer") else 0
    _x, _y, _w, _h, mh = layout.preview_rect(gw, gh, o["anchor"], o.get("pos_x", 0.0), o.get("pos_y", 0.0),
                                             height_frac, o["margin"], o.get("keep_in_bar", True), aspect, rows,
                                             drop, bool(o.get("grow_past_bar", False)), lift)
    def map_pic_at(h, th):
        return fitted(lambda hh: overlay_picture(map_pic, hh, caption, o.get("transparent", True),
                                                 lines.get("timer", ""), lines.get("server", ""), lines.get("ping"),
                                                 lines.get("record", ""), th, dark, style, accent,
                                                 lines.get("name", ""), lines.get("realm", "")),
                      h, 0, ("map", id(map_pic), caption, o.get("transparent", True), dark, repr(lines), th, style,
                             accent))

    over = map_pic_at(mh, text_h)
    x0, _y0 = layout.preview_place(gw, gh, o["anchor"], o.get("pos_x", 0.0), o.get("pos_y", 0.0), margin, False,
                                   over.width, over.height, drop)
    in_bar = (o["anchor"] == "auto" or o.get("keep_in_bar", True)) and \
        layout.bar_side(o["anchor"], x0, over.width, 0, gw, bar)
    edge = min(skin.frame_pad(style, text_h) if modern else backdrop_pad(text_h) if dark else 0, max(0, margin - 2))
    th = text_h
    if in_bar and over.width > avail + 2 * edge and not o.get("grow_past_bar", False):
        map_w = round(mh * aspect) + 2 * edge
        for _try in range(3):                           # lines wider: smaller text (the area's edge does not scale)
            if over.width <= avail + 2 * edge or over.width <= map_w or th <= 40:
                break
            th = max(40, int(th * (avail + 2 * edge) / over.width))
            over = map_pic_at(mh, th)
        if over.width > avail + 2 * edge:               # still too wide: the map too
            g = (avail + 2 * edge) / over.width
            mh, th = max(80, int(mh * g)), max(40, int(th * g))
            over = map_pic_at(mh, th)
    over_h_room = gh - drop - lift - 2 * margin if o["anchor"] != "custom" else \
        layout.own_room((x0, 0, over.width, over.height), game, bands)       # 1.8.22: between its bar's lines
    if info_pic is not None and o["anchor"] == "custom" and ispot in ("below", "above"):
        over_h_room -= info_pic.height + gap
    for _try in range(3):                                   # the lines below the map made it too tall: smaller
        if over.height <= over_h_room or mh <= 80:
            break
        mh = max(80, mh - (over.height - over_h_room))
        over = map_pic_at(mh, th)
    asked = gh * min(0.9, max(0.05, height_frac))
    fits["map"] = mh / max(1.0, asked)
    if not apart:
        fits["text"] = th / max(1, text_h)
    mx, my = layout.preview_place(gw, gh, o["anchor"], o.get("pos_x", 0.0), o.get("pos_y", 0.0), margin,
                                  o.get("keep_in_bar", True), over.width, over.height, drop, align, lift)
    if in_bar and edge:                                 # the area's edge may stand in the margin (like the App)
        mx = int(layout.clamp_x(in_bar, mx, over.width, 0, gw, bar, margin - edge))
    if o["anchor"] == "custom" and band:                # an own place in a bar stays between its lines (1.8.14)
        my = layout.clamp_box((mx, my, over.width, over.height), game, bands)[1]
    map_rect = (mx, my, over.width, over.height)
    out.append(("map", over, mx, my))
    block = map_rect                                    # what hangs above/below the map goes around both
    if info_pic is not None:
        ix, iy = layout.info_xy(ispot, map_rect, info_pic.size, game, gap, margin, o.get("info_xy"), align, bands)
        out.append(("text", info_pic, ix, iy))
        if ispot != "custom":
            block = layout.union(map_rect, (ix, iy, info_pic.width, info_pic.height))
    if hud is not None and hud_side == "above":             # right above the map, the cards below them
        side = layout.box_side(block, game) if bands else None
        hx, hy = layout.hud_preview_xy(hud_side, gw, gh, margin, hud.size, hud_own, block, align, gap,
                                       top=bands[side][0] if side else 0)
        hud_rect = layout.clamp_box((hx, hy, hud.width, hud.height), game, bands)
        hy = hud_rect[1]
        placed = layout.place_cards(game, {n: (c[0].size, c[1], c[2]) for n, c in cards.items()},
                                    hud_rect, margin, align, gap, up=hy < block[1], below_box=block, bands=bands)
    if hud_rect is not None:
        out.append(("hud", hud, hud_rect[0], hud_rect[1]))
    for name, (cx, cy, _w, _h) in placed.items():       # stacked in order (1.2.7), like the App
        out.append((name, cards[name][0], cx, cy))
    return out, map_rect
