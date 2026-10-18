"""System values (CPU/GPU temperature, load, VRAM, RAM) at the top of a black bar while a map is on screen.

Mixin of App (app.py) – the methods use App's attributes."""
from __future__ import annotations

import logging
import time

from . import history, layout, media, official, qt_theme, skin, spotify, sysinfo
from .capture import IS_WIN
from .i18n import N_, _
from .textnorm import fmt_duration

log = logging.getLogger("dbdmapscout")

HUD_SIDES = [("off", N_("Aus")), ("above", N_("Direkt über der Karte (wandert mit)")),
             ("left", N_("Links oben (über der Karte)")), ("right", N_("Rechts oben")),
             ("custom", N_("Eigene Position (mit der Maus verschieben)"))]
HUD_SHOWN = ("above", "left", "right", "custom")
BAR_ALIGNS = [("left", N_("Links")), ("centre", N_("Mittig")), ("right", N_("Rechts"))]     # 1.2.8
PRESET_LABELS = [("left", N_("Alles links")), ("right", N_("Alles rechts")),           # 1.2.9 (layoutmem.PRESETS)
                 ("spread", N_("Verteilt: Karte links, Werte rechts")),
                 ("standard", N_("Standard (wie ausgeliefert)"))]                         # 1.2.17 (config.DEFAULTS)
HUD_ROW_LABELS = [("cpu", N_("Zeile CPU (Temperatur, Last)")), ("gpu", N_("Zeile GPU (Temperatur, Last)")),
                  ("spot", N_("Zeile Hotspot / GPU-Speicher (HWiNFO)")), ("vram", N_("Zeile VRAM")),
                  ("ram", N_("Zeile RAM"))]


def today_rows(j, now: float) -> list:
    """HUD rows of today (pure apart from the clock): [[(text, colour), ...], ...]."""
    d = history.today(j.rounds, now)
    day = history.period_start("day", now)
    s = official.summary([j.off[id(r)] for r in j.rounds if r.t >= day and id(r) in j.off and not r.custom])
    rows = [[(_("HEUTE "), sysinfo.DIM),
             (_("{n} RUNDEN · {time}", n=d["count"], time=fmt_duration(d["total"])), sysinfo.WHITE)]]
    res = []
    if s["killer"]:
        res += [(_("Ø KILLS "), sysinfo.DIM), (f"{s['kills']:.1f}", sysinfo.WHITE)]
    if s["survivor"]:
        res += ([(" · ", sysinfo.DIM)] if res else []) + [(_("ENTKOMMEN "), sysinfo.DIM),
                                                         (f"{s['escaped']:.0%}", sysinfo.WHITE)]
    if res:
        rows.append(res)
    return rows


MEDIA_SPOTS = [("below", N_("Unter den Systemwerten")), ("under_today", N_("Unter „Heute“")),
               ("bottom_right", N_("Rechts unten im Balken")), ("bottom_left", N_("Links unten im Balken")),
               ("custom", N_("Eigene Position (mit der Maus verschieben)"))]
TODAY_SPOTS = [("below", N_("Unter den Systemwerten")), ("under_music", N_("Unter der Musik")),
               ("bottom_right", N_("Rechts unten im Balken")), ("bottom_left", N_("Links unten im Balken")),
               ("custom", N_("Eigene Position (mit der Maus verschieben)"))]
OPACITY_KEYS = {"hud": "hud_opacity", "today": "today_opacity", "music": "media_opacity"}   # 1.2.7; else "opacity"
MEDIA_STYLES = [("big", N_("Groß – Cover oben, Titel darunter")), ("compact", N_("Kompakt – Cover links"))]
MEDIA_SCALE = (60, 200)                     # slider of the music card, percent
HUD_SCALE = (60, 200)                       # size of the system values / "today", percent (1.64.9)
MAP_SCALE = (15, 90)                        # size of the map, percent of the game height
# 1.64.9 (user: one size for what was picked instead of three sliders): the elements of the preview
SELECTABLE = (("map", N_("Karte")), ("text", N_("Schrift der Karte (Name, Timer, Infos)")),
              ("hud", N_("Systemwerte")), ("today", N_("Heute")), ("music", N_("Musik")))
TODAY_SCALE = (60, 200)                     # size of "today", percent (1.2.6)
TEXT_SCALE = (50, 200)                      # size of the map's name/timer/info lines, percent (1.65)
TEXT_BASE = 0.36                            # … of the text at the standard map size (share of the game height)
# 1.2.12: the tab of the overlay page (qt_window.SPECS frame keys) that holds each element's settings
ELEMENT_TABS = {"map": "ov.look", "text": "ov.look", "hud": "ov.sys", "today": "ov.today_f", "music": "ov.music_f"}


def text_scale(o: dict) -> float:
    """Size factor of the map's name, timer and info lines (setting overlay.text_scale, 1.65)."""
    return min(TEXT_SCALE[1], max(TEXT_SCALE[0], float(o.get("text_scale", 1.0)) * 100)) / 100


