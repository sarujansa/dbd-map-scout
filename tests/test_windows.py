"""Windows only (CI job on windows-latest): the Win32 code paths that Linux never runs.

No game is needed: native overlay, notification window, window/cursor queries, hotkey registration and
the window-capture package are exercised on the runner's own desktop.
"""
import importlib
import os
import pkgutil
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_every_module_imports():
    import dbdmapscout
    names = [m.name for m in pkgutil.iter_modules(dbdmapscout.__path__)]
    assert "overlay_win32" in names and "toast" in names
    for name in names:
        if name == "__main__":
            continue
        importlib.import_module(f"dbdmapscout.{name}")


@pytest.fixture(scope="module")
def root():
    """The program's main loop (Qt) – what the overlays and the notification window get as ``root``."""
    from dbdmapscout import qt_window
    from dbdmapscout.mainloop import MainLoop
    return MainLoop(qt_window.application())


def pump(ms=100):
    """Let Qt's loop run a moment (window messages, timers)."""
    import time
    from PySide6.QtWidgets import QApplication
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        QApplication.processEvents()
        time.sleep(0.01)


def _window(x, y, w, h):
    """A plain top-level window at this place: (widget, hwnd)."""
    from PySide6.QtWidgets import QWidget
    win = QWidget()
    win.setWindowTitle("test")
    win.setGeometry(x, y, w, h)
    win.show()
    pump()
    return win, int(win.winId())


def test_native_overlay_renders_and_shows(root):
    from dbdmapscout.overlay_win32 import Win32Overlay, make_overlay
    ov = make_overlay(root, prefer_native=True)
    assert isinstance(ov, Win32Overlay), getattr(ov, "last_error", "")
    ov.set_map(os.path.join(ROOT, "maps", "McMillan", "Coal Tower.webp"), "Coal Tower", 90)
    ov.set_timer("01:23")
    ov.set_server("Frankfurt", 24)
    w, h = ov.render(400)
    assert w > 0 and h > 400                                  # map + info block below it
    ov.show_at(20, 20)
    pump()
    assert ov.is_visible()
    ov.hide()
    pump()
    assert not ov.is_visible()
    ov.destroy()


def test_notification_window_never_takes_the_focus(root):
    import ctypes
    from dbdmapscout.overlay import GWL_EXSTYLE, WS_EX_NOACTIVATE, _GetLong
    from dbdmapscout.toast import Toast
    t = Toast(root)
    t.show("Lobby gefunden", "nach 04:12 – READY drücken.", seconds=5)
    pump()
    h = int(t.win.winId())
    assert _GetLong(h, GWL_EXSTYLE) & WS_EX_NOACTIVATE
    assert ctypes.windll.user32.GetForegroundWindow() != h
    t.close()
    assert not t.shown


def test_window_and_cursor_queries():
    from dbdmapscout import capture
    assert capture.find_game_window() is None                # no DBD on the runner
    cur = capture.cursor_state()
    assert cur is None or len(cur) == 3
    capture.foreground_root()                                  # must not raise


def test_window_geometry_of_a_real_window(root):
    from dbdmapscout import capture
    w, hwnd = _window(50, 60, 640, 400)
    r = w.devicePixelRatioF()
    client, outer, window, monitor = capture.window_geometry(hwnd)
    w.close()
    assert client and outer and window and monitor
    assert client[2] >= 600 * r and client[3] >= 380 * r
    # title bar: client starts below the outer top, outer lies inside GetWindowRect
    assert outer[1] < client[1] and window[0] <= outer[0] and outer[2] <= window[2]
    assert monitor[2] > 0 and monitor[3] > 0


def test_windows_above_see_what_covers_a_window(root):
    from dbdmapscout import capture
    from dbdmapscout.overlay_win32 import Win32Overlay, make_overlay
    low, lo = _window(80, 80, 400, 300)
    high, hi = _window(150, 150, 200, 150)
    high.raise_()
    pump()
    hi_rect = capture.window_geometry(hi)[1]
    above = capture.windows_above(lo)
    assert hi_rect in above and capture.overlaps(capture.window_geometry(lo)[0], above)
    assert capture.window_geometry(lo)[1] not in capture.windows_above(hi)     # below, not above
    ov = make_overlay(root, prefer_native=True)
    assert isinstance(ov, Win32Overlay), getattr(ov, "last_error", "")
    ov.set_map(os.path.join(ROOT, "maps", "McMillan", "Coal Tower.webp"))
    ov.render(200)
    ov.show_at(100, 100)
    pump()
    assert ov.shown and capture.window_geometry(ov._hwnd)[1] not in capture.windows_above(lo)  # click-through
    ov.destroy()
    high.hide()
    pump()
    assert hi_rect not in capture.windows_above(lo)                            # hidden windows hide nothing
    high.close()
    low.close()


