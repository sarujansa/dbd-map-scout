"""Keep the overlay inside the black bars of an ultrawide screen (pure logic, testable).

DBD renders 16:9 centred; on 21:9 the bars left/right are empty. A map placed there must not
reach into the game picture. Which bar applies:
  auto, top-left, bottom-left      -> left bar
  top-right, bottom-right          -> right bar
  custom                           -> the bar the overlay starts in (left edge in the left bar,
                                      right edge in the right bar); placed over the game on
                                      purpose (both edges inside the picture) -> no limit
"""
from __future__ import annotations

MIN_BAR = 200          # narrower bars (e.g. 16:10 letterbox) are not used for the map
MIN_VBAR = 100         # black bar above/below the picture (window narrower than 16:9) used for map and values
VBAR_FRESH = 3.0       # s: a measurement older than this (lobby, menus: no bars) does not count


def bar_width(gw: float, gh: float) -> float:
    """Width of one black bar left/right of the centred 16:9 picture (0 if none)."""
    return max(0.0, (gw - gh * 16 / 9) / 2)


def bar_side(anchor: str, x: float, w: float, gx: float, gw: float, bar: float):
    """'left', 'right' or None (no bar to stay in)."""
    if bar < MIN_BAR:
        return None
    if anchor in ("auto", "top-left", "bottom-left"):
        return "left"
    if anchor in ("top-right", "bottom-right"):
        return "right"
    if x < gx + bar:
        return "left"
    if x + w > gx + gw - bar:
        return "right"
    return None


def max_width(bar: float, margin: float) -> float:
    return bar - 2 * margin


def fit_height(height: int, avail: float, img_w: int, img_h: int, minimum: int = 80) -> int:
    """Largest height <= ``height`` at which the scaled map (compose: round(img_w * h / img_h)) is at
    most ``avail`` wide. Computed from the picture size, so nothing too big is ever put on screen
    (rendering first and shrinking afterwards made the overlay pulse on every tick)."""
    if img_w <= 0 or img_h <= 0 or round(img_w * height / img_h) <= avail:
        return height
    h = int(avail * img_h / img_w) + 1
    while h > minimum and round(img_w * h / img_h) > avail:
        h -= 1
    return max(minimum, min(height, h))


def clamp_x(side: str, x: float, w: float, gx: float, gw: float, bar: float, margin: float) -> float:
    """Move x so that [x, x+w] lies inside the bar (with margin). Wider than the bar (1.65.4: may grow past it):
    at the bar's outer edge, reaching into the game picture – never off the screen."""
    if side == "left":
        lo, hi = gx + margin, gx + bar - margin - w
    else:
        lo, hi = gx + gw - bar + margin, gx + gw - margin - w
    if hi < lo:
        return lo if side == "left" else hi
    return min(max(x, lo), hi)


def outside_slot(ox: float, ow: float, mx: float, mw: float, min_w: float = MIN_BAR):
    """Free desktop space beside a DBD window that does not fill the monitor (windowed mode):
    ("left" | "right", x0, width) or None. ``ox``/``ow``: the window's outer edges, ``mx``/``mw``:
    the monitor's work area. Left is preferred, like the left bar on ultrawide."""
    left, right = ox - mx, mx + mw - (ox + ow)
    if left >= min_w:
        return "left", mx, left
    if right >= min_w:
        return "right", ox + ow, right
    return None


def slot_x(slot, w: float, margin: float) -> float:
    """x of an overlay ``w`` wide in ``slot``: right next to the window (short way for the eyes),
    never past the monitor edge."""
    side, x0, width = slot
    if side == "left":
        return max(x0 + margin, x0 + width - margin - w)
    return x0 + margin


def bar_centre(side: str, gx: float, gw: float, bar: float) -> float:
    """x of the middle of the left/right black bar."""
    return gx + bar / 2 if side == "left" else gx + gw - bar / 2


ALIGNS = ("left", "centre", "right")


def stack_gap(o: dict, gh: float) -> int:
    """Room between stacked cards and between the system values and a map below/above them (1.2.8, user's
    pick: one slider) – ``overlay.stack_gap`` px at 1440p, scaled with the game height."""
    return max(0, round(float(o.get("stack_gap", 8)) * gh / 1440))


def aligned_x(align: str, lo: float, hi: float, centre: float, w: float) -> float:
    """x of a block of width ``w`` in [lo, hi]: at the left edge, round ``centre`` or at the right edge (1.2.8)."""
    if align == "left":
        x = lo
    elif align == "right":
        x = hi
    else:
        x = centre - w / 2
    return min(max(x, lo), max(lo, hi))


