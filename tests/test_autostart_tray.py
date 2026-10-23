"""Task Scheduler start (no UAC prompt), autostart, desktop shortcut and the tray icon."""
import base64
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fogscout import autostart as au  # noqa: E402
from fogscout.tray import Tray  # noqa: E402

ROOT = r"C:\Users\Player\Desktop\fog-scout"


# ------------------------------------------------------------------ tasks
def test_on_demand_task_runs_start_bat_elevated_without_trigger():
    s = au.task_script(ROOT, au.TASK, False)
    assert "-RunLevel Highest" in s and "-LogonType Interactive" in s
    assert "New-ScheduledTaskTrigger" not in s and "-Trigger" not in s
    # via start.bat (updates/packages keep working), explicit cmd /c so the minimised console closes again
    assert """-Argument '/c start "" /min cmd /c .\\start.bat'""" in s
    assert " tray'" not in s
    assert f"-TaskName '{au.TASK}'" in s and "-MultipleInstances IgnoreNew" in s


def test_autostart_task_at_logon_in_tray():
    s = au.task_script(ROOT, au.TASK_AUTO, True)
    assert "New-ScheduledTaskTrigger -AtLogOn -User $user" in s and "$t.Delay = 'PT20S'" in s
    assert ".\\start.bat tray'" in s and "-Trigger $t" in s


def test_paths_with_quotes_stay_one_literal():
    s = au.task_script(r"C:\Users\O'Brien\dbd", au.TASK, False)
    assert "O''Brien" in s                                    # PowerShell single-quote escaping


def test_remove_only_existing_task():
    s = au.remove_script(au.TASK_AUTO)
    assert "Get-ScheduledTask" in s and "Unregister-ScheduledTask" in s and "-Confirm:$false" in s


def test_shortcut_runs_the_task():
    s = au.shortcut_script(ROOT, ROOT + r"\fogscout.ico")
    assert "schtasks.exe" in s and "'/run /tn \"Fog Scout\"'" in s
    assert "$s.WindowStyle = 7" in s and "fogscout.ico,0'" in s
    assert "GetFolderPath('Desktop')" in s
    assert "GetFolderPath('Programs')" in au.shortcut_script(ROOT, "", "Programs")


def test_shortcut_gets_the_program_app_id(monkeypatch, tmp_path):
    """Pinned shortcut and running window must share one AppUserModelID (one taskbar button, own icon)."""
    import fogscout.icon as icon
    monkeypatch.setattr(icon, "save_ico", lambda path: None)
    start = r"C:\Users\Player\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Fog Scout.lnk"
    desk = r"C:\Users\Player\Desktop\Fog Scout.lnk"

    def fake(script):
        if "CreateShortcut" not in script:
            return True, ""
        return True, start if "GetFolderPath('Programs')" in script else desk
    monkeypatch.setattr(au, "powershell", fake)
    seen = []
    monkeypatch.setattr(au, "set_link_app_id", lambda path: seen.append(path) or True)
    ok, msg = au.install(str(tmp_path))
    # Start menu: Windows pins that shortcut for the running window (none there -> pythonw.exe is pinned)
    assert ok and seen == [start, desk] and desk in msg


def test_powershell_is_encoded(monkeypatch):
    seen = {}

    def fake_run(args, **kw):
        seen["args"] = args
        return types.SimpleNamespace(returncode=0, stdout="ok\n", stderr="")
    monkeypatch.setattr(au.subprocess, "run", fake_run)
    ok, out = au.powershell("Write-Output 'ä \" $x'")
    assert ok and out == "ok"
    enc = seen["args"][seen["args"].index("-EncodedCommand") + 1]
    assert base64.b64decode(enc).decode("utf-16-le") == "Write-Output 'ä \" $x'"
    assert "-NonInteractive" in seen["args"]


# ------------------------------------------------------------------ tray
class _FakePystray:
    def __init__(self):
        lib = self
        self.icons = []

        class MenuItem:
            def __init__(self, text, action, default=False):
                self.text, self.action, self.default = text, action, default

        class Menu:
            SEPARATOR = object()

            def __init__(self, *items):
                self.items = items

        class Icon:
            def __init__(self, name, image, title, menu):
                self.name, self.image, self.title, self.menu = name, image, title, menu
                self.running = False
                lib.icons.append(self)

            def run_detached(self):
                self.running = True

            def stop(self):
                self.running = False

        self.module = types.SimpleNamespace(MenuItem=MenuItem, Menu=Menu, Icon=Icon)


