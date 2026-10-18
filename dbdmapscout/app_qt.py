"""Mixin of App: the Qt control window (since 1.51; since 1.57 the only one – Tk is gone).

The tabs and dialogs are a UI model (uimodel.py) built by the App; the Qt window draws them. Pages are either
hand-made (qt_window.SPECS, widgets named with ``_reg``) or built from a tab's structure (``ui_layout``, AUTO_PAGES).
``_qt_refresh`` pushes the state (from ``_tick_overlay``, 4×/s), clicks arrive as ("ui", action, arg) in
``self.events`` and are done on the model (``_qt_event`` from ``_poll``).
"""
from __future__ import annotations

import logging
import os
import time
import traceback

from PIL import Image

from . import __version__, history, official, overview, tooltip
from . import uimodel as ui
from .capture import IS_WIN
from .i18n import _
from .mainloop import MainLoop

log = logging.getLogger("dbdmapscout")

WARM_AFTER_MS = 1500                 # 1.3.4: pages laid out once after the start
GEOMETRY_DELAY = 1.0          # s after the last move/resize before the size is saved
QT_HOTKEYS = {"scan": "scan_now", "reject": "reject_map"}
PREVIEW_PX = 900              # map preview on the maps page: picture scaled to fit this box first


def ui_shown(w) -> bool:
    """The widget and all its frames up to the tab or the dialog are placed (a row hidden with pack_forget is not)."""
    while w is not None and not isinstance(w, (ui.Notebook, ui.Toplevel)):
        if not w.winfo_exists() or not w.winfo_manager():
            return False
        w = w.master
    return True


def _side(w) -> str:
    try:
        return str(w.pack_info().get("side", "top"))
    except ui.UIError:                         # not packed (yet): shown later like a line of its own
        return "top"


KINDS = ((ui.Treeview, "table"), (ui.Checkbutton, "check"), (ui.Button, "button"), (ui.Combobox, "combo"),
         (ui.Scale, "slider"), (ui.Entry, "entry"), (ui.Radiobutton, "radio"), (ui.Log, "log"),
         (ui.Chart, "chart"), (ui.Dashboard, "dashboard"), (ui.Tiles, "tiles"),
         (ui.Preview, "preview"), (ui.Swatches, "swatches"), (ui.Host, "host"))


def ui_layout(w, reg: dict):
    """The structure of a tab (or dialog) as nested nodes for the Qt window: {"kind", "key", "children", "side",
    ...}. Every node's key (the widget's path) goes into ``reg`` – the widgets the Qt page may read and press."""
    key = str(w)
    if isinstance(w, ui.Notebook):
        reg[key] = w
        pages = [w.nametowidget(t) for t in w.tabs()]
        try:                                    # packed to fill: the tabs take the page's height (statistics)
            fill = bool(w.pack_info().get("expand"))
        except ui.UIError:
            fill = False
        return {"kind": "tabs", "key": key, "fill": fill,
                "children": [n for n in (ui_layout(p, reg) for p in pages) if n]}
    kind = next((k for cls, k in KINDS if isinstance(w, cls)), None)
    if kind is None and isinstance(w, ui.Label):
        style = str(w.cget("style"))
        kind = ("image" if hasattr(w, "_dbdms_pil") else "big" if style == "Big.TLabel"
                else "hint" if style == "Dim.TLabel" else "label")
    if kind is not None:
        reg[key] = w
        node = {"kind": kind, "key": key, "side": _side(w)}
        if isinstance(w, ui.Treeview):           # packed without expand: as tall as its rows (server regions)
            try:
                node["fit"] = not w.pack_info().get("expand")
            except ui.UIError:
                node["fit"] = False
        return node
    nodes = []
    grid = False
    for c in w.winfo_children():
        if getattr(c, "_dbdms_slider_part", False):    # name/value of a _slider row: part of the slider control
            continue
        n = ui_layout(c, reg)
        if n is not None:
            n["side"] = _side(c)                    # how this child sits in this frame
            if c.winfo_manager() == "grid":         # e.g. the game languages: a grid of check boxes
                info = c.grid_info()
                n["cell"] = (int(info.get("row", 0)), int(info.get("column", 0)))
                n["span"] = max(1, int(info.get("columnspan", 1) or 1))          # 1.8.8: a hint below two cells
                sticky = str(info.get("sticky", ""))
                n["wide"] = "w" in sticky and "e" in sticky                       # stretched across its column
                grid = True
            nodes.append(n)
    if not nodes:
        return None
    reg[key] = w
    kind = "card" if isinstance(w, ui.LabelFrame) else "box"
    return {"kind": kind, "key": key, "side": _side(w), "children": nodes, "grid": grid,
            "row": not grid and any(n["side"] in ("left", "right") for n in nodes)}


