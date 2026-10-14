"""Control window that follows its size: wrap lengths (pure part; the Tk part runs in tests/test_windows.py)."""
import importlib.util
import sys
from unittest import mock

if "tkinter" not in sys.modules and importlib.util.find_spec("tkinter") is None:   # headless CI: Tk only imported
    sys.modules["tkinter"] = mock.MagicMock()
if isinstance(sys.modules.get("tkinter"), mock.MagicMock):                      # mocked here or by another test
    sys.modules.setdefault("tkinter.font", mock.MagicMock())
    sys.modules.setdefault("tkinter.ttk", mock.MagicMock())

from dbdmapscout import uiscale  # noqa: E402


def test_wrap_width_uses_the_room_and_never_gets_tiny():
    assert uiscale.wrap_width(1000, 0, pad=0) == 1000
    assert uiscale.wrap_width(1000, 250, pad=16) == 734                  # a choice box right of the text
    assert uiscale.wrap_width(200, 0) == uiscale.MIN_WRAP                # narrow window: minimum
    assert 1.0 in uiscale.ZOOMS and min(uiscale.ZOOMS) < 1 < max(uiscale.ZOOMS)
