"""Mixin of App: the Qt control window (setting ``ui_toolkit`` = "qt", since 1.51; stage 1 of the move to Qt).

The Tk App stays the controller and Tk's mainloop the main loop; its window is hidden and only opened for the
pages that are not in Qt yet. Qt is driven from here: ``_qt_refresh`` pushes the state (from ``_tick_overlay``),
button clicks arrive as ("ui", action, arg) in ``self.events`` (``_qt_event`` from ``_poll``). See qt_window.py
for why Qt code never calls Tk directly.
"""
from __future__ import annotations

import gc
import logging
import os
import time
import tkinter as tk
import traceback
from tkinter import ttk

from . import overview, tooltip
from .capture import IS_WIN
from .i18n import _

log = logging.getLogger("dbdmapscout")

GEOMETRY_DELAY = 1.0          # s after the last move/resize before the size is saved
GC_FULL_EVERY = 100           # polls (≈5 s) between full garbage collections in Qt mode
QT_TIPS = {"toggle": "toggle_btn", "layout": "layout_btn", "rotate": "rotate_btn", "floor": "floor_btn"}
QT_HOTKEYS = {"scan": "scan_now", "reject": "reject_map"}


def tk_shown(w) -> bool:
    """The widget and all its frames up to the tab are placed (a row hidden with pack_forget is not)."""
    while w is not None and not isinstance(w, ttk.Notebook):
        try:
            if not w.winfo_manager():
                return False
        except tk.TclError:
            return False
        w = w.master
    return True


def tk_state(w) -> dict:
    """What a Qt control needs to mirror a Tk widget (text, value, enabled, shown). Tk context only."""
    st = {"visible": tk_shown(w)}
    if isinstance(w, ttk.Scale):
        value = float(w.get())
        st.update(value=value, lo=float(w.cget("from")), hi=float(w.cget("to")),
                  label=getattr(w, "_dbdms_label", ""), text=getattr(w, "_dbdms_fmt", "{:.0f}").format(value))
        return st
    if isinstance(w, (ttk.LabelFrame, ttk.Label, ttk.Button, ttk.Checkbutton)):
        st["text"] = str(w.cget("text"))
    if isinstance(w, (ttk.Button, ttk.Checkbutton, ttk.Combobox, ttk.Entry)):
        st["enabled"] = not w.instate(["disabled"])
        tip = getattr(w, "_dbdms_tip", None)
        st["tip"] = tip._text() if tip is not None else ""
    if isinstance(w, ttk.Checkbutton):
        st["value"] = w.instate(["selected"])
    elif isinstance(w, ttk.Combobox):
        st.update(value=w.get(), values=[str(v) for v in w.cget("values")])
    elif isinstance(w, ttk.Entry):
        st["value"] = w.get()
    return st


def tk_act(w, value=None):
    """A click/choice from the Qt window, done on the Tk widget – its own command runs as if clicked there."""
    if isinstance(w, ttk.Checkbutton):
        if value is None or bool(value) != w.instate(["selected"]):
            w.invoke()
    elif isinstance(w, ttk.Button):
        w.invoke()
    elif isinstance(w, ttk.Combobox):
        if value in [str(v) for v in w.cget("values")]:
            w.set(value)
            w.event_generate("<<ComboboxSelected>>")
    elif isinstance(w, ttk.Scale):
        w.set(float(value))                       # runs the scale's command (label + setting)


class QtShell:
    def _reg(self, key, widget):
        """Name a Tk control for the Qt window (qt_window page specs use these keys)."""
        self.__dict__.setdefault("_qt_reg", {})[key] = widget
        return widget

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
            # A collection inside a Qt slot would run finalizers of Tk variables/images there (= tkinter from
            # Tcl's message loop, see qt_window.py): collect only from _poll, a Tk callback.
            gc.disable()
            self._gc_polls = 0
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
            if self.qt is not None and self.qt.isMinimized() and self.tray.active and self.settings.get("tray", True):
                self.qt.hide()
            return
        if action == "act":
            key, value = arg
            w = self.__dict__.get("_qt_reg", {}).get(key)
            if w is not None and key in self._qt_mod.page_keys() and tk_shown(w):
                tk_act(w, value)
        elif action == "search":
            self._qt_search = str(arg or "")
            self._qt_maps_rev = getattr(self, "_qt_maps_rev", 0) + 1
        elif action == "show_map":
            mid, v = arg
            if mid in self.catalog.maps:
                self.show_map(mid, int(v), "manual")
        elif action == "add_picture":
            self._show_window()                  # a Tk dialog (hidden window: invisible)
            self.add_picture()
        elif action == "tab":
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
        if key == "settings_more":                # the rarely needed part of the settings stays in Tk for now
            key = "settings"
            if not self._more_open:
                self._toggle_more()
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
        """From _poll (a Tk callback). Windows: Tcl's loop already delivers Qt's window messages – only Qt's posted
        events here; processEvents() would also take Tk's messages (a press on the Tk title bar would start
        Windows' move loop inside this callback, where Tk runs its timers → Python aborts). Elsewhere Tk's loop
        does not see Qt at all: processEvents(). Also the garbage collection (see _qt_early)."""
        if self.qapp is None:
            return
        try:
            if IS_WIN:
                self.qapp.sendPostedEvents()
            else:
                self.qapp.processEvents()
        except Exception:
            self._report_once("Qt", traceback.format_exc())
        self._gc_polls += 1
        gc.collect(2 if self._gc_polls % GC_FULL_EVERY == 0 else 0)

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
        if not (visible or force):
            return
        page = q.current_key()
        if page == "overview":
            q.show_model(overview.overview_model(self, now, IS_WIN), getattr(self, "_thumb_src", None), self._qt_tip)
        elif page == "maps":
            rev = (getattr(self, "_qt_maps_rev", 0), id(self.catalog), self.current)
            if force or rev != getattr(self, "_qt_maps_shown", None):
                self._qt_maps_shown = rev
                q.show_maps(self._qt_map_items(), self.current)
        reg = self.__dict__.get("_qt_reg", {})
        keys = self._qt_mod.page_keys(page)
        if keys:
            q.show_states(page, {k: tk_state(reg[k]) for k in keys if k in reg})

    def _qt_map_items(self):
        """[(realm, label, map_id, variant)] like the Tk list (search with the catalog's own matching)."""
        out = []
        for m in self.catalog.search(getattr(self, "_qt_search", "")):
            realm = self.catalog.realm_display(m) or _("Eigene Bilder")
            for v in [v for v in sorted(m.variants) if m.variants[v]]:
                out.append((realm, m.label(v) if len(m.variants) > 1 else m.name, m.id, v))
        return out

    def _qt_hwnd(self) -> int:
        return self.qt.hwnd() if self.qt is not None and IS_WIN else 0

    def _main_hwnd(self) -> int:
        """Owner of prompts (UAC): the window the user works in – the Tk window when it is open (Server tab)."""
        if self.qt is not None and self.qt.isVisible() and self.root.state() not in ("normal", "zoomed"):
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