def ui_state(w) -> dict:
    """What a Qt control needs to show a widget of the UI model (text, value, enabled, shown)."""
    st = {"visible": ui_shown(w)}
    lines = getattr(w, "_dbdms_lines", None)
    if lines is not None:                         # the log: its entries (ts, category, text), filtered
        entries, dark = lines()
        st.update(lines=entries, dark=dark, rev=getattr(w, "_dbdms_rev", 0))
        return st
    if isinstance(w, ui.Preview):
        st.update(data=w.source())
        return st
    if isinstance(w, ui.Host):
        return st
    if isinstance(w, ui.Swatches):
        st.update(values=[tuple(v) for v in w.values], current=w.current, dark=w.dark)
        return st
    if isinstance(w, ui.Tiles):
        st.update(data=w.data)
        return st
    if isinstance(w, ui.Dashboard):
        st.update(data=w.data, dark=w.dark)
        return st
    chart = getattr(w, "_dbdms_chart", None)
    if chart is not None:
        st.update(data=chart.data, dark=chart.dark, panels=chart.panels)
        return st
    if isinstance(w, ui.Notebook):
        st.update(tabs=[str(w.tab(t, "text")) for t in w.tabs()], index=w.index("current") if w.tabs() else 0)
        return st
    if isinstance(w, ui.Treeview):
        show = str(w.cget("show"))
        cols = [("#0", str(w.heading("#0", "text")), str(w.heading("#0", "anchor")))] if "tree" in show else []
        cols += [(c, str(w.heading(c, "text")), str(w.heading(c, "anchor"))) for c in w.cget("columns")]
        rows = w.rows()
        tags = {tag for r in rows for tag in r[4]}
        colours = {}
        for tag in tags:
            fg = str(w.tag_configure(tag, "foreground") or "")
            if fg:
                colours[tag] = fg
        stretch = next((i for i, c in enumerate(cols) if w.column(c[0], "stretch")), 0)   # e.g. the map name
        widths = [int(w.column(c[0], "width") or 0) for c in cols]
        st.update(columns=cols, rows=rows, selection=list(w.selection()), colours=colours, stretch=stretch,
                  widths=widths,
                  selectable=str(w.cget("selectmode")) != "none" or hasattr(w, "_dbdms_click"),
                  multi=str(w.cget("selectmode")) == "extended",          # 1.5.4: several rows at once
                  menu=hasattr(w, "_dbdms_menu"))                         # 1.8.10: right-click actions
        return st
    if isinstance(w, ui.Scale):
        value = w.get()
        st.update(value=value, lo=float(w.cget("from") or 0), hi=float(w.cget("to") or 100),
                  label=getattr(w, "_dbdms_label", ""), text=getattr(w, "_dbdms_fmt", "{:.0f}").format(value))
        return st
    if isinstance(w, (ui.LabelFrame, ui.Label, ui.Button, ui.Checkbutton, ui.Radiobutton)):
        st["text"] = w.cget("text")
    if hasattr(w, "_dbdms_pil"):                  # a picture (dialog previews): the PIL image itself
        st["pil"] = w._dbdms_pil
    if isinstance(w, (ui.Button, ui.Checkbutton, ui.Radiobutton, ui.Combobox, ui.Entry)):
        st["enabled"] = not w.instate(["disabled"])
        tip = getattr(w, "_dbdms_tip", None)
        st["tip"] = tip() if tip is not None else ""
    rec = getattr(w, "_dbdms_recording", None)
    if rec is not None:
        st["recording"] = bool(rec())
    if isinstance(w, (ui.Checkbutton, ui.Radiobutton)):
        st["value"] = w.instate(["selected"])
    elif isinstance(w, ui.Combobox):
        st.update(value=w.get(), values=[str(v) for v in w.cget("values") or ()], editable=w.editable())
    elif isinstance(w, ui.Entry):
        st["value"] = w.get()
        st["placeholder"] = getattr(w, "_dbdms_placeholder", "")      # 1.2.19 (the log's search field)
        st["secret"] = bool(getattr(w, "_dbdms_secret", False))        # 1.4: shown as dots (OBS password)
    return st


