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
