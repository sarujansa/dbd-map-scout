"""Start without a UAC prompt, optionally with Windows (Task Scheduler), and the desktop shortcut.

A scheduled task with "run with highest privileges" starts the program as administrator
without asking; running an existing task needs no elevation. Creating or changing the
tasks does – the setup (verknuepfung_erstellen.bat) is elevated, and the program itself
runs elevated when started through the task.

    python -m fogscout.autostart install      (elevated) icon + task + desktop and Start menu shortcut

Tasks:
  "Fog Scout"               on demand; the shortcuts run it (schtasks /run)
  "Fog Scout (Autostart)"   at logon (20 s delay), starts in the notification area ("tray")
Both run: cmd /c start "" /min cmd /c .\\start.bat [tray]  in the program folder (working directory) – so
updates and packages keep working, and the minimised console closes again (start alone would use cmd /K and
leave it open). 1.8.45: the folder is never part of the command line – cmd would read "&" in it as a second
command and expand "%…%" (the working directory is not parsed).

Both shortcuts carry the program's AppUserModelID (appid.py). The Start menu one is needed for pinning
the running window: Windows looks for a shortcut with that ID there (not on the desktop) and pins it –
without one it pins .venv\\Scripts\\pythonw.exe (Python icon, starts nothing).
"""
from __future__ import annotations

import base64
import os
import subprocess
import sys

from . import icon as icon_mod
from .appid import set_link_app_id
from .i18n import _

SETUP_VERSION = 7           # raise when task, shortcut or icon change: the program then renews them itself
TASK = "Fog Scout"
TASK_AUTO = "Fog Scout (Autostart)"
LINK_NAME = "Fog Scout.lnk"
# 1.9: the program was "DbD Map Scout" until 1.8.91 – its tasks and shortcuts are removed when the new ones are made
OLD_TASK = "DbD Map Scout"
OLD_TASK_AUTO = "DbD Map Scout (Autostart)"
OLD_LINK_NAME = "DbD Map Scout.lnk"
IS_WIN = sys.platform == "win32"


def _q(s: str) -> str:
    """PowerShell single-quoted literal."""
    return "'" + str(s).replace("'", "''") + "'"


def task_script(root: str, name: str, at_logon: bool) -> str:
    """PowerShell that (re)creates one task for the current user, run level highest."""
    root = os.path.abspath(root)
    # "start" alone would run the .bat with cmd /K – its (minimised) console would stay open afterwards.
    # Explicit cmd /c closes it. 1.8.45: start.bat by its name in the working directory (-WorkingDirectory,
    # which start passes on) – a folder with "&" or "%" on the command line broke the task.
    arg = '/c start "" /min cmd /c .\\start.bat' + (" tray" if at_logon else "")
    lines = [
        "$ErrorActionPreference = 'Stop'",
        "$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name",
        f"$a = New-ScheduledTaskAction -Execute \"$env:SystemRoot\\System32\\cmd.exe\" -Argument {_q(arg)} "
        f"-WorkingDirectory {_q(root)}",
        "$p = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Highest",
        "$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
        "-ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew",
    ]
    if at_logon:
        lines += ["$t = New-ScheduledTaskTrigger -AtLogOn -User $user",
                  "$t.Delay = 'PT20S'",
                  f"Register-ScheduledTask -TaskName {_q(name)} -Action $a -Principal $p -Settings $s -Trigger $t "
                  "-Force | Out-Null"]
    else:
        lines.append(f"Register-ScheduledTask -TaskName {_q(name)} -Action $a -Principal $p -Settings $s -Force "
                     "| Out-Null")
    return "\n".join(lines)


def remove_script(name: str) -> str:
    return (f"$t = Get-ScheduledTask -TaskName {_q(name)} -ErrorAction SilentlyContinue\n"
            f"if ($t) {{ Unregister-ScheduledTask -TaskName {_q(name)} -Confirm:$false }}")


def remove_old_script() -> str:
    """1.9: PowerShell that removes the tasks and shortcuts of the old program name (nothing else)."""
    lines = [remove_script(OLD_TASK), remove_script(OLD_TASK_AUTO)]
    for folder in ("Desktop", "Programs"):
        lines.append(f"$old = Join-Path ([Environment]::GetFolderPath({_q(folder)})) {_q(OLD_LINK_NAME)}")
        lines.append("if (Test-Path -LiteralPath $old) { Remove-Item -LiteralPath $old -Force }")
    return "\n".join(lines)


def relaunch_command() -> str:
    """1.9.1: what the taskbar runs for a pinned button of the window – the same as the shortcuts (the task)."""
    system_root = (os.environ.get("SystemRoot") or r"C:\Windows").rstrip("\\/")
    return f'"{system_root}\\System32\\schtasks.exe" /run /tn "{TASK}"'


