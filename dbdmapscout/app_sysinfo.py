"""System values (CPU/GPU temperature, load, VRAM, RAM) at the top of a black bar while a map is on screen.

Mixin of App (app.py) – the methods use App's attributes."""
from __future__ import annotations

import logging
import time

from . import history, layout, media, official, sysinfo
from .capture import IS_WIN
from .i18n import N_, _
from .textnorm import fmt_duration

log = logging.getLogger("dbdmapscout")

HUD_SIDES = [("off", N_("Aus")), ("above", N_("Direkt über der Karte (wandert mit)")),
             ("left", N_("Links oben (über der Karte)")), ("right", N_("Rechts oben")),
             ("custom", N_("Eigene Position (mit der Maus verschieben)"))]
HUD_SHOWN = ("above", "left", "right", "custom")


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


MEDIA_SPOTS = [("below", N_("Unter den Systemwerten")), ("bottom_right", N_("Rechts unten im Balken")),
               ("bottom_left", N_("Links unten im Balken")),
               ("custom", N_("Eigene Position (mit der Maus verschieben)"))]
MEDIA_STYLES = [("big", N_("Groß – Cover oben, Titel darunter")), ("compact", N_("Kompakt – Cover links"))]
MEDIA_SCALE = (60, 200)                     # slider of the music card, percent
HUD_SCALE = (60, 200)                       # size of the system values / "today", percent (1.64.9)
MAP_SCALE = (15, 90)                        # size of the map, percent of the game height
# 1.64.9 (user: one size for what was picked instead of three sliders): the elements of the preview
SELECTABLE = (("map", N_("Karte")), ("text", N_("Schrift der Karte (Name, Timer, Infos)")),
              ("hud", N_("Systemwerte · Heute")), ("music", N_("Musik")))
TEXT_SCALE = (50, 200)                      # size of the map's name/timer/info lines, percent (1.65)
TEXT_BASE = 0.36                            # … of the text at the standard map size (share of the game height)