def test_tray_menu_posts_actions_to_the_ui_thread(monkeypatch):
    fake = _FakePystray()
    monkeypatch.setitem(sys.modules, "pystray", fake.module)
    posted = []
    t = Tray(posted.append)
    assert t.start() and t.active
    icon = fake.icons[0]
    assert icon.running and icon.image.size == (64, 64)
    items = [i for i in icon.menu.items if i is not fake.module.Menu.SEPARATOR]
    assert [i.text for i in items] == ["Fenster öffnen", "Overlay ein/aus", "Beenden"]
    assert items[0].default                                          # double click opens the window
    for i in items:
        i.action(icon, i)
    assert posted == ["open", "toggle", "quit"]                       # only posted, never Tk from this thread
    t.set_title("Fog Scout – " + "x" * 200)
    assert len(icon.title) == 127
    t.stop()
    assert not icon.running and not t.active


def test_tray_without_package(monkeypatch):
    monkeypatch.setitem(sys.modules, "pystray", None)
    t = Tray(lambda a: None)
    assert not t.start() and not t.active and t.error
    t.set_title("x")                                                 # harmless
    t.stop()


# ------------------------------------------------------------------ automatic setup
def test_setup_needed_on_first_run_move_update_or_missing_task():
    v = au.SETUP_VERSION
    assert au.needs_setup(None, None, ROOT, False)                       # first run
    assert not au.needs_setup(v, ROOT, ROOT, True)                       # all in place: nothing to do
    assert au.needs_setup(v - 1, ROOT, ROOT, True)                        # update changed the setup
    assert au.needs_setup(v, ROOT + "-old", ROOT, True)                  # folder moved
    assert au.needs_setup(v, ROOT, ROOT, False)                          # task removed


def test_ensure_renews_autostart_only_if_it_was_on(monkeypatch):
    monkeypatch.setattr(au, "IS_WIN", True)
    calls = []
    monkeypatch.setattr(au, "install", lambda root: calls.append("install") or (True, "ok"))
    monkeypatch.setattr(au, "set_autostart", lambda root, on: calls.append(("autostart", on)) or (True, ""))
    present = {au.TASK: False, au.TASK_AUTO: False}
    monkeypatch.setattr(au, "task_exists", lambda name: present.get(name, False))
    assert au.ensure(ROOT, None, None) == (True, "ok") and calls == ["install"]
    present[au.TASK] = True
    calls.clear()
    assert au.ensure(ROOT, au.SETUP_VERSION, ROOT) is None and calls == []    # nothing to do
    present[au.TASK_AUTO] = True
    assert au.ensure(ROOT, au.SETUP_VERSION - 1, ROOT)[0]
    assert calls == ["install", ("autostart", True)]                          # autostart kept, renewed


def test_autostart_is_on_unless_switched_off(monkeypatch):
    from fogscout.config import DEFAULTS
    assert DEFAULTS["autostart"] is True                                      # user's wish: always on
    monkeypatch.setattr(au, "IS_WIN", True)
    calls = []
    monkeypatch.setattr(au, "set_autostart", lambda root, on: calls.append(on) or (True, ""))
    present = {au.TASK_AUTO: False}
    monkeypatch.setattr(au, "task_exists", lambda name: present.get(name, False))
    assert au.ensure_autostart(ROOT, False) is None and calls == []           # switched off: stays off
    assert au.ensure_autostart(ROOT, True) == (True, "") and calls == [True]  # missing: set up again
    present[au.TASK_AUTO] = True
    assert au.ensure_autostart(ROOT, True) is None and calls == [True]        # already there


def test_task_command_line_never_carries_the_folder():
    """1.8.45: cmd reads "&" in a folder name as a second command and expands "%…%" – the folder goes only into
    -WorkingDirectory (a PowerShell literal), the command line runs .\\start.bat from there."""
    import re
    root = r"C:\Spiele & Tools\100% dbd"
    for at_logon, tail in ((False, ""), (True, " tray")):
        s = au.task_script(root, au.TASK, at_logon)
        arg = re.search(r"-Argument '([^']*)'", s).group(1)
        assert arg == '/c start "" /min cmd /c .\\start.bat' + tail
        assert f"-WorkingDirectory '{os.path.abspath(root)}'" in s