def test_hotkeys_register_and_stop():
    import time
    from dbdmapscout.config import DEFAULTS
    from dbdmapscout.hotkeys import HotkeyThread
    t = HotkeyThread(DEFAULTS["hotkeys"], lambda name: None)
    t.start()
    time.sleep(1.0)
    t.stop()
    t.join(timeout=3)
    assert not t.is_alive()


def test_own_taskbar_identity():
    from dbdmapscout import appid
    assert appid.set_process_app_id()
    assert appid.process_app_id() == appid.APP_ID


def test_shortcut_app_id_is_written_and_read_back(tmp_path):
    from dbdmapscout import appid
    from dbdmapscout.autostart import powershell
    lnk = str(tmp_path / "DbD Map Scout.lnk")
    ok, out = powershell(f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}')\n"
                         "$s.TargetPath = \"$env:SystemRoot\\System32\\schtasks.exe\"\n$s.Save()")
    assert ok and os.path.exists(lnk), out
    assert appid.link_app_id(lnk) is None
    assert appid.set_link_app_id(lnk)
    assert appid.link_app_id(lnk) == appid.APP_ID


def _locked_mutex(name):
    """A named mutex nobody may open – what a copy running as administrator owns, seen from a normal one."""
    import ctypes
    from ctypes import wintypes
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    conv = adv.ConvertStringSecurityDescriptorToSecurityDescriptorW
    conv.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
    conv.restype = wintypes.BOOL
    sd = ctypes.c_void_p()
    assert conv("D:(D;;GA;;;WD)", 1, ctypes.byref(sd), None), ctypes.get_last_error()     # deny everyone

    class SA(ctypes.Structure):
        _fields_ = [("nLength", wintypes.DWORD), ("lpSecurityDescriptor", ctypes.c_void_p),
                    ("bInheritHandle", wintypes.BOOL)]
    sa = SA(ctypes.sizeof(SA), sd, False)
    k32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    k32.CreateMutexW.restype = wintypes.HANDLE
    h = k32.CreateMutexW(ctypes.byref(sa), False, name)
    assert h, ctypes.get_last_error()
    return h


def test_single_instance_also_against_a_copy_with_more_rights():
    import ctypes
    from dbdmapscout.__main__ import _claim_mutex
    from dbdmapscout.restart import _program_running
    free = f"Local\\DbDMapScout.Test.{os.getpid()}.free"
    assert not _program_running(free)
    assert _claim_mutex(free)                                  # first copy
    assert _program_running(free)
    assert not _claim_mutex(free)                              # second copy: ERROR_ALREADY_EXISTS
    locked = f"Local\\DbDMapScout.Test.{os.getpid()}.locked"
    h = _locked_mutex(locked)
    try:
        assert not _claim_mutex(locked)                        # ERROR_ACCESS_DENIED is another copy, too
        assert _program_running(locked)                        # restart helper: wait, no second copy
    finally:
        ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(h))


def test_window_capture_package_is_the_checked_version():
    from importlib.metadata import version
    assert version("windows-capture") == "2.0.1"             # CLAUDE.md: re-audit before changing it
    importlib.import_module("windows_capture")


def test_native_overlay_stacks_the_floors(root):
    from dbdmapscout.overlay_win32 import Win32Overlay, make_overlay
    ov = make_overlay(root, prefer_native=True)
    assert isinstance(ov, Win32Overlay), getattr(ov, "last_error", "")
    ov.set_map(os.path.join(ROOT, "maps", "Other", "Midwich.gif"), "Midwich")
    assert ov.floors() == [0, 3]
    assert ov.stacked() == 2
    w, h = ov.map_size()
    assert 1.9 < h / w < 2.2                                  # both floors, one below the other
    ov.set_timer("1:23")
    both = ov.render(600)
    assert both[0] < 330 and not ov._anim_job                 # one still picture
    ov.set_floor(3)
    assert ov.stacked() == 1 and ov.map_size()[0] == ov.map_size()[1]
    one = ov.render(both[0])                                  # square floor, as high as the stack is wide
    assert not ov._anim_job and abs(one[0] - both[0]) <= 1    # one floor as wide as each stacked one
    assert abs((both[1] - 600) - (one[1] - both[0])) <= 2     # timer below: same size either way
    ov.set_floor(None)
    assert ov.stacked() == 2
    ov.destroy()