def shortcut_script(root: str, icon: str, folder: str = "Desktop") -> str:
    """Shortcut that runs the on-demand task (no UAC prompt); folder: "Desktop" or "Programs" (Start menu)."""
    run_args = '/run /tn "' + TASK + '"'
    lines = [
        "$ErrorActionPreference = 'Stop'",
        f"$lnk = Join-Path ([Environment]::GetFolderPath({_q(folder)})) {_q(LINK_NAME)}",
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)",
        "$s.TargetPath = \"$env:SystemRoot\\System32\\schtasks.exe\"",
        f"$s.Arguments = {_q(run_args)}",
        f"$s.WorkingDirectory = {_q(os.path.abspath(root))}",
        "$s.WindowStyle = 7",
        f"$s.Description = {_q('Fog Scout - Map-Overlay fuer Dead by Daylight')}",
    ]
    if icon:
        lines.append(f"$s.IconLocation = {_q(os.path.abspath(icon) + ',0')}")
    lines += ["$s.Save()", "Write-Output $lnk"]
    return "\n".join(lines)


def powershell(script: str, timeout: float = 60.0):
    """Run a PowerShell script (encoded: no quoting trouble). Returns (ok, output)."""
    enc = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                            "-EncodedCommand", enc], capture_output=True, text=True, timeout=timeout,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)
    out = (r.stdout or "").strip() or (r.stderr or "").strip()
    return r.returncode == 0, out


def task_exists(name: str) -> bool:
    if not IS_WIN:
        return False
    try:
        r = subprocess.run(["schtasks", "/Query", "/TN", name], capture_output=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=15)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def set_autostart(root: str, on: bool):
    """Create or remove the logon task (needs administrator rights). Returns (ok, message)."""
    ok, out = powershell(task_script(root, TASK_AUTO, True) if on else remove_script(TASK_AUTO))
    return ok, out


def ensure_autostart(root: str, wanted: bool):
    """Autostart is on unless the user switched it off in the settings: create the logon task if it
    is missing (needs administrator rights). Returns None (nothing to do) or (ok, output)."""
    if not IS_WIN or not wanted or task_exists(TASK_AUTO):
        return None
    return set_autostart(root, True)


def needs_setup(saved_version, saved_root, root: str, task_present: bool) -> bool:
    """Should the program (running as administrator) create or renew task, icon and shortcut?
    First run, other folder (moved), a newer setup after an update, or the task was removed.
    A shortcut the user deleted on purpose is not brought back on every start."""
    same_root = bool(saved_root) and os.path.normcase(os.path.abspath(saved_root)) == \
        os.path.normcase(os.path.abspath(root))
    return not (task_present and same_root and saved_version == SETUP_VERSION)


def ensure(root: str, saved_version, saved_root):
    """Called at program start when running as administrator. Returns None (nothing to do) or
    (ok, message). Also renews the logon task if the user switched autostart on earlier."""
    if not IS_WIN or not needs_setup(saved_version, saved_root, root, task_exists(TASK)):
        return None
    had_auto = task_exists(TASK_AUTO) or task_exists(OLD_TASK_AUTO)    # 1.9: before install removes the old one
    ok, msg = install(root)
    if ok and had_auto:
        ok2, out = set_autostart(root, True)
        if not ok2:
            msg += " " + _("(Autostart nicht erneuert: {error})", error=out)
    return ok, msg


def install(root: str):
    """Icon, on-demand task, desktop and Start menu shortcut. Returns (ok, message)."""
    try:
        icon = icon_mod.ensure_ico(root)
    except OSError:
        icon = ""
    powershell(remove_old_script())                 # 1.9: the old name's tasks and shortcuts (best effort) …
    for old in icon_mod.OLD_FILES:                  # … and the icons only they showed (1.9.1: also 1.9's file)
        try:
            os.remove(os.path.join(root, old))
        except OSError:
            pass
    ok, out = powershell(task_script(root, TASK, False))
    if not ok:
        return False, _("Aufgabe konnte nicht angelegt werden: {error}", error=out)
    links = []
    for folder in ("Programs", "Desktop"):        # Start menu first: pinning the running window uses it
        ok, out = powershell(shortcut_script(root, icon, folder))
        if not ok:
            return False, _("Verknüpfung konnte nicht angelegt werden: {error}", error=out)
        set_link_app_id(out)      # same ID as the program: pinned shortcut and window share one button
        links.append(out)
    return True, _("Verknüpfung erstellt: {path}", path=links[-1])


def main(argv) -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if argv[:1] == ["install"]:
        ok, msg = install(root)
        print(msg)
        return 0 if ok else 1
    print("usage: python -m fogscout.autostart install")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
