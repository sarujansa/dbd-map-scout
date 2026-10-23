"""Window-capture offsets of the game picture (fogscout/capture.py, pure part)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fogscout.capture import GameWindow, overlaps  # noqa: E402


def test_borderless_picture_is_the_whole_capture():
    g = GameWindow(hwnd=1, title="", left=0, top=0, width=3440, height=1440,
                   client=(0, 0, 3440, 1440), outer=(0, 0, 3440, 1440), window=(0, 0, 3440, 1440))
    assert g.capture_offset((3440, 1440)) == (0, 0)


def test_window_mode_capture_includes_the_title_bar():
    # user's diagnose: GetWindowRect (-1727,0)-(7,1399), client at (-1719,31) 1718×1360
    g = GameWindow(hwnd=1, title="DeadByDaylight", left=-1719, top=31, width=1718, height=1360,
                   client=(-1719, 31, 1718, 1360), outer=(-1720, 0, 1720, 1392), window=(-1727, 0, 1734, 1399))
    assert g.capture_offset((1720, 1392)) == (1, 31)          # DWM frame bounds
    assert g.capture_offset((1734, 1399)) == (8, 31)          # incl. invisible resize borders
    assert g.capture_offset((1718, 1360)) == (0, 0)           # client only
    assert g.capture_offset((800, 600)) is None               # unknown size: screen capture instead
    assert g.capture_offset(None) is None


def test_covered_parts_of_the_game_picture():
    # user's diagnose 1.41.0: DBD as a 1920×1080 window at (-3422, 254) on the left monitor; banner region
    # (detector.ROI) of that window on screen – another window over it must not be read as the game
    banner = (-3422 + 0, 254 + int(0.52 * 1080), int(0.64 * 1920), int(0.47 * 1080))
    assert overlaps(banner, [(-3000, 600, 900, 700)])            # our own window over the lower left part
    assert not overlaps(banner, [(100, 0, 1200, 800)])           # a browser on the other monitor
    assert not overlaps(banner, [(-3440, 0, 18, 1440)])           # ends where DBD's picture starts
    assert not overlaps(banner, [(-3422, 254, 1920, banner[1] - 254)])   # only above the banner region
    assert overlaps(banner, [(0, 0, 10, 10), (-2300, 1300, 50, 50)])
    assert not overlaps(banner, [])


def test_a_screen_grab_turns_mss_bgra_into_writable_bgr():
    """1.3.5: BGRA -> BGR straight from mss' buffer by OpenCV (the numpy copy took 28 ms per 3440×1440 look);
    the worker blacks out our overlay in place, so the picture must be its own writable array."""
    import types
    import numpy as np
    from fogscout import capture
    px = (np.arange(4 * 5 * 4) + 1).astype(np.uint8).reshape(4, 5, 4)
    for raw in (bytearray(px.tobytes()), px.tobytes()):                  # Windows: bytearray; elsewhere bytes
        g = capture.ScreenGrabber.__new__(capture.ScreenGrabber)
        g._sct = types.SimpleNamespace(grab=lambda mon, _r=raw: types.SimpleNamespace(raw=_r, width=5, height=4))
        img = g.grab(0, 0, 5, 4)
        assert img.shape == (4, 5, 3) and np.array_equal(img, px[:, :, :3])
        img[0, 0] = 0                                                   # writable, and not mss' buffer
        assert raw[0] == px[0, 0, 0]