def test_the_tray_dot_shows_the_state():
    """1.3.6: green = map on display, yellow = doubtful, red = problem, grey = waiting, none = no DBD."""
    from fogscout import status
    st = lambda **kw: status.user_state(**{"game_found": True, **kw})
    assert status.tray_dot(st(has_map=True)) == "ok"
    assert status.tray_dot(st(has_map=True, menu_paused=True)) == "ok"
    assert status.tray_dot(st(has_map=True), unsure=True) == "warn"
    assert status.tray_dot(st(worker_status="Aufnahme ist schwarz")) == "err"
    assert status.tray_dot(st()) == "idle"
    assert status.tray_dot(st(has_map=True, hidden_after_match=True)) == "idle"
    assert status.tray_dot(status.user_state(game_found=False), game_found=False) is None


def test_the_tray_icon_changes_only_when_the_state_does():
    from fogscout import icon, theme
    plain, green = icon.draw_status(64, None), icon.draw_status(64, theme.DOT["ok"])
    assert plain.tobytes() == icon.draw(64).tobytes()
    r, g, b, a = green.getpixel((50, 50))                    # the dot, bottom right
    assert a == 255 and g > r and g > b
    assert green.getpixel((10, 10)) == plain.getpixel((10, 10))
    t = Tray(lambda a: None)
    t._icon = types.SimpleNamespace(icon=None)
    t.set_status("ok")
    first = t._icon.icon
    t.set_status("ok")
    assert t._icon.icon is first and first.getpixel((50, 50))[1] > 150
    t.set_status("err")
    assert t._icon.icon is not first and t._icon.icon.getpixel((50, 50))[0] > 150


def test_install_removes_the_old_name_s_tasks_and_shortcuts_first(monkeypatch, tmp_path):
    """1.9: until 1.8.91 the tasks and shortcuts said "DbD Map Scout" – they go when the new ones are made, nothing
    else does, and a failure there never stops the setup."""
    import fogscout.icon as icon
    monkeypatch.setattr(icon, "save_ico", lambda path: None)
    scripts = []

    def fake(script):
        scripts.append(script)
        if "Remove-Item" in script:
            return False, "access denied"                       # best effort: the setup goes on
        return True, r"C:\x\Fog Scout.lnk" if "CreateShortcut" in script else ""
    monkeypatch.setattr(au, "powershell", fake)
    monkeypatch.setattr(au, "set_link_app_id", lambda path: True)
    (tmp_path / au.OLD_ICON).write_bytes(b"\0")                   # the icon only the old shortcuts showed
    ok, _msg = au.install(str(tmp_path))
    assert ok and len(scripts) == 4 and not (tmp_path / au.OLD_ICON).exists()
    first = scripts[0]
    assert "Unregister-ScheduledTask" in first and "'DbD Map Scout'" in first and "'DbD Map Scout (Autostart)'" in first
    assert "'DbD Map Scout.lnk'" in first and "Remove-Item -LiteralPath" in first
    assert "Register-ScheduledTask" not in first and "Fog Scout" not in first
    assert "Register-ScheduledTask -TaskName 'Fog Scout'" in scripts[1]
    assert all("CreateShortcut" in s and "'Fog Scout.lnk'" in s for s in scripts[2:])


def test_ensure_keeps_an_autostart_that_ran_under_the_old_name(monkeypatch):
    """1.9: the user's autostart was the task "DbD Map Scout (Autostart)" – install removes it, so ensure must look
    before and set the new one up."""
    monkeypatch.setattr(au, "IS_WIN", True)
    monkeypatch.setattr(au, "task_exists", lambda name: name == au.OLD_TASK_AUTO)
    calls = []
    monkeypatch.setattr(au, "install", lambda root: calls.append("install") or (True, "ok"))
    monkeypatch.setattr(au, "set_autostart", lambda root, on: calls.append(("autostart", on)) or (True, ""))
    assert au.ensure(ROOT, 5, ROOT) == (True, "ok") and calls == ["install", ("autostart", True)]
    assert au.SETUP_VERSION == 6                                  # a renewed setup for every installation