def hud_x(side: str, gx: float, gw: float, margin: float, w: float, bar: float = 0, align: str = "centre") -> float:
    """x of the system values at the top of a bar: centred in it (1.65.2, user: "untereinander und mittig"; since
    1.2.8 ``align`` = left / centre / right), without a wide bar from the left edge / flush right."""
    if bar >= MIN_BAR:
        lo, hi = (gx + margin, gx + bar - margin - w) if side == "left" else \
            (gx + gw - bar + margin, gx + gw - margin - w)
        return aligned_x(align, lo, hi, bar_centre(side, gx, gw, bar), w)
    return gx + margin if side == "left" else gx + gw - margin - w


def below_hud(hud_side, anchor: str) -> bool:
    """Map at the top of the same bar as the system values: it moves down below them."""
    tops = {"left": ("auto", "top-left"), "right": ("top-right",), "above": ("auto", "top-left", "top-right")}
    return bool(hud_side) and anchor in tops.get(hud_side, ())


def vbars(measured, gw: float, gh: float, now: float):
    """(top, bottom) black bars above/below the picture to put map and system values in, or None.
    ``measured``: worker.vbars = (top, bottom, time, (w, h)). Only for windows without side bars, only while the
    measurement is fresh (the bars exist in the trial only) and for this window size."""
    if not measured or bar_width(gw, gh) >= MIN_BAR:
        return None
    top, bottom, t, size = measured
    if now - t > VBAR_FRESH or tuple(size) != (int(gw), int(gh)) or min(top, bottom) < MIN_VBAR:
        return None
    return top, bottom


def fit_scale(w: float, h: float, avail_w: float, avail_h: float) -> float:
    """Factor (≤ 1) that makes a w×h picture fit into avail_w×avail_h."""
    if w <= 0 or h <= 0:
        return 1.0
    return min(1.0, avail_w / w, avail_h / h)


def preview_place(gw: int, gh: int, anchor: str, pos_x: float, pos_y: float, margin: int, keep_in_bar: bool,
                  w: int, h: int, drop: int = 0, align: str = "centre"):
    """Top-left corner of an overlay of w × h on a full-screen DBD (App._place_overlay's rules for the preview);
    ``drop``: room the system values take above a map at the top of the same bar."""
    bar = bar_width(gw, gh)
    if anchor == "auto":
        x, y = max(margin, (bar - w) / 2) if align == "centre" else (bar - margin - w if align == "right" else margin), \
            margin + drop
    elif anchor == "custom":
        x, y = pos_x * max(0, gw - w), pos_y * max(0, gh - h)
    else:
        x = margin if anchor.endswith("left") else gw - w - margin
        y = margin + drop if anchor.startswith("top") else gh - h - margin
    side = bar_side(anchor, x, w, 0, gw, bar) if (anchor == "auto" or keep_in_bar) else None
    if side:
        x = clamp_x(side, x, w, 0, gw, bar, margin)
    return int(x), int(y)


def preview_rect(gw: int, gh: int, anchor: str, pos_x: float, pos_y: float, height_frac: float,
                 margin_frac: float, keep_in_bar: bool, aspect: float, info_rows: int = 0, drop: int = 0,
                 grow: bool = False):
    """Where the overlay sits on a full-screen DBD of gw × gh (the overlay tab's preview, since 1.61): (x, y, w,
    h, map_h) – the same rules as App._place_overlay for the common case (no window mode, no bars above/below).
    ``aspect`` = map width / height, ``info_rows`` = lines below the map (timer counts double), ``drop`` = room
    of the system values above the map (1.64)."""
    margin = int(gh * margin_frac)
    height = int(gh * min(0.9, max(0.05, height_frac)))
    height = min(height, gh - drop - 2 * margin)
    bar = bar_width(gw, gh)

    def size(hm):
        info = 0 if not info_rows else round(hm * (0.11 + 0.055 * max(0, info_rows - 2)))
        return max(1, round(hm * aspect)), hm + info

    w, h = size(height)
    x0, _y0 = preview_place(gw, gh, anchor, pos_x, pos_y, margin, False, w, h, drop)
    side = bar_side(anchor, x0, w, 0, gw, bar) if (anchor == "auto" or keep_in_bar) else None
    if side and not grow:
        avail = max_width(bar, margin)
        if w > avail:
            height = max(40, int(height * avail / w))
            w, h = size(height)
    x, y = preview_place(gw, gh, anchor, pos_x, pos_y, margin, keep_in_bar, w, h, drop)
    return x, y, w, h, height


