"""Mixin of App: the Qt control window (setting ``ui_toolkit`` = "qt", since 1.51; stage 1 of the move to Qt).

The Tk App stays the controller and Tk's mainloop the main loop; its window is hidden and only opened for the
pages that are not in Qt yet. Qt is driven from here: ``_qt_refresh`` pushes the state (from ``_tick_overlay``),
button clicks arrive as ("ui", action, arg) in ``self.events`` (``_qt_event`` from ``_poll``). See qt_window.py
for why Qt code never calls Tk directly.
"""
from __future__ import annotations

import logging
import os
import time
import traceback

from . import overview, tooltip
from .capture import IS_WIN
from .i18n import _

log = logging.getLogger("dbdmapscout")

GEOMETRY_DELAY = 1.0          # s after the last move/resize before the size is saved
QT_TIPS = {"toggle": "toggle_btn", "layout": "layout_btn", "rotate": "rotate_btn", "floor": "floor_btn"}
QT_HOTKEYS = {"scan": "scan_now", "reject": "reject_map"}


class QtShell:
    def _qt_early(self):
        """Right after tk.Tk(): load Qt if wanted, so the Tk window never flashes up. Without PySide6 (old
        .venv, failed install) the program stays in Tk and says so in the log."""
        self.qt = None
        self.qapp = None
        self._qt_mod = None
        self._qt_failed = ""
        self._qt_geo_due = 0.0
        if self.settings.get("ui_toolkit", "tk") != "qt":
            return
        try:
            from . import qt_window
            self.qapp = qt_window.application()
            self._qt_mod = qt_window
            self.root.withdraw()
        except Exception as e:
            self._qt_failed = f"{type(e).__name__}: {e}"
            log.error("Qt: %s", traceback.format_exc())

    def _qt_build(self, start_in_tray: bool):
        if self._qt_failed:
            self._log(_("Neue Oberfläche (Qt) nicht verfügbar, das bisherige Fenster bleibt: {error}",
                        error=self._qt_failed), "Fehler")
        if self._qt_mod is None:
            return
        try:
            ico = os.path.join(self.root_dir, "dbdmapscout.ico")
            self.qt = self._qt_mod.MainWindow(self._qt_post, ico if os.path.exists(ico) else None)
            self._qt_theme()
            # first start of the Qt window: the hint what to do (gone with "Verstanden" or from the next start)
            self._qt_welcome = not self.settings.get("welcome_seen") and not self.settings.get("qt_geometry")
            self.qt.restore_b64(self.settings.get("qt_geometry") or "")
            self.root.protocol("WM_DELETE_WINDOW", self.root.withdraw)   # the old window only closes
            self._qt_refresh(force=True)
            if not start_in_tray:
                self.qt.show()
            elif not self.tray.active:
                self.qt.showMinimized()
        except Exception:
            self._report_once("Qt", traceback.format_exc())
            self.qt = None
            self.root.protocol("WM_DELETE_WINDOW", self.quit)
            self.root.deiconify()

    def _qt_post(self, action, arg=None):
        """Called from Qt (any context): only hand the click over to the Tk side."""
        self.events.put(("ui", action, arg))

    def _qt_event(self, action, arg=None):
        if action == "quit":
            self.quit()
            return
        if action == "minimised":
            if self.qt is not None and self.tray.active and self.settings.get("tray", True):
                self.qt.hide()
            return
        if action == "tab":
            self._open_tab(arg)
        elif action in ("assign", "picture"):
            self._show_window()                  # its dialogs belong to the Tk window (hidden: invisible)
            if action == "assign":
                self.assign_unknown()
            else:
                self.add_picture(from_unknown=True)
        else:
            {"scan": self.scan_now, "rotate": self.rotate_map, "toggle": self.toggle_overlay,
             "reject": self.reject_detection, "confirm": self._confirm_unsure, "layout": self.next_variant,
             "floor": self.next_floor, "welcome": self._hide_welcome}.get(action, lambda: None)()
        self._qt_refresh(force=True)

    def _open_tab(self, key):
        tab = getattr(self, f"tab_{key}", None)
        if tab is not None:
            self.nb.select(tab)
        self._show_window()

    def _show_main(self):
        """Tray "Öffnen": the Qt window if there is one, else the Tk window."""
        if self.qt is not None:
            self.qt.bring_to_front()
        else:
            self._show_window()

    def _qt_pump(self):
        """Qt's own events (posted events, and on Linux everything): Windows also delivers them through Tk's
        message loop, this is the safety net – from a Tk callback, where Qt slots cannot reach Tcl's loop."""
        if self.qapp is None:
            return
        try:
            self.qapp.processEvents()
        except Exception:
            self._report_once("Qt", traceback.format_exc())

    def _qt_theme(self):
        if self.qt is not None:
            self.qt.apply_theme(bool(self.settings.get("dark_mode", True)), float(self.settings.get("ui_zoom", 1.0)))

    def _qt_tip(self, key, label):
        attr = QT_TIPS.get(key)
        if attr:
            tip = self._tip_lookup(getattr(self, attr))
            if tip is not None:
                return tip()
        tip = tooltip.tip_for_label(label) or ""
        return tip + (self._hk_hint(QT_HOTKEYS[key]) if key in QT_HOTKEYS and tip else "")

    def _qt_refresh(self, force=False):
        """Push the state into the Qt window (4×/s from _tick_overlay; only while it can be seen)."""
        q = self.qt
        if q is None:
            return
        now = time.time()
        visible = q.isVisible() and not q.isMinimized()
        if q.geometry_changed:
            q.geometry_changed = False
            self._qt_geo_due = now + GEOMETRY_DELAY
        if self._qt_geo_due and now >= self._qt_geo_due and visible:
            self._qt_geo_due = 0.0
            text = q.geometry_b64()
            if text != self.settings.get("qt_geometry"):
                self.settings.set("qt_geometry", text)
                self._save_soon()
        if visible or force:
            q.show_model(overview.overview_model(self, now, IS_WIN), getattr(self, "_thumb_src", None), self._qt_tip)

    def _qt_hwnd(self) -> int:
        return self.qt.hwnd() if self.qt is not None and IS_WIN else 0

    def _main_hwnd(self) -> int:
        """Owner of prompts (UAC): the window the user sees."""
        if self.qt is not None and self.qt.isVisible():
            return self._qt_hwnd()
        return self._root_hwnd()

    def _qt_close(self):
        """On quit: remember the size, then really close."""
        if self.qt is None:
            return
        try:
            self.settings.set("qt_geometry", self.qt.geometry_b64())
            self.qt.allow_close = True
            self.qt.close()
            self._qt_pump()
        except Exception:
            log.error("Qt: %s", traceback.format_exc())