def today_scale(o: dict) -> float:
    """Size factor of "today" (setting overlay.today_scale, 1.2.6)."""
    return min(TODAY_SCALE[1], max(TODAY_SCALE[0], float(o.get("today_scale", 1.0)) * 100)) / 100


def hud_scale(o: dict) -> float:
    """Size factor of the system values / "today" (setting overlay.hud_scale, 1.64.9)."""
    return min(HUD_SCALE[1], max(HUD_SCALE[0], float(o.get("hud_scale", 1.0)) * 100)) / 100


def make_hud(title: str = "DbD Map Scout Systemwerte"):
    """Native HUD window, or None (not Windows / window could not be made)."""
    if not IS_WIN:
        return None
    try:
        from .overlay_win32 import HudWindow
        return HudWindow(title)
    except Exception as e:
        log.warning("Systemwerte-Fenster nicht verfügbar: %s", e)
        return None


class SysInfo:
    def _hud_init(self):
        self.sysmon = sysinfo.SysMonitor()
        self.sysmon.start()
        self.media = media.MediaWatcher()
        self.media.start()
        self.hud = make_hud()
        if self.hud is not None:
            self.hud.on_moved = lambda x, y: self.events.put(("call", self._hud_dragged, (x, y)))   # see app.py
            self.hud.edit_label = _("SYSTEMWERTE · HEUTE")
        self.media_win = make_hud("DbD Map Scout Musik")     # 1.64: the music card, a window of its own
        if self.media_win is not None:
            self.media_win.on_moved = lambda x, y: self.events.put(("call", self._media_dragged, (x, y)))
            self.media_win.edit_label = _("MUSIK")
        self.today_win = make_hud("DbD Map Scout Heute")     # 1.2.6: "today", a card of its own
        if self.today_win is not None:
            self.today_win.on_moved = lambda x, y: self.events.put(("call", self._today_dragged, (x, y)))
            self.today_win.edit_label = _("HEUTE")
        self._today_box = None             # (x, y, w, h) of "today" on screen (the music card hangs below it)
        self._media_ctx = None             # (gx, gy, gw, gh, show) of the last placement
        self._fades = {}                   # name: [media.Fader, timer job] – 1.2.4 music, 1.2.9 every element
        self._media_song = None            # (title, artist) on the card – a new song fades in
        self._media_prev = None            # render arguments of the card as drawn last (1.8.1: the old song of a change)
        self._media_trans = None           # media.Transition while a song change cross-fades
        self._media_anim_job = None        # timer of its frames
        self._media_box = None             # (x, y, w, h) of the music card on screen
        self._hud_reserved = None          # (side, height) taken at the top of a bar, for the map below
        self._hud_pending = ""             # "above"/"beside": rendered, placed once the map's place is known
        self._sysrec = None                # readings of the open round (tab Statistik → System)

    # ---------------------------------------------------------- overlay style (1.3)
    def _skin(self) -> str:
        """The overlay style of the cards (settings overlay.style): classic | glass | chips | line."""
        style = self.settings["overlay"].get("style", "classic")
        return style if style in skin.STYLES else "classic"

    def _skin_accent(self) -> str:
        """The window theme's accent (dark palette – the overlay sits on dark bars) for the modern styles."""
        try:
            return str(qt_theme.colours(True)["accent"])
        except Exception:
            return "#c9a227"

    def _hud_place(self, gx, gy, gw, gh, show: bool):
        """Show/hide the system values; returns (side, height) when they take the top of a bar."""
        side = self.settings.get("sysinfo", "off")
        sys_on = side in HUD_SHOWN
        self._media_ctx = (gx, gy, gw, gh, show)            # "today" and the music card are placed after the map
        on = sys_on and self.hud is not None
        self.sysmon.active = sys_on and self.hud is not None and self.game is not None
        bar = layout.bar_width(gw, gh)
        snap = self.sysmon.snapshot
        if self._hist is not None and self._sysrec is not None and sys_on and time.time() - snap.t < 3:
            self._sysrec.add(snap)
        forced = getattr(self, "_forced", False)            # "Overlay testen" (1.2.8): every element, sample values
        if on and forced and time.time() - snap.t >= 3:
            from .preview import sample_snapshot
            snap = sample_snapshot()
        rows = sysinfo.hud_rows(snap, self.settings["overlay"].get("hud_rows")) if on else []
        editing = on and self.overlay.editing          # 1.64.1: always draggable while moving, like the music
        if self.hud is not None:
            self.hud.set_editing(editing)
        if editing and not rows:
            rows = [[(_("SYSTEMWERTE"), sysinfo.DIM)]]          # something to drag before the first reading
        vb = layout.vbars(self.worker.vbars, gw, gh, time.time())      # narrow window: bar above the picture
        own = side == "custom" and not vb                   # own place: needs no black bar (over the game)
        follow = side == "above" and not vb                 # right above the map, wherever it is
        beside = side == "above" and bool(vb)               # narrow window: right of the map in the bottom bar
        self._hud_pending = ""
        fade = bool(self.settings["overlay"].get("fade", True)) and not editing
        if not (on and (show or editing) and rows and (bar >= layout.MIN_BAR or vb or own or follow)
                and (self.game is not None or editing or forced)):
            if self.hud is not None:
                self._fade_hide("hud", fade)
            self.worker.hud_rect = None
            return None
        o = self.settings["overlay"]
        margin = int(gh * o["margin"])
        avail_w, avail_h = (gw / 2 - 2 * margin, vb[1 if beside else 0] - 2 * margin) if vb else \
            (layout.max_width(bar, margin) if bar >= layout.MIN_BAR else gw / 3, gh)
        self.hud.opacity = o.get("hud_opacity", o["opacity"])
        hh = int(gh * hud_scale(o))
        look = ("backdrop",) if o.get("hud_backdrop", False) else ()
        style = dict(skin=self._skin(), accent=self._skin_accent(), title=_("SYSTEM"))     # 1.3
        w, h = self.hud.render(rows, hh, look=look, **style)
        f = layout.fit_scale(w, h, avail_w, avail_h)
        if f < 1:                                           # narrow bar / low bar: smaller text
            w, h = self.hud.render(rows, max(200, int(hh * f)), look=look, **style)
        labels = tuple(r[0][0] for r in rows if r)
        self._hud_steady, sw = layout.steady_width(getattr(self, "_hud_steady", None), (side, hh, labels), w)
        if follow or beside:                                # shown by _hud_follow_map() after the map
            self._hud_pending = "beside" if beside else "above"
            return ("above", h) if follow else None
        if own:
            fx, fy = self.settings.get("sysinfo_pos") or (1.0, 0.0)
            x, y = gx + fx * max(0, gw - sw), gy + fy * max(0, gh - h)
        else:                                               # own place in the narrow window: the bar above
            x, y = layout.hud_x("left" if side == "left" else "right", gx, gw, margin, sw, 0 if vb else bar,
                                o.get("bar_align", "centre")), gy + margin
        self._fade_show("hud", fade)
        self.hud.show_at(int(x), int(y))
        self.worker.hud_rect = (int(x), int(y), w, h)
        self._hud_box = (int(x), int(y), sw, h)             # steady box: the music card centres below it
        return None if vb or own else (side, h)   # only at the top of a side bar does the map move below it

    def _today_rows(self, now: float) -> list:
        """Block "today" below the system values (1.62, user: the black bars are big): rounds and play time,
        average kills / escaped from the stats page, the clock. Recomputed once a minute."""
        cache = getattr(self, "_today_cache", None)
        j = self._joined()
        if cache is None or cache[0] is not j or cache[1] != int(now // 60):
            self._today_cache = cache = (j, int(now // 60), today_rows(j, now))
        return cache[2] + [[(_("UHR "), sysinfo.DIM), (time.strftime("%H:%M", time.localtime(now)), sysinfo.WHITE)]]

    def _cards_measure(self) -> dict:
        """Render "today" and the music card for this tick (hidden when they have nothing to show) and remember
        their sizes – {name: (w, h) or None}; placed afterwards by _cards_place (1.2.11)."""
        self._card_sizes = {"today": self._today_card(), "music": self._media_card()}
        return self._card_sizes

    def _cards_place(self, free_only: bool = False):
        """"Today" and the music card, each below the system values / another card / in the bar / at its own place
        (1.2.7: stacking in order) – the geometry comes from layout.place_cards, shared with the preview.
        ``free_only``: only the cards that do not hang on the system values (those follow the map later)."""
        o = self.settings["overlay"]
        sizes = dict(self._cards_measure())
        spots = {"today": o.get("today_pos", "below"), "music": o.get("media_pos", "below")}
        if free_only:
            for name in sizes:
                if layout.hangs_on_hud(name, spots):
                    sizes[name] = None
                    setattr(self.worker, f"{'media' if name == 'music' else name}_rect", None)
        gx, gy, gw, gh, _show = self._media_ctx or (0, 0, 0, 0, False)
        hud = self.worker.hud_rect if self.hud is not None and self.hud.shown else None
        box = getattr(self, "_hud_box", None)
        if hud and box and box[:2] == hud[:2]:
            hud = box                                       # by its widest width: no wobble when values change
        cards = {"today": (sizes["today"], o.get("today_pos", "below"), o.get("today_xy")),
                 "music": (sizes["music"], o.get("media_pos", "below"), o.get("media_xy"))}
        placed = layout.place_cards((gx, gy, gw, gh), cards, hud, int(gh * o["margin"]),
                                    o.get("bar_align", "centre"), layout.stack_gap(o, gh),
                                    up=self.settings.get("sysinfo") == "above" and hud is not None
                                    and bool(self._last_place) and hud[1] < self._last_place[1],
                                    below_box=self._last_place)
        self._today_box = placed.get("today")
        if "today" in placed:
            self._fade_show("today", bool(o.get("fade", True)) and not self.overlay.editing)
            self.today_win.show_at(placed["today"][0], placed["today"][1])
            self.worker.today_rect = placed["today"]
        if "music" in placed:
            self._fade_show("music", bool(o.get("media_fade", True)) and not self.overlay.editing,
                            restart=getattr(self, "_media_restart", False))
            self._media_restart = False
            self.media_win.show_at(placed["music"][0], placed["music"][1])
            self.worker.media_rect = self._media_box = placed["music"]
        else:
            self._media_box = None

    def _today_card(self):
        """"Today" (1.2.6, user: "unter dem GPU/CPU-Zähler macht keinen Sinn"): a card of its own like the music.
        Rendered for this tick; returns its size, or None (then hidden) – placed by _cards_place."""
        o = self.settings["overlay"]
        win = self.today_win
        on = bool(o.get("show_today", True)) and win is not None
        ctx = self._media_ctx
        if win is None:
            return None
        editing = on and self.overlay.editing
        win.set_editing(editing)
        rows = self._today_rows(time.time()) if on else []
        spot = o.get("today_pos", "below")
        gx, gy, gw, gh, show = ctx or (0, 0, 0, 0, False)
        bar = layout.bar_width(gw, gh) if gh else 0
        forced = getattr(self, "_forced", False)
        fade = bool(o.get("fade", True)) and not editing
        if not (ctx and rows and (show or editing) and (self.game is not None or editing or forced)
                and (bar >= layout.MIN_BAR or spot == "custom" or editing)):
            self._fade_hide("today", fade)
            self.worker.today_rect = None
            self._today_box = None
            return None
        margin = int(gh * o["margin"])
        win.opacity = o.get("today_opacity", o["opacity"])
        look = ("backdrop",) if o.get("today_backdrop", False) else ()
        height = int(gh * today_scale(o))
        style = dict(skin=self._skin(), accent=self._skin_accent())                        # 1.3
        w, h = win.render(rows, height, look=look, **style)
        avail = layout.max_width(bar, margin) if bar >= layout.MIN_BAR and spot != "custom" else gw / 3
        if w > avail:                                       # never wider than the black bar
            w, h = win.render(rows, max(200, int(height * avail / w)), look=look, **style)
        return (w, h)

    def _today_dragged(self, x, y):
        """"Today" dropped somewhere (edit mode): from now on its own place there."""
        self._layout_mark()
        gx, gy, gw, gh = self._game_rect()
        self._today_own_place(*layout.media_own(gw, gh, self.today_win.size, x - gx, y - gy))

    def _today_own_place(self, fx, fy):
        """"Today" dragged in the preview or the game: its own place (its centre) from now on."""
        o = self.settings["overlay"]
        o["today_xy"], o["today_pos"] = [fx, fy], "custom"
        if hasattr(self, "today_pos_var"):
            self.today_pos_var.set(_(dict(TODAY_SPOTS)["custom"]))
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _preset_apply(self):
        """Button "Vorlage anwenden" (1.2.9): one of layoutmem.PRESETS as a layout change (undo works)."""
        from . import layoutmem
        from .config import DEFAULTS
        key = dict((_(label), k) for k, label in PRESET_LABELS).get(self.preset_var.get(), "left")
        self._layout_mark()
        self._layout_apply(layoutmem.standard_layout(DEFAULTS) if key == layoutmem.STANDARD
                           else layoutmem.PRESETS[key])
        self._log(_("Vorlage „{name}“ angewendet.", name=self.preset_var.get()), "Overlay")

    def _hud_rows_changed(self):
        """Rows of the system values switched on/off (1.2.8)."""
        self.settings["overlay"]["hud_rows"] = {k: bool(v.get()) for k, v in self.hud_row_vars.items()}
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _bar_align_changed(self):
        self._layout_mark()
        key = dict((_(label), k) for k, label in BAR_ALIGNS).get(self.bar_align_var.get(), "centre")
        self.settings["overlay"]["bar_align"] = key
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _gap_changed(self):
        self._layout_mark()
        self.settings["overlay"]["stack_gap"] = int(round(self.gap_var.get()))
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _today_spot_changed(self):
        self._layout_mark()
        key = dict((_(label), k) for k, label in TODAY_SPOTS).get(self.today_pos_var.get(), "below")
        self.settings["overlay"]["today_pos"] = key
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _hud_follow_map(self, rect, gx, gy, gw, gh, margin):
        """"Direkt über der Karte": centred right above the map on display (below it when there is no room);
        stays inside the black bar the map is in. In a narrow window (map in the bar below the picture, user:
        "rechts von der Map") right of the map instead, centred in its height."""
        mode, self._hud_pending = self._hud_pending, ""
        if not mode or self.hud is None:
            return
        fade = bool(self.settings["overlay"].get("fade", True)) and not self.overlay.editing
        if rect is None or not self.overlay.shown:
            self._fade_hide("hud", fade)
            self.worker.hud_rect = None
            return
        x, y, w, h = rect
        hw, hh = self.hud.size
        steady = getattr(self, "_hud_steady", None)
        hw = max(hw, steady[1]) if steady else hw            # centred by its widest width: no wobble
        gap = layout.stack_gap(self.settings["overlay"], gh)
        if mode == "beside":
            hx, hy = min(x + w + 3 * gap, gx + gw - gap - hw), y + max(0, (h - hh) // 2)
            self._fade_show("hud", fade)
            self.hud.show_at(int(hx), int(hy))
            self.worker.hud_rect = (int(hx), int(hy), hw, hh)
            return
        hx = x + (w - hw) / 2
        bar = layout.bar_width(gw, gh)
        lo, hi = gx, gx + gw - hw
        if bar >= layout.MIN_BAR and x < gx + bar:          # map in the left bar: stay in it
            lo, hi = gx + gap, gx + bar - gap - hw
        elif bar >= layout.MIN_BAR and x + w > gx + gw - bar:
            lo, hi = gx + gw - bar + gap, gx + gw - gap - hw
        hx = min(max(hx, lo), max(lo, hi))
        hy = y - gap - hh if y - gap - hh >= gy else y + h + gap
        self._fade_show("hud", fade)
        self.hud.show_at(int(hx), int(hy))
        self.worker.hud_rect = (int(hx), int(hy), hw, hh)

    def _hud_dragged(self, x, y):
        """System values dropped somewhere: remember the place relative to the DBD window (like the map)."""
        self._layout_mark()
        gx, gy, gw, gh = self._game_rect()
        steady = getattr(self, "_hud_steady", None)
        w, h = max(self.hud.size[0], steady[1] if steady else 0), self.hud.size[1]
        self._hud_own_place(round(min(1.0, max(0.0, (x - gx) / max(1, gw - w))), 4),
                            round(min(1.0, max(0.0, (y - gy) / max(1, gh - h))), 4))

    def _media_card(self):
        """The music card (1.64, user: own place, cover, size slider): rendered for this tick; returns its size,
        or None (then hidden) – placed by _cards_place (below the system values or another card, in the bar, or
        at its own place). A new song sets ``_media_restart`` (fades in from nothing)."""
        o = self.settings["overlay"]
        win = self.media_win
        music = bool(o.get("show_media", True)) and win is not None
        self.media.active = music and self.game is not None
        self.media.want_cover = bool(o.get("media_cover", True))
        self.spotify.active = self.media.active and bool(self.settings.get("spotify_on", False))   # 1.8
        ctx = self._media_ctx
        if win is None:
            return None
        editing = music and self.overlay.editing
        win.set_editing(editing)
        now = self.media.now
        rows = media.rows(now, time.time(), "", sysinfo.DIM, sysinfo.WHITE) if music else []
        forced = getattr(self, "_forced", False)
        if music and forced and not rows:                   # "Overlay testen" (1.2.8): a sample song
            from .preview import sample_cover
            now = media.NowPlaying("Blinding Lights", "The Weeknd", True, time.time(), position=70.0,
                                   duration=176.0, at=time.time(), cover=sample_cover())
            rows = media.rows(now, time.time(), "", sysinfo.DIM, sysinfo.WHITE)
        if editing and not rows:
            rows = [[(_("MUSIK"), sysinfo.DIM)], [(_("läuft gerade"), sysinfo.DIM)]]   # something to drag
        spot = o.get("media_pos", "below")
        gx, gy, gw, gh, show = ctx or (0, 0, 0, 0, False)
        bar = layout.bar_width(gw, gh) if gh else 0
        fade = bool(o.get("media_fade", True)) and not editing
        if not (ctx and rows and (show or editing) and (self.game is not None or editing or forced)
                and (bar >= layout.MIN_BAR or spot == "custom" or editing)):
            self._fade_hide("music", fade)                  # hidden at the end of the fade
            self._media_song = self._media_prev = self._media_trans = None
            self.worker.media_rect = None
            return None
        margin = int(gh * o["margin"])
        win.opacity = o.get("media_opacity", o["opacity"])
        cover = now.cover if o.get("media_cover", True) and not (editing and not media.playing(now, time.time())) \
            else None
        height = int(gh * max(MEDIA_SCALE[0], min(MEDIA_SCALE[1], o.get("media_scale", 1.0) * 100)) / 100)
        prog = media.progress(now, time.time()) if o.get("media_progress", True) and media.playing(now, time.time()) \
            else None
        look = media.look(o)
        up = self._upnext(now, sample=forced)                                              # 1.8
        kw = dict(rows=rows, height=height, cover=cover, style=o.get("media_style", "big"), progress=prog,
                  look=look, skin=self._skin(), accent=self._skin_accent(), upnext=up,
                  upnext_pos=o.get("media_next_pos", "below"))
        song = (now.title, now.artist)
        changed = self._media_song is not None and song != self._media_song
        if changed:
            self.spotify.kick(now.title, now.artist)        # 1.8: the queue moved on with the song
            prev_items = (self._media_prev or {}).get("upnext") or ("", ())
            leaving = prev_items[1][0] if prev_items[1] and spotify.same_title(prev_items[1][0][0], now.title) \
                else None
            # 1.8.1 (user: "smoother … die Liste rutscht hoch"): the old card cross-fades into the new one and
            # the queue rows slide up, instead of the whole card fading in from nothing
            if fade and win.shown and self._media_prev is not None:
                self._media_trans = media.Transition(dict(self._media_prev), leaving, time.monotonic())
        self._media_restart = not win.shown or (changed and self._media_trans is None)
        self._media_song = song
        avail = layout.max_width(bar, margin) if bar >= layout.MIN_BAR and spot != "custom" else gw / 3
        w, h = self._media_render(win, kw, avail)
        self._media_prev = kw
        return (w, h)

    def _media_render(self, win, kw: dict, avail: float):
        """Draw the music card – during a song change (``_media_trans``) the cross-fade frame, else the card;
        never wider than ``avail``."""
        trans = self._media_trans
        if trans is not None and not trans.done(time.monotonic()):
            w, h = self._media_frame(win, kw, trans)
            if w > avail:                                   # both songs smaller, by the same factor
                f = max(200, int(kw["height"] * avail / w)) / kw["height"]
                kw["height"] = max(200, int(kw["height"] * f))
                trans.old["height"] = max(200, int(trans.old["height"] * f))
                w, h = self._media_frame(win, kw, trans)
            if self._media_anim_job is None:
                self._media_anim_job = self.root.after(media.Transition.STEP_MS, self._media_anim_tick)
            return w, h
        self._media_trans = None
        w, h = win.render(**kw)
        if w > avail:                                       # never wider than the black bar
            kw["height"] = max(200, int(kw["height"] * avail / w))
            w, h = win.render(**kw)
        return w, h

    def _media_frame(self, win, kw: dict, trans):
        """One frame of the song change: the new card with the queue rows sliding (``anim``) blended over the old."""
        t = trans.progress(time.monotonic())
        new = dict(kw)
        if trans.leaving and new.get("upnext"):
            new["anim"] = (trans.leaving, t)
        old = dict(trans.old, upnext=new.get("upnext"), upnext_pos=new.get("upnext_pos"), anim=new.get("anim"))
        return win.render_blend(old, new, t)      # same list on both: only cover and text cross-fade

    def _media_anim_tick(self):
        """Frames of the song change between the 4-per-second ticks (STEP_MS); the last one draws the final card."""
        self._media_anim_job = None
        win, trans, kw, box = self.media_win, self._media_trans, self._media_prev, self._media_box
        if win is None or trans is None or kw is None or not win.shown:
            self._media_trans = None
            return
        try:
            if trans.done(time.monotonic()):
                self._media_trans = None
                win.render(**kw)
            else:
                self._media_frame(win, kw, trans)
                self._media_anim_job = self.root.after(media.Transition.STEP_MS, self._media_anim_tick)
            if box:
                win.show_at(box[0], box[1])
        except Exception as e:                              # a drawing error must not kill the ticks
            log.warning("Musikkarte: Übergang abgebrochen (%s)", e)
            self._media_trans = None

    # ---- fading (1.2.4 the music card, 1.2.9 map, system values and "today" too): media.Fader per window
    def _fade_win(self, name):
        attr = {"map": "overlay", "hud": "hud", "today": "today_win", "music": "media_win"}[name]
        return getattr(self, attr, None)

    def _fade_state(self, name):
        st = self._fades.get(name)
        if st is None:
            st = self._fades[name] = [media.Fader(), None]
        return st

    def _fade_to(self, name, target, start=None):
        st = self._fade_state(name)
        st[0].go(target, time.monotonic(), start)
        self._fade_win(name).set_fade(st[0].value)
        if st[1] is None:
            st[1] = self.root.after(st[0].STEP_MS, lambda: self._fade_tick(name))

    def _fade_tick(self, name):
        st = self._fade_state(name)
        st[1] = None
        win = self._fade_win(name)
        if win is None:
            return
        done = st[0].step(time.monotonic())
        win.set_fade(st[0].value)
        if not done:
            st[1] = self.root.after(st[0].STEP_MS, lambda: self._fade_tick(name))
        elif st[0].target == 0:
            win.hide()
            win.set_fade(1.0)

    def _fade_stop(self, name):
        """No fading: cancel a running one, full opacity."""
        st = self._fade_state(name)
        if st[1] is not None:
            self.root.after_cancel(st[1])
            st[1] = None
        st[0].go(1, time.monotonic(), 1.0)
        win = self._fade_win(name)
        if win is not None:
            win.set_fade(1.0)

    def _fade_show(self, name, on: bool, restart: bool = False):
        """Right before ``show_at``: a window that appears (or ``restart``: new content) fades in from nothing,
        one caught while fading out comes back from where it is; ``on`` False = no fading at all."""
        win = self._fade_win(name)
        if win is None:
            return
        if not on:
            self._fade_stop(name)
        elif not win.shown or restart:
            self._fade_to(name, 1, start=0.0)
        elif self._fade_state(name)[0].target != 1:
            self._fade_to(name, 1)

    def _fade_hide(self, name, on: bool):
        """Hide the window – fading out when ``on`` and it is shown (hidden at the end of the fade)."""
        win = self._fade_win(name)
        if win is None:
            return
        if on and win.shown:
            if self._fade_state(name)[0].target != 0:
                self._fade_to(name, 0)
        else:
            self._fade_stop(name)
            win.hide()

    def _guides_place(self):
        """Centre cross over the DBD window while moving (1.64.5): two thin click-through windows, hidden
        otherwise. The worker blacks them out (a long light line would look like a banner's separator)."""
        on = self.overlay.editing and self.game is not None
        if not on:
            for g in getattr(self, "_guides", ()):
                g.hide()
            self.worker.guide_rects = ()
            return
        if not getattr(self, "_guides", None):
            self._guides = [g for g in (make_hud("DbD Map Scout Mitte"), make_hud("DbD Map Scout Mitte"))
                            if g is not None]
            if len(self._guides) < 2:
                return
        from .overlay_win32 import guide_line
        gx, gy, gw, gh = self._game_rect()
        v, hz = self._guides
        v.set_picture(guide_line(gh, True), ("v", gh))
        hz.set_picture(guide_line(gw, False), ("h", gw))
        vx, hy = gx + gw // 2 - 1, gy + gh // 2 - 1
        v.show_at(vx, gy)
        hz.show_at(gx, hy)
        self.worker.guide_rects = ((vx, gy, 3, gh), (gx, hy, gw, 3))

    def _media_dragged(self, x, y):
        """Music card dropped somewhere (edit mode): from now on its own place there."""
        self._layout_mark()
        gx, gy, gw, gh = self._game_rect()
        o = self.settings["overlay"]
        o["media_xy"] = list(layout.media_own(gw, gh, self.media_win.size, x - gx, y - gy))
        o["media_pos"] = "custom"
        if hasattr(self, "media_pos_var"):
            self.media_pos_var.set(_(dict(MEDIA_SPOTS)["custom"]))
        self._save_soon()

    def _hud_own_place(self, fx, fy):
        """System values dragged in the preview: their own place from now on (1.64.1)."""
        self.settings.set("sysinfo_pos", [fx, fy])
        if self.settings.get("sysinfo", "off") in HUD_SHOWN:
            self.settings.set("sysinfo", "custom")
            if hasattr(self, "sysinfo_var"):
                self.sysinfo_var.set(_(dict(HUD_SIDES)["custom"]))
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _music_own_place(self, fx, fy):
        """Music card dragged in the preview: its own place from now on (1.64.1)."""
        o = self.settings["overlay"]
        o["media_xy"], o["media_pos"] = [fx, fy], "custom"
        if hasattr(self, "media_pos_var"):
            self.media_pos_var.set(_(dict(MEDIA_SPOTS)["custom"]))
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _media_spot_changed(self):
        self._layout_mark()
        key = dict((_(label), k) for k, label in MEDIA_SPOTS).get(self.media_pos_var.get(), "below")
        self.settings["overlay"]["media_pos"] = key
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _media_style_changed(self):
        key = dict((_(label), k) for k, label in MEDIA_STYLES).get(self.media_style_var.get(), "big")
        self.settings["overlay"]["media_style"] = key
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _media_size_changed(self):
        self._layout_mark()
        self.settings["overlay"]["media_scale"] = round(float(self.media_size_var.get()) / 100, 2)
        self._save_soon()
        self._sel_sync()
        self._tick_overlay(reschedule=False)

    # ---- 1.64.9: pick an element (preview or list), then one slider / the corner / the wheel sizes it
    def _sel_range(self, name):
        """(low, high, value) in percent of the element's size setting."""
        o = self.settings["overlay"]
        if name == "hud":
            return HUD_SCALE + (hud_scale(o) * 100,)
        if name == "text":
            return TEXT_SCALE + (text_scale(o) * 100,)
        if name == "music":
            return MEDIA_SCALE + (min(MEDIA_SCALE[1], max(MEDIA_SCALE[0], o.get("media_scale", 1.0) * 100)),)
        if name == "today":
            return TODAY_SCALE + (today_scale(o) * 100,)
        return MAP_SCALE + (self._map_height() * 100,)

    def _select(self, name):
        """The element the size slider works on (a click on it in the preview, or the list)."""
        if name not in dict(SELECTABLE):
            return
        if name != getattr(self, "_sel", "map"):
            self._sel = name
            self.sel_var.set(_(dict(SELECTABLE)[name]))
            self._sel_sync()
        qt = getattr(self, "qt", None)              # 1.2.12 (analysis point 10): its settings tab opens with it
        if qt is not None and hasattr(qt, "open_tab"):     # (also when it was picked already: a second click)
            qt.open_tab("overlay", ELEMENT_TABS.get(name, "ov.look"))

    def _sel_picked(self):
        names = {_(label): k for k, label in SELECTABLE}
        self._select(names.get(self.sel_var.get(), "map"))

    def _own_size_map(self):
        """The map whose own size the size controls change (1.65.5, user: "sobald ich eine Map in der Runde
        bearbeite, zählt es nur für die Map"): the map on display – not the test map; None = all maps."""
        if self.current and not getattr(self, "_test_map", False) and self.overlay.has_map():
            return self.current[0]
        return None

    def _size_scope_text(self) -> str:
        """Under the size slider: what the size applies to – for the map its own size per map (1.65.5), for every
        element the window size whose layout is being edited (1.2.17; before, nothing for the other elements)."""
        key = self.settings.get("layout_key") if self.settings.get("layout_per_size", True) else None
        window = (_("Fenster {size}", size=str(key).replace("x", "×")) if key else _("alle Fenstergrössen"))
        if getattr(self, "_sel", "map") != "map":
            return _("Gilt für: {window}", window=window)
        mid = self._own_size_map()
        m = self.catalog.maps.get(mid) if mid else None
        maps = _("nur {map}", map=m.name) if m else _("alle Maps (keine Map eingeblendet)")
        return _("Gilt für: {maps} · {window}", maps=maps, window=window)

    def _sel_sync(self):
        """Slider range, label and value for the element picked (also when its size changed elsewhere); since
        1.2.7 the opacity slider shows that element's opacity too."""
        scale = getattr(self, "sel_scale", None)
        if scale is None:
            return
        name = getattr(self, "_sel", "map")
        lo, hi, value = self._sel_range(name)
        scale.configure(from_=lo, to=hi)
        self.sel_size_var.set(round(value))
        self.sel_size_label.configure(text=f"{value:.0f} %")
        o = self.settings["overlay"]
        op = float(o.get(OPACITY_KEYS.get(name, "opacity"), o["opacity"])) * 100
        self.opacity_var.set(round(op))
        self.opacity_label.configure(text=f"{op:.0f} %")

    def _sel_size_changed(self):
        self._set_size(getattr(self, "_sel", "map"), float(self.sel_size_var.get()))

    def _set_size(self, name, percent):
        """Size of one element in percent (slider, corner in the preview, wheel). The map: its own size when the
        map on display has one (hotkeys), else the size of all maps – the one you see is the one that changes."""
        self._layout_mark()
        lo, hi, _v = self._sel_range(name)
        percent = min(hi, max(lo, percent))
        o = self.settings["overlay"]
        if name == "hud":
            o["hud_scale"] = round(percent / 100, 2)
        elif name == "text":
            o["text_scale"] = round(percent / 100, 2)
        elif name == "music":
            o["media_scale"] = round(percent / 100, 2)
            self.media_size_var.set(round(percent))
        elif name == "today":
            o["today_scale"] = round(percent / 100, 2)
        else:
            value = round(percent / 100, 3)
            mid = self._own_size_map()
            if mid:                                  # 1.65.5 (user): a map on display = a size for this map only
                o.setdefault("map_heights", {})[mid] = value
                self._show_map_size()
            else:
                o["height"] = value
                self.size_var.set(value * 100)
                self.size_label.configure(text=f"{percent:.0f} %")
        if name == getattr(self, "_sel", "map"):
            self.sel_size_var.set(round(percent))
            self.sel_size_label.configure(text=f"{percent:.0f} %")
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _resize_to(self, name, height):
        """The preview's corner or wheel: element ``name`` this tall (screen px) – its setting scaled by how much
        taller than now. Picks the element too."""
        self._select(name)
        sizes = {n: h for n, _x, _y, _w, h in self._preview_data()["layers"]}
        if not sizes.get(name):
            return
        _lo, _hi, value = self._sel_range(name)
        self._set_size(name, value * height / sizes[name])

    def _sysinfo_changed(self):
        self._layout_mark()
        key = dict((_(label), k) for k, label in HUD_SIDES).get(self.sysinfo_var.get(), "off")
        self.settings.set("sysinfo", key)
        self._save_soon()
        self._sysinfo_status()
        self._tick_overlay(reschedule=False)

    def _sysinfo_status(self):
        """Which sources the HUD has (below the setting)."""
        if not hasattr(self, "sysinfo_hint_var"):
            return
        m = self.sysmon
        s = m.snapshot
        parts = [_("GPU: {name}", name=s.gpu_name) if s.gpu_name else
                 _("GPU: keine NVIDIA-Karte gefunden") if m.nvml_error else ""]
        if s.hwinfo:                         # without it the text above already says what to do
            parts.append(_("CPU-Temperatur: aus HWiNFO"))
        if self.settings.get("sysinfo", "off") == "off":
            parts = []
        text = " · ".join(p for p in parts if p)
        if text != self.sysinfo_hint_var.get():
            self.sysinfo_hint_var.set(text)