def text_scale(o: dict) -> float:
    """Size factor of the map's name, timer and info lines (setting overlay.text_scale, 1.65)."""
    return min(TEXT_SCALE[1], max(TEXT_SCALE[0], float(o.get("text_scale", 1.0)) * 100)) / 100


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
        self._media_ctx = None             # (gx, gy, gw, gh, show) of the last placement
        self._media_fader = media.Fader()  # 1.2.4: the music card fades in/out
        self._media_fade_job = None
        self._media_song = None            # (title, artist) on the card – a new song fades in
        self._hud_reserved = None          # (side, height) taken at the top of a bar, for the map below
        self._hud_pending = ""             # "above"/"beside": rendered, placed once the map's place is known
        self._sysrec = None                # readings of the open round (tab Statistik → System)

    def _hud_place(self, gx, gy, gw, gh, show: bool):
        """Show/hide the system values; returns (side, height) when they take the top of a bar."""
        side = self.settings.get("sysinfo", "off")
        sys_on = side in HUD_SHOWN
        today = bool(self.settings["overlay"].get("show_today", True))
        self._media_ctx = (gx, gy, gw, gh, show)            # the music card is placed after the map
        if not sys_on and today:                            # only "today": top of the right bar or dragged
            side = "custom" if self.settings.get("today_side") == "custom" else "right"
        on = (sys_on or today) and self.hud is not None
        self.sysmon.active = sys_on and self.hud is not None and self.game is not None
        bar = layout.bar_width(gw, gh)
        snap = self.sysmon.snapshot
        if self._hist is not None and self._sysrec is not None and sys_on and time.time() - snap.t < 3:
            self._sysrec.add(snap)
        rows = sysinfo.hud_rows(snap) if sys_on and self.hud is not None else []
        if on and today:
            rows = rows + ([[(" ", sysinfo.DIM)]] if rows else []) + self._today_rows(time.time())
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
        if not (on and (show or editing) and rows and (bar >= layout.MIN_BAR or vb or own or follow)
                and (self.game is not None or editing)):
            if self.hud is not None:
                self.hud.hide()
            self.worker.hud_rect = None
            return None
        o = self.settings["overlay"]
        margin = int(gh * o["margin"])
        avail_w, avail_h = (gw / 2 - 2 * margin, vb[1 if beside else 0] - 2 * margin) if vb else \
            (layout.max_width(bar, margin) if bar >= layout.MIN_BAR else gw / 3, gh)
        self.hud.opacity = o["opacity"]
        hh = int(gh * hud_scale(o))
        look = ("backdrop",) if o.get("hud_backdrop", False) else ()
        w, h = self.hud.render(rows, hh, look=look)
        f = layout.fit_scale(w, h, avail_w, avail_h)
        if f < 1:                                           # narrow bar / low bar: smaller text
            w, h = self.hud.render(rows, max(200, int(hh * f)), look=look)
        labels = tuple(r[0][0] for r in rows if r)
        self._hud_steady, sw = layout.steady_width(getattr(self, "_hud_steady", None), (side, hh, labels), w)
        if follow or beside:                                # shown by _hud_follow_map() after the map
            self._hud_pending = "beside" if beside else "above"
            return ("above", h) if follow else None
        if own:
            fx, fy = self.settings.get("sysinfo_pos") or (1.0, 0.0)
            x, y = gx + fx * max(0, gw - sw), gy + fy * max(0, gh - h)
        else:                                               # own place in the narrow window: the bar above
            x, y = layout.hud_x("left" if side == "left" else "right", gx, gw, margin, sw, 0 if vb else bar), \
                gy + margin
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

    def _hud_follow_map(self, rect, gx, gy, gw, gh, margin):
        """"Direkt über der Karte": centred right above the map on display (below it when there is no room);
        stays inside the black bar the map is in. In a narrow window (map in the bar below the picture, user:
        "rechts von der Map") right of the map instead, centred in its height."""
        mode, self._hud_pending = self._hud_pending, ""
        if not mode or self.hud is None:
            return
        if rect is None or not self.overlay.shown:
            self.hud.hide()
            self.worker.hud_rect = None
            return
        x, y, w, h = rect
        hw, hh = self.hud.size
        steady = getattr(self, "_hud_steady", None)
        hw = max(hw, steady[1]) if steady else hw            # centred by its widest width: no wobble
        gap = max(2, margin // 2)
        if mode == "beside":
            hx, hy = min(x + w + 3 * gap, gx + gw - gap - hw), y + max(0, (h - hh) // 2)
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

    def _media_place(self):
        """The music card (1.64, user: own place, cover, size slider): below the system values (default), bottom
        right / left in the black bar, or an own place dragged in the map's edit mode. Shown with the map."""
        o = self.settings["overlay"]
        win = self.media_win
        music = bool(o.get("show_media", True)) and win is not None
        self.media.active = music and self.game is not None
        self.media.want_cover = bool(o.get("media_cover", True))
        ctx = self._media_ctx
        if win is None:
            return
        editing = music and self.overlay.editing
        win.set_editing(editing)
        now = self.media.now
        rows = media.rows(now, time.time(), "", sysinfo.DIM, sysinfo.WHITE) if music else []
        if editing and not rows:
            rows = [[(_("MUSIK"), sysinfo.DIM)], [(_("läuft gerade"), sysinfo.DIM)]]   # something to drag
        spot = o.get("media_pos", "below")
        gx, gy, gw, gh, show = ctx or (0, 0, 0, 0, False)
        bar = layout.bar_width(gw, gh) if gh else 0
        fade = bool(o.get("media_fade", True)) and not editing
        if not (ctx and rows and (show or editing) and (self.game is not None or editing)
                and (bar >= layout.MIN_BAR or spot == "custom" or editing)):
            if fade and win.shown:
                if self._media_fader.target != 0:
                    self._media_fade(0)                     # hidden at the end of the fade
            else:
                win.hide()
            self._media_song = None
            self.worker.media_rect = None
            return
        margin = int(gh * o["margin"])
        win.opacity = o["opacity"]
        cover = now.cover if o.get("media_cover", True) and not (editing and not media.playing(now, time.time())) \
            else None
        height = int(gh * max(MEDIA_SCALE[0], min(MEDIA_SCALE[1], o.get("media_scale", 1.0) * 100)) / 100)
        prog = media.progress(now, time.time()) if o.get("media_progress", True) and media.playing(now, time.time()) \
            else None
        look = media.look(o)
        w, h = win.render(rows, height, cover, o.get("media_style", "big"), prog, look)
        avail = layout.max_width(bar, margin) if bar >= layout.MIN_BAR and spot != "custom" else gw / 3
        if w > avail:                                       # never wider than the black bar
            w, h = win.render(rows, max(200, int(height * avail / w)), cover, o.get("media_style", "big"), prog,
                              look)
        hud = self.worker.hud_rect if self.hud is not None and self.hud.shown else None
        box = getattr(self, "_hud_box", None)
        if hud and box and box[:2] == hud[:2]:
            hud = box                                       # by its widest width: no wobble when values change
        x, y = layout.media_xy(spot, (gx, gy, gw, gh), (w, h), margin, hud, o.get("media_xy"))
        song = (now.title, now.artist)
        if not fade:
            self._media_fade_stop()
        elif not win.shown or song != self._media_song:
            self._media_fade(1, start=0.0)                  # appears / a new song: from nothing
        elif self._media_fader.target != 1:
            self._media_fade(1)                             # back while fading out: from where it is
        self._media_song = song
        win.show_at(int(x), int(y))
        self.worker.media_rect = (int(x), int(y), w, h)

    def _media_fade(self, target, start=None):
        f = self._media_fader
        f.go(target, time.monotonic(), start)
        self.media_win.set_fade(f.value)
        if self._media_fade_job is None:
            self._media_fade_job = self.root.after(f.STEP_MS, self._media_fade_tick)

    def _media_fade_tick(self):
        self._media_fade_job = None
        f, win = self._media_fader, self.media_win
        if win is None:
            return
        done = f.step(time.monotonic())
        win.set_fade(f.value)
        if not done:
            self._media_fade_job = self.root.after(f.STEP_MS, self._media_fade_tick)
        elif f.target == 0:
            win.hide()
            win.set_fade(1.0)

    def _media_fade_stop(self):
        if self._media_fade_job is not None:
            self.root.after_cancel(self._media_fade_job)
            self._media_fade_job = None
        self._media_fader.go(1, time.monotonic(), 1.0)
        self.media_win.set_fade(1.0)

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
        """System values (or "today" alone) dragged in the preview: their own place from now on (1.64.1). With
        the system values off only "today" moves – they are not switched on by it."""
        self.settings.set("sysinfo_pos", [fx, fy])
        if self.settings.get("sysinfo", "off") in HUD_SHOWN:
            self.settings.set("sysinfo", "custom")
            if hasattr(self, "sysinfo_var"):
                self.sysinfo_var.set(_(dict(HUD_SIDES)["custom"]))
        else:
            self.settings.set("today_side", "custom")
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
        return MAP_SCALE + (self._map_height() * 100,)

    def _select(self, name):
        """The element the size slider works on (a click on it in the preview, or the list)."""
        if name not in dict(SELECTABLE) or name == getattr(self, "_sel", "map"):
            return
        self._sel = name
        self.sel_var.set(_(dict(SELECTABLE)[name]))
        self._sel_sync()

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
        if getattr(self, "_sel", "map") != "map":
            return ""
        mid = self._own_size_map()
        m = self.catalog.maps.get(mid) if mid else None
        return _("Gilt nur für {map}", map=m.name) if m else _("Gilt für alle Maps (keine Map eingeblendet)")

    def _sel_sync(self):
        """Slider range, label and value for the element picked (also when its size changed elsewhere)."""
        scale = getattr(self, "sel_scale", None)
        if scale is None:
            return
        lo, hi, value = self._sel_range(getattr(self, "_sel", "map"))
        scale.configure(from_=lo, to=hi)
        self.sel_size_var.set(round(value))
        self.sel_size_label.configure(text=f"{value:.0f} %")

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