def test_single_key_hotkeys_only_while_dbd_is_in_front():
    import ctypes
    import time
    from dbdmapscout.hotkeys import VK, HotkeyThread
    user32 = ctypes.windll.user32

    def free(vk):                      # can another program still take the key?
        if user32.RegisterHotKey(None, 0x7ABC, 0, vk):
            user32.UnregisterHotKey(None, 0x7ABC)
            return True
        return False

    vk = VK["f9"]
    assert free(vk), "F9 is taken by another program on this machine"
    t = HotkeyThread({"next_floor": "f9"}, lambda name: None)
    t.start()
    assert t.ready.wait(3)
    assert free(vk)                                           # DBD not in front: the key stays free
    t.set_game_active(True)
    time.sleep(0.3)
    assert not free(vk)                                       # DBD in front: ours
    t.set_game_active(False)
    time.sleep(0.3)
    assert free(vk)
    t.stop()
    t.join(timeout=3)
    assert not t.is_alive()


def test_system_values_window_can_be_dragged_in_edit_mode(root):
    from dbdmapscout import overlay_win32 as ow
    hud = ow.HudWindow()
    rows = [[("CPU ", (210, 214, 224, 255)), ("62°C", (134, 239, 172, 255))]]
    w, h = hud.render(rows, 1440)
    hud.show_at(30, 30)
    pump()
    ex = ow._GetLong(hud.hwnd(), ow.GWL_EXSTYLE)
    assert ex & ow.WS_EX_TRANSPARENT                          # click-through while playing
    hud.set_editing(True)
    w2, h2 = hud.render(rows, 1440)
    ex = ow._GetLong(hud.hwnd(), ow.GWL_EXSTYLE)
    assert not ex & ow.WS_EX_TRANSPARENT and (w2, h2) == (w, h)   # draggable, same size (border drawn inside)
    moved = []
    hud.on_moved = lambda x, y: moved.append((x, y))
    hud._wndproc(hud.hwnd(), ow.WM_EXITSIZEMOVE, 0, 0)
    assert moved == [(30, 30)]
    hud.set_editing(False)
    hud.destroy()


def test_window_gets_real_clicks_while_the_timers_run(root):
    """Qt's loop is the program's main loop: real Win32 clicks reach the window, the slot only hands the action
    over (post), and the timers (MainLoop.after) keep running."""
    import ctypes
    from PySide6.QtCore import QPoint
    from dbdmapscout import qt_window
    posted = []
    win = qt_window.MainWindow(lambda a, arg=None: posted.append(a))
    win.apply_theme(True, 1.0)
    win.show()
    btn = win.overview.buttons["scan"]
    btn.setText("Scannen")
    ticks = []
    user32 = ctypes.windll.user32
    user32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]

    def tick(n=0):
        ticks.append(n)
        if n == 10:                                  # a real click, delivered by the message loop
            p = btn.mapTo(win, QPoint(btn.width() // 2, btn.height() // 2))
            r = win.devicePixelRatioF()
            lparam = (round(p.y() * r) << 16) | round(p.x() * r)
            user32.PostMessageW(win.hwnd(), 0x0201, 1, lparam)       # WM_LBUTTONDOWN, MK_LBUTTON
            user32.PostMessageW(win.hwnd(), 0x0202, 0, lparam)       # WM_LBUTTONUP
        if n < 40:
            root.after(25, lambda: tick(n + 1))
        else:
            root.quit()
    root.after(25, tick)
    root.after(15000, root.quit)                     # watchdog: a broken tick fails the test instead of hanging
    root.mainloop()
    assert len(ticks) == 41 and posted == ["scan"]
    win.allow_close = True
    win.close()
    import shiboken6
    shiboken6.delete(win)                            # no Qt window may live on until the interpreter shuts down
