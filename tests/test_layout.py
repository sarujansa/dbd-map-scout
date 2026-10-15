"""Overlay stays inside the black bar on ultrawide (dbdmapscout/layout.py)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dbdmapscout import layout as L  # noqa: E402

GX, GW, GH, M = 0, 3440, 1440, 17
BAR = L.bar_width(GW, GH)


def test_bar_of_the_users_screen():
    assert BAR == 440 and L.max_width(BAR, M) == 406
    assert L.bar_width(2560, 1440) == 0 and L.bar_width(1920, 1200) == 0


def test_side_by_anchor():
    for a in ("auto", "top-left", "bottom-left"):
        assert L.bar_side(a, 17, 500, GX, GW, BAR) == "left"
    for a in ("top-right", "bottom-right"):
        assert L.bar_side(a, 2900, 500, GX, GW, BAR) == "right"
    assert L.bar_side("top-left", 17, 500, GX, 2560, L.bar_width(2560, 1440)) is None   # 16:9: no bar


def test_custom_follows_the_bar_it_starts_in():
    assert L.bar_side("custom", 100, 500, GX, GW, BAR) == "left"
    assert L.bar_side("custom", 2800, 500, GX, GW, BAR) == "right"          # right edge reaches the right bar
    assert L.bar_side("custom", 1200, 500, GX, GW, BAR) is None             # over the game on purpose


def test_clamp_inside_the_bar():
    assert L.clamp_x("left", 300, 406, GX, GW, BAR, M) == 17                # pushed back left
    assert L.clamp_x("left", 0, 200, GX, GW, BAR, M) == 17
    assert L.clamp_x("left", 100, 200, GX, GW, BAR, M) == 100               # already inside: unchanged
    x = L.clamp_x("right", 2800, 406, GX, GW, BAR, M)
    assert x == GW - BAR + M and x + 406 == GW - M
    assert L.clamp_x("left", 300, 406, 1000, GW, BAR, M) == 1017            # window not at 0,0


def test_fit_height_from_the_picture_size():
    # map pictures are 0.909 : 1 (e.g. 1455 x 1600); 36 % of 1440 = 518 px high would be 471 wide
    h = L.fit_height(518, 406, 1455, 1600)
    assert round(1455 * h / 1600) <= 406 < round(1455 * (h + 1) / 1600)
    assert L.fit_height(300, 406, 1455, 1600) == 300                        # fits: unchanged
    assert L.fit_height(518, 10, 1455, 1600) == 80                          # never below the minimum
    assert L.fit_height(518, 406, 0, 0) == 518                              # no picture


def test_window_mode_slot_beside_the_window():
    # the user's setup: DBD as a 1718 px window at the right of a 3440 px monitor starting at -3440
    assert L.outside_slot(-1727, 1734, -3440, 3440) == ("left", -3440, 1713)
    assert L.outside_slot(0, 1734, 0, 3440) == ("right", 1734, 1706)          # window at the left edge
    assert L.outside_slot(100, 3240, 0, 3440) is None                          # only 100 px free
    assert L.outside_slot(0, 3440, 0, 3440) is None                            # fullscreen
    slot = ("left", -3440, 1713)
    assert L.slot_x(slot, 400, 17) == -1727 - 17 - 400                         # right next to the window
    assert L.slot_x(slot, 1800, 17) == -3440 + 17                              # never past the monitor edge
    assert L.slot_x(("right", 1734, 1706), 400, 17) == 1734 + 17


def test_preview_puts_the_map_where_the_overlay_goes():
    """1.61: the overlay tab's preview – automatic = centred in the left bar (3440×1440: 440 px), corners with
    the margin, own position over the free space; kept inside the bar when asked."""
    x, y, w, h, mh = L.preview_rect(3440, 1440, "auto", 0, 0, 0.36, 0.012, True, 0.75, 3)
    assert x + w <= 440 and x == (440 - w) // 2 and y == 17 and mh == 518 and h > mh
    x, y, w, h, mh = L.preview_rect(3440, 1440, "bottom-right", 0, 0, 0.36, 0.012, True, 0.75, 0)
    assert x >= 3440 - 440 and x + w == 3440 - 17 and y + h == 1440 - 17
    x, y, w, h, mh = L.preview_rect(3440, 1440, "custom", 0.5, 0.5, 0.36, 0.012, False, 0.75, 0)
    assert abs(x + w / 2 - 1720) <= 1 and abs(y + h / 2 - 720) <= 1          # over the game picture when allowed
    x, y, w, h, mh = L.preview_rect(1920, 1080, "auto", 0, 0, 0.36, 0.012, True, 0.75, 0)
    assert (x, y) == (12, 12)                                                  # 16:9: no bar, top left
    assert L.pos_from_point(3440, 1440, 400, 600, 3440, 0) == (1.0, 0.0)
    fx, fy = L.pos_from_point(3440, 1440, 400, 600, 1720, 720)
    assert abs(fx - 0.5) < 1e-6 and abs(fy - 0.5) < 1e-6
