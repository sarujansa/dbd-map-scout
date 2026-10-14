"""System values (CPU/GPU temperature, load, VRAM, RAM) at the top of a black bar while a map is on screen.

Mixin of App (app.py) – the methods use App's attributes."""
from __future__ import annotations

import logging

from . import layout, sysinfo
from .capture import IS_WIN
from .i18n import N_, _

log = logging.getLogger("dbdmapscout")

HUD_SIDES = [("off", N_("Aus")), ("left", N_("Links oben (über der Karte)")), ("right", N_("Rechts oben"))]


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
        self._hud_reserved = None          # (side, height) taken at the top of a bar, for the map below

    def _hud_place(self, gx, gy, gw, gh, show: bool):
        """Show/hide the system values; returns (side, height) when they take the top of a bar."""
        side = self.settings.get("sysinfo", "off")
        on = side in ("left", "right") and self.hud is not None
        self.sysmon.active = on and self.game is not None
        bar = layout.bar_width(gw, gh)
        rows = sysinfo.hud_rows(self.sysmon.snapshot) if on else []
        if not (on and show and rows and bar >= layout.MIN_BAR and self.game is not None):
            if self.hud is not None:
                self.hud.hide()
            self.worker.hud_rect = None
            return None
        o = self.settings["overlay"]
        margin = int(gh * o["margin"])
        avail = layout.max_width(bar, margin)
        self.hud.opacity = o["opacity"]
        w, h = self.hud.render(rows, gh)
        if w > avail:                                       # narrow bar: smaller text
            w, h = self.hud.render(rows, max(200, int(gh * avail / w)))
        x, y = layout.hud_x(side, gx, gw, margin, w), gy + margin
        self.hud.show_at(int(x), int(y))
        self.worker.hud_rect = (int(x), int(y), w, h)
        return side, h

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
