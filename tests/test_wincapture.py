"""Window capture (Windows Graphics Capture) while DBD is in the background."""
import os
import sys
import threading
import time
import types

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fogscout.wincapture import CapturePolicy, WindowCapture, describe  # noqa: E402


# ------------------------------------------------------------------ policy
def test_policy_runs_only_while_dbd_is_in_the_background():
    p = CapturePolicy()
    assert not p.update(0.0, True, True, True)          # DBD active in front: screen capture as before
    assert p.update(1.0, True, True, False)             # another window active: window capture
    assert p.update(2.0, True, True, True)              # back to DBD: keep it a while (quick Alt+Tab)
    assert p.update(2.0 + p.STOP_AFTER - 0.1, True, True, True)
    assert not p.update(2.0 + p.STOP_AFTER, True, True, True)   # active long enough: off again


def test_policy_restarts_the_hold_after_another_alt_tab():
    p = CapturePolicy()
    p.update(0.0, True, True, False)
    p.update(1.0, True, True, True)
    p.update(4.0, True, True, False)                    # away again before the hold ran out
    assert p.update(4.0 + p.STOP_AFTER - 0.1, True, True, True)


def test_policy_off_without_window_or_option():
    p = CapturePolicy()
    assert not p.update(0.0, False, True, False)        # option off
    assert not p.update(0.0, True, False, False)        # DBD gone or minimised
    p.update(1.0, True, True, False)
    assert not p.update(1.5, True, False, False)        # window vanished: stop at once


# ------------------------------------------------------------------ capture (fake windows_capture)
class _FakeLib:
    """Behaves like windows_capture 2.0.1: callbacks on its own thread, BGRA buffer valid only
    during the callback, options that older Windows refuses raise at construction."""

    def __init__(self, refuse=(), size=(64, 40)):
        self.refuse, self.size, self.made = set(refuse), size, []
        lib = self

        class WindowsCapture:
            def __init__(self, **kw):
                if any(k in lib.refuse and v not in (None,) for k, v in kw.items()):
                    raise RuntimeError("unsupported")
                lib.made.append(kw)
                self.handlers = {}

            def event(self, h):
                self.handlers[h.__name__] = h
                return h

            def start_free_threaded(self):
                stop = threading.Event()

                def loop():
                    n = 0
                    while not stop.is_set():
                        w, h = lib.size
                        buf = np.zeros((h, w, 4), np.uint8)
                        buf[..., 0], buf[..., 1], buf[..., 2], buf[..., 3] = n % 256, 7, 9, 255
                        self.handlers["on_frame_arrived"](types.SimpleNamespace(frame_buffer=buf, width=w, height=h),
                                                          None)
                        buf[:] = 0                                        # "unmapped" after the callback
                        n += 1
                        time.sleep(0.01)
                    self.handlers["on_closed"]()

                threading.Thread(target=loop, daemon=True).start()
                return types.SimpleNamespace(stop=stop.set)

        self.module = types.SimpleNamespace(WindowsCapture=WindowsCapture)


def _with_lib(monkeypatch, lib):
    monkeypatch.setitem(sys.modules, "windows_capture", lib.module)


def test_capture_copies_the_requested_region(monkeypatch):
    lib = _FakeLib()
    _with_lib(monkeypatch, lib)
    cap = WindowCapture(1234)
    assert cap.start()
    assert lib.made[0] == {"window_hwnd": 1234, "cursor_capture": False, "draw_border": False,
                           "minimum_update_interval": 200}
    img = cap.grab(10, 5, 20, 8, expect_size=(64, 40))
    assert img is not None and img.shape == (8, 20, 3)         # BGR, requested region only
    assert (img[..., 1] == 7).all() and (img[..., 2] == 9).all()   # still valid after the callback
    cap.stop()
    time.sleep(0.05)
    assert cap.grab(0, 0, 4, 4) is None                         # stopped


def test_capture_falls_back_to_options_older_windows_accepts(monkeypatch):
    lib = _FakeLib(refuse={"minimum_update_interval", "draw_border"})
    _with_lib(monkeypatch, lib)
    cap = WindowCapture(1)
    assert cap.start()
    assert cap.options == {"cursor_capture": False}
    assert describe(cap, True) == "Fenster (WGC)"
    cap.stop()


def test_wrong_picture_size_is_not_used(monkeypatch):
    lib = _FakeLib(size=(64, 70))                               # e.g. with a title bar: pixels would be shifted
    _with_lib(monkeypatch, lib)
    cap = WindowCapture(1)
    cap.start()
    assert cap.grab(0, 0, 10, 10, expect_size=(64, 40)) is None
    assert cap.grab(0, 0, 10, 10, expect_size=(64, 40)) is None   # size known now: refused at once
    cap.stop()


def test_no_picture_in_time_returns_none(monkeypatch):
    lib = _FakeLib()
    _with_lib(monkeypatch, lib)
    cap = WindowCapture(1)
    cap.start()
    cap._on_frame = lambda frame: None                          # frames arrive but never answer
    t0 = time.time()
    assert cap.grab(0, 0, 4, 4, timeout=0.1) is None
    assert time.time() - t0 < 0.5
    t1 = time.time()
    assert cap.grab(0, 0, 4, 4, timeout=0.1) is None             # right after a timeout: no waiting at all
    assert time.time() - t1 < 0.05
    cap.stop()


def test_missing_package_reports_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "windows_capture", None)  # import fails
    cap = WindowCapture(1)
    assert not cap.start() and "windows-capture" in cap.error
    assert describe(None, True).startswith("Bildschirm")
    assert describe(None, False) == "Bildschirm"
