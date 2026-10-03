"""System-wide hotkeys via RegisterHotKey (Windows only, no extra packages)."""
from __future__ import annotations

import ctypes
import sys
import threading

from .i18n import _

IS_WIN = sys.platform == "win32"

MODS = {"alt": 0x0001, "ctrl": 0x0002, "control": 0x0002, "strg": 0x0002,
        "shift": 0x0004, "win": 0x0008}
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
WM_APP_GAME = 0x8001              # WM_APP + 1: DBD came to the front / went to the back

VK = {
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "pageup": 0x21, "pagedown": 0x22, "end": 0x23, "home": 0x24,
    "insert": 0x2D, "delete": 0x2E, "space": 0x20, "tab": 0x09,
    "plus": 0xBB, "minus": 0xBD, "comma": 0xBC, "period": 0xBE,
    "numpadplus": 0x6B, "numpadminus": 0x6D, "pause": 0x13, "scrolllock": 0x91,
}
VK.update({f"f{i}": 0x6F + i for i in range(1, 25)})
VK.update({f"numpad{i}": 0x60 + i for i in range(10)})

# keys that may stand alone (no Ctrl/Alt) – registered only while DBD is the active window, so every other
# program keeps them; DBD itself no longer gets them. Letters, digits, space: never alone (DBD needs them).
SOLO_KEYS = ({f"f{i}" for i in range(1, 13)} | {f"numpad{i}" for i in range(10)}
             | {"numpadplus", "numpadminus", "pause", "scrolllock", "insert", "home", "end", "pageup", "pagedown"})


def game_only(combo: str) -> bool:
    """A single key like F5 or Numpad 1: active only while DBD is in front (F13–F24 stay always on)."""
    parts = [p.strip().lower() for p in (combo or "").split("+") if p.strip()]
    return len(parts) == 1 and parts[0] in SOLO_KEYS


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


# Tk keysym -> our key names (for recording a hotkey by pressing it)
_TK_KEYS = {"Left": "left", "Right": "right", "Up": "up", "Down": "down", "Prior": "pageup", "Next": "pagedown",
            "Home": "home", "End": "end", "Insert": "insert", "Delete": "delete", "space": "space",
            "Tab": "tab", "plus": "plus", "minus": "minus", "comma": "comma", "period": "period",
            "KP_Add": "numpadplus", "KP_Subtract": "numpadminus", "Pause": "pause", "Scroll_Lock": "scrolllock"}
_TK_KEYS.update({f"KP_{i}": f"numpad{i}" for i in range(10)})
_TK_MODS = {"Control_L": "ctrl", "Control_R": "ctrl", "Alt_L": "alt", "Alt_R": "alt",
            "Shift_L": "shift", "Shift_R": "shift"}


def modifier_name(keysym: str):
    """'Control_L' -> 'ctrl' (None if not a modifier we use)."""
    return _TK_MODS.get(keysym)


_VK_NAME = {v: k for k, v in VK.items()}


def _key_from_vk(vk):
    """Windows virtual-key code (Tk's event.keycode on Windows) -> our key name; layout independent."""
    if vk is None:
        return None
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
        return chr(vk).lower()
    return _VK_NAME.get(vk)


def combo_from_keys(mods, keysym: str, keycode=None):
    """Held modifiers + pressed key (Tk keysym, Windows keycode) -> ('ctrl+alt+m', None) or (None, reason).

    A global hotkey swallows its keys in every program, DBD included – so letters, digits and the
    like need Ctrl or Alt (Shift alone would steal capital letters in the chat). F-keys may use
    any modifier; F13–F24 (no normal keyboard has them) may stand alone, and so may the SOLO_KEYS
    (F1–F12, numpad, Pause …), which are only registered while DBD is the active window."""
    ks = keysym or ""
    if ks in _TK_MODS:
        return None, None                                # still holding modifiers
    vk_key = _key_from_vk(keycode)
    if vk_key and vk_key.startswith("numpad"):
        key = vk_key                                     # Tk on Windows may call numpad 1 just "1"
    elif len(ks) == 1 and ks.isalnum():
        key = ks.lower()
    elif ks[:1] == "F" and ks[1:].isdigit() and 1 <= int(ks[1:]) <= 24:
        key = ks.lower()
    else:
        key = _TK_KEYS.get(ks) or vk_key                  # e.g. Shift+1 gives keysym "exclam"
    if key is None:
        return None, _("Taste „{key}“ geht nicht als Hotkey", key=ks)
    order = [m for m in ("ctrl", "alt", "shift") if m in mods]
    is_f = key.startswith("f") and key[1:].isdigit()
    if not order and key in SOLO_KEYS:
        parse(key)
        return key, None                                  # game_only(): only while DBD is in front
    if not order and not (is_f and int(key[1:]) >= 13):
        return None, _("Bitte mit Strg und/oder Alt kombinieren")
    if not is_f and not ({"ctrl", "alt"} & set(order)):
        return None, _("Bitte mit Strg und/oder Alt kombinieren")
    combo = "+".join(order + [key])
    parse(combo)                                          # must be registrable
    return combo, None


