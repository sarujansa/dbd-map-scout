"""System-wide hotkeys via RegisterHotKey (Windows only, no extra packages)."""
from __future__ import annotations

import ctypes
import sys
import threading

IS_WIN = sys.platform == "win32"

MODS = {"alt": 0x0001, "ctrl": 0x0002, "control": 0x0002, "strg": 0x0002,
        "shift": 0x0004, "win": 0x0008}
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

VK = {
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "pageup": 0x21, "pagedown": 0x22, "end": 0x23, "home": 0x24,
    "insert": 0x2D, "delete": 0x2E, "space": 0x20, "tab": 0x09,
    "plus": 0xBB, "minus": 0xBD, "comma": 0xBC, "period": 0xBE,
    "numpadplus": 0x6B, "numpadminus": 0x6D, "pause": 0x13, "scrolllock": 0x91,
}
VK.update({f"f{i}": 0x6F + i for i in range(1, 25)})
VK.update({f"numpad{i}": 0x60 + i for i in range(10)})


def parse(combo: str):
    """'ctrl+alt+m' -> (modifiers, virtual key). Raises ValueError."""
    mods, vk = 0, None
    for part in [p.strip().lower() for p in combo.replace(" ", "").split("+") if p.strip()]:
        if part in MODS:
            mods |= MODS[part]
        elif part in VK:
            vk = VK[part]
        elif len(part) == 1 and (part.isalpha() or part.isdigit()):
            vk = ord(part.upper())
        else:
            raise ValueError(f"unbekannte Taste '{part}' in '{combo}'")
    if vk is None:
        raise ValueError(f"keine Taste in '{combo}'")
    return mods, vk


def pretty(combo: str) -> str:
    names = {"ctrl": "Strg", "control": "Strg", "strg": "Strg", "alt": "Alt", "shift": "Shift", "win": "Win",
             "left": "←", "right": "→", "up": "↑", "down": "↓"}
    return "+".join(names.get(p.lower(), p.upper()) for p in combo.split("+"))


class HotkeyThread(threading.Thread):
    def __init__(self, bindings: dict, callback):
        super().__init__(daemon=True, name="hotkeys")
        self.bindings = dict(bindings)
        self.callback = callback
        self.failed = []                  # (name, combo, reason)
        self.ready = threading.Event()
        self._tid = None

    def run(self):
        if not IS_WIN:
            self.ready.set()
            return
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        user32.RegisterHotKey.restype = wintypes.BOOL
        user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        user32.GetMessageW.restype = ctypes.c_int
        kernel32.GetCurrentThreadId.restype = wintypes.DWORD
        self._tid = kernel32.GetCurrentThreadId()
        ids = {}
        for i, (name, combo) in enumerate(self.bindings.items(), start=1):
            if not combo:
                continue
            try:
                mods, vk = parse(combo)
            except ValueError as e:
                self.failed.append((name, combo, str(e)))
                continue
            if user32.RegisterHotKey(None, i, mods | MOD_NOREPEAT, vk):
                ids[i] = name
            else:
                self.failed.append((name, combo, "schon von einem anderen Programm belegt"))
        self.ready.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam in ids:
                try:
                    self.callback(ids[msg.wParam])
                except Exception:
                    pass
        for i in ids:
            user32.UnregisterHotKey(None, i)

    def stop(self):
        if IS_WIN and self._tid:
            from ctypes import wintypes
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
