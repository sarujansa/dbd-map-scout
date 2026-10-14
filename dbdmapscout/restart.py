"""Restart through start.bat after "Aktualisieren und neu starten".

The program starts a small helper (``python -m dbdmapscout --restart``) and quits. The helper waits
until the program has really ended (its single-instance mutex is gone – so no package file is still
in use when pip updates it), then runs start.bat, which installs the update as on every start
(``DBDMS_FORCE_UPDATE=1``: also when "check for updates at start" is switched off).
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

MUTEX_NAME = "Local\\DbDMapScout.SingleInstance"
IS_WIN = sys.platform == "win32"


def start_command(root: str) -> str:
    """cmd line that runs start.bat minimised; cmd /c strips the outer quotes of ""…""."""
    bat = os.path.join(os.path.abspath(root), "start.bat")
    comspec = os.environ.get("COMSPEC", "cmd.exe")
    return f'"{comspec}" /c start "" /min cmd /c ""{bat}""'


def helper_args(python: str | None = None, update: bool = True) -> list:
    return [python or sys.executable, "-m", "dbdmapscout", "--restart"] + ([] if update else ["--no-update"])


def spawn_helper(root: str, update: bool = True) -> bool:
    """Called by the program right before it quits."""
    if not IS_WIN:
        return False
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(helper_args(update=update), cwd=root, creationflags=flags, close_fds=True)
    return True


def _program_running(name: str = MUTEX_NAME) -> bool:
    import ctypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenMutexW.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p]
    k32.OpenMutexW.restype = ctypes.c_void_p
    h = k32.OpenMutexW(0x00100000, False, name)                # SYNCHRONIZE
    if not h:
        return ctypes.get_last_error() == 5    # access denied: it exists, owned by a copy with more rights
    k32.CloseHandle(ctypes.c_void_p(h))
    return True


def wait_and_start(root: str, timeout: float = 30.0, running=None, run=None, update: bool = True) -> bool:
    """Helper process: wait for the program to end, then run start.bat. ``running``/``run`` for tests.
    ``update`` False: a plain restart (e.g. Tk ↔ Qt window) – start.bat's update follows the user's setting."""
    running = running or _program_running
    deadline = time.time() + timeout
    while running():
        if time.time() > deadline:
            return False                                       # still running: do not start a second copy
        time.sleep(0.3)
    env = dict(os.environ, DBDMS_FORCE_UPDATE="1") if update else dict(os.environ)
    if not update:
        env.pop("DBDMS_FORCE_UPDATE", None)
    env.pop("DBDMS_UPDATED", None)       # left by start.bat after an earlier update: would skip this one
    run = run or (lambda cmd, env: subprocess.Popen(cmd, cwd=root, env=env,
                                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)))
    run(start_command(root), env)
    return True
