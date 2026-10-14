"""System values (CPU/GPU temperature, load, VRAM, RAM) at the top of a black bar while a map is on screen.

Mixin of App (app.py) – the methods use App's attributes."""
from __future__ import annotations

import logging
import time

from . import layout, sysinfo
from .capture import IS_WIN
from .i18n import N_, _

log = logging.getLogger("dbdmapscout")

HUD_SIDES = [("off", N_("Aus")), ("above", N_("Direkt über der Karte (wandert mit)")),
             ("left", N_("Links oben (über der Karte)")), ("right", N_("Rechts oben")),
             ("custom", N_("Eigene Position (mit der Maus verschieben)"))]
HUD_SHOWN = ("above", "left", "right", "custom")


def make_hud():
    """Native HUD window, or None (not Windows / window could not be made)."""
    if not IS_WIN:
        return None
    try:
        from .overlay_win32 import HudWindow
        return HudWindow()
    except Exception as e:
        log.warning("Systemwerte-Fenster nicht verfügbar: %s", e)
        return None


class SysInfo:
    def _hud_init(self):
        self.sysmon = sysinfo.SysMonitor()
        self.sysmon.start()
        self.hud = make_hud()
        if self.hud is not None:
            self.hud.on_moved = self._hud_dragged
        self._hud_reserved = None          # (side, height) taken at the top of a bar, for the map below
        self._hud_pending = ""             # "above"/"beside": rendered, placed once the map's place is known
        self._sysrec = None                # readings of the open round (tab Statistik → System)

    def _hud_place(self, gx, gy, gw, gh, show: bool):
        """Show/hide the system values; returns (side, height) when they take the top of a bar."""
        side = self.settings.get("sysinfo", "off")
        on = side in HUD_SHOWN and self.hud is not None
        self.sysmon.active = on and self.game is not None
        bar = layout.bar_width(gw, gh)
        snap = self.sysmon.snapshot
        if self._hist is not None and self._sysrec is not None and on and time.time() - snap.t < 3:
            self._sysrec.add(snap)
        rows = sysinfo.hud_rows(snap) if on else []
        editing = on and side == "custom" and self.overlay.editing
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
        w, h = self.hud.render(rows, gh)
        f = layout.fit_scale(w, h, avail_w, avail_h)
        if f < 1:                                           # narrow bar / low bar: smaller text
            w, h = self.hud.render(rows, max(200, int(gh * f)))
        if follow or beside:                                # shown by _hud_follow_map() after the map
            self._hud_pending = "beside" if beside else "above"
            return ("above", h) if follow else None
        if own:
            fx, fy = self.settings.get("sysinfo_pos") or (1.0, 0.0)
            x, y = gx + fx * max(0, gw - w), gy + fy * max(0, gh - h)
        else:                                               # own place in the narrow window: the bar above
            x, y = layout.hud_x("left" if side == "left" else "right", gx, gw, margin, w), gy + margin
        self.hud.show_at(int(x), int(y))
        self.worker.hud_rect = (int(x), int(y), w, h)
        return None if vb or own else (side, h)   # only at the top of a side bar does the map move below it

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
        gx, gy, gw, gh = self._game_rect()
        w, h = self.hud.size
        self.settings.set("sysinfo_pos", [round(min(1.0, max(0.0, (x - gx) / max(1, gw - w))), 4),
                                          round(min(1.0, max(0.0, (y - gy) / max(1, gh - h))), 4)])
        self._save_soon()

    def _sysinfo_changed(self):
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
        parts.append(_("CPU-Temperatur: aus HWiNFO") if s.hwinfo else
                     _("CPU-Temperatur: nur mit HWiNFO („Shared Memory Support“ an)"))
        if self.settings.get("sysinfo", "off") == "off":
            parts = []
        text = " · ".join(p for p in parts if p)
        if text != self.sysinfo_hint_var.get():
            self.sysinfo_hint_var.set(text)