def ui_act(w, value=None):
    """A click/choice from the Qt window, done on the model widget – its own command runs as if clicked."""
    if isinstance(w, ui.Checkbutton):
        if value is None or bool(value) != w.instate(["selected"]):
            w.invoke()
    elif isinstance(w, (ui.Button, ui.Radiobutton)):
        w.invoke()
    elif isinstance(w, ui.Combobox):
        if w.instate(["disabled"]):
            return
        if value in [str(v) for v in w.cget("values") or ()]:
            w.set(value)
            w.event_generate("<<ComboboxSelected>>")
        elif w.editable():                        # typed into an editable choice (e.g. a new realm)
            w.set(str(value))
    elif isinstance(w, ui.Entry):
        if not w.instate(["disabled"]) and w.get() != str(value):
            w.delete(0, "end")
            w.insert(0, str(value))
    elif isinstance(w, (ui.Preview, ui.Swatches, ui.Dashboard)):
        if w.command is not None:
            w.command(value)
    elif isinstance(w, ui.Scale):
        w.set(float(value))                       # runs the slider's command (label + setting)
    elif isinstance(w, ui.Notebook):
        tabs = w.tabs()
        if isinstance(value, int) and 0 <= value < len(tabs):
            w.select(tabs[value])
    elif isinstance(w, ui.Treeview):
        what, arg = value
        if what == "sort":
            cmd = w.heading(arg, "command")
            if callable(cmd):
                cmd()
        elif what == "click" and w.exists(arg):
            click = getattr(w, "_dbdms_click", None)
            if click is not None:
                click(arg)
            elif str(w.cget("selectmode")) != "none":
                w.selection_set(arg)
                w.focus(arg)
                w.event_generate("<<TreeviewSelect>>")
        elif what == "select":                            # 1.5.4: the whole selection of a multi-select table
            w.selection_set([i for i in (arg or []) if w.exists(i)])
            w.event_generate("<<TreeviewSelect>>")
        elif what == "menu":                              # 1.8.10: right click on a row (marked before)
            menu = getattr(w, "_dbdms_menu", None)
            if menu is not None:
                menu(tuple(arg))


