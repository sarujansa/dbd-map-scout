"""Own taskbar identity (Windows AppUserModelID).

Without it Windows files the control window under the executable that hosts it (.venv\\Scripts\\pythonw.exe):
the taskbar button shows the Python icon and never joins a pinned desktop shortcut. With an explicit ID the
button shows the window's own icon, and the desktop shortcut carries the same ID, so a pinned shortcut and
the running program are one taskbar button.

1.9.1 (user's screenshot after the rename: the taskbar showed the Python icon): with an explicit ID the taskbar takes
the button's icon from a Start menu shortcut that carries the same ID – and from the hosting executable while there
is none (the shortcuts are made in a thread after the window, or never without administrator rights). The window's
own relaunch properties (``set_window_relaunch``: icon, display name, command) tell the taskbar what to show and
what to pin without any shortcut – the documented way for windows hosted by a shared executable.
"""
from __future__ import annotations

import ctypes
import os
import sys
import uuid

APP_ID = "FogScout.App"
IS_WIN = sys.platform == "win32"

GPS_READWRITE = 2
VT_LPWSTR = 31
IID_IPROPERTYSTORE = "{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}"
PKEY_APPUSERMODEL_ID = ("{9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}", 5)
PKEY_RELAUNCH_COMMAND = ("{9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}", 2)       # 1.9.1: System.AppUserModel.Relaunch…
PKEY_RELAUNCH_ICON = ("{9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}", 3)
PKEY_RELAUNCH_NAME = ("{9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}", 4)


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16), ("Data3", ctypes.c_uint16),
                ("Data4", ctypes.c_ubyte * 8)]


def _guid(text: str) -> _GUID:
    return _GUID.from_buffer_copy(uuid.UUID(text).bytes_le)


class _PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", _GUID), ("pid", ctypes.c_uint32)]


class _PROPVARIANT(ctypes.Structure):             # only the VT_LPWSTR case; size as in the SDK (16 / 24 bytes)
    _fields_ = [("vt", ctypes.c_ushort), ("r1", ctypes.c_ushort), ("r2", ctypes.c_ushort),
                ("r3", ctypes.c_ushort), ("pwszVal", ctypes.c_void_p), ("pad", ctypes.c_void_p)]


def start_menu_link(name: str = "Fog Scout.lnk") -> str:
    """Where the setup puts the Start menu shortcut (the one Windows pins for the running window)."""
    return os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", name)


def set_process_app_id() -> bool:
    """Call before the first window is created."""
    if not IS_WIN:
        return False
    try:
        f = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        f.argtypes = [ctypes.c_wchar_p]
        f.restype = ctypes.c_long
        return f(APP_ID) == 0
    except (AttributeError, OSError):
        return False


def process_app_id() -> str | None:
    if not IS_WIN:
        return None
    p = ctypes.c_wchar_p()
    try:
        f = ctypes.windll.shell32.GetCurrentProcessExplicitAppUserModelID
        f.argtypes = [ctypes.POINTER(ctypes.c_wchar_p)]
        f.restype = ctypes.c_long
        if f(ctypes.byref(p)) != 0:
            return None
        value = p.value
        ctypes.windll.ole32.CoTaskMemFree(p)
        return value
    except (AttributeError, OSError):
        return None


def _with_store(path: str, write: bool, use):
    """Open the property store of a file (here: a .lnk), run use(store, vtable), release it."""
    ole32 = ctypes.windll.ole32
    ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    ole32.CoInitializeEx.restype = ctypes.c_long
    inited = ole32.CoInitializeEx(None, 2) in (0, 1)          # S_OK / S_FALSE: must be balanced
    try:
        f = ctypes.windll.shell32.SHGetPropertyStoreFromParsingName
        f.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(_GUID),
                      ctypes.POINTER(ctypes.c_void_p)]
        f.restype = ctypes.c_long
        store = ctypes.c_void_p()
        iid = _guid(IID_IPROPERTYSTORE)
        if f(path, None, GPS_READWRITE if write else 0, ctypes.byref(iid), ctypes.byref(store)) != 0:
            return None
        vtbl = ctypes.cast(store, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        try:
            return use(store, vtbl)
        finally:
            ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl[2])(store)            # Release
    finally:
        if inited:
            ole32.CoUninitialize()


def _key(pkey=PKEY_APPUSERMODEL_ID) -> _PROPERTYKEY:
    return _PROPERTYKEY(_guid(pkey[0]), pkey[1])


