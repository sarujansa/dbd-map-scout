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


def arrange(gw, gh, anchor, hud_side, tp, mp, align, gap, map_h=518, map_w=406):
    """The App's / preview's order: system values, cards, then the map below / above the stack in its bar."""
    margin = int(gh * 0.012)
    bar = layout.bar_width(gw, gh)
    bars = bar >= layout.MIN_BAR
    boxes = {}
    follow = hud_side == "above" and bars                      # the values right above the map: placed after it
    if hud_side and (bars or hud_side == "custom") and not follow:   # like the App: no bars, no system values
        hx, hy = layout.hud_preview_xy(hud_side, gw, gh, margin, HUD_SIZE, (0.5, 0.5), None, align, gap)
        boxes["hud"] = (hx, hy, *HUD_SIZE)
    cards = {"today": (TODAY_SIZE if bars or tp == "custom" else None, tp, (0.5, 0.5)),
             "music": (MUSIC_SIZE if bars or mp == "custom" else None, mp, (0.5, 0.5))}
    spots = {n: c[1] for n, c in cards.items()}
    free = {n: c for n, c in cards.items() if not follow or not layout.hangs_on_hud(n, spots)}
    boxes.update(layout.place_cards((0, 0, gw, gh), free, boxes.get("hud"), margin, align, gap))
    drop = lift = 0
    span = layout.map_bar_range(anchor, 0.4, 0, gw, bar)
    if span and anchor != "custom":
        fixed = [boxes.get("hud")] + [boxes[n] for n, c in cards.items() if c[1] != "custom" and n in boxes]
        drop, lift = layout.bar_stack(fixed, span[0], span[1], 0, gh, margin, gap)
        drop = drop + margin if drop else 0
        lift = lift + margin if lift else 0
    mh = max(40, min(map_h, gh - drop - lift - 2 * margin))
    w, h = round(map_w * mh / map_h), mh + 60                      # + the lines below the map
    mx, my = layout.preview_place(gw, gh, anchor, 0.4, 0.6, margin, True, w, h, drop, align, lift)
    boxes["map"] = (mx, my, w, h)
    if follow:
        hx, hy = layout.hud_preview_xy("above", gw, gh, margin, HUD_SIZE, None, boxes["map"], align, gap)
        boxes["hud"] = (hx, hy, *HUD_SIZE)
        boxes.update(layout.place_cards((0, 0, gw, gh), cards, boxes["hud"], margin, align, gap, up=hy < my,
                                        below_box=boxes["map"]))
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