def pretty(combo: str) -> str:
    ctrl = _("Strg")
    names = {"ctrl": ctrl, "control": ctrl, "strg": ctrl, "alt": "Alt", "shift": "Shift", "win": "Win",
             "left": "←", "right": "→", "up": "↑", "down": "↓", "pageup": _("Bild↑"), "pagedown": _("Bild↓"),
             "insert": _("Einfg"), "home": _("Pos1"), "end": _("Ende"), "scrolllock": _("Rollen"),
             "pause": "Pause", "numpadplus": "Num +", "numpadminus": "Num −"}
    names.update({f"numpad{i}": f"Num {i}" for i in range(10)})
    return "+".join(names.get(p.lower(), p.upper()) for p in combo.split("+"))


class HotkeyThread(threading.Thread):
    def __init__(self, bindings: dict, callback):
        super().__init__(daemon=True, name="hotkeys")
        self.bindings = dict(bindings)
        self.callback = callback
        self.failed = []                  # (name, combo, reason)
        self.on_failed = None             # callback(name, combo, reason): a single key failed when DBD came up
        self.ready = threading.Event()
        self._tid = None
        self._game = False                # wanted: DBD is the active window (single keys registered)
        self._stop_req = False

    def set_game_active(self, on: bool):
        """DBD came to the front / went to the back: (un)register the single-key hotkeys (any thread)."""
        on = bool(on)
        if on == self._game:
            return
        self._game = on
        if IS_WIN and self._tid:
            from ctypes import wintypes
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            user32.PostThreadMessageW(self._tid, WM_APP_GAME, 0, 0)

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
        user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT,
                                        wintypes.UINT]
        kernel32.GetCurrentThreadId.restype = wintypes.DWORD
        ids = {}
        solo = {}                         # id -> (name, mods, vk, combo): only while DBD is in front
        told = set()
        for i, (name, combo) in enumerate(self.bindings.items(), start=1):
            if not combo:
                continue
            try:
                mods, vk = parse(combo)
            except ValueError as e:
                self.failed.append((name, combo, str(e)))
                continue
            if game_only(combo):
                solo[i] = (name, mods, vk, combo)
            elif user32.RegisterHotKey(None, i, mods | MOD_NOREPEAT, vk):
                ids[i] = name
            else:
                self.failed.append((name, combo, _("schon von einem anderen Programm belegt")))
        user32.PeekMessageW(ctypes.byref(wintypes.MSG()), None, 0, 0, 0)    # make sure the queue exists
        self._tid = kernel32.GetCurrentThreadId()     # from now on set_game_active()/stop() reach this loop
        solo_on = False
        if self._stop_req:                            # stop() came before the loop could hear it
            for i in ids:
                user32.UnregisterHotKey(None, i)
            self.ready.set()
            return

        def apply(on):
            nonlocal solo_on
            if on == solo_on:
                return
            solo_on = on
            for i, (name, mods, vk, combo) in solo.items():
                if not on:
                    if ids.pop(i, None) is not None:
                        user32.UnregisterHotKey(None, i)
                elif user32.RegisterHotKey(None, i, mods | MOD_NOREPEAT, vk):
                    ids[i] = name
                elif name not in told:
                    told.add(name)
                    why = _("schon von einem anderen Programm belegt")
                    self.failed.append((name, combo, why))
                    if self.on_failed and self.ready.is_set():     # before that: in .failed for the report
                        self.on_failed(name, combo, why)

        apply(self._game)
        self.ready.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_APP_GAME:
                apply(self._game)
            elif msg.message == WM_HOTKEY and msg.wParam in ids:
                try:
                    self.callback(ids[msg.wParam])
                except Exception:
                    pass
        for i in ids:
            user32.UnregisterHotKey(None, i)

    def stop(self):
        self._stop_req = True
        if IS_WIN and self._tid:
            from ctypes import wintypes
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
