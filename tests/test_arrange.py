"""1.2.11 (user: "alles in jeglicher Kombination testen"): the shared placement of map, system values, "today"
and music (layout.place_cards / bar_stack / preview_place) over every combination of positions, alignment, gap
and window size – no rendering, synthetic sizes, so it stays fast. The rendered preview (preview.layers) is
checked on a smaller grid in test_preview."""
import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dbdmapscout import layout  # noqa: E402

SIZES = [(3440, 1440), (2560, 1440), (1920, 1080)]
ANCHORS = ["auto", "top-left", "top-right", "bottom-left", "bottom-right", "custom"]
HUDS = ["", "left", "right", "above", "custom"]
TODAYS = ["below", "under_music", "bottom_right", "bottom_left", "custom"]
MUSICS = ["below", "under_today", "bottom_right", "bottom_left", "custom"]
HUD_SIZE, TODAY_SIZE, MUSIC_SIZE = (300, 160), (265, 93), (264, 406)


def overlaps(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def arrange(gw, gh, anchor, hud_side, tp, mp, align, gap, map_h=518, map_w=406, limits=None):
    """The App's / preview's order: system values, cards, then the map below / above the stack in its bar.
    ``limits`` = overlay.bar_limits with the limiter on (1.8.14)."""
    margin = int(gh * 0.012)
    game = (0, 0, gw, gh)
    bands = layout.bar_bands({"bar_limits_on": True, "bar_limits": limits}, game, margin) if limits else None
    bar = layout.bar_width(gw, gh)
    bars = bar >= layout.MIN_BAR
    boxes = {}
    follow = hud_side == "above" and bars                      # the values right above the map: placed after it
    if hud_side and (bars or hud_side == "custom") and not follow:   # like the App: no bars, no system values
        hx, hy = layout.hud_preview_xy(hud_side, gw, gh, margin, HUD_SIZE, (0.5, 0.5), None, align, gap)
        boxes["hud"] = layout.clamp_box((hx, hy, *HUD_SIZE), game, bands)
    cards = {"today": (TODAY_SIZE if bars or tp == "custom" else None, tp, (0.5, 0.5)),
             "music": (MUSIC_SIZE if bars or mp == "custom" else None, mp, (0.5, 0.5))}
    spots = {n: c[1] for n, c in cards.items()}
    free = {n: c for n, c in cards.items() if not follow or not layout.hangs_on_hud(n, spots)}
    boxes.update(layout.place_cards(game, free, boxes.get("hud"), margin, align, gap, bands=bands))
    drop = lift = 0
    span = layout.map_bar_range(anchor, 0.4, 0, gw, bar)
    band = bands["left" if span[0] <= 0 else "right"] if bands and span else None
    if span and anchor != "custom":
        fixed = [boxes.get("hud")] + [boxes[n] for n, c in cards.items() if c[1] != "custom" and n in boxes]
        drop, lift = layout.bar_room(fixed, span[0], span[1], 0, gh, margin, gap, band)
        if band and follow:                                    # like the App: room above the map for the chain
            drop += layout.follow_reserve(HUD_SIZE[1], {n: c[0] for n, c in cards.items()}, spots, gap)
    mh = max(40, min(map_h, gh - drop - lift - 2 * margin - 60))
    w, h = round(map_w * mh / map_h), mh + 60                      # + the lines below the map
    mx, my = layout.preview_place(gw, gh, anchor, 0.4, 0.6, margin, True, w, h, drop, align, lift)
    boxes["map"] = layout.clamp_box((mx, my, w, h), game, bands) if anchor == "custom" else (mx, my, w, h)
    if follow:
        side = layout.box_side(boxes["map"], game) if bands else None
        hx, hy = layout.hud_preview_xy("above", gw, gh, margin, HUD_SIZE, None, boxes["map"], align, gap,
                                       top=bands[side][0] if side else 0)
        boxes["hud"] = layout.clamp_box((hx, hy, *HUD_SIZE), game, bands)
        boxes.update(layout.place_cards(game, cards, boxes["hud"], margin, align, gap, up=boxes["hud"][1] < my,
                                        below_box=boxes["map"], bands=bands))
    return boxes, {"today": tp, "music": mp, "hud": hud_side, "map": anchor}


def test_every_combination_keeps_the_elements_apart_and_on_screen():
    combos = itertools.product(SIZES, ANCHORS, HUDS, TODAYS, MUSICS, ("left", "centre", "right"), (0, 8, 40))
    n = 0
    for (gw, gh), anchor, hud_side, tp, mp, align, gap in combos:
        boxes, spots = arrange(gw, gh, anchor, hud_side, tp, mp, align, gap)
        n += 1
        why = (gw, gh, anchor, hud_side, tp, mp, align, gap)
        for name, (x, y, w, h) in boxes.items():
            assert x >= -1 and y >= -1 and x + w <= gw + 1 and y + h <= gh + 1, (why, name, boxes[name])
        fixed = [n_ for n_, s in spots.items() if s != "custom"]
        for a, b in itertools.combinations(fixed, 2):
            if a in boxes and b in boxes:
                assert not overlaps(boxes[a], boxes[b]), (why, a, b, boxes[a], boxes[b])
    assert n == 3 * 6 * 5 * 5 * 5 * 3 * 3


def test_cards_stack_below_each_other_and_flip_above_a_card_at_the_bottom():
    game, m = (0, 0, 3440, 1440), 17
    hud = (3130, 17, 290, 300)
    cards = {"today": (TODAY_SIZE, "below", None), "music": (MUSIC_SIZE, "below", None)}
    placed = layout.place_cards(game, cards, hud, m, "centre", 8)
    assert placed["today"][1] == 17 + 300 + 8 and placed["music"][1] == placed["today"][1] + 93 + 8
    cards = {"today": (TODAY_SIZE, "under_music", None), "music": (MUSIC_SIZE, "bottom_right", None)}
    placed = layout.place_cards(game, cards, None, m, "centre", 8)
    assert placed["today"][1] + 93 + 8 == placed["music"][1]          # no room below the music card: above it
    assert layout.bar_stack([hud, placed["today"]], 3000, 3440, 0, 1440, m, 8) == (317, 0)   # only the top one
    drop, lift = layout.bar_stack([placed["music"], placed["today"]], 3000, 3440, 0, 1440, m, 8)
    assert drop == 0 and lift == 1440 - placed["today"][1]            # both at the bottom: a map there moves up
    assert layout.map_bar_range("auto", 0, 0, 3440, 440) == (0, 440)
    assert layout.map_bar_range("custom", 0.95, 0, 3440, 440) == (3000, 3440)
    assert layout.map_bar_range("custom", 0.5, 0, 3440, 440) is None and layout.map_bar_range("auto", 0, 0, 2560, 0) is None


def test_cards_grow_upwards_when_the_system_values_sit_right_above_the_map():
    """1.2.11 sweep: with "direkt über der Karte" a card below the system values landed on the map."""
    game, m = (0, 0, 3440, 1440), 17
    hud = (103, 687, 234, 189)                                # right above a map at the bottom of the left bar
    cards = {"today": (TODAY_SIZE, "below", None), "music": (MUSIC_SIZE, "under_today", None)}
    placed = layout.place_cards(game, cards, hud, m, "left", 8, up=True)
    assert placed["today"][1] + 93 + 8 == hud[1] and placed["music"][1] + 406 + 8 == placed["today"][1]
    hud_top = (103, 17, 234, 189)                             # no room above: below instead, never off the screen
    placed = layout.place_cards(game, cards, hud_top, m, "left", 8, up=True)
    assert placed["today"][1] == 17 + 189 + 8


def test_with_limiter_lines_every_element_stays_between_the_lines_of_its_bar():
    """1.8.14 (user: "Limiter … oben und unten, wo die GUI-Elemente nicht überschreiten dürfen"): with lines in
    both bars (different on each side) every element in a bar stays between them, still apart and on screen;
    the map at the top / bottom of a bar starts at the line."""
    combos = itertools.product(((3440, 1440), (5120, 1440), (2560, 1440)), ANCHORS, HUDS, TODAYS, MUSICS,
                               ("left", "centre", "right"), ([0.1, 0.1, 0.1, 0.1], [0.05, 0.2, 0.15, 0.08]))
    for (gw, gh), anchor, hud_side, tp, mp, align, limits in combos:
        boxes, spots = arrange(gw, gh, anchor, hud_side, tp, mp, align, 8, limits=limits)
        why = (gw, gh, anchor, hud_side, tp, mp, align, limits)
        game = (0, 0, gw, gh)
        bands = layout.bar_bands({"bar_limits_on": True, "bar_limits": limits}, game, int(gh * 0.012))
        assert (bands is None) == (gw == 2560)                  # 16:9: no bars, nothing to limit
        for name, (x, y, w, h) in boxes.items():
            assert x >= -1 and y >= -1 and x + w <= gw + 1 and y + h <= gh + 1, (why, name, boxes[name])
            side = layout.box_side((x, y, w, h), game) if bands else None
            if side:
                top, bottom = bands[side]
                assert y >= top and (y + h <= bottom or y == top), (why, name, boxes[name], bands[side])
        fixed = [n_ for n_, s in spots.items() if s != "custom"]
        for a, b in itertools.combinations(fixed, 2):
            if a in boxes and b in boxes:
                assert not overlaps(boxes[a], boxes[b]), (why, a, b, boxes[a], boxes[b])
    margin = int(1440 * 0.012)
    bands = layout.bar_bands({"bar_limits_on": True, "bar_limits": [0.1, 0.1, 0.1, 0.1]}, (0, 0, 3440, 1440), margin)
    boxes, _spots = arrange(3440, 1440, "auto", "", "custom", "custom", "centre", 8, limits=[0.1, 0.1, 0.1, 0.1])
    assert boxes["map"][1] == bands["left"][0] == 144                  # alone in its bar: right at the line


def test_limiter_lines_are_kept_sane():
    assert layout.limit_pair([0.1, 0.2, 0.3, 0.05], "left") == (0.1, 0.2)
    assert layout.limit_pair([0.1, 0.2, 0.3, 0.05], "right") == (0.3, 0.05)
    t, b = layout.limit_pair([0.45, 0.45, 0, 0], "left")
    assert abs(t + b - (1 - layout.LIMIT_MIN_ROOM)) < 1e-9 and t == b      # always some room between them
    assert layout.limit_pair(None, "left") == (0.0, 0.0) and layout.limit_pair([-1, 9], "left") == (0.0, 0.45)
    game = (100, 50, 3440, 1440)
    assert layout.bar_bands({"bar_limits": [0.1] * 4}, game, 17) is None              # switched off
    assert layout.bar_bands({"bar_limits_on": True, "bar_limits": [0.1] * 4}, (0, 0, 2560, 1440), 17) is None
    bands = layout.bar_bands({"bar_limits_on": True, "bar_limits": [0.0, 0.1, 0.2, 0.0]}, game, 17)
    assert bands == {"left": (67, 1346), "right": (338, 1473)}              # never closer than the margin
    assert layout.clamp_box((120, 0, 300, 100), game, bands) == (120, 67, 300, 100)
    assert layout.clamp_box((3200, 1450, 300, 100), game, bands) == (3200, 1373, 300, 100)
    assert layout.clamp_box((1500, 0, 300, 100), game, bands) == (1500, 0, 300, 100)   # over the game: free
    assert layout.bar_room([], 100, 540, 50, 1440, 17, 8) == (0, 0)                     # no lines: as before
    assert layout.bar_room([(200, 67, 300, 100)], 100, 540, 50, 1440, 17, 8) == \
        (layout.bar_stack([(200, 67, 300, 100)], 100, 540, 50, 1440, 17, 8)[0] + 17, 0)