def hud_preview_xy(side: str, gw: int, gh: int, margin: int, size, own=None, map_rect=None, align: str = "centre",
                   gap=None):
    """Top-left corner of the system values on a full-screen DBD (App._hud_place / _hud_follow_map, 1.64)."""
    w, h = size
    if side == "custom":
        fx, fy = own or (1.0, 0.0)
        return int(fx * max(0, gw - w)), int(fy * max(0, gh - h))
    if side == "above" and map_rect:
        x, y, mw, mh = map_rect
        gap = max(2, margin // 2) if gap is None else gap
        bar = bar_width(gw, gh)
        lo, hi = 0, gw - w
        if bar >= MIN_BAR and x < bar:
            lo, hi = gap, bar - gap - w
        elif bar >= MIN_BAR and x + mw > gw - bar:
            lo, hi = gw - bar + gap, gw - gap - w
        hx = min(max(x + (mw - w) / 2, lo), max(lo, hi))
        hy = y - gap - h if y - gap - h >= 0 else y + mh + gap
        return int(hx), int(hy)
    return int(hud_x("left" if side == "left" else "right", 0, gw, margin, w, bar_width(gw, gh), align)), margin


def pos_from_point(gw: int, gh: int, w: int, h: int, cx: float, cy: float):
    """Own position (pos_x, pos_y as in the settings) that puts an overlay of w × h with its centre at (cx, cy)."""
    fx = (cx - w / 2) / max(1, gw - w)
    fy = (cy - h / 2) / max(1, gh - h)
    return min(1.0, max(0.0, fx)), min(1.0, max(0.0, fy))


def media_xy(spot: str, game, size, margin: int, hud=None, own=None, align: str = "centre", gap=None):
    """Top-left corner of the music card (1.64): "below" the system values (centred under them; without them at
    the top of the right bar), "bottom_right" / "bottom_left" in the black bar (1.65.2: centred in it, on one
    line with the system values above), "custom" = ``own`` (share of the free room in the game window, like the
    system values' own place). 1.2.8: ``align`` = left / centre / right in the bar and under the card above,
    ``gap`` = px below the card above (default half the margin)."""
    gx, gy, gw, gh = game
    w, h = size
    bar = bar_width(gw, gh)
    gap = max(2, margin // 2) if gap is None else gap
    if spot == "custom":                      # 1.2.5: by its centre – a wider/taller card (long title) stays put
        fx, fy = own or (1.0, 1.0)
        return (min(max(gx + fx * gw - w / 2, gx), gx + max(0, gw - w)),
                min(max(gy + fy * gh - h / 2, gy), gy + max(0, gh - h)))
    if spot in ("bottom_left", "bottom_right"):
        side = "left" if spot == "bottom_left" else "right"
        return hud_x(side, gx, gw, margin, w, bar, align), gy + gh - margin - h
    if hud:
        x = aligned_x(align, gx + margin, gx + gw - margin - w, hud[0] + hud[2] / 2, w)
        if align == "left":
            x = min(max(hud[0], gx + margin), gx + gw - margin - w)
        elif align == "right":
            x = min(max(hud[0] + hud[2] - w, gx + margin), gx + gw - margin - w)
        return x, hud[1] + hud[3] + gap
    return hud_x("right", gx, gw, margin, w, bar, align), gy + margin


STACK_ANCHORS = {"below": "hud", "under_today": "today", "under_music": "music"}


def stack_order(spots: dict) -> list:
    """[(name, anchor)] for the cards that may hang below another element (1.2.7, user: "Elemente stapeln"), in
    the order to place them: an anchor before the card below it. ``spots`` = {name: its position setting};
    ``anchor`` = "hud" / another name / None (a place of its own). A card under a card that is not there, or in a
    loop (today under music, music under today), hangs below the system values instead."""
    rest = {n: STACK_ANCHORS.get(s) for n, s in spots.items()}
    order = list(spots)
    out, done = [], {"hud"}
    while rest:
        ready = [n for n, a in rest.items() if a is None or a in done]
        if not ready:                                       # a loop: the first one goes below the system values
            rest[min(rest, key=order.index)] = "hud"
            continue
        for n in sorted(ready, key=order.index):
            a = rest.pop(n)
            out.append((n, "hud" if a is not None and a != "hud" and a not in spots else a))
            done.add(n)
    return out


def media_own(gw: float, gh: float, size, x: float, y: float):
    """``media_xy`` of a music card of ``size`` whose top-left corner is at (x, y) in the game window (1.2.5: the
    share of the window where its centre is – before, the share of the free room, so a card that got wider with
    a long title moved, user: "nicht mehr zentriert")."""
    w, h = size
    return (round(min(1.0, max(0.0, (x + w / 2) / max(1, gw))), 4),
            round(min(1.0, max(0.0, (y + h / 2) / max(1, gh))), 4))


def steady_width(state, key, w: int):
    """(new state, width to place by) for a block whose width changes with its values (1.64.7, user: the system
    values moved left and right): the widest width seen for the same ``key`` (side, size, row labels) – placed
    by it, a right-aligned block keeps its left edge instead of following every "38 %" → "100 %"."""
    if state is None or state[0] != key:
        return (key, w), w
    width = max(state[1], w)
    return (key, width), width

