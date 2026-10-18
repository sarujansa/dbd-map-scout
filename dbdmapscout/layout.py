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
                  w: int, h: int, drop: int = 0, align: str = "centre", lift: int = 0, block=(0, 0)):
    """Top-left corner of an overlay of w × h on a full-screen DBD (App._place_overlay's rules for the preview);
    ``drop``: room the system values (and the cards below them) take above a map at the top of the same bar,
    ``lift`` (1.2.11): room the cards at the bottom of the bar take below a map at the bottom, ``block`` (1.8.24):
    own_block() – an own place puts map + lines as one block."""
    bar = bar_width(gw, gh)
    if anchor == "auto":                                    # like App._place_overlay_map's place()
        x = (bar - w) / 2 if align == "centre" else (bar - margin - w if align == "right" else margin)
        x, y = max(margin, x), margin + drop
    elif anchor == "custom":
        x, y = pos_x * max(0, gw - w), pos_y * max(0, gh - h - block[0]) + block[1]
    else:
        x = margin if anchor.endswith("left") else gw - w - margin
        y = margin + drop if anchor.startswith("top") else gh - h - margin - lift
    y = max(0, min(y, gh - h)) if anchor != "custom" else y                  # never off the screen (1.2.11)
    side = bar_side(anchor, x, w, 0, gw, bar) if (anchor == "auto" or keep_in_bar) else None
    if side:
        x = clamp_x(side, x, w, 0, gw, bar, margin)
    return int(x), int(y)


def preview_rect(gw: int, gh: int, anchor: str, pos_x: float, pos_y: float, height_frac: float,
                 margin_frac: float, keep_in_bar: bool, aspect: float, info_rows: int = 0, drop: int = 0,
                 grow: bool = False, lift: int = 0):
    """Where the overlay sits on a full-screen DBD of gw × gh (the overlay tab's preview, since 1.61): (x, y, w,
    h, map_h) – the same rules as App._place_overlay for the common case (no window mode, no bars above/below).
    ``aspect`` = map width / height, ``info_rows`` = lines below the map (timer counts double), ``drop`` = room
    of the system values above the map (1.64)."""
    margin = int(gh * margin_frac)
    height = int(gh * min(0.9, max(0.05, height_frac)))
    height = max(40, min(height, gh - drop - lift - 2 * margin))
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
                   gap=None, top: int = 0):
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
        hy = y - gap - h if y - gap - h >= top else y + mh + gap        # top = the bar's limiter line (1.8.14)
        return int(hx), int(hy)
    return int(hud_x("left" if side == "left" else "right", 0, gw, margin, w, bar_width(gw, gh), align)), margin


def pos_from_point(gw: int, gh: int, w: int, h: int, cx: float, cy: float):
    """Own position (pos_x, pos_y as in the settings) that puts an overlay of w × h with its centre at (cx, cy)."""
    fx = (cx - w / 2) / max(1, gw - w)
    fy = (cy - h / 2) / max(1, gh - h)
    return min(1.0, max(0.0, fx)), min(1.0, max(0.0, fy))


def media_xy(spot: str, game, size, margin: int, hud=None, own=None, align: str = "centre", gap=None, band=None):
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
        lo, hi = band or (gy + margin, gy + gh - margin)   # 1.8.14: the limiter lines of the bar
        y = hud[1] + hud[3] + gap
        if y + h > hi:                                   # no room below (the card above sits at the bottom, 1.2.11
            y = hud[1] - gap - h                         # sweep): above it instead, never off the screen
            if y < lo:
                y = max(lo, hi - h)
        return x, y
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


def hangs_on_hud(name: str, spots: dict) -> bool:
    """Whether the card's chain of anchors ends at the system values (then it waits for them when they follow
    the map); a bar corner or an own place does not (1.2.11)."""
    seen = set()
    while True:
        anchor = STACK_ANCHORS.get(spots.get(name))
        if anchor is None:
            return False
        if anchor == "hud" or anchor in seen or anchor not in spots:
            return True
        seen.add(name)
        name = anchor


