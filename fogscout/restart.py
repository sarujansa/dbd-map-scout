"""Restart through start.bat after "Aktualisieren und neu starten".

The program starts a small helper (``python -m fogscout --restart``) and quits. The helper waits
until the program has really ended (its single-instance mutex is gone – so no package file is still
in use when pip updates it), then runs start.bat, which installs the update as on every start
(``DBDMS_FORCE_UPDATE=1``: also when "check for updates at start" is switched off).
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

MUTEX_NAME = "Local\\FogScout.SingleInstance"
SHOW_EVENT = "Local\\FogScout.Show"      # a second start asks the running copy to show its window (1.65.1)
# anyone of this session may set/wait for it – the running copy is often an administrator (autostart task)
SHOW_EVENT_SDDL = "D:(A;;0x1F0003;;;WD)S:(ML;;NW;;;LW)"
SHOW_ACK_S = 3.0                                # the running copy must take the request within this time
IS_WIN = sys.platform == "win32"
WAIT_S = 60.0                                   # the helper waits this long for the old copy to end


def start_command() -> str:
    """cmd line that runs start.bat minimised – run in the program folder (cwd). 1.8.45: the folder is not on
    the command line: cmd reads "&" in it as a second command and expands "%…%"."""
    comspec = os.environ.get("COMSPEC", "cmd.exe")
    return f'"{comspec}" /c start "" /min cmd /c .\\start.bat'


def helper_args(python: str | None = None, update: bool = True) -> list:
    return [python or sys.executable, "-m", "fogscout", "--restart"] + ([] if update else ["--no-update"])


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


def _kernel32():
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    k32.CreateEventW.restype = wintypes.HANDLE
    k32.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    k32.OpenEventW.restype = wintypes.HANDLE
    k32.SetEvent.argtypes = k32.ResetEvent.argtypes = k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k32.WaitForSingleObject.restype = wintypes.DWORD
    return k32


def show_event_create(name: str = SHOW_EVENT):
    """The running copy: a manual-reset event a second start sets (handle, or None)."""
    if not IS_WIN:
        return None
    import ctypes
    from ctypes import wintypes

    class SA(ctypes.Structure):
        _fields_ = [("nLength", wintypes.DWORD), ("lpSecurityDescriptor", ctypes.c_void_p),
                    ("bInheritHandle", wintypes.BOOL)]
    sd = ctypes.c_void_p()
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
    sa = None
    if adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(SHOW_EVENT_SDDL, 1, ctypes.byref(sd), None):
        sa = SA(ctypes.sizeof(SA), sd, False)
    h = _kernel32().CreateEventW(ctypes.byref(sa) if sa else None, True, False, name)
    return h or None


def show_requested(handle) -> bool:
    """The running copy, in its timer: True once when a second start asked for the window."""
    if not handle:
        return False
    k32 = _kernel32()
    if k32.WaitForSingleObject(handle, 0) != 0:      # WAIT_OBJECT_0
        return False
    k32.ResetEvent(handle)                           # taken: the asking copy sees it was answered
    return True


def ask_running_copy_to_show(name: str = SHOW_EVENT, wait: float = SHOW_ACK_S, sleep=time.sleep) -> bool:
    """A second start: ask the running copy to show its window. True when it took the request within ``wait``
    seconds (it is alive); False when there is none or it does not answer (hung) – then the caller says so."""
    if not IS_WIN:
        return False
    k32 = _kernel32()
    h = k32.OpenEventW(0x00100002, False, name)      # SYNCHRONIZE | EVENT_MODIFY_STATE
    if not h:
        return False
    try:
        try:                                         # let the running copy bring its window to the front
            import ctypes
            ctypes.windll.user32.AllowSetForegroundWindow(-1)
        except Exception:
            pass
        k32.SetEvent(h)
        deadline = time.time() + wait
        while time.time() < deadline:
            if k32.WaitForSingleObject(h, 0) != 0:   # reset by the running copy: it answered
                return True
            sleep(0.1)
        k32.ResetEvent(h)
        return False
    finally:
        k32.CloseHandle(h)


def wait_and_start(root: str, timeout: float = WAIT_S, running=None, run=None, update: bool = True,
                   stuck=None) -> bool:
    """Helper process: wait for the program to end, then run start.bat. ``running``/``run`` for tests.
    ``update`` False: a plain restart – start.bat's update follows the user's setting."""
    running = running or _program_running
    deadline = time.time() + timeout
    while running():
        if time.time() > deadline:                             # still running: never a second copy …
            (stuck or _stuck_message)()                        # … but say so instead of nothing at all
            return False
        time.sleep(0.3)
    env = dict(os.environ, DBDMS_FORCE_UPDATE="1") if update else dict(os.environ)
    if not update:
        env.pop("DBDMS_FORCE_UPDATE", None)
    env.pop("DBDMS_UPDATED", None)       # left by start.bat after an earlier update: would skip this one
    run = run or (lambda cmd, env: subprocess.Popen(cmd, cwd=root, env=env,
                                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)))
    run(start_command(), env)
    return True


def _stuck_message():
    """The old copy did not end (1.65.1, user: after an update the program did not come back)."""
    try:
        import ctypes
        from .i18n import _
        ctypes.windll.user32.MessageBoxW(None, _(
            "Fog Scout konnte nicht neu gestartet werden: Die alte Kopie läuft noch im Hintergrund.\n\n"
            "Im Task-Manager unter „Details“ „pythonw.exe“ (Fog Scout) beenden und das Programm neu "
            "starten."), "Fog Scout", 0x30)
    except Exception:
        pass