def _with_window_store(hwnd: int, use):
    """Open the property store of a window (SHGetPropertyStoreForWindow), run use(store, vtable), release it."""
    ole32 = ctypes.windll.ole32
    ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    ole32.CoInitializeEx.restype = ctypes.c_long
    inited = ole32.CoInitializeEx(None, 2) in (0, 1)          # S_OK / S_FALSE: must be balanced (Qt: already OLE)
    try:
        f = ctypes.windll.shell32.SHGetPropertyStoreForWindow
        f.argtypes = [ctypes.c_void_p, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p)]
        f.restype = ctypes.c_long
        store = ctypes.c_void_p()
        iid = _guid(IID_IPROPERTYSTORE)
        if f(ctypes.c_void_p(int(hwnd)), ctypes.byref(iid), ctypes.byref(store)) != 0:
            return None
        vtbl = ctypes.cast(store, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        try:
            return use(store, vtbl)
        finally:
            ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl[2])(store)            # Release
    finally:
        if inited:
            ole32.CoUninitialize()


def set_window_relaunch(hwnd: int, command: str, icon: str, name: str) -> bool:
    """1.9.1: the taskbar's picture of this window – its icon (``icon`` = path to an .ico, ",0" appended),
    display name and the command a pinned button runs – independent of any shortcut. Before the window is shown.
    False if that did not work (then the Start menu shortcut, once made, still does it)."""
    if not IS_WIN or not hwnd:
        return False
    values = [(PKEY_RELAUNCH_COMMAND, command), (PKEY_RELAUNCH_ICON, icon + ",0" if icon else ""),
              (PKEY_RELAUNCH_NAME, name)]
    values = [(k, v) for k, v in values if v]
    texts = [ctypes.create_unicode_buffer(v) for _k, v in values]              # kept alive until Commit

    def use(store, vtbl):
        set_value = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(_PROPERTYKEY),
                                       ctypes.POINTER(_PROPVARIANT))(vtbl[6])
        commit = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(vtbl[7])
        for (pkey, _v), text in zip(values, texts):
            pv = _PROPVARIANT(vt=VT_LPWSTR, pwszVal=ctypes.cast(text, ctypes.c_void_p).value)
            key = _key(pkey)
            if set_value(store, ctypes.byref(key), ctypes.byref(pv)) != 0:
                return False
        return commit(store) == 0
    try:
        return bool(_with_window_store(hwnd, use))
    except (AttributeError, OSError):
        return False


def window_relaunch(hwnd: int):
    """(command, icon, name) stored on a window, each None when unset; None when the store cannot be read."""
    if not IS_WIN or not hwnd:
        return None

    def use(store, vtbl):
        get_value = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(_PROPERTYKEY),
                                       ctypes.POINTER(_PROPVARIANT))(vtbl[5])
        out = []
        for pkey in (PKEY_RELAUNCH_COMMAND, PKEY_RELAUNCH_ICON, PKEY_RELAUNCH_NAME):
            pv = _PROPVARIANT()
            key = _key(pkey)
            if get_value(store, ctypes.byref(key), ctypes.byref(pv)) != 0:
                out.append(None)
                continue
            out.append(ctypes.wstring_at(pv.pwszVal) if pv.vt == VT_LPWSTR and pv.pwszVal else None)
            ctypes.windll.ole32.PropVariantClear(ctypes.byref(pv))
        return tuple(out)
    try:
        return _with_window_store(hwnd, use)
    except (AttributeError, OSError):
        return None


def set_link_app_id(path: str, app_id: str = APP_ID) -> bool:
    """Give a shortcut (.lnk) the program's AppUserModelID. False if that did not work."""
    if not IS_WIN:
        return False
    text = ctypes.create_unicode_buffer(app_id)             # kept alive until Commit
    pv = _PROPVARIANT(vt=VT_LPWSTR, pwszVal=ctypes.cast(text, ctypes.c_void_p).value)
    key = _key()

    def use(store, vtbl):
        set_value = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(_PROPERTYKEY),
                                       ctypes.POINTER(_PROPVARIANT))(vtbl[6])
        commit = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(vtbl[7])
        return set_value(store, ctypes.byref(key), ctypes.byref(pv)) == 0 and commit(store) == 0
    try:
        return bool(_with_store(path, True, use))
    except (AttributeError, OSError):
        return False


def link_app_id(path: str) -> str | None:
    """AppUserModelID stored in a shortcut (None: none or unreadable)."""
    if not IS_WIN:
        return None
    key = _key()

    def use(store, vtbl):
        pv = _PROPVARIANT()
        get_value = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(_PROPERTYKEY),
                                       ctypes.POINTER(_PROPVARIANT))(vtbl[5])
        if get_value(store, ctypes.byref(key), ctypes.byref(pv)) != 0:
            return None
        value = ctypes.wstring_at(pv.pwszVal) if pv.vt == VT_LPWSTR and pv.pwszVal else None
        ctypes.windll.ole32.PropVariantClear(ctypes.byref(pv))
        return value
    try:
        return _with_store(path, False, use)
    except (AttributeError, OSError):
        return None