def place_cards(game, cards: dict, hud_box, margin: int, align: str = "centre", gap=None,
                up: bool = False, below_box=None, bands=None) -> dict:
    """Top-left corner and size of every card ("today", "music") in stacking order (1.2.11: the one place for
    App and preview). ``cards`` = {name: ((w, h) or None, position setting, own place)}; a card hangs below its
    anchor's box – below the system values when the anchor is not there – or stands in the bar / at its own
    place (media_xy). ``up``: the system values sit right above the map, so the stack grows upwards from them –
    without room above, a card goes below ``below_box`` (the map) instead. Returns {name: (x, y, w, h)} for the
    cards with a size."""
    order = stack_order({n: c[1] for n, c in cards.items()})
    boxes, out, corners = {"hud": hud_box}, {}, {}
    gy, gh = game[1], game[3]
    g = gap if gap is not None else max(2, margin // 2)
    for name, anchor in order:
        size, spot, own = cards[name]
        if not size:
            boxes[name] = None
            continue
        under = (boxes.get(anchor) or boxes.get("hud")) if anchor else None
        side = box_side(under, game) if bands and under else None
        band = bands[side] if side else None
        lo, hi = band or (gy + margin, gy + gh - margin)
        x, y = media_xy("below" if anchor else spot, game, size, margin, under, own, align, gap, band)
        if anchor and under is not None and up:         # above the card / values it hangs on (the map is below)
            y = under[1] - g - size[1]
            if y < lo:                                  # no room above: below the map (and what hangs there)
                floor = below_box if below_box is not None else under
                y = min(hi - size[1], floor[1] + floor[3] + g)
                below_box = (floor[0], y, size[0], size[1])
        if spot in corners:                             # two cards in the same bottom corner: the second above
            y = max(lo, corners[spot][1] - g - size[1])
        # 1.8.14: between the limiter lines of its bar (a bottom corner from the bottom line up)
        out[name] = boxes[name] = clamp_box((int(x), int(y), int(size[0]), int(size[1])), game, bands)
        if anchor:                                      # two cards below the same element: the second below the
            boxes[anchor] = out[name]                   # first (1.2.11 sweep: they sat on top of each other)
        elif spot in ("bottom_left", "bottom_right"):
            corners[spot] = out[name]
    return out


def bar_stack(boxes, x0: float, x1: float, gy: float, gh: float, margin: int, gap: int):
    """(drop, lift): how far the elements standing at the top / the bottom of the bar [x0, x1] reach down / up
    (1.2.11, one rule for App and preview): a box at the top edge counts, and every box that hangs right below
    it (within ``gap`` + a few px) – the same from the bottom up. ``boxes`` = (x, y, w, h) of the system values
    and the cards; a map at the top of that bar moves below the stack, one at the bottom above it."""
    inside = [b for b in boxes if b and b[0] < x1 and b[0] + b[2] > x0]
    drop, lift = 0, 0
    bottom = gy + margin
    for b in sorted(inside, key=lambda b: b[1]):
        if b[1] <= bottom + gap + 2:
            bottom = max(bottom, b[1] + b[3])
    if bottom > gy + margin:
        drop = int(bottom - gy)
    top = gy + gh - margin
    for b in sorted(inside, key=lambda b: b[1] + b[3], reverse=True):
        if b[1] + b[3] >= top - gap - 2:
            top = min(top, b[1])
    if top < gy + gh - margin:
        lift = int(gy + gh - top)
    return drop, lift


# 1.8.14 (user: "in beiden schwarzen Bereichen so einen Limiter … 2 Stück, wo die GUI-Elemente nicht überschreiten
# dürfen, oben und unten"): per black bar a line at the top and one at the bottom; every element in that bar stays
# between them. overlay.bar_limits = [left top, left bottom, right top, right bottom] as shares of the game height
# (top from the top edge, bottom from the bottom edge) – a list, so the preview's cache key sees a change.
LIMIT_DEFAULT = 0.08          # where the lines start when the limiter is switched on
LIMIT_MAX = 0.45              # a line never further in than this
LIMIT_MIN_ROOM = 0.15         # the lines keep at least this share of the height between them
LIMIT_SIDES = ("left", "right")


def limit_pair(limits, side: str) -> tuple:
    """(top, bottom) shares of one bar from the setting – clamped, and never closer than LIMIT_MIN_ROOM."""
    i = 0 if side == "left" else 2
    try:
        t, b = float(limits[i]), float(limits[i + 1])
    except (TypeError, ValueError, IndexError):
        t = b = 0.0
    t, b = min(LIMIT_MAX, max(0.0, t)), min(LIMIT_MAX, max(0.0, b))
    over = t + b - (1 - LIMIT_MIN_ROOM)
    if over > 0:
        t, b = t - over / 2, b - over / 2
    return t, b


def bar_bands(o: dict, game, margin: int, zones: bool = True):
    """{"left": (top y, bottom y), "right": (…)} – the room between the lines of each black bar (absolute screen
    y; at least ``margin`` from the edges), or None when the limiter is off or the window has no side bars.
    1.8.25: a keep-out area (keep_out_boxes, e.g. Discord's voice widget) at the top / bottom edge of a bar moves
    that bar's line past it – also with the limiter off; ``zones`` False = the limiter lines alone (drawing)."""
    gx, gy, gw, gh = game
    if gh <= 0 or bar_width(gw, gh) < MIN_BAR:
        return None
    edges = bar_zone_edges(o, game) if zones else {}
    if not o.get("bar_limits_on") and not edges:
        return None
    out = {}
    for side in LIMIT_SIDES:
        t, b = limit_pair(o.get("bar_limits"), side) if o.get("bar_limits_on") else (0.0, 0.0)
        top, bottom = int(gy + max(margin, round(t * gh))), int(gy + gh - max(margin, round(b * gh)))
        zt, zb = edges.get(side, (None, None))
        if zt is not None:
            top = max(top, zt + margin)
        if zb is not None:
            bottom = min(bottom, zb - margin)
        if bottom - top < gh * LIMIT_MIN_ROOM:           # never squeezed to nothing
            bottom = top + int(gh * LIMIT_MIN_ROOM)
        out[side] = (top, bottom)
    return out


# 1.8.25 (user screenshots with Discord's overlay open: "was du beachten musst beim Anordnen"): areas our elements
# keep out of – Discord's overlay widgets where the user has them, as shares of the DBD window (x, y, w, h):
# voice widget bottom left, streams + notifications top right, text chat right. Nothing is read from Discord.
# (measured on 2000×837 screenshots: voice 2–160 × 750–812, streams + notifications 1817–2000 × 0–200, the pinned
# chat 1630–1767 × 470–665 – its wide input line only shows with the overlay open –, quick actions 680–940 × 15–70)
DISCORD_ZONES = [[0.0, 0.89, 0.082, 0.11], [0.905, 0.0, 0.095, 0.245], [0.814, 0.56, 0.07, 0.235],
                 [0.34, 0.015, 0.13, 0.07]]
EDGE_TOUCH = 0.02                                   # a zone this close to the top / bottom edge moves the bar's line


def keep_out_boxes(o: dict, game) -> list:
    """The keep-out areas in screen pixels [(x, y, w, h)], [] when switched off."""
    if not o.get("keep_out_on", False):            # settings: on by default (config.DEFAULTS)
        return []
    gx, gy, gw, gh = game
    out = []
    for z in o.get("keep_out") or DISCORD_ZONES:
        try:
            x, y, w, h = (float(v) for v in z)
        except (TypeError, ValueError):
            continue
        out.append((gx + x * gw, gy + y * gh, w * gw, h * gh))
    return out


def bar_zone_edges(o: dict, game) -> dict:
    """{side: (lowest bottom of the zones at the bar's top or None, highest top of those at its bottom or None)}."""
    gx, gy, gw, gh = game
    bar = bar_width(gw, gh)
    out = {}
    for x, y, w, h in keep_out_boxes(o, game):
        for side, (b0, b1) in (("left", (gx, gx + bar)), ("right", (gx + gw - bar, gx + gw))):
            if x >= b1 or x + w <= b0:
                continue
            top, bottom = out.get(side, (None, None))
            if y <= gy + EDGE_TOUCH * gh:
                top = max(top or 0, int(y + h))
            elif y + h >= gy + gh - EDGE_TOUCH * gh:
                bottom = int(y) if bottom is None else min(bottom, int(y))
            out[side] = (top, bottom)
    return out


def boxes_overlap(a, b, pad: int = 0) -> bool:
    return (a[0] < b[0] + b[2] + pad and b[0] < a[0] + a[2] + pad and
            a[1] < b[1] + b[3] + pad and b[1] < a[1] + a[3] + pad)


def resolve(boxes, fixed, game, bands, gap: int, soft=()) -> dict:
    """1.8.25 (user: "alle UI-Elemente beachten, damit es immer sauber aussieht"): {name: (dx, dy)} so that no box
    lies on an earlier one or on a ``fixed`` box (the map). ``boxes`` = [(name, (x, y, w, h))] in priority order;
    a box that collides moves up or down to the nearest free place in its bar between its lines (else on the
    screen) – without one, sideways within its bar (a narrow area reaching in from the game picture); with no
    free place at all it stays where it is. ``soft`` (1.8.29) = the keep-out areas (Discord): kept free when
    that leaves every element off the others – else ignored, so two cards never end up on each other because
    a zone reaches a few pixels into the bar (bar-wide cards of one column did)."""
    out = _resolve(boxes, list(fixed) + list(soft), game, bands, gap)
    if soft:
        final = [(x + out.get(n, (0, 0))[0], y + out.get(n, (0, 0))[1], w, h) for n, (x, y, w, h) in
                 ((n, b) for n, b in boxes if b)]
        hard = [tuple(f) for f in fixed if f]
        for i, b in enumerate(final):
            if any(boxes_overlap(b, p) for p in hard + final[:i]):
                return _resolve(boxes, fixed, game, bands, gap)
    return out


def _resolve(boxes, fixed, game, bands, gap: int) -> dict:
    gx, gy, gw, gh = game
    bar = bar_width(gw, gh)
    placed = [tuple(f) for f in fixed if f]
    out = {}
    for name, box in boxes:
        if not box:
            continue
        x, y, w, h = box
        if any(boxes_overlap(box, p) for p in placed):
            side = box_side(box, game)
            top, bottom = bands[side] if bands and side else (gy, gy + gh)
            left, right = ((gx, gx + bar) if side == "left" else (gx + gw - bar, gx + gw)) if side else (gx, gx + gw)
            free = lambda b: not any(boxes_overlap(b, p) for p in placed)          # noqa: E731
            cands = {y}
            for p in placed:
                cands |= {p[1] + p[3] + gap, p[1] - gap - h}
            spot = next((c for c in sorted(cands, key=lambda c: (abs(c - y), c))
                         if top <= c and c + h <= bottom and free((x, c, w, h))), None)
            if spot is not None:
                y = spot
            else:
                xs = set()
                for p in placed:
                    xs |= {p[0] + p[2] + gap, p[0] - gap - w}
                spot = next((c for c in sorted(xs, key=lambda c: (abs(c - x), c))
                             if left <= c and c + w <= right and free((c, y, w, h))), None)
                if spot is not None:
                    x = spot
        if (x, y) != tuple(box[:2]):
            out[name] = (int(x - box[0]), int(y - box[1]))
        placed.append((x, y, w, h))
    return out


def column_widths(boxes: dict, game, widths: dict | None = None) -> dict:
    """1.8.29 (user: "rechts sind die Felder nicht untereinander"): the cards in the same black bar share one
    width – the widest of them. ``boxes`` = {name: (x, y, w, h)} as placed; ``widths`` = natural widths to count
    instead of the boxes' (the App: before any widening). Returns {name: width} for the cards that get wider."""
    sides = {n: box_side(b, game) for n, b in boxes.items() if b}
    nat = {n: int((widths or {}).get(n, boxes[n][2])) for n in sides}
    out = {}
    for n, s in sides.items():
        if s is None:
            continue
        w = max(nat[m] for m, s2 in sides.items() if s2 == s)
        if w > nat[n]:
            out[n] = w
    return out


def box_side(box, game):
    """"left" / "right": the black bar the box's centre is in, None over the game picture (or no bars)."""
    if not box:
        return None
    gx, _gy, gw, gh = game
    bar = bar_width(gw, gh)
    if bar < MIN_BAR:
        return None
    cx = box[0] + box[2] / 2
    return "left" if cx < gx + bar else "right" if cx > gx + gw - bar else None


def clamp_box(box, game, bands):
    """The box moved up/down so it stays between the lines of its bar (taller than the room: at the top line)."""
    side = box_side(box, game) if bands else None
    if side is None:
        return box
    top, bottom = bands[side]
    x, y, w, h = box
    return (x, int(max(top, min(y, bottom - h))), w, h)


def own_room(box, game, bands) -> int:
    """1.8.22 (user: "Midwich ignoriert die Regel" – both floors at an own place ran past the bottom line): how tall
    a box at an own place may be – the room between the lines of its bar, else the game's height."""
    side = box_side(box, game) if bands else None
    if side is None:
        return game[3]
    top, bottom = bands[side]
    return max(0, bottom - top)


def follow_reserve(hud_h: int, card_sizes: dict, spots: dict, gap: int) -> int:
    """Room above the map for the system values "right above the map" and the cards hanging on them (1.8.14):
    between limiter lines the map makes room for them, so the chain fits above it instead of spilling over."""
    if not hud_h:
        return 0
    return int(hud_h + gap + sum(size[1] + gap for name, size in card_sizes.items()
                                 if size and hangs_on_hud(name, spots)))


def bar_room(boxes, x0: float, x1: float, gy: float, gh: float, margin: int, gap: int, band=None):
    """(drop, lift) for the map in the bar [x0, x1] as App and preview use them (y = gy + margin + drop, bottom =
    gy + gh - margin - lift): what stands at the top / bottom of the bar (bar_stack, + a margin), measured from
    the limiter lines ``band`` = (top y, bottom y) when there are some (1.8.14) – the map then starts at the line."""
    top, bottom = band or (gy + margin, gy + gh - margin)
    d, li = bar_stack(boxes, x0, x1, top - margin, bottom - top + 2 * margin, margin, gap)
    return ((d + margin if d else 0) + int(top - margin - gy),
            (li + margin if li else 0) + int(gy + gh - margin - bottom))


def map_bar_range(anchor: str, pos_x: float, gx: float, gw: float, bar: float):
    """x range of the black bar the map stands in (for bar_stack), or None without bars / over the picture."""
    if bar < MIN_BAR:
        return None
    if anchor in ("auto", "top-left", "bottom-left"):
        return gx, gx + bar
    if anchor in ("top-right", "bottom-right"):
        return gx + gw - bar, gx + gw
    x = gx + pos_x * gw                                    # custom: the bar its left edge starts in
    if x < gx + bar:
        return gx, gx + bar
    if x >= gx + gw - bar:
        return gx + gw - bar, gx + gw
    return None


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



SHRINK_AFTER = 8.0           # s a card's smaller content must last before the card gets smaller (1.8.30)


def steady_box(state, key, w: int, h: int, now: float, hold: float = SHRINK_AFTER):
    """(new state, width, height) for a card whose content comes and goes for a moment (1.8.30, user: "wenn Spotify
    den Song wechselt, werden die Felder kurz kleiner und wieder normal – die Felder sollen ihre fixe Grösse
    behalten"): the largest size seen for the same ``key``; it only gets smaller once the smaller content has
    lasted ``hold`` seconds (a song change without cover or queue for a second never shows). Another ``key``
    (style, size, layout) starts anew."""
    if state is None or state[0] != key:
        return (key, int(w), int(h), None), int(w), int(h)
    _k, sw, sh, since = state
    if w >= sw and h >= sh:
        return (key, int(w), int(h), None), int(w), int(h)
    if since is None:
        since = now
    if now - since >= hold:                      # it stayed smaller: the card follows
        return (key, int(w), int(h), None), int(w), int(h)
    sw, sh = max(sw, int(w)), max(sh, int(h))
    return (key, sw, sh, since), sw, sh


# 1.8.24 (user: "Zeit etc. nicht mehr mit der Map verbunden – ich will ab und zu nur die Map-Grösse ändern"): the
# map's lines (timer, record, server) as an element of their own: right below / above the map, at an own place, or
# drawn into the map window as before ("inside")
INFO_SPOTS = ("below", "above", "custom", "inside", "inside_top")      # 1.8.34: inside, lines above the map


def info_apart(o: dict) -> bool:
    """The lines are their own element (not with "nur Infos": then they are all there is)."""
    return o.get("info_pos", "below") in ("below", "above", "custom") and bool(o.get("show_map", True))


def info_reserve(o: dict, size, gap: int):
    """(drop, lift) the lines take right above / below the map in its bar – the map makes room for them."""
    if not size or not info_apart(o) or o.get("anchor") == "custom":
        return 0, 0
    spot = o.get("info_pos", "below")
    return (size[1] + gap, 0) if spot == "above" else (0, size[1] + gap) if spot == "below" else (0, 0)


def own_block(o: dict, size, gap: int):
    """(extra, shift) of a map at an own place whose lines hang right below / above it (1.8.24, user screenshot:
    the lines sat on Midwich's top floor): the vertical slider places map + lines as one block – ``extra`` = what
    the lines add to its height, ``shift`` = how far the map sits below the block's top (lines above it)."""
    if not size or not info_apart(o) or o.get("anchor") != "custom":
        return 0, 0
    spot = o.get("info_pos", "below")
    if spot not in ("below", "above"):
        return 0, 0
    extra = size[1] + gap
    return extra, (extra if spot == "above" else 0)


def info_xy(spot: str, map_rect, size, game, gap: int, margin: int, own=None, align: str = "centre",
            bands=None):
    """Top-left corner of the lines: centred (or aligned like the bar) right below / above the map – the other
    side when there is no room –, in the map's bar; ``custom``: their centre at ``own`` (shares of the window,
    like the music card)."""
    gx, gy, gw, gh = game
    w, h = size
    if spot == "custom" or not map_rect:
        fx, fy = own or (0.5, 0.5)
        x, y = gx + fx * gw - w / 2, gy + fy * gh - h / 2
    else:
        mx, my, mw, mh = map_rect
        x = mx + (mw - w) / 2 if align == "centre" else (mx if align == "left" else mx + mw - w)
        below, above = my + mh + gap, my - gap - h
        y = above if spot == "above" else below
        if spot == "above" and y < gy:
            y = below
        elif spot != "above" and y + h > gy + gh:
            y = above
        bar = bar_width(gw, gh)
        if bar >= MIN_BAR and mx < gx + bar:
            x = clamp_x("left", x, w, gx, gw, bar, margin)
        elif bar >= MIN_BAR and mx + mw > gx + gw - bar:
            x = clamp_x("right", x, w, gx, gw, bar, margin)
    x = min(max(x, gx), gx + max(0, gw - w))
    y = min(max(y, gy), gy + max(0, gh - h))
    if spot == "custom" and bands:
        y = clamp_box((x, y, w, h), game, bands)[1]
    return int(x), int(y)


def union(a, b):
    """The box around two boxes (x, y, w, h); a missing one counts as nothing."""
    if not a or not b:
        return a or b
    x0, y0 = min(a[0], b[0]), min(a[1], b[1])
    x1, y1 = max(a[0] + a[2], b[0] + b[2]), max(a[1] + a[3], b[1] + b[3])
    return (x0, y0, x1 - x0, y1 - y0)
