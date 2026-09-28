"""Start without a UAC prompt, optionally with Windows (Task Scheduler), and the desktop shortcut.

A scheduled task with "run with highest privileges" starts the program as administrator
without asking; running an existing task needs no elevation. Creating or changing the
tasks does – the setup (verknuepfung_erstellen.bat) is elevated, and the program itself
runs elevated when started through the task.

    python -m dbdmapscout.autostart install      (elevated) icon + task + desktop shortcut

Tasks:
  "DbD Map Scout"               on demand; the desktop shortcut runs it (schtasks /run)
  "DbD Map Scout (Autostart)"   at logon (20 s delay), starts in the notification area ("tray")
Both run: cmd /c start "" /min cmd /c ""<folder>\\start.bat" [tray]"  – so updates and packages keep
working, and the minimised console closes again (start alone would use cmd /K and leave it open).
"""
from __future__ import annotations

import base64
import os
import subprocess
import sys

SETUP_VERSION = 2           # raise when task, shortcut or icon change: the program then renews them itself
TASK = "DbD Map Scout"
TASK_AUTO = "DbD Map Scout (Autostart)"
LINK_NAME = "DbD Map Scout.lnk"
IS_WIN = sys.platform == "win32"


def _q(s: str) -> str:
    """PowerShell single-quoted literal."""
    return "'" + str(s).replace("'", "''") + "'"


def task_script(root: str, name: str, at_logon: bool) -> str:
    """PowerShell that (re)creates one task for the current user, run level highest."""
    root = os.path.abspath(root)
    bat = os.path.join(root, "start.bat")
    # "start" alone would run the .bat with cmd /K – its (minimised) console would stay open afterwards.
    # Explicit cmd /c closes it. Quoting: cmd /c strips the outer pair of ""…"".
    arg = f'/c start "" /min cmd /c ""{bat}"' + (" tray" if at_logon else "") + '"'
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


def shortcut_script(root: str, icon: str) -> str:
    """Desktop shortcut that runs the on-demand task (no UAC prompt)."""
    run_args = '/run /tn "' + TASK + '"'
    lines = [
        "$ErrorActionPreference = 'Stop'",
        f"$lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) {_q(LINK_NAME)}",
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)",
        "$s.TargetPath = \"$env:SystemRoot\\System32\\schtasks.exe\"",
        f"$s.Arguments = {_q(run_args)}",
        f"$s.WorkingDirectory = {_q(os.path.abspath(root))}",
        "$s.WindowStyle = 7",
        f"$s.Description = {_q('DbD Map Scout - Map-Overlay fuer Dead by Daylight')}",
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
    ok, msg = install(root)
    if ok and task_exists(TASK_AUTO):
        ok2, out = set_autostart(root, True)
        if not ok2:
            msg += f" (Autostart nicht erneuert: {out})"
    return ok, msg


def install(root: str):
    """Icon, on-demand task and desktop shortcut. Returns (ok, message)."""
    from .icon import save_ico
    icon = os.path.join(root, "dbdmapscout.ico")
    try:
        save_ico(icon)
    except OSError:
        icon = ""
    ok, out = powershell(task_script(root, TASK, False))
    if not ok:
        return False, f"Aufgabe konnte nicht angelegt werden: {out}"
    ok, out = powershell(shortcut_script(root, icon))
    if not ok:
        return False, f"Verknüpfung konnte nicht angelegt werden: {out}"
    return True, f"Verknüpfung erstellt: {out}"


def main(argv) -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if argv[:1] == ["install"]:
        ok, msg = install(root)
        print(msg)
        return 0 if ok else 1
    print("usage: python -m dbdmapscout.autostart install")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
