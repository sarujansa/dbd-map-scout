"""Ultrawide: result screen, lobby and menus use the full window width, a trial only 16:9."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dbdmapscout.detector import _right_region, fills_bars  # noqa: E402

W, H, VX = 3440, 1440, 440          # the user's monitor; 16:9 picture from x=440 to x=3000


def trial_frame(scene=60):
    """16:9 picture with black bars left and right."""
    f = np.zeros((H, W, 3), np.uint8)
    f[:, VX:W - VX] = scene
    return f


def menu_frame(scene=60):
    return np.full((H, W, 3), scene, np.uint8)


def test_trial_bars_are_not_picture():
    assert not fills_bars(trial_frame())


def test_trial_with_fps_counter_notification_and_overlay_is_not_picture():
    f = trial_frame()
    f[0:60, 0:200] = 200                         # FPS counter top left
    f[1200:1420, W - 440:W] = 180                # notification bottom right (whole bar width)
    f[300:700, W - 400:W - 40] = 120             # even a big popup in the right bar
    f[17:650, 17:423] = 150                      # our own map overlay (if not masked)
    assert not fills_bars(f)


def test_result_screen_and_menus_fill_the_bars():
    assert fills_bars(menu_frame())
    assert fills_bars(menu_frame(scene=14))      # dark lobby / fog still counts


def test_overlay_masked_in_left_bar_still_full_width():
    f = menu_frame()
    f[17:800, 17:423] = 0                        # worker blacks out our overlay before looking
    assert fills_bars(f)


def test_no_bars_on_16_9():
    assert not fills_bars(np.full((1440, 2560, 3), 60, np.uint8))


def test_region_reaches_window_edge_only_on_full_width_screens():
    f = menu_frame()
    part = _right_region(f, 0.78, 0.86, 0.99)
    full = _right_region(f, 0.78, 0.86, 0.99, full_width=True)
    # 16:9 region ends at the right edge of the 16:9 picture (+1 %), before the black bar
    assert part.shape[1] == int(VX + 1.01 * 2560) - int(VX + 0.78 * 2560)
    # full width: up to the window edge, covering the CONTINUE button at x≈3150..3290
    x_start = min(int(VX + 0.78 * 2560), int(W - 0.22 * 2560))
    assert full.shape[1] == W - x_start and x_start <= 3150
    cur = _right_region(f, 0.62, 0.0, 0.12, full_width=True)
    assert W - cur.shape[1] <= 2795                              # currency counters from x≈2795
