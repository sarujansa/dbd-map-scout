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


def test_our_big_overlay_in_the_left_bar_does_not_hide_a_full_width_screen():
    f = menu_frame()
    f[17:1000, 17:423] = 0                       # a tall map (keep-in-bar off) blacked out before looking
    assert not fills_bars(f)                     # without knowing it, the left bar looks empty …
    assert fills_bars(f, ignore=(17, 17, 423, 1000))   # … its area simply does not count
    t = trial_frame()
    t[17:1000, 17:423] = 0
    assert not fills_bars(t, ignore=(17, 17, 423, 1000))   # trial: the other bar is black too


def test_no_currency_ocr_in_a_trial_on_ultrawide():
    from dbdmapscout.detector import OutOfMatchWatcher, has_bars
    calls = []
    w = OutOfMatchWatcher.__new__(OutOfMatchWatcher)
    w._thumb = None
    w._continue_fit = lambda img, h: (None, "")
    w._currency = lambda img, h: calls.append(img.shape) or (0, 0, "")
    w.observe(trial_frame())
    assert calls == [] and has_bars(trial_frame())         # black bars: score events are not read
    w.observe(menu_frame())
    assert len(calls) == 1                                  # lobby/menus: counters are read
    w.observe(np.full((1440, 2560, 3), 60, np.uint8))
    assert len(calls) == 2                                  # 16:9 monitor: no bars to tell, always read


# ------------------------------------------------------------------ loading screen vs. lying on the ground
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "end")


def _full(name):
    import cv2
    return cv2.resize(cv2.imread(os.path.join(DATA, name)), (W, H))


def _watcher():
    from dbdmapscout.detector import OutOfMatchWatcher
    from dbdmapscout.ocr import Recognizer
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return OutOfMatchWatcher(Recognizer(os.path.join(root, "models", "ch_PP-OCRv4_rec_infer.onnx")))


def test_real_loading_screen_counts():
    from dbdmapscout.detector import has_loading_bar, is_dark
    f = _full("loading.jpg")                    # user screenshot: black, white logo, tip, filled bar
    assert has_loading_bar(f) and is_dark(f)
    w = _watcher()
    w.observe(f)
    ob = w.observe(f)                           # second look: still
    assert (ob.loading, ob.static, ob.dark, ob.reason) == (True, True, True, "Ladebildschirm")


def test_lying_on_the_ground_is_no_loading_screen():
    """Slugged (Ironworks of Misery, 1.31.2): a progress bar, the camera barely moves – but the game
    world is lit. Upper picture from a real match, bottom quarter with the loading bar."""
    from dbdmapscout.detector import is_dark
    f = _full("loading.jpg")
    f[:int(0.72 * H)] = _full("spectate.jpg")[:int(0.72 * H)]
    assert not is_dark(f)
    w = _watcher()
    w.observe(f)
    ob = w.observe(f)
    assert ob.loading and ob.static and ob.reason is None
    assert not is_dark(_full("spectate.jpg"))
