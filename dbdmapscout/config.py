"""User settings (settings.json next to the program)."""
from __future__ import annotations

import copy
import json
import os

SETTINGS_VERSION = 3

DEFAULTS = {
    "settings_version": SETTINGS_VERSION,
    # languages the game may show map names in (en, de, fr, es, es-MX, it, pl, pt-BR, tr)
    "languages": ["en", "de"],
    "auto_detect": True,
    "scans_per_second": 5,
    "hide_after_match": True,
    "pause_in_menus": True,             # hide the overlay while a DBD menu is open (mouse pointer visible)
    "window_capture": True,             # DBD in the background: picture via Windows Graphics Capture (like OBS)
    "show_connection": False,           # Server tab: show the connected game server (elevated netwatch helper)
    "overlay": {
        "anchor": "auto",              # auto | top-left | top-right | bottom-left | bottom-right | custom
                                        # auto = in the black bar left of a 16:9 picture, else top-left
        "native_window": True,          # Windows: native layered window (False = Tk window)
        "pos_x": 0.0,                   # anchor=custom: 0 = left edge, 1 = right edge of the free space
        "pos_y": 0.0,                   # anchor=custom: 0 = top, 1 = bottom
        "margin": 0.012,                # distance to the window edge (fraction of the game height)
        "height": 0.36,                 # overlay height as a fraction of the game height
        "opacity": 0.85,
        "only_when_game_focused": True,
        "show_caption": False,          # the map pictures already carry their name
        "show_timer": True,             # round timer below the map (map shown -> map gone)
        "show_server": True,            # connected server region below the timer (needs the Server tab option)
        "transparent": True,            # transparent area around the map (off = dark rectangle)
    },
    "hotkeys": {
        "toggle_overlay": "ctrl+alt+m",
        "next_variant": "ctrl+alt+v",
        "scan_now": "ctrl+alt+s",
        "next_map": "ctrl+alt+right",
        "prev_map": "ctrl+alt+left",
        "bigger": "ctrl+alt+up",
        "smaller": "ctrl+alt+down",
        "edit_position": "ctrl+alt+p",
    },
    "dark_mode": True,
    "window_geometry": "",
    "log_categories": ["Erkennung", "Overlay", "System", "Fehler"],
    "ocr_threads": 2,
    "save_debug_images": False,
    "user_aliases": {},                 # own assignments of unknown banner texts: {map_id: [text, ...]}
}


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


class Settings:
    def __init__(self, path: str):
        self.path = path
        self.data = copy.deepcopy(DEFAULTS)
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    raw = json.load(fh)
                self.data = _merge(DEFAULTS, raw)
                ov = self.data["overlay"]
                if raw.get("settings_version", 1) < 2:                # defaults changed in 1.1
                    if ov.get("anchor") == "top-left":
                        ov["anchor"] = "auto"
                    ov["show_caption"] = False
                if raw.get("settings_version", 1) < 3:                # 1.2: position sliders
                    ov["pos_x"] = min(1.0, max(0.0, float(ov.pop("custom_x", 0.0))))
                    ov["pos_y"] = min(1.0, max(0.0, float(ov.pop("custom_y", 0.0))))
                self.data["settings_version"] = SETTINGS_VERSION
            except (OSError, ValueError, AttributeError):
                pass  # broken file -> defaults, will be rewritten on save

    def __getitem__(self, key):
        return self.data[key]

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

    def save(self):
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
        except OSError:
            pass
