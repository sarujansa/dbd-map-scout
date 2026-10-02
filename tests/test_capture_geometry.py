"""Window-capture offsets of the game picture (dbdmapscout/capture.py, pure part)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dbdmapscout.capture import GameWindow  # noqa: E402


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
