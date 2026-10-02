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
    """One Tk for all tests (like the program): a second Tk interpreter in the same process does not
    find its message catalogue on the Windows runner."""
    tk = pytest.importorskip("tkinter")
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


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
    root.update()
    assert ov.is_visible()
    ov.hide()
    root.update()
    assert not ov.is_visible()
    ov.destroy()


def test_notification_window_never_takes_the_focus(root):
    import ctypes
    from dbdmapscout.overlay import GWL_EXSTYLE, WS_EX_NOACTIVATE, _GetLong, _user32
    from dbdmapscout.toast import Toast
    t = Toast(root)
    t.show("Lobby gefunden", "nach 04:12 – READY drücken.", seconds=5)
    root.update()
    h = int(_user32.GetParent(t.win.winfo_id()) or 0) or t.win.winfo_id()
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
    import tkinter as tk
    from dbdmapscout import capture
    w = tk.Toplevel(root)
    w.geometry("640x400+50+60")
    w.update()
    hwnd = int(w.wm_frame(), 16)
    client, outer, window, monitor = capture.window_geometry(hwnd)
    w.destroy()
    assert client and outer and window and monitor
    assert client[2] >= 600 and client[3] >= 380
    # title bar: client starts below the outer top, outer lies inside GetWindowRect
    assert outer[1] < client[1] and window[0] <= outer[0] and outer[2] <= window[2]
    assert monitor[2] > 0 and monitor[3] > 0


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