class QtShell:
    def _context_menu(self, items, pos, act):
        """1.8.10: a right-click menu at screen ``pos``: ``items`` = [(id, label, enabled[, checked]) or None for a
        line]; the picked id goes to ``act(id)``."""
        self._menu_act = act
        if self.qt is not None and items:
            self.qt.popup_menu(items, pos)

    def _table_menu(self, tree, items, act):
        """Give a model table right-click actions: ``items()`` builds the menu for the marked rows, ``act(id)``."""
        tree._dbdms_menu = lambda pos: self._context_menu(items(), pos, act)

    def _reg(self, key, widget):
        """Name a widget for the Qt window's hand-made pages (qt_window.SPECS use these keys)."""
        self.__dict__.setdefault("_qt_reg", {})[key] = widget
        return widget

    def _qt_init(self):
        """Before anything else: the Qt application and the main loop (timers) on it."""
        from . import qt_window
        self._qt_mod = qt_window
        self.qapp = qt_window.application()
        self.root = MainLoop(self.qapp, on_error=lambda text: self._report_once("Timer", text))
        self.qt = None
        self._qt_geo_due = 0.0
        self._qt_auto = {}                  # widget path -> widget of the pages built from the tabs
        self._qt_dialogs = {}               # dialog path -> (Toplevel, its keys)
        self._qt_question = None            # (title, text, retry | None) shown as a bar in the Qt window

    def _qt_build(self, start_in_tray: bool):
        ico = os.path.join(self.root_dir, "dbdmapscout.ico")
        self._qt_auto = {}
        layouts = {key: ui_layout(getattr(self, f"tab_{key}"), self._qt_auto) for key in self._qt_mod.AUTO_PAGES}
        self.qt = self._qt_mod.MainWindow(self._qt_post, ico if os.path.exists(ico) else None, layouts)
        self.qt.setWindowTitle(f"DbD Map Scout {__version__}")
        self._qt_theme()
        # first start: the setup assistant (language, overlay, keys) instead of the overview
        first = not self.settings.get("welcome_seen") and not self.settings.get("qt_geometry")
        self.qt.restore_b64(self.settings.get("qt_geometry") or "")
        if first:
            self.qt.show_setup(True)
        self.qt.set_card_order(self.settings.get("card_order") or {})
        self.qt.set_tab_order(self.settings.get("tab_order") or {})              # 1.7.6
        self.qt.set_nav_order(self.settings.get("nav_order") or [])
        self.qt.set_hidden_columns(self.settings.get("hidden_columns") or {})
        self._qt_refresh(force=True)
        if not start_in_tray:
            self.qt.show()
        elif not self.tray.active:
            self.qt.showMinimized()
        self.root.after(WARM_AFTER_MS, self._qt_warm)

    def _qt_warm(self):
        """1.3.4: every page filled and laid out once while nothing happens, so the first visit is as quick as the
        next ones (measured: settings 112 → ~11 ms)."""
        if self.qt is None or self._quitting:
            return
        try:
            reg, auto = self.__dict__.get("_qt_reg", {}), self._qt_auto
            for page, form in self.qt.forms.items():
                src = auto if page in self._qt_mod.AUTO_PAGES else reg
                self.qt.show_states(page, {k: ui_state(src[k]) for k in form.controls if k in src})
            self.qt.warm_pages()
        except Exception:
            log.debug("warm pages", exc_info=True)

    def _ask(self, title, text, retry, parent=None) -> bool:
        """OK/Cancel before something that cannot be undone: a bar at the top of the window (no modal dialog –
        it would stop the timers); OK runs ``retry`` again, which then gets True here."""
        if getattr(self, "_confirmed", False):
            self._confirmed = False
            return True
        self._qt_question = (title, text, retry)
        if self.qt is not None:
            self.qt.bring_to_front()
            self._qt_refresh(force=True)
        return False

    def _inform(self, title, text):
        self._qt_question = (title, text, None)
        if self.qt is not None:
            self._qt_refresh(force=True)

    def _dialog(self, dlg):
        """End of building a dialog (UI model): the Qt window shows it, built from its content; closing it
        (X, Esc) destroys the model too."""
        reg = {}
        kids = [n for n in (ui_layout(c, reg) for c in dlg.winfo_children()) if n]
        node = {"kind": "box", "key": str(dlg), "children": kids, "row": False, "grid": False, "side": "top"}
        self._qt_auto.update(reg)
        self._qt_dialogs[str(dlg)] = (dlg, list(reg))
        if self.qt is not None:
            self.qt.open_dialog(str(dlg), dlg.title(), node)
            self._qt_refresh(force=True)

    def _qt_dialog_tick(self):
        for key, (dlg, keys) in list(self._qt_dialogs.items()):
            if not dlg.winfo_exists():                    # closed by the program (saved, cancelled)
                del self._qt_dialogs[key]
                for k in keys:
                    self._qt_auto.pop(k, None)
                self.qt.close_dialog(key)
                continue
            self.qt.show_dialog_states(key, {k: ui_state(self._qt_auto[k]) for k in keys if k in self._qt_auto})

    def _qt_file(self, mode, title, initial, callback, pattern="JSON (*.json)"):
        """Ask for a file (Qt's own non-modal dialog); ``callback(path)`` runs once one is chosen."""
        self._qt_file_cb = callback
        if self.qt is not None:
            self.qt.choose_file(mode, title, initial, pattern)

    def _qt_answer(self, ok: bool):
        q, self._qt_question = getattr(self, "_qt_question", None), None
        if q is not None and ok and q[2] is not None:
            self._confirmed = True
            try:
                q[2]()
            finally:
                self._confirmed = False

    def _qt_post(self, action, arg=None):
        """Called from Qt slots: the click is handled in _poll (one place, in order with the other events)."""
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
            if w is None or key not in self._qt_mod.page_keys():
                w = self._qt_auto.get(key)               # pages and dialogs built from the model
            if w is not None and ui_shown(w):
                ui_act(w, value)
        elif action == "answer":
            self._qt_answer(bool(arg))
        elif action == "menu_act":                       # 1.8.10: a line of a context menu was picked
            act = getattr(self, "_menu_act", None)
            if act is not None:
                act(arg)
        elif action == "hk_record":
            self._hk_begin(arg.split(".", 2)[2])         # "st.hk.<name>"
        elif action == "hk_key":
            key, mods, keysym, keycode = arg
            self._hk_qt_key(key.split(".", 2)[2], mods, keysym, keycode)
        elif action == "hk_cancel":
            if self._hk_rec == arg.split(".", 2)[2]:
                self._hk_stop(save=False)
        elif action == "hk_menu":                    # 1.2.19: right click on a hotkey button
            self._hk_set(arg[0].split(".", 2)[2], arg[1])
        elif action == "dlg_close":
            entry = self._qt_dialogs.get(arg)
            if entry is not None:
                entry[0].destroy()
        elif action == "file":
            cb, self._qt_file_cb = getattr(self, "_qt_file_cb", None), None
            if cb is not None and arg:
                cb(arg)
        elif action == "page":
            tab = getattr(self, f"tab_{arg}", None)
            if tab is not None and self.nb.select() != str(tab):
                self.nb.select(tab)                  # its "opened" work runs (statistics computed, pings …)
            if arg == "log":
                self._log_alert = False
        elif action == "undo":                       # Ctrl+Z on the overlay page (1.65)
            self.undo_layout()
        elif action == "map_style":                  # 1.3.3: the buttons on the maps page
            self._set_map_style(str(arg or "classic"))
        elif action == "search":
            self._qt_search = str(arg or "")
            self._qt_maps_rev = getattr(self, "_qt_maps_rev", 0) + 1
            self._fill_list()
        elif action == "search_open":                # the search reads the texts of all pages: fill them now
            reg, auto = self.__dict__.get("_qt_reg", {}), self._qt_auto
            for page, form in self.qt.forms.items():
                src = auto if page in self._qt_mod.AUTO_PAGES else reg
                self.qt.show_states(page, {k: ui_state(src[k]) for k in form.controls if k in src})
            self.qt.update_search_index()
        elif action == "setup_done":                 # assistant finished or skipped: not again on the next start
            self.settings.set("welcome_seen", True)
            self._save_soon()
            self.qt.show_setup(False)
            self._qt_refresh(force=True)
        elif action == "table_cols":                 # 1.3.6: columns hidden by a right-click on a table's heading
            key, cols = arg
            hidden = dict(self.settings.get("hidden_columns") or {})
            if cols:
                hidden[str(key)] = [str(c) for c in cols]
            else:
                hidden.pop(str(key), None)
            self.settings.set("hidden_columns", hidden)
            self._save_soon()
        elif action == "card_order":                 # a card dragged to another place: remember the order
            page, run, ids = arg
            orders = dict(self.settings.get("card_order") or {})
            orders[str(page)] = dict(orders.get(str(page)) or {}, **{str(run): [str(i) for i in ids]})
            self.settings.set("card_order", orders)
            self._save_soon()
        elif action == "tab_order":                  # 1.7.6: a tab dragged along its row
            page, tabs_id, ids = arg
            orders = dict(self.settings.get("tab_order") or {})
            orders[str(page)] = dict(orders.get(str(page)) or {}, **{str(tabs_id): [str(i) for i in ids]})
            self.settings.set("tab_order", orders)
            self._save_soon()
        elif action == "nav_order":                  # 1.7.6: a page dragged in the navigation
            self.settings.set("nav_order", [str(k) for k in arg])
            self._save_soon()
        elif action == "map_preview":
            mid, v = arg
            self._qt_preview_sel = (mid, int(v))
        elif action == "show_map":
            mid, v = arg
            if mid in self.catalog.maps:
                self.show_map(mid, int(v), "manual")
        elif action == "add_picture":
            self.add_picture()
        elif action == "assign":
            self.assign_unknown()
        elif action == "picture":
            self.add_picture(from_unknown=True)
        elif action == "dismiss_unknown":
            self._hide_unknown()
        elif action == "choose":                     # overview without a map: to the maps page
            self.qt.show_page("maps")
        elif action == "map_action":                 # 1.2.18: right click on a map tile
            name, (mid, v) = arg
            if name == "show":
                self.show_map(mid, v, "manual")
            elif name == "rotate":
                self.rotate_map(mid)
            elif name == "size_reset":
                self._reset_map_size(mid)
            elif name == "picture":
                from .picturedlg import PictureDialog
                self._picture_from_unknown = False
                PictureDialog(self, "", "", map_id=mid, variant=v)
        elif action == "server_page":                # 1.2.15: "Server aus" on the overview → the server tab
            self.qt.show_page("server")
        elif action == "official_setup":             # 1.2.15: "noch keine Stats-Daten" → the card under "Mehr"
            self._reveal_official()
        elif action == "rec_setup":                  # 1.4.2: tile "Aufnahmen" without a folder/drive
            self._reveal_rec()
        else:
            {"scan": self.scan_now, "rotate": self.rotate_map, "toggle": self.toggle_overlay,
             "power": self.toggle_overlay_master,
             "reject": self.reject_detection, "confirm": self._confirm_unsure, "layout": self.next_variant,
             "floor": self.next_floor}.get(action, lambda: None)()
        self._qt_refresh(force=True)

    def _reveal_official(self):
        """Settings → "Mehr" opened → the card "Offizielle Match-Daten" scrolled into view and lit up."""
        self.qt.show_page("settings")
        if not self._more_open:
            self._toggle_more()
        self._qt_refresh(force=True)
        self.qt.reveal("settings", "st.more.official")

    def _show_main(self):
        """Tray "Öffnen"."""
        if self.qt is not None:
            self.qt.bring_to_front()

    def _qt_theme(self):
        if self.qt is not None:
            self._qt_mod.qt_theme.set_theme(str(self.settings.get("color_theme", "gold")),
                                            bool(self.settings.get("oled_black", False)),
                                            self.settings.get("accent_custom"))
            self.qt.apply_theme(bool(self.settings.get("dark_mode", True)), float(self.settings.get("ui_zoom", 1.0)))

    def _qt_tip(self, key, label):
        tip = self._button_tip(key)
        if tip is not None:
            return tip
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
        else:
            q.show_log_alert(bool(getattr(self, "_log_alert", False)))
        if page == "maps":
            sel = getattr(self, "_qt_preview_sel", None) or self.current
            rev = (getattr(self, "_qt_maps_rev", 0), id(self.catalog), self.current, sel,
                   self.settings["overlay"].get("map_style", "classic"))
            if force or rev != getattr(self, "_qt_maps_shown", None):
                self._qt_maps_shown = rev
                items = self._qt_map_items()
                q.show_maps(items, self.current, self._qt_preview(sel), self._qt_thumbs(items), self._qt_recent(),
                            self._qt_marks(items), self.settings["overlay"].get("map_style", "classic"))
        reg = self.__dict__.get("_qt_reg", {})
        keys = self._qt_mod.page_keys(page)
        if keys:
            q.show_states(page, {k: ui_state(reg[k]) for k in keys if k in reg})
        elif page in self._qt_mod.AUTO_PAGES:
            q.show_states(page, {k: ui_state(self._qt_auto[k]) for k in q.visible_keys(page) if k in self._qt_auto})
        self._qt_dialog_tick()
        qq = self._qt_question
        q.show_question(None if qq is None else (qq[0], qq[1], qq[2] is not None))

    def _qt_preview(self, sel):
        """(map_id, variant, name, realm, picture) of the map selected on the maps page (the shown map before a
        click), the picture as a small PIL image – only the first frame (Midwich: the bottom floor)."""
        if not sel or sel[0] not in self.catalog.maps:
            return None
        mid, v = sel[0], int(sel[1])
        cached = getattr(self, "_qt_preview_cache", None)
        if cached is not None and cached[0] == (mid, v, id(self.catalog)):
            return cached[1]
        m = self.catalog.maps[mid]
        path, shown = self._map_file(mid, v)
        pic = None
        if path:
            try:
                with Image.open(path) as im:
                    im.seek(0)
                    pic = im.convert("RGBA")
                pic.thumbnail((PREVIEW_PX, PREVIEW_PX))
            except (OSError, ValueError) as e:
                self._log(_("Kartenbild nicht lesbar: {error}", error=e), "Fehler")
        realm = self.catalog.realm_display(m) or _("Eigene Bilder")
        out = (mid, shown, m.label(shown), realm, pic)
        self._qt_preview_cache = ((mid, v, id(self.catalog)), out)
        return out

    def _qt_thumbs(self, items):
        """{(map_id, variant): picture path} for the tiles – the dark picture only if already made (no waiting)."""
        style = self.settings["overlay"].get("map_style", "classic")
        cached = getattr(self, "_qt_thumbs_cache", None)
        if cached is None or cached[0] is not self.catalog or cached[1] != style:
            cached = self._qt_thumbs_cache = (self.catalog, style, {})
        out, paths = cached[2], {}
        for _r, _l, mid, v in items:
            path = out.get((mid, v))
            if path is None:
                path = self._map_file(mid, v, make=False)[0]
                if style == "classic" or path != self.catalog.image_path(mid, v)[0]:
                    out[(mid, v)] = path           # the original in the dark style: the warm-up may still make it
            paths[(mid, v)] = path
        return paths

    def _qt_marks(self, items):
        """1.2.18: {(map_id, variant): (info line, tooltip, has own values)} for the tiles – rounds and Ø kills
        from the history, and the map's own size / rotation / picture (settings, user_maps/)."""
        j = self._joined()
        cache = getattr(self, "_qt_map_stats", None)
        if cache is None or cache[0] is not j:
            stats = {}
            for r in j.rounds:
                if not history.normal(r):            # custom games and farming rounds are no record
                    continue
                n, kills = stats.get(r.map, (0, []))
                m = j.off.get(id(r))
                k = official.kills(m) if m is not None else None
                stats[r.map] = (n + 1, kills + ([k] if k is not None else []))
            cache = self._qt_map_stats = (j, stats)
        o = self.settings["overlay"]
        heights, rots = o.get("map_heights") or {}, o.get("map_rotations") or {}
        out = {}
        for _realm, label, mid, v in items:
            parts, tips = [], []
            n, kills = cache[1].get(label, (0, []))
            if n:
                parts.append(_("{n} Runden", n=n) + (" · " + _("Ø {kills} Kills", kills=f"{sum(kills) / len(kills):.1f}")
                                                     if kills else ""))
            own = []
            if heights.get(mid):
                own.append(_("Grösse {pct} %", pct=f"{heights[mid] * 100:.0f}"))
            if rots.get(mid):
                own.append(f"{rots[mid]}°")
            if self.catalog.is_own(mid, v):
                own.append(_("eigenes Bild"))
            if own:
                parts.append(" · ".join(own))
                tips.append(_("Eigene Einstellungen dieser Map: {what}", what=", ".join(own)))
            if parts or own:
                out[(mid, v)] = (" · ".join(parts), "\n".join([" · ".join(parts)] + tips), bool(own))
        return out

    def _qt_recent(self, kept=12):
        """Map ids of the rounds played last, newest first, each once (the list entry "Zuletzt gespielt")."""
        out = []
        for r in sorted(self._joined().rounds, key=lambda r: r.t, reverse=True):
            if r.map_id in self.catalog.maps and r.map_id not in out:
                out.append(r.map_id)
                if len(out) >= kept:
                    break
        return out

    def _qt_map_items(self):
        """[(realm, label, map_id, variant)] (search with the catalog's own matching)."""
        out = []
        for m in self.catalog.search(getattr(self, "_qt_search", "")):
            realm = self.catalog.realm_display(m) or _("Eigene Bilder")
            for v in [v for v in sorted(m.variants) if m.variants[v]]:
                out.append((realm, m.label(v) if len(m.variants) > 1 else m.name, m.id, v))
        return out

    def _qt_hwnd(self) -> int:
        return self.qt.hwnd() if self.qt is not None and IS_WIN else 0

    _main_hwnd = _qt_hwnd                   # owner of prompts (UAC)
    _root_hwnd = _qt_hwnd

    def _qt_close(self):
        """On quit: remember the size, then really close."""
        if self.qt is None:
            return
        try:
            self.settings.set("qt_geometry", self.qt.geometry_b64())
            self.qt.allow_close = True
            self.qt.close()
        except Exception:
            log.error("Qt: %s", traceback.format_exc())
