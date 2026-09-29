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


def test_window_capture_package_is_the_checked_version():
    from importlib.metadata import version
    assert version("windows-capture") == "2.0.1"             # CLAUDE.md: re-audit before changing it
    importlib.import_module("windows_capture")
