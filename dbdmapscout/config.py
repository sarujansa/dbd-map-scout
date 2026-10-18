"""User settings (settings.json next to the program)."""
from __future__ import annotations

import copy
import json
import os

HUD_SHOWN = ("above", "left", "right", "custom")    # settings.sysinfo values that show the system values
SETTINGS_VERSION = 8

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
        "native_window": True,          # Windows: native layered window (False = Qt window)
        "style": "classic",             # 1.3: look of the cards – classic | glass | chips | line (skin.py)
        "pos_x": 0.0,                   # anchor=custom: 0 = left edge, 1 = right edge of the free space
        "pos_y": 0.0,                   # anchor=custom: 0 = top, 1 = bottom
        "margin": 0.012,                # distance to the window edge (fraction of the game height)
        "height": 0.36,                 # overlay height as a fraction of the game height
        "opacity": 0.85,                # of the map (+ its lines); the other cards have their own (1.2.7)
        "hud_opacity": 0.85,
        "today_opacity": 0.85,
        "media_opacity": 0.85,
        "only_when_game_focused": True,
        "show_caption": False,          # the map pictures already carry their name
        "show_timer": True,             # round timer below the map (map shown -> map gone)
        "show_waiting": True,           # no map on screen: small card "Warte auf Map" + lobby state
        "show_server": True,            # connected server region below the timer (needs the Server tab option)
        "transparent": True,            # transparent area around the map (off = dark rectangle)
        "keep_in_bar": True,
        "grow_past_bar": False,         # a map bigger than the bar may reach into the game picture (1.65.4)            # ultrawide: shrink/move the map so it stays inside the black bar
        "map_heights": {},              # map id -> own size (hotkeys / mouse wheel with that map on display)
        "map_rotations": {},            # map id -> map turned clockwise by 90/180/270° (button / hotkey)
        "floor_auto": True,             # maps with floors (Midwich): all one below the other (False: bottom only)
        "show_record": True,            # own record on the map below the timer (official match data)
        "show_map": True,               # off: overlay shows only timer, server and ping
        "show_media": True,             # "Läuft gerade": music of the Windows media controls (1.64)
        "media_pos": "bottom_right",    # its own window: below / bottom_right / bottom_left / custom (1.64.7)
        "media_xy": [1.0, 1.0],         # custom: share of the free room in the DBD window (dragged in edit mode)
        "media_progress": True,         # music card: how far the song is (bar + times, 1.64.7)
        "map_style": "classic",         # callout maps: classic = as supplied / dark = see-through floor (1.66)
        "media_style": "big",           # music card: big = cover on top (1.64.7) / compact = cover left (1.64)
        "media_scale": 1.0,             # size of the music card (slider 60–200 %)
        "media_cover": True,            # album cover left of title and artist
        "media_videos": True,           # 1.8.4: a video (YouTube, Twitch …) shows too ("▶ Titel"); off = music only
        "media_next_pos": "below",      # 1.8: the Spotify queue below the song / right of it
        "media_next_n": 3,              # … how many coming tracks (1–5)
        "map_backdrop": False,          # dark area with rounded corners behind the map and its lines (1.2.4)
        "hud_backdrop": False,          # … behind the system values / "today"
        "hud_rows": {"cpu": True, "gpu": True, "spot": True, "vram": True, "ram": True},   # rows shown (1.2.8)
        "stack_gap": 8,                 # px at 1440p between stacked cards / above the map (1.2.8)
        "bar_align": "centre",
        "bar_limits_on": False,         # 1.8.14: limiter lines at the top/bottom of the black bars
        "bar_limits": [0.08, 0.08, 0.08, 0.08],   # left top, left bottom, right top, right bottom (share of the height)
        "bar_limits_same": False,       # 1.8.17: each bar has lines of its own (on: dragging one moves the other too)          # left / centre / right: cards and the map "auto" in the black bar (1.2.8)
        "media_accent": True,           # music card: progress bar in the cover's main colour (1.2.4)
        "media_remaining": True,        # … time left ("−1:46") right of the bar instead of the length
        "media_backdrop": True,         # … on a dark half-transparent area
        "media_fade": True,             # … fades in/out (also on a new song)
        "fade": True,                   # map, system values and "today" fade in/out too (1.2.9)
        "text_scale": 1.0,              # name/timer/info lines of the map, independent of its size (1.65)
        "hud_scale": 1.0,               # size of the system values / "today" (60–200 %, 1.64.9)
        "show_today": True,             # block "today" (rounds, play time, kills/escaped, clock; 1.62)
        "today_pos": "below",           # 1.2.6: its own element – below the system values / bottom_right /
        "today_xy": [1.0, 0.0],         #   bottom_left / custom (centre of the card as a share of the window)
        "today_scale": 1.0,             # size of "today" (slider 60–200 %)
        "today_backdrop": False,        # dark area behind "today"
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
        "rotate_map": "ctrl+alt+r",
        "next_floor": "ctrl+alt+f",     # not E: Ctrl+Alt+E is AltGr+E = € on German keyboards
        "reject_map": "ctrl+alt+x",
        "mark_clip": "f8",              # 1.4.2: a mark in the running OBS recording (single key: only while DBD is in front)
    },
    "overlay_on": True,               # 1.8.18: master switch – off hides every overlay window, detection goes on
    "ui_language": "auto",            # auto (Windows language) | de | en
    "dark_mode": True,
    "color_theme": "gold",              # control window: qt_theme.THEMES (accent colour)
    "accent_custom": "#2f8fe0",         # control window: own accent (color_theme "custom", qt_theme.derive_accent)
    "oled_black": False,                # control window: true black instead of the dark greys (qt_theme.OLED)
    "ui_zoom": 1.0,                     # control window: font size factor (qt_theme.ZOOMS)
    "qt_geometry": "",                  # control window: QWidget.saveGeometry() as base64
    "card_order": {},
    "tab_order": {},                    # 1.7.6: {page: {tabs id: [tab ids]}} – the user's order of the tab rows
    "nav_order": [],                    # 1.7.6: page keys in the user's order of the navigation
    "hidden_columns": {},             # 1.3.6: {"col|col|…" of a table: [column ids]} hidden by a right-click
    "layout_per_size": True,            # overlay: place and size of every element per DBD window size (1.65)
    "layouts": {},                      # {"3440x1440": layoutmem.snapshot(...)}
    "layout_key": "",                   # the window size the current layout belongs to                   # control window: own order of the cards {page: {run: [card ids]}}
    "log_categories": ["Erkennung", "Overlay", "System", "Fehler"],
    "ocr_threads": 2,
    "save_debug_images": False,
    "show_advanced": False,             # detection tab: technical options unfolded
    "tray": True,                       # minimise into the notification area
    "autostart": True,                  # start with Windows (logon task, set up as admin) unless switched off
    "lobby_notify": True,               # sound + notification when a lobby was found
    "lobby_remind": True,               # … and when its countdown runs out while READY is not pressed
    "notify_background_only": True,     # only while DBD is not the active window
    "auto_update": True,                # start.bat: pull the newest state from GitHub before starting
    "user_aliases": {},                 # own assignments of unknown banner texts: {map_id: [text, ...]}
    "welcome_seen": False,              # the setup assistant of the first start was finished or skipped
    "killer_aliases": {},               # killer names as read (skins, new killers): {fold(name): "The Nurse"}
    "official_open_after_dbd": False,   # open stats.deadbydaylight.com once DBD was closed (userscript saves the matches)
    "official_dir": "",                 # where the userscript's files land ("" = the Windows download folder)
    "official_notify": True,
    "farming_crossplay": True,          # 1.2.20: a round whose lobby showed cross-play off is a farming round
    "farming_region": "ap-southeast-1",  # … and every round on this server region ("" = none)
    "farming_ignored": [],              # 1.6.1: rounds (repr of the start) not to offer as farming again
    "rec_on": False,                    # 1.4: round recordings with OBS (obs-websocket on this PC)
    "rec_port": 4455,
    "rec_password": "",
    "rec_volume": "",                   # the recording folder's drive (volume GUID) + path on it + last path
    "rec_rel": "",
    "rec_folder": "",
    "rec_limit_gb": 0,                  # 0 = the whole drive (older recordings go when it fills up)
    "rec_pre": False,                   # save OBS's replay buffer at the banner (1.5.5: off – it holds the lobby)
    "rec_tail_s": 5,                    # 1.4.1: seconds recorded after the detected end (result screen)
    "rec_buffer_auto": True,            # 1.4.1: start/stop OBS's replay buffer with DBD
    "rec_merge": False,                 # 1.4.2: pre-roll + round → one file (1.5.5: off – played too fast at the user's PC)
    "rec_farming_days": 7,              # 1.8.23: farming recordings go after this many days (0 = never)
    "rec_farming_dir": True,            # 1.5.3: recordings of farming rounds go into the subfolder "Farming"
    "rec_early": True,                  # 1.6: start at the end of the loading screen (spawn), the banner names it
    "rec_instant": True,                # 1.6: F8 also saves the last seconds of the replay buffer as a clip
    "rec_clip_s": 30,
    "rec_clip_notify": True,            # 1.8.13: a short notification for the F8 clip (also while DBD is in front)
    "rec_audio": True,                  # 1.6: set OBS's audio sources when DBD starts (user: only DBD + Discord)
    "rec_audio_dbd": True,
    "rec_audio_discord": True,
    "rec_audio_desktop": False,
    "rec_audio_mic": False,
    "rec_tracks": True,                 # 1.8.6: every sound source on its own OBS track (1 all, 2 game, 3 Discord, 4 mic)
    "rec_clip_sources": ["dbd", "mic"], # 1.8.6: what the F8 instant clip keeps when the buffer file has the tracks
    "clip_mode": "copy",                # 1.5.1: clip editor – "copy" (key frames, fast) / "exact" (re-encoded)
    "clip_sound": True,                 # 1.5.1: clip editor plays the sound while previewing (Windows)
    "clip_target_mb": 10,               # 1.6.1: clip editor "Für Discord" – stays under this many MB
    "clip_censor_on": False,            # 1.7.2: clip editor hides the censor boxes when saving
    "clip_censor_style": "pixel",       # pixel | blur | black
    "clip_censor_boxes": [],            # [[x, y, w, h] …] as fractions of the picture (the names stay put)
    "clip_mix_on": {"dbd": True, "discord": True, "mic": True},     # 1.8.6: clip editor sound mix – source on/off
    "clip_mix_vol": {"dbd": 100, "discord": 100, "mic": 100},       # and its level in percent (MIX_MAX 150)
    "discord_on": False,                # 1.7: Rich Presence over the local Discord client (user's pick)
    "discord_client_id": "",            # the Application-ID the user registered in Discord's developer portal
    "discord_killer": True,             # name the killer in the status
    "discord_lobby": True,              # also show lobby / search / menu (else only the match)
    "spotify_on": False,                # 1.8: "Als nächstes" from the Spotify Web API on the music card (user's pick)
    "spotify_client_id": "",            # the Client-ID of the app the user registered in Spotify's dashboard
    "spotify_token": "",                # the refresh token, DPAPI-protected (spotify.protect), PC-specific
    "sysinfo": "right",                 # system values at the top of a black bar: off | left | right | custom
    "sysinfo_pos": [1.0, 0.0],          # sysinfo = custom: 0..1 of the free space in the DBD window (x, y)
}


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def export_settings(data: dict, path: str) -> None:
    """Backup of all settings (hotkeys, sizes/rotations per map, own map assignments …)."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


# per-PC values that must not come along from a backup (other folder / other machine)
LOCAL_KEYS = ("setup_version", "setup_root", "qt_geometry", "official_dir", "layouts", "layout_key",
              "rec_volume", "rec_rel", "rec_folder", "rec_password", "spotify_token")


def reset_data(current: dict) -> dict:
    """1.2.19 ("Alle Einstellungen zurücksetzen"): the defaults, with the PC-specific values (LOCAL_KEYS) of
    ``current`` kept – the window geometry, the setup marker, the download folder; the layouts per window size
    go with the layout (they are layout). ``welcome_seen`` stays: the assistant is not forced again."""
    data = copy.deepcopy(DEFAULTS)
    for k in ("setup_version", "setup_root", "qt_geometry", "official_dir"):
        if k in current:
            data[k] = copy.deepcopy(current[k])
    if current.get("welcome_seen"):
        data["welcome_seen"] = True
    return data


def read_backup(path: str, current: dict) -> dict:
    """Settings from a backup file, merged over the defaults (keys missing in older backups get their
    default); ValueError if it is no settings file of this program."""
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError) as e:
        raise ValueError(str(e)) from e
    if not isinstance(raw, dict) or not isinstance(raw.get("overlay"), dict) or "hotkeys" not in raw:
        raise ValueError("no DbD Map Scout settings")
    for k in LOCAL_KEYS:
        raw.pop(k, None)
        if k in current:
            raw[k] = current[k]
    merged = _merge(DEFAULTS, raw)
    merged["settings_version"] = SETTINGS_VERSION
    return merged


class Settings:
    def __init__(self, path: str):
        self.path = path
        self.frozen = False             # after importing a backup: nothing is written until the restart
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
                if raw.get("settings_version", 1) < 4 and ov.get("media_pos") == "below":
                    ov["media_pos"] = "bottom_right"  # 1.64.7: the music card stands on its own (user's wish)
                if raw.get("settings_version", 1) < 5:                # 1.2.6: "today" is an element of its own
                    if self.data.pop("today_side", None) == "custom" and raw.get("sysinfo") not in HUD_SHOWN:
                        ov["today_pos"] = "custom"                    # it stood alone at its own place
                        fx, fy = (self.data.get("sysinfo_pos") or [1.0, 0.0])[:2]
                        ov["today_xy"] = [float(fx), float(fy)]
                if raw.get("settings_version", 1) < 6:                # 1.2.7: opacity per card, cards stack
                    for key in ("hud_opacity", "today_opacity", "media_opacity"):
                        ov[key] = ov.get("opacity", 0.85)             # as before: one opacity for everything
                    if ov.get("media_pos") == "below" and ov.get("today_pos", "below") == "below" \
                            and ov.get("show_today", True):
                        ov["media_pos"] = "under_today"               # 1.2.6 hung the music below "today"
                if raw.get("settings_version", 1) < 7:                # 1.5.5 (user: "no lobby in the recording",
                    self.data["rec_pre"] = False                      # joined files played too fast in the round)
                    self.data["rec_merge"] = False
                if raw.get("settings_version", 1) < 8:                # 1.8.17 (user: left and right lines of their own)
                    ov["bar_limits_same"] = False
                if self.data.get("color_theme") == "oled":            # 1.62.0: OLED was a theme of its own
                    self.data["color_theme"], self.data["oled_black"] = "gold", True
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
        if self.frozen:
            return
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
        except OSError:
            pass
