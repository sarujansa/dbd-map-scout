"""Control window (Tk) + overlay + hotkeys, glued together."""
from __future__ import annotations

import collections
import logging
import os
import queue
import re
import sys
import threading
import time
import tkinter as tk
import traceback
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from . import __version__, history, i18n, layout, regions, theme, tooltip
from .capture import IS_WIN, describe_window, find_game_window, foreground_root, is_game_window
from .catalog import Catalog
from .config import Settings
from . import autostart
from .connwatch import ConnectionWatch, IdlePause, is_admin
from .i18n import N_, _
from .hotkeys import HotkeyThread, combo_from_keys, modifier_name, pretty
from .overlay import load_frames
from .overlay_win32 import make_overlay
from .roundtimer import RoundTimer
from .status import DOT_STYLE, user_state
from .textnorm import fmt_duration, fold, roman
from .worker import DetectionWorker

LANGS = [("en", "EN"), ("de", "DE"), ("fr", "FR"), ("es", "ES"), ("es-MX", "ES-MX"), ("it", "IT"),
         ("pl", "PL"), ("pt-BR", "PT"), ("tr", "TR")]
ANCHORS = [("auto", N_("automatisch")), ("top-left", N_("oben links")), ("top-right", N_("oben rechts")),
           ("bottom-left", N_("unten links")), ("bottom-right", N_("unten rechts")), ("custom", N_("eigene Position"))]
HOTKEY_LABELS = [("toggle_overlay", N_("Overlay ein/aus")), ("next_variant", N_("Layout-Variante")),
                 ("scan_now", N_("Bildschirm scannen")), ("prev_map", N_("Vorherige Map")),
                 ("next_map", N_("Nächste Map")), ("bigger", N_("Grösser")), ("smaller", N_("Kleiner")),
                 ("edit_position", N_("Mit Maus verschieben")), ("rotate_map", N_("Karte drehen"))]
CATS = [N_("Erkennung"), N_("Overlay"), N_("System"), N_("Fehler")]
STATS_PERIODS = [("all", N_("Alle")), ("day", N_("Heute")), ("week", N_("Diese Woche")), ("month", N_("Dieser Monat")),
                 ("year", N_("Dieses Jahr"))]      # log categories (keys; shown translated)


def anchor_label(key: str) -> str:
    return _(dict(ANCHORS).get(key, "automatisch"))

log = logging.getLogger("dbdmapscout")


class App:
    def __init__(self, root_dir: str, simulate: str | None = None, start_in_tray: bool = False):
        self.root_dir = root_dir
        self.simulate = simulate
        self.settings = Settings(os.path.join(root_dir, "settings.json"))
        i18n.set_language(self.settings.get("ui_language", "auto"))
        self.catalog = Catalog(root_dir, self.settings["languages"], self.settings.get("user_aliases"))
        self._unknown = None             # (name text, realm text) of the last banner that matched no map
        self.events: queue.Queue = queue.Queue()

        self.root = tk.Tk()
        self.root.title(f"DbD Map Scout {__version__}")
        ico = os.path.join(root_dir, "dbdmapscout.ico")        # made by verknuepfung_erstellen.bat
        if IS_WIN and os.path.exists(ico):
            try:
                self.root.iconbitmap(default=ico)
            except tk.TclError:
                pass
        self.root.minsize(470, 420)                  # tabs scroll when the window is small
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.report_callback_exception = self._tk_error

        self.current = None            # (map_id, variant)
        self.source = None             # "auto" | "manual" | "scan"
        self.user_visible = True       # overlay toggle
        self.hidden_after_match = False  # match over -> hidden until the next map
        self.menu_paused = False         # a DBD menu is open (pointer visible) -> hidden for now
        self._watch_gen = 0
        self.round = RoundTimer()        # runs while a map is on display
        self._hist = None                # round for the statistics: detected map -> detected end of the match
        self.game = None
        self._game_checked = 0.0
        self._save_job = None
        self._thumb = None
        self._list_items = {}
        self._log_entries = collections.deque(maxlen=1500)
        self._syncing = False
        self._last_place = None
        self._errors_seen = set()
        self.srv_ping = {}               # region code -> latency result
        self.srv_state = {}              # result of regions.current_state()
        self._srv_busy = False
        self._srv_last_ping = 0.0
        self.conn = ConnectionWatch()      # "Verbunden mit": which game server DBD talks to (needs admin rights)
        self._conn_busy = False
        self._conn_next = 0.0
        self._conn_last = None
        self._conn_idle = IdlePause()    # capture paused while DBD is not running

        self.overlay = make_overlay(self.root, prefer_native=self.settings["overlay"].get("native_window", True))
        self.overlay.game_hwnd = lambda: self.game.hwnd if self.game else None
        self.overlay.on_moved = self._overlay_dragged
        self.overlay.on_wheel = lambda d: self._resize(0.02 * d)

        self._build_ui()
        self._apply_overlay_settings()
        self._restore_geometry()

        self.worker = DetectionWorker(root_dir, self.settings, self.catalog, self.events, simulate=simulate)
        self.worker.start()
        self.hotkeys = self._start_hotkeys()
        self.root.after(50, self._poll)
        self.root.after(250, self._tick_overlay)
        self._log(_("Bereit. {n} Maps geladen, Spielsprachen: {langs}.", n=len(self.catalog.maps),
                    langs=", ".join(self.settings["languages"])), "System")
        self._srv_refresh(log_summary=True)
        self._show_update_status()
        if self.settings.get("show_connection"):
            self.root.after(1500, self._conn_start)
        if not IS_WIN and not simulate:
            self._log(_("Kein Windows: Fenstersuche, Hotkeys und Click-Through sind nur unter Windows aktiv."), "System")

        # notification area icon; "minimise" hides the window there
        from .tray import Tray
        self.tray = Tray(lambda action: self.events.put(("tray", action)))
        if IS_WIN and self.settings.get("tray", True):
            self._tray_start()
        self.root.bind("<Unmap>", self._on_unmap)
        if start_in_tray:                                 # autostart with Windows
            if self.tray.active:
                self.root.withdraw()
            else:
                self.root.iconify()
        threading.Thread(target=self._setup_then_read_autostart, daemon=True, name="autostart").start()

    # ================================================================== UI
    def _build_ui(self):
        theme.apply(self.root, False)             # base styles; dark mode is applied at the end
        # ---------------------------------------------------------- header
        head = ttk.Frame(self.root)
        head.pack(fill="x", padx=10, pady=(8, 2))
        self.dot = ttk.Label(head, text="●", style="DotWarn.TLabel")
        self.dot.pack(side="left")
        self.status_var = tk.StringVar(value=_("Starte …"))
        self._worker_status = ""
        ttk.Label(head, textvariable=self.status_var, wraplength=430).pack(side="left", padx=(4, 0))

        card = ttk.Frame(self.root)
        card.pack(fill="x", padx=10, pady=4)
        self.thumb_label = ttk.Label(card)
        self.thumb_label.pack(side="left", padx=(0, 10))
        info = ttk.Frame(card)
        info.pack(side="left", fill="x", expand=True)
        self.map_var = tk.StringVar(value=_("Noch keine Map"))
        self.realm_var = tk.StringVar(value="")
        self.detail_var = tk.StringVar(value=_("Wird beim Match-Start automatisch erkannt."))
        ttk.Label(info, textvariable=self.map_var, style="Big.TLabel").pack(anchor="w")
        ttk.Label(info, textvariable=self.realm_var).pack(anchor="w")
        ttk.Label(info, textvariable=self.detail_var, style="Dim.TLabel", wraplength=320).pack(anchor="w")
        self.timer_var = tk.StringVar(value="")
        ttk.Label(info, textvariable=self.timer_var).pack(anchor="w")
        self.conn_var = tk.StringVar(value="")
        ttk.Label(info, textvariable=self.conn_var).pack(anchor="w")

        btns = ttk.Frame(self.root)
        btns.pack(fill="x", padx=10, pady=(2, 6))
        self.toggle_btn = ttk.Button(btns, text=_("Overlay ausblenden"), command=self.toggle_overlay)
        self.toggle_btn.pack(side="left")
        # only shown for maps with several layouts (7 of 45), labelled with the one on display
        self.layout_btn = ttk.Button(btns, text="Layout ▸", command=self.next_variant)
        self._layout_unsure = False
        self.rotate_btn = ttk.Button(btns, text=_("Drehen ↻"), command=self.rotate_map)
        self.rotate_btn.pack(side="left", padx=(4, 0))
        self.scan_btn = ttk.Button(btns, text=_("Scannen"), command=self.scan_now)
        self.scan_btn.pack(side="left", padx=(4, 0))
        self.test_btn = ttk.Button(btns, text=_("Overlay testen"), command=self.test_overlay)
        self.test_btn.pack(side="left", padx=4)

        # shown when a banner matched no map: assign the read name to a map with one click
        self.unknown_bar = ttk.Frame(self.root)
        self.unknown_var = tk.StringVar(value="")
        ttk.Button(self.unknown_bar, text="✕", width=3, command=self._hide_unknown).pack(side="right")
        ttk.Button(self.unknown_bar, text=_("Bild hinzufügen …"),
                   command=lambda: self.add_picture(from_unknown=True)).pack(side="right")
        ttk.Button(self.unknown_bar, text=_("Zuordnen …"), command=self.assign_unknown).pack(side="right", padx=4)
        ttk.Label(self.unknown_bar, textvariable=self.unknown_var, wraplength=300).pack(side="left", fill="x")

        # ------------------------------------------------------- tab menu
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        self.tab_maps = self._tab_maps()
        self.tab_overlay = self._tab_overlay()
        self.tab_detect = self._tab_detect()
        self.tab_server = self._tab_server()
        self.tab_log = self._tab_log()
        self.tab_stats = self._tab_stats()
        self.tab_settings = self._tab_settings()
        self.nb.add(self.tab_maps, text="Maps")
        self.nb.add(self.tab_overlay, text=_("Overlay"))
        self.nb.add(self.tab_detect, text=_("Erkennung"))
        self.nb.add(self.tab_server, text=_("Server"))
        self.nb.add(self.tab_log, text="Log")
        self.nb.add(self.tab_stats, text=_("Statistik"))
        self.nb.add(self.tab_settings, text=_("Einstellungen"))
        self.nb.bind("<<NotebookTabChanged>>", lambda e: self._tab_changed())

        self._apply_theme()
        tooltip.attach_all(self.root, self._tip_lookup)
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):     # Windows / Linux
            self.root.bind_all(seq, self._on_wheel, add="+")
        # pages scroll vertically only: never narrower than the widest page (and the tab row)
        self.root.update_idletasks()
        widest = max([p["inner"].winfo_reqwidth() for p in self._pages] + [self.nb.winfo_reqwidth() - 20])
        self.root.minsize(max(470, widest + 40), 420)

    # ------------------------------------------------------------ scrollable tabs
    def _scroll_tab(self):
        """(outer, inner): the tab page scrolls vertically when its content is taller than the window.
        When there is room, inner fills the page, so lists and the log still grow with the window."""
        outer = ttk.Frame(self.nb)
        canvas = tk.Canvas(outer, highlightthickness=0, borderwidth=0, yscrollincrement=8)
        sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas, padding=8)
        item = canvas.create_window(0, 0, window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        page = {"canvas": canvas, "sb": sb, "inner": inner, "item": item, "size": None}
        self._pages = getattr(self, "_pages", [])
        self._pages.append(page)
        canvas.bind("<Configure>", lambda e: self._layout_page(page))
        return outer, inner

    def _layout_page(self, page):
        c, inner = page["canvas"], page["inner"]
        w, h = c.winfo_width(), c.winfo_height()
        need = inner.winfo_reqheight()
        if w <= 1 or h <= 1 or page["size"] == (w, h, need):
            return
        page["size"] = (w, h, need)
        c.itemconfigure(page["item"], width=w, height=max(h, need))
        c.configure(scrollregion=(0, 0, w, max(h, need)))
        if need > h + 1:
            if not page["sb"].winfo_manager():
                page["sb"].pack(side="right", fill="y", before=c)
        else:
            c.yview_moveto(0)
            if page["sb"].winfo_manager():
                page["sb"].pack_forget()

    def _layout_pages(self):
        """Content can grow later (advanced options, hints): checked with the overlay tick."""
        for page in getattr(self, "_pages", []):
            self._layout_page(page)

    def _on_wheel(self, e):
        """Mouse wheel scrolls the tab page under the pointer – lists, the log and choice boxes keep
        their own scrolling."""
        try:
            w = self.root.winfo_containing(e.x_root, e.y_root)
        except (tk.TclError, KeyError):
            return
        pages = {str(p["canvas"]): p for p in getattr(self, "_pages", [])}
        while w is not None:
            if isinstance(w, (ttk.Treeview, tk.Text, tk.Listbox, ttk.Combobox)):
                return
            page = pages.get(str(w))
            if page:
                if page["sb"].winfo_manager():
                    step = -1 if (getattr(e, "num", 0) == 4 or getattr(e, "delta", 0) > 0) else 1
                    page["canvas"].yview_scroll(step * 6, "units")
                return
            w = w.master

    # ------------------------------------------------------------ tab: maps
    def _tab_maps(self):
        outer, f = self._scroll_tab()
        srow = ttk.Frame(f)
        srow.pack(fill="x", pady=(0, 6))
        ttk.Label(srow, text=_("Suche")).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._fill_list())
        entry = ttk.Entry(srow, textvariable=self.search_var)
        entry.pack(side="left", fill="x", expand=True, padx=(8, 0))
        entry.bind("<Return>", lambda e: self._pick_first())
        tf = ttk.Frame(f)
        tf.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tf, show="tree", height=12, selectmode="browse")
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda e: self._pick_selected())
        self.tree.bind("<Return>", lambda e: self._pick_selected())
        ttk.Label(f, text=_("Doppelklick zeigt die Map. Die Erkennung übernimmt beim nächsten Match wieder."),
                  style="Dim.TLabel", wraplength=420).pack(anchor="w", pady=(6, 0))
        prow = ttk.Frame(f)
        prow.pack(fill="x", pady=(6, 0))
        ttk.Button(prow, text=_("Kartenbild hinzufügen …"), command=self.add_picture).pack(side="left")
        ttk.Label(prow, text=_("eigenes Bild für eine Map (Hintergrund wird entfernt)"), style="Dim.TLabel").pack(
            side="left", padx=8)
        self._fill_list()
        return outer

    # --------------------------------------------------------- tab: overlay
    def _slider(self, parent, label, var, lo, hi, cmd, fmt="{:.0f} %"):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=3)
        ttk.Label(row, text=label, width=12).pack(side="left")
        val = ttk.Label(row, text=fmt.format(var.get()), width=6, anchor="e")
        val.pack(side="right")

        def changed(_=None):
            val.configure(text=fmt.format(var.get()))
            cmd()
        scale = ttk.Scale(row, from_=lo, to=hi, variable=var, command=changed)
        scale.pack(side="left", fill="x", expand=True, padx=6)
        return val

    def _tab_overlay(self):
        outer, f = self._scroll_tab()
        o = self.settings["overlay"]
        pos = ttk.LabelFrame(f, text=_("Position"), padding=8)
        pos.pack(fill="x")
        r = ttk.Frame(pos)
        r.pack(fill="x", pady=(0, 4))
        ttk.Label(r, text=_("Vorgabe"), width=12).pack(side="left")
        self.anchor_var = tk.StringVar(value=anchor_label(o["anchor"]))
        cb = ttk.Combobox(r, textvariable=self.anchor_var, values=[_(a[1]) for a in ANCHORS], state="readonly", width=16)
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self._anchor_changed())
        ttk.Button(r, text=_("Zurücksetzen"), command=self._reset_position).pack(side="right")
        self.posx_var = tk.DoubleVar(value=o.get("pos_x", 0.0) * 100)
        self.posy_var = tk.DoubleVar(value=o.get("pos_y", 0.0) * 100)
        self.posx_label = self._slider(pos, _("Horizontal"), self.posx_var, 0, 100, self._pos_changed)
        self.posy_label = self._slider(pos, _("Vertikal"), self.posy_var, 0, 100, self._pos_changed)
        r2 = ttk.Frame(pos)
        r2.pack(fill="x", pady=(4, 0))
        self.edit_btn = ttk.Button(r2, text=_("Mit der Maus verschieben"), command=self.toggle_edit)
        self.edit_btn.pack(side="left")
        ttk.Label(r2, text=_("0 % = links/oben, 100 % = rechts/unten"), style="Dim.TLabel").pack(side="right")

        look = ttk.LabelFrame(f, text=_("Darstellung"), padding=8)
        look.pack(fill="x", pady=(8, 0))
        self.size_var = tk.DoubleVar(value=o["height"] * 100)
        self.size_label = self._slider(look, _("Grösse"), self.size_var, 15, 90, self._size_changed)
        self.map_size_row = ttk.Frame(look)
        self.map_size_var = tk.StringVar(value="")
        ttk.Label(self.map_size_row, textvariable=self.map_size_var, style="Dim.TLabel", wraplength=330).pack(
            side="left")
        ttk.Button(self.map_size_row, text=_("Für diese Map zurücksetzen"), command=self._reset_map_size).pack(
            side="right")
        self._size_row_after = self.size_label.master
        self.opacity_var = tk.DoubleVar(value=o["opacity"] * 100)
        self._slider(look, _("Deckkraft"), self.opacity_var, 25, 100, self._opacity_changed)
        self.focus_var = tk.BooleanVar(value=o["only_when_game_focused"])
        self.caption_var = tk.BooleanVar(value=o["show_caption"])
        self.transp_var = tk.BooleanVar(value=o.get("transparent", True))
        self.timer_show_var = tk.BooleanVar(value=o.get("show_timer", True))
        self.server_show_var = tk.BooleanVar(value=o.get("show_server", True))
        self.keep_bar_var = tk.BooleanVar(value=o.get("keep_in_bar", True))
        self.show_map_var = tk.BooleanVar(value=o.get("show_map", True))
        ttk.Checkbutton(pos, text=_("Karte im schwarzen Rand halten (Ultrawide: nie ins Spielbild ragen)"),
                        variable=self.keep_bar_var, command=self._overlay_flags_changed).pack(anchor="w", pady=(4, 0))
        for text, var in ((N_("Karte anzeigen (aus: nur Timer, Ort und Ping)"), self.show_map_var),
                          (N_("Nur zeigen, wenn DBD das aktive Fenster ist"), self.focus_var),
                          (N_("Map-Namen über der Karte anzeigen"), self.caption_var),
                          (N_("Rundentimer unter der Karte anzeigen"), self.timer_show_var),
                          (N_("Verbundenen Server unter der Karte anzeigen (Tab Server)"), self.server_show_var),
                          (N_("Transparenter Rand um die Karte"), self.transp_var)):
            ttk.Checkbutton(look, text=_(text), variable=var, command=self._overlay_flags_changed).pack(anchor="w", pady=1)
        return outer

    # ------------------------------------------------------- tab: detection
    def _tab_detect(self):
        outer, f = self._scroll_tab()
        auto = ttk.LabelFrame(f, text=_("Automatik"), padding=8)
        auto.pack(fill="x")
        self.auto_var = tk.BooleanVar(value=self.settings["auto_detect"])
        self.hide_var = tk.BooleanVar(value=self.settings["hide_after_match"])
        ttk.Checkbutton(auto, text=_("Map beim Match-Start automatisch erkennen"), variable=self.auto_var,
                        command=self._detect_flags_changed).pack(anchor="w", pady=1)
        ttk.Checkbutton(auto, text=_("Overlay ausblenden, sobald ich nicht mehr in der Runde bin"),
                        variable=self.hide_var, command=self._detect_flags_changed).pack(anchor="w", pady=1)
        ttk.Label(auto, text=_("erkennt Ergebnisbildschirm, Lobby/Menüs, Ladebildschirm und geschlossenes DBD"),
                  style="Dim.TLabel", wraplength=400).pack(anchor="w", padx=(22, 0))
        self.menu_var = tk.BooleanVar(value=self.settings.get("pause_in_menus", True))
        ttk.Checkbutton(auto, text=_("Overlay pausieren, solange ein DBD-Menü offen ist"),
                        variable=self.menu_var, command=self._detect_flags_changed).pack(anchor="w", pady=(4, 1))
        ttk.Label(auto, text=_("erkannt am sichtbaren Mauszeiger (ESC-Menü, Ergebnisbildschirm, Lobby)"),
                  style="Dim.TLabel", wraplength=400).pack(anchor="w", padx=(22, 0))
        lang = ttk.LabelFrame(f, text=_("Spielsprache (Map-Namen)"), padding=8)
        lang.pack(fill="x", pady=(8, 0))
        grid = ttk.Frame(lang)
        grid.pack(anchor="w")
        self.lang_vars = {}
        for i, (code, label) in enumerate(LANGS):
            v = tk.BooleanVar(value=code in self.settings["languages"])
            self.lang_vars[code] = v
            ttk.Checkbutton(grid, text=label, variable=v, command=self._langs_changed).grid(
                row=i // 5, column=i % 5, sticky="w", padx=(0, 12), pady=1)

        # technical options: folded away, only needed when something does not work
        self.adv_open = tk.BooleanVar(value=bool(self.settings.get("show_advanced", False)))
        self.adv_btn = ttk.Button(f, command=self._toggle_advanced)
        self.adv_btn.pack(anchor="w", pady=(10, 0))
        adv = self.adv_frame = ttk.LabelFrame(f, text=_("Erweitert"), padding=8)
        self.wgc_var = tk.BooleanVar(value=self.settings.get("window_capture", True))
        ttk.Checkbutton(adv, text=_("Auch erkennen, wenn andere Fenster über DBD liegen"),
                        variable=self.wgc_var, command=self._detect_flags_changed).pack(anchor="w", pady=1)
        ttk.Label(adv, text=_("Fensteraufnahme wie bei OBS, nur solange DBD im Hintergrund ist"),
                  style="Dim.TLabel", wraplength=400).pack(anchor="w", padx=(22, 0))
        self.rate_var = tk.DoubleVar(value=float(self.settings.get("scans_per_second", 5)))
        self._slider(adv, _("Scans/Sek."), self.rate_var, 2, 10, self._rate_changed, fmt="{:.0f}")
        self.watch_var = tk.StringVar(value=_("Rundenende-Erkennung: {state}", state=_("keine Map angezeigt")))
        ttk.Label(adv, textvariable=self.watch_var, style="Dim.TLabel", wraplength=420).pack(anchor="w", pady=(4, 6))
        self.debug_var = tk.BooleanVar(value=self.settings["save_debug_images"])
        ttk.Checkbutton(adv, text=_("Debug-Bilder speichern (Ordner debug/)"), variable=self.debug_var,
                        command=self._detect_flags_changed).pack(anchor="w")
        r = ttk.Frame(adv)
        r.pack(fill="x", pady=(6, 0))
        ttk.Button(r, text=_("Bildschirm jetzt scannen"), command=self.scan_now).pack(side="left")
        ttk.Button(r, text=_("Diagnose kopieren"), command=self.show_diagnose).pack(side="left", padx=6)
        self._show_advanced()
        return outer

    def _toggle_advanced(self):
        self.adv_open.set(not self.adv_open.get())
        self.settings.set("show_advanced", bool(self.adv_open.get()))
        self._save_soon()
        self._show_advanced()

    def _show_advanced(self):
        if self.adv_open.get():
            self.adv_btn.configure(text="▾ " + _("Erweitert (Fehlersuche, Technik)"))
            self.adv_frame.pack(fill="x", pady=(4, 0))
        else:
            self.adv_btn.configure(text="▸ " + _("Erweitert (Fehlersuche, Technik)"))
            self.adv_frame.pack_forget()

    # ----------------------------------------------------------- tab: server
    def _tab_server(self):
        outer, f = self._scroll_tab()
        conn = ttk.LabelFrame(f, text=_("Verbundener Spielserver"), padding=8)
        conn.pack(fill="x")
        self.conn_show_var = tk.BooleanVar(value=bool(self.settings.get("show_connection")))
        ttk.Checkbutton(conn, text=_("Anzeigen, mit welchem Server DBD verbunden ist"),
                        variable=self.conn_show_var, command=self._conn_toggled).pack(anchor="w")
        self.conn_tab_var = tk.StringVar(value="")
        ttk.Label(conn, textvariable=self.conn_tab_var, style="Big.TLabel", wraplength=540).pack(anchor="w", pady=(2, 0))

        reg = ttk.LabelFrame(f, text=_("Serverregionen"), padding=8)
        reg.pack(fill="both", expand=True, pady=(8, 0))
        ttk.Label(reg, text=_("DBD sucht Matches nur in den angehakten Regionen (über die Windows-hosts-Datei, "
                              "das Spiel wird nicht verändert). Nach „Auswahl anwenden“ DBD neu starten."),
                  style="Dim.TLabel", wraplength=430).pack(anchor="w")
        f_outer, f = f, reg
        tf = ttk.Frame(f)
        tf.pack(fill="both", expand=True, pady=(6, 0))
        t = ttk.Treeview(tf, columns=("ping", "state"), show="tree headings", height=11, selectmode="browse")
        t.heading("#0", text=_("Region"), anchor="w")
        t.heading("ping", text="Ping", anchor="e")
        t.heading("state", text=_("hosts-Datei"), anchor="w")
        t.column("#0", width=215, stretch=True)
        t.column("ping", width=78, anchor="e", stretch=False)
        t.column("state", width=120, anchor="w", stretch=False)
        sb = ttk.Scrollbar(tf, orient="vertical", command=t.yview)
        t.configure(yscrollcommand=sb.set)
        t.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.srv_tree = t
        saved = self.settings.get("regions_selected")
        self.srv_sel = set(saved) if saved else {c for c, _, _ in regions.REGIONS}
        for g in regions.GROUPS:
            t.insert("", "end", iid=f"g:{g}", text=_(g), open=True, tags=("group",))
            for code, name, grp in regions.REGIONS:
                if grp == g:
                    t.insert(f"g:{g}", "end", iid=f"r:{code}", text=_(name), values=("", ""))
        t.bind("<Button-1>", self._srv_click)
        t.bind("<space>", lambda e: self._srv_toggle(t.focus()))
        row = ttk.Frame(f)
        row.pack(fill="x", pady=(6, 0))
        self.srv_btns = [ttk.Button(row, text=_("Ping messen"), command=self.srv_measure),
                         ttk.Button(row, text=_("Auswahl anwenden"), command=self.srv_apply),
                         ttk.Button(row, text=_("Alles freigeben"), command=self.srv_release)]
        self.srv_btns[0].pack(side="left")
        self.srv_btns[1].pack(side="left", padx=6)
        self.srv_btns[2].pack(side="left")
        self.srv_status = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.srv_status, wraplength=430).pack(anchor="w", pady=(6, 0))
        ttk.Label(f_outer, text=_("Mit VPN unzuverlässig. Region-Tools sind von BHVR weder erlaubt noch verboten – "
                                  "auf eigene Verantwortung."), style="Dim.TLabel", wraplength=440).pack(
            anchor="w", pady=(6, 0))
        self._srv_render()
        return outer

    # ---------------------------------------------------------- connected server
    def _conn_toggled(self):
        on = bool(self.conn_show_var.get())
        self.settings.set("show_connection", on)
        self._save_soon()
        if on:
            self._conn_start()
        else:
            self.conn.stop()
            self._conn_idle.reset()
            self._log(_("Anzeige des Spielservers beendet."), "System")
            self._conn_tick(force=True)

    def _conn_start(self):
        if self.conn.running or self._conn_busy:
            return
        self._conn_busy = True
        self.conn_tab_var.set(_("Warte auf Windows (Administratorrechte) …"))
        hwnd = self._root_hwnd()

        def work():
            try:
                err = self.conn.start(hwnd)
            except Exception as e:
                err = {"error": f"{type(e).__name__}: {e}"}
            self.events.put(("conn_started", err))
        threading.Thread(target=work, daemon=True, name="netwatch").start()

    def _conn_started(self, err):
        self._conn_busy = False
        if not err and not self.conn_show_var.get():      # unticked while Windows was asking
            self.conn.stop()
        elif err:
            self._log(_("Spielserver-Anzeige: {error}", error=err.get("error") or _("Fehler")), "Fehler")
            self.conn.error = err.get("error", "")
            if err.get("cancelled") or not IS_WIN:
                self.conn_show_var.set(False)
                self.settings.set("show_connection", False)
                self._save_soon()
                self.conn.error = ""
        else:
            self._log(_("Spielserver-Anzeige läuft (liest nur Paketköpfe, keine Inhalte)."), "System")
        self._conn_tick(force=True)

    def _conn_tick(self, force=False):
        now = time.time()
        if not force and now < self._conn_next:
            return
        self._conn_next = now + 1.0
        if self.conn_show_var.get() and not self._conn_busy:
            act = self._conn_idle.update(now, self.game is not None, self.conn.running, self.conn.in_process)
            if act == "pause":
                self.conn.stop()
                self._log(_("Spielserver-Anzeige pausiert – DBD läuft nicht (startet automatisch mit DBD)."), "System")
            elif act == "resume" and not self.conn.running:
                self._conn_start()
        was_running = self.conn.running
        self.conn.poll(now)
        if was_running and not self.conn.running and self.conn.error:
            self._log(_("Spielserver-Anzeige beendet: {error}", error=self.conn.error), "Fehler")
        srv = self.conn.server
        if srv and self._hist is not None:
            self._hist["region"] = srv["region"]           # region only, never the address
        key = (srv["ip"], srv["region"]) if srv else None
        if key != self._conn_last:
            self._conn_last = key
            if srv:
                note = "" if srv["region"] in self.srv_sel else _(" – nicht in deiner Regionsauswahl")
                # region only: the log file is kept on disk, the server address is shown live in the window only
                self._log(_("Verbunden mit Spielserver: {region}{note}.", region=_(regions.NAMES.get(srv["region"], srv["region"])),
                            note=note), "System")
        text = self.conn.text()
        if self._conn_busy:
            text = _("Warte auf Windows (Administratorrechte) …")
        elif self._conn_idle.paused:
            text = _("pausiert, bis DBD läuft")
        if not text and not self.conn_show_var.get():
            text = _("Aus. Zeigt Region und Ping des Spielservers, auch im Overlay (braucht Administratorrechte).")
        self.conn_tab_var.set(_("Verbunden mit: {server}", server=text) if text and self.conn.running else text)
        show = self.settings["overlay"].get("show_server", True)
        self.overlay.set_server(_(regions.NAMES.get(srv["region"], srv["region"])) if srv and show else "",
                                self.conn.ping_ms)
        main = _("Verbunden mit: {server}", server=text) if self.conn.running else ""
        if main != self.conn_var.get():
            self.conn_var.set(main)

    def _srv_click(self, e):
        t = self.srv_tree
        if t.identify_region(e.x, e.y) not in ("tree", "cell"):
            return
        iid = t.identify_row(e.y)
        if iid and t.identify_element(e.x, e.y) != "Treeitem.indicator":
            self._srv_toggle(iid)

    def _srv_toggle(self, iid):
        if not iid or self._srv_busy:
            return
        if iid.startswith("g:"):
            codes = [c for c, _, g in regions.REGIONS if g == iid[2:]]
            if all(c in self.srv_sel for c in codes):
                self.srv_sel.difference_update(codes)
            else:
                self.srv_sel.update(codes)
        elif iid.startswith("r:"):
            self.srv_sel ^= {iid[2:]}
        self.settings.set("regions_selected", sorted(self.srv_sel))
        self._save_soon()
        self._srv_render()

    def _srv_render(self):
        t = self.srv_tree
        states = self.srv_state.get("regions", {})
        for g in regions.GROUPS:
            codes = [c for c, _, grp in regions.REGIONS if grp == g]
            n = sum(c in self.srv_sel for c in codes)
            box = "☑" if n == len(codes) else "☐" if n == 0 else "◪"
            t.item(f"g:{g}", text=f"{box}  {_(g)}")
            for c in codes:
                p = self.srv_ping.get(c)
                ms = p.get("ms") if p else None
                ping = "…" if self._srv_busy and p is None else ("–" if ms is None else f"{ms:.0f} ms")
                tag = ("p_na" if ms is None else "p_good" if ms < 80 else "p_mid" if ms < 130 else "p_bad")
                t.item(f"r:{c}", text=f"{'☑' if c in self.srv_sel else '☐'}  {_(regions.NAMES[c])}",
                       values=(ping, _(states.get(c, "?"))), tags=(tag,))

    def _srv_refresh(self, log_summary=False):
        """Read the hosts file (no administrator rights needed)."""
        self.srv_state = regions.current_state()
        st = self.srv_state
        if st.get("error"):
            self.srv_status.set(_("hosts-Datei nicht lesbar: {error}", error=st["error"]))
            self._srv_render()
            return
        rs = st["regions"]
        visible = [c for c, _, _ in regions.REGIONS]
        free = [c for c in visible if rs.get(c) == "frei"]
        if st["own"] and not self.settings.get("regions_selected"):
            self.srv_sel = set(free)                          # show what is actually active
        if st["own"]:
            text = _("Aktiv: nur {regions} erlaubt.", regions=", ".join(_(regions.NAMES[c]) for c in free) or _("(keine)"))
        elif any(v != "frei" for v in rs.values()):
            text = _("Keine eigene Auswahl aktiv, aber andere Einträge sperren Regionen.")
        else:
            text = _("Keine Region gesperrt – DBD wählt selbst.")
        if st["foreign"]:
            who = "Make Your Choice" if st["myc"] else _("anderen Programmen")
            text += _(" Es gibt {n} Einträge von {who} für DBD-Server (werden beim Anwenden ersetzt).",
                      n=st["foreign"], who=who)
        self.srv_status.set(text)
        self._srv_render()
        if log_summary and (st["own"] or st["foreign"]):
            self._log(_("Serverregionen: {text}", text=text), "System")

    def srv_measure(self):
        if self._srv_busy:
            return
        self._srv_busy = True
        self.srv_ping = {}
        self._srv_render()
        self.srv_status.set(_("Messe Ping zu den Serverregionen …"))
        for b in self.srv_btns:
            b.state(["disabled"])

        def work():
            try:
                res = regions.measure_all()
            except Exception as e:  # pragma: no cover
                res = {"_error": str(e)}
            self.events.put(("srv_ping", res))
        threading.Thread(target=work, daemon=True, name="ping").start()

    def _srv_ping_done(self, res):
        self._srv_busy = False
        self._srv_last_ping = time.time()
        for b in self.srv_btns:
            b.state(["!disabled"])
        if "_error" in res:
            self._srv_render()
            self.srv_status.set(_("Ping fehlgeschlagen: {error}", error=res["_error"]))
            return
        self.srv_ping = res
        ok = {c: r["ms"] for c, r in res.items() if r.get("ms") is not None}
        self._srv_refresh()
        if ok:
            best = sorted(ok, key=ok.get)[:3]
            self.srv_status.set(self.srv_status.get() + "  " + _("Am schnellsten: {list}.", list=", ".join(
                f"{_(regions.NAMES[c])} {ok[c]:.0f} ms" for c in best)))
        else:
            self.srv_status.set(_("Keine Region hat geantwortet (Internet/Firewall/VPN?)."))

    def srv_apply(self):
        if self._srv_busy:
            return
        sel = [c for c, _, _ in regions.REGIONS if c in self.srv_sel]
        if not sel:
            messagebox.showinfo(_("Serverregionen"), _("Bitte mindestens eine Region anhaken."))
            return
        if len(sel) == len(regions.REGIONS):
            self.srv_release()
            return
        names = ", ".join(_(regions.NAMES[c]) for c in sel)
        foreign = self.srv_state.get("foreign", 0)
        msg = _("Erlaubt bleiben: {names}.\n\nAlle anderen DBD-Serverregionen werden in der Windows-hosts-Datei "
                "gesperrt. Windows fragt gleich nach Administratorrechten.", names=names)
        if foreign:
            msg += "\n\n" + _("{n} vorhandene Einträge anderer Programme (z. B. Make Your Choice) für DBD-Server "
                                 "werden dabei entfernt.", n=foreign)
        msg += "\n\n" + _("Danach DBD neu starten, damit es wirkt.")
        if not messagebox.askokcancel(_("Serverregionen anwenden"), msg, parent=self.root):
            return
        self._srv_run({"block": regions.block_list(sel), "allowed": sel, "remove_foreign": True},
                      _("Nur noch {names} erlaubt", names=names))

    def srv_release(self):
        if self._srv_busy:
            return
        st = self.srv_state
        if not st.get("own") and not st.get("foreign"):
            self.srv_status.set(_("Es ist nichts gesperrt."))
            return
        msg = (_("Alle Sperren für DBD-Serverregionen aus der hosts-Datei entfernen (auch die von Make Your Choice)?")
               if st.get("myc") else _("Alle Sperren für DBD-Serverregionen aus der hosts-Datei entfernen?"))
        msg += "\n\n" + _("Windows fragt gleich nach Administratorrechten. Danach DBD neu starten.")
        if not messagebox.askokcancel(_("Serverregionen freigeben"), msg, parent=self.root):
            return
        self._srv_run({"block": [], "remove_foreign": True}, _("Alle Regionen freigegeben"))

    def _srv_run(self, job, label):
        self._srv_busy = True
        for b in self.srv_btns:
            b.state(["disabled"])
        self.srv_status.set(_("Warte auf Windows (Administratorrechte) …"))
        hwnd = self._root_hwnd()

        def work():
            try:
                res = regions.run_job(job, hwnd=hwnd)
            except Exception as e:
                res = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            self.events.put(("srv_job", res, label))
        threading.Thread(target=work, daemon=True, name="hosts").start()

    def _srv_job_done(self, res, label):
        self._srv_busy = False
        for b in self.srv_btns:
            b.state(["!disabled"])
        self._srv_refresh()
        if res.get("ok"):
            if res.get("changed", True):
                self._log(_("Serverregionen: {text}. DBD neu starten, damit es wirkt.", text=label), "System")
                self.srv_status.set(_("{text}. DBD jetzt neu starten.", text=label) + "  " + self.srv_status.get())
            else:
                self.srv_status.set(_("Keine Änderung nötig.") + "  " + self.srv_status.get())
        else:
            err = res.get("error") or _("unbekannter Fehler")
            self._log(_("Serverregionen: {text}", text=err), "System" if res.get("cancelled") else "Fehler")
            self.srv_status.set(err)

    # -------------------------------------------------------------- tab: statistics
    def _tab_stats(self):
        outer, f = self._scroll_tab()
        fr = ttk.Frame(f)
        fr.pack(fill="x", pady=(0, 6))
        ttk.Label(fr, text=_("Zeitraum")).pack(side="left")
        self._stats_periods = [(k, _(label)) for k, label in STATS_PERIODS]
        self.stats_period_var = tk.StringVar(value=self._stats_periods[0][1])
        cb = ttk.Combobox(fr, textvariable=self.stats_period_var, values=[lbl for _k, lbl in self._stats_periods],
                          state="readonly", width=14)
        cb.pack(side="left", padx=(6, 14))
        cb.bind("<<ComboboxSelected>>", lambda e: self._stats_render())
        ttk.Label(fr, text=_("Region")).pack(side="left")
        self._stats_regions = [(None, _("Alle Regionen"))]
        self.stats_region_var = tk.StringVar(value=self._stats_regions[0][1])
        self.stats_region_cb = ttk.Combobox(fr, textvariable=self.stats_region_var, state="readonly", width=24,
                                            values=[lbl for _c, lbl in self._stats_regions])
        self.stats_region_cb.pack(side="left", padx=6)
        self.stats_region_cb.bind("<<ComboboxSelected>>", lambda e: self._stats_render())
        self.stats_var = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.stats_var, style="Big.TLabel", wraplength=540).pack(anchor="w")
        ttk.Label(f, text=_("Gezählt werden Runden mit automatisch erkannter Map, vom Map-Banner bis zum erkannten "
                            "Rundenende (mindestens 1 Minute). Gespeichert nur lokal in rounds.jsonl."),
                  style="Dim.TLabel", wraplength=540).pack(anchor="w", pady=(2, 6))
        box = ttk.LabelFrame(f, text=_("Maps"), padding=6)
        box.pack(fill="both", expand=True)
        self.stats_maps = self._stats_tree(box, (("map", _("Map"), 230, "w"), ("n", _("Runden"), 70, "e"),
                                                 ("avg", _("Ø Dauer"), 80, "e"), ("max", _("Längste"), 80, "e")), 9)
        box_r = ttk.LabelFrame(f, text=_("Serverregionen"), padding=6)
        box_r.pack(fill="both", expand=True, pady=(8, 0))
        self.stats_regs = self._stats_tree(box_r, (("reg", _("Region"), 230, "w"), ("n", _("Runden"), 70, "e"),
                                                   ("avg", _("Ø Dauer"), 80, "e"), ("share", _("Anteil"), 80, "e")), 5)
        ttk.Label(box_r, text=_("Region nur bekannt, wenn im Tab Server „Verbundener Spielserver“ an war."),
                  style="Dim.TLabel", wraplength=520).pack(anchor="w", pady=(4, 0))
        box2 = ttk.LabelFrame(f, text=_("Letzte Runden"), padding=6)
        box2.pack(fill="both", expand=True, pady=(8, 0))
        self.stats_last = self._stats_tree(box2, (("when", _("Wann"), 115, "w"), ("map", _("Map"), 170, "w"),
                                                  ("dur", _("Dauer"), 60, "e"), ("srv", _("Server"), 175, "w")), 9)
        row = ttk.Frame(f)
        row.pack(fill="x", pady=(8, 0))
        ttk.Button(row, text=_("Verlauf löschen"), command=self._stats_clear).pack(side="left")
        self._stats_sort = ("n", True)
        return outer

    def _stats_tree(self, parent, cols, height):
        tf = ttk.Frame(parent)
        tf.pack(fill="both", expand=True)
        t = ttk.Treeview(tf, columns=[c[0] for c in cols], show="headings", height=height, selectmode="none")
        for key, title, width, anchor in cols:
            t.heading(key, text=title, anchor=anchor, command=lambda k=key, tr=t: self._stats_sort_by(tr, k))
            t.column(key, width=width, anchor=anchor, stretch=key in ("map", "reg"))
        sb = ttk.Scrollbar(tf, orient="vertical", command=t.yview)
        t.configure(yscrollcommand=sb.set)
        t.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        return t

    def _stats_sort_by(self, tree, key):
        if tree is not self.stats_maps:
            return
        col, desc = self._stats_sort
        self._stats_sort = (key, not desc if col == key else key != "map")
        self._stats_render()

    def _stats_region_name(self, code):
        if not code or code == history.NO_REGION:
            return _("ohne Region")
        return _(regions.NAMES.get(code, code))

    def _stats_render(self):
        all_rounds = history.load(self._hist_path())
        # region filter: the regions that occur (kept selected even if the list changes)
        wanted = next((c for c, lbl in self._stats_regions if lbl == self.stats_region_var.get()), None)
        self._stats_regions = [(None, _("Alle Regionen"))] + \
            [(c, self._stats_region_name(c)) for c in history.regions_used(all_rounds)] + \
            ([(history.NO_REGION, _("ohne Region"))] if any(not r.region for r in all_rounds) else [])
        if wanted not in [c for c, _lbl in self._stats_regions]:
            wanted = None
        self.stats_region_cb.configure(values=[lbl for _c, lbl in self._stats_regions])
        self.stats_region_var.set(dict(self._stats_regions)[wanted])
        period = next((k for k, lbl in self._stats_periods if lbl == self.stats_period_var.get()), "all")
        rounds = history.select(all_rounds, since=history.period_start(period, time.time()), region=wanted)
        s = history.summary(rounds)
        if not all_rounds:
            self.stats_var.set(_("Noch keine Runden gespeichert."))
        elif not s["count"]:
            self.stats_var.set(_("Keine Runden in dieser Auswahl."))
        else:
            self.stats_var.set(_("{n} Runden · Ø {avg} · gesamt {total}", n=s["count"], avg=fmt_duration(s["avg"]),
                                 total=fmt_duration(s["total"])))
        rows = history.per_map(rounds)
        col, desc = self._stats_sort
        idx = {"map": 0, "n": 1, "avg": 2, "max": 3}[col]
        rows.sort(key=lambda r: r[idx].lower() if idx == 0 else r[idx], reverse=desc)
        t = self.stats_maps
        t.delete(*t.get_children())
        for name, n, avg, longest in rows:
            t.insert("", "end", values=(name, n, fmt_duration(avg), fmt_duration(longest)))
        t = self.stats_regs
        t.delete(*t.get_children())
        for code, n, avg, share in history.per_region(rounds):
            t.insert("", "end", values=(self._stats_region_name(code), n, fmt_duration(avg), f"{share:.0%}"))
        t = self.stats_last
        t.delete(*t.get_children())
        for r in sorted(rounds, key=lambda r: r.t, reverse=True)[:100]:
            t.insert("", "end", values=(time.strftime("%d.%m.%y %H:%M", time.localtime(r.t)), r.map,
                                        fmt_duration(r.seconds),
                                        _(regions.NAMES.get(r.region, r.region)) if r.region else "–"))

    def _stats_clear(self):
        if not os.path.exists(self._hist_path()):
            return
        if not messagebox.askokcancel(_("Verlauf löschen"), _("Alle gespeicherten Runden löschen?"), parent=self.root):
            return
        history.clear(self._hist_path())
        self._stats_render()
        self._log(_("Rundenverlauf gelöscht."), "System")

    # -------------------------------------------------------------- tab: log
    def _tab_log(self):
        outer, f = self._scroll_tab()
        top = ttk.Frame(f)
        top.pack(fill="x", pady=(0, 6))
        ttk.Label(top, text=_("Anzeigen:")).pack(side="left")
        enabled = set(self.settings.get("log_categories", CATS))
        self.cat_vars = {}
        for c in CATS:
            v = tk.BooleanVar(value=c in enabled)
            self.cat_vars[c] = v
            ttk.Checkbutton(top, text=_(c), variable=v, command=self._log_filter_changed).pack(side="left", padx=(6, 0))
        tf = ttk.Frame(f)
        tf.pack(fill="both", expand=True)
        self.log_text = tk.Text(tf, height=14, width=58, wrap="word", state="disabled", relief="flat",
                                font=("Segoe UI", 9),
                                highlightthickness=0, borderwidth=0, padx=6, pady=4)
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        bottom = ttk.Frame(f)
        bottom.pack(fill="x", pady=(6, 0))
        ttk.Button(bottom, text=_("Leeren"), command=self._clear_log).pack(side="left")
        ttk.Button(bottom, text=_("Log-Datei öffnen"), command=self._open_logfile).pack(side="left", padx=6)
        ttk.Button(bottom, text=_("Diagnose kopieren"), command=self.show_diagnose).pack(side="left")
        return outer

    # --------------------------------------------------------- tab: settings
    def _tab_settings(self):
        outer, f = self._scroll_tab()
        look = ttk.LabelFrame(f, text=_("Sprache und Darstellung"), padding=8)
        look.pack(fill="x")
        lr = ttk.Frame(look)
        lr.pack(fill="x")
        ttk.Label(lr, text="Sprache / Language").pack(side="left")
        cur = self.settings.get("ui_language", "auto")
        self._ui_langs = [(code, _(label) if code == "auto" else label) for code, label in i18n.LANGUAGES]
        self.ui_lang_var = tk.StringVar(value=dict(self._ui_langs).get(cur, self._ui_langs[0][1]))
        lcb = ttk.Combobox(lr, textvariable=self.ui_lang_var, values=[lbl for _c, lbl in self._ui_langs],
                           state="readonly", width=30)
        lcb.pack(side="left", padx=8)
        lcb.bind("<<ComboboxSelected>>", lambda e: self._ui_lang_changed())
        self.ui_lang_note = tk.StringVar(value="")
        ttk.Label(look, textvariable=self.ui_lang_note, style="Dim.TLabel", wraplength=400).pack(anchor="w")
        self.dark_var = tk.BooleanVar(value=self.settings.get("dark_mode", True))
        ttk.Checkbutton(look, text=_("Dark Mode"), variable=self.dark_var, command=self._dark_changed).pack(
            anchor="w", pady=(4, 0))

        hk = ttk.LabelFrame(f, text=_("Hotkeys"), padding=8)
        hk.pack(fill="x", pady=(8, 0))
        self.hk_buttons = {}
        self._hk_rec, self._hk_mods = None, set()
        grid = ttk.Frame(hk)
        grid.pack(fill="x")
        for i, (key, label) in enumerate(HOTKEY_LABELS):
            ttk.Label(grid, text=_(label)).grid(row=i, column=0, sticky="w", pady=1)
            b = ttk.Button(grid, width=22, command=lambda k=key: self._hk_record(k))
            b.grid(row=i, column=1, sticky="w", padx=(10, 0), pady=1)
            self.hk_buttons[key] = b
        self._hk_show_all()
        r = ttk.Frame(hk)
        r.pack(fill="x", pady=(6, 0))
        ttk.Button(r, text=_("Standard"), command=self._hk_defaults).pack(side="left")
        self.hk_status = tk.StringVar(value=_("Zum Ändern anklicken und die neue Tastenkombination drücken."))
        ttk.Label(r, textvariable=self.hk_status, style="Dim.TLabel", wraplength=300).pack(side="left", padx=8)

        st = ttk.LabelFrame(f, text=_("Start und Infobereich"), padding=8)
        st.pack(fill="x", pady=(8, 0))
        self.tray_var = tk.BooleanVar(value=self.settings.get("tray", True))
        ttk.Checkbutton(st, text=_("Beim Minimieren in den Infobereich (neben der Uhr)"), variable=self.tray_var,
                        command=self._tray_flag_changed).pack(anchor="w")
        self.autostart_var = tk.BooleanVar(value=False)
        self.autostart_cb = ttk.Checkbutton(st, text=_("Mit Windows starten (im Infobereich, ohne Windows-Abfrage)"),
                                            variable=self.autostart_var, command=self._autostart_changed)
        self.autostart_cb.pack(anchor="w", pady=(2, 0))
        self.autostart_cb.state(["disabled"])
        self.autostart_info = tk.StringVar(value="")
        ttk.Label(st, textvariable=self.autostart_info, style="Dim.TLabel", wraplength=400).pack(
            anchor="w", padx=(22, 0))

        upd = ttk.LabelFrame(f, text=_("Updates"), padding=8)
        upd.pack(fill="x", pady=(8, 0))
        self.update_var = tk.BooleanVar(value=self.settings.get("auto_update", True))
        ttk.Checkbutton(upd, text=_("Beim Start nach Updates suchen und installieren (GitHub)"),
                        variable=self.update_var, command=self._update_flag_changed).pack(anchor="w")
        ttk.Label(upd, text=_("nur über start.bat bzw. die Desktop-Verknüpfung; eigene Änderungen werden nie "
                              "überschrieben"), style="Dim.TLabel", wraplength=400).pack(anchor="w", padx=(22, 0))
        ur = ttk.Frame(upd)
        ur.pack(fill="x", pady=(6, 0))
        self.upd_btn = ttk.Button(ur, text=_("Jetzt nach Updates suchen"), command=self.check_update)
        self.upd_btn.pack(side="left")
        self.upd_apply_btn = ttk.Button(ur, text=_("Aktualisieren und neu starten"), command=self.apply_update)
        self.upd_status = tk.StringVar(value="")
        ttk.Label(upd, textvariable=self.upd_status, wraplength=420, justify="left").pack(anchor="w", pady=(4, 0))

        own = ttk.LabelFrame(f, text=_("Eigene Map-Zuordnungen"), padding=8)
        own.pack(fill="x", pady=(8, 0))
        self.alias_var = tk.StringVar(value="")
        ttk.Label(own, textvariable=self.alias_var, style="Dim.TLabel", wraplength=300).pack(side="left", fill="x")
        ttk.Button(own, text=_("Alle löschen"), command=self._clear_aliases).pack(side="right")
        self._show_aliases()

        folders = ttk.LabelFrame(f, text=_("Ordner"), padding=8)
        folders.pack(fill="x", pady=(8, 0))
        ttk.Button(folders, text=_("Programmordner öffnen"), command=lambda: self._open(self.root_dir)).pack(side="left")
        ttk.Button(folders, text=_("Karten-Ordner öffnen"),
                   command=lambda: self._open(os.path.join(self.root_dir, "maps"))).pack(side="left", padx=6)
        ttk.Label(f, text=f"DbD Map Scout {__version__} · " + _("liest nur Bildschirmpixel, sendet keine Eingaben ans Spiel."),
                  style="Dim.TLabel", wraplength=430).pack(anchor="w", pady=(10, 0))
        return outer

    def _ui_lang_changed(self):
        code = next((c for c, lbl in self._ui_langs if lbl == self.ui_lang_var.get()), "auto")
        self.settings.set("ui_language", code)
        self._save_soon()
        changed = i18n.resolve(code) != i18n.current()
        self.ui_lang_note.set(_("Wirkt nach dem nächsten Start des Programms.") if changed else "")
        if changed:
            self._log(_("Sprache geändert – wirkt nach dem nächsten Start des Programms."), "System")

    # ----------------------------------------------------------- map list
    def _fill_list(self):
        self.tree.delete(*self.tree.get_children())
        self._list_items = {}
        realms = {}
        for m in self.catalog.search(self.search_var.get()):
            realm = self.catalog.realm_display(m) or _("Eigene Bilder")
            if realm not in realms:
                realms[realm] = self.tree.insert("", "end", text=realm, open=bool(self.search_var.get()))
            for v in [v for v in sorted(m.variants) if m.variants[v]]:
                label = m.label(v) if len(m.variants) > 1 else m.name
                iid = self.tree.insert(realms[realm], "end", text=label)
                self._list_items[iid] = (m.id, v)

    def _pick_selected(self):
        sel = self.tree.selection()
        if sel and sel[0] in self._list_items:
            mid, v = self._list_items[sel[0]]
            self.show_map(mid, v, "manual")

    def _pick_first(self):
        for mid, v in self._list_items.values():
            self.show_map(mid, v, "manual")
            return

    # ============================================================ actions
    def show_map(self, map_id: str, variant: int, source: str, detail: str = "", keep_timer: bool = False):
        m = self.catalog.maps.get(map_id)
        if m is None:
            return
        path, shown = self.catalog.image_path(map_id, variant)
        if path is None:
            self._log(_("Für „{map}“ gibt es kein Bild.", map=m.label(variant)), "Overlay")
            return
        rotation = self._map_rotation(map_id)
        try:
            frames = load_frames(path, rotation)
        except Exception as e:
            self._log(_("Bild konnte nicht geladen werden: {path} ({error})", path=path, error=e), "Fehler")
            return
        was_on = self._map_on()
        self._test_map = False                   # a real/manual choice replaces the test picture
        self._layout_unsure = False
        self.current = (map_id, shown)
        self.source = source
        self.overlay.set_map(path, m.label(shown), rotation)
        if not was_on and not keep_timer:
            self._round_started(time.time())     # map appears -> timer from zero (a switch while on keeps it)
        self.user_visible = True
        self.hidden_after_match = False
        self.menu_paused = False
        self._watch(source)
        self.map_var.set(m.label(shown))
        self.tray.set_title(f"DbD Map Scout – {m.label(shown)}")
        self.realm_var.set(self.catalog.realm_display(m))
        self.detail_var.set(detail or {"manual": _("manuell gewählt"), "scan": _("per Scan gefunden")}.get(source, ""))
        self._set_thumb(frames[0][0])
        self._update_toggle_text()
        self._show_map_size()
        self._update_layout_btn()
        if source == "manual":
            self._log(_("Map gewählt: {map}", map=m.label(shown)), "Overlay")
        self._tick_overlay(reschedule=False)

    def _set_thumb(self, img):
        thumb = img.copy()
        thumb.thumbnail((88, 88))
        bg = Image.new("RGBA", thumb.size, (40, 40, 44, 255))
        bg.alpha_composite(thumb)
        self._thumb = ImageTk.PhotoImage(bg)
        self.thumb_label.configure(image=self._thumb)

    def toggle_overlay(self):
        if not self.overlay.has_map():
            self._log(_("Noch keine Map gewählt."), "Overlay")
            return
        was_on = self._map_on()
        if self.hidden_after_match or self.menu_paused:
            # hidden automatically -> the user wants to see it now; watch again as if picked by hand
            self.user_visible = True
            self.hidden_after_match = self.menu_paused = False
            self._watch("manual")
        else:
            self.user_visible = not self.user_visible
        if self._map_on() and not was_on:
            self._round_started(time.time())
        elif was_on and not self._map_on():
            self._round_ended(time.time())
        self._update_toggle_text()
        self._log(_("Overlay eingeblendet.") if self.user_visible else _("Overlay ausgeblendet."), "Overlay")
        self._tick_overlay(reschedule=False)

    def _watch(self, source):
        """Tell the detector which map is on display (it watches for the end of the match)."""
        self._watch_gen += 1
        self.worker.watch_gen = (self._watch_gen, source)
        self.worker.map_on_screen = True

    def _map_on(self):
        """A map is on display for this round (a menu pause or another active window only hides it briefly)."""
        return self.overlay.has_map() and self.user_visible and not self.hidden_after_match

    def _update_toggle_text(self):
        on = self.user_visible and not self.hidden_after_match and not self.menu_paused
        self.toggle_btn.configure(text=_("Overlay ausblenden") if on else _("Overlay einblenden"))

    def _layouts(self):
        """Layouts with a picture of the map on display ([] without a map)."""
        m = self.catalog.maps.get(self.current[0]) if self.current else None
        return [v for v in sorted(m.variants) if m.variants[v]] if m else []

    def _update_layout_btn(self):
        vs = self._layouts()
        if len(vs) < 2:
            self.layout_btn.pack_forget()
            return
        text = _("Layout {n} von {total}", n=roman(self.current[1]), total=roman(vs[-1])) + " ▸"
        self.layout_btn.configure(text=text + (" " + _("(unsicher)") if self._layout_unsure else ""))
        if not self.layout_btn.winfo_manager():
            self.layout_btn.pack(side="left", padx=(4, 0), before=self.rotate_btn)

    def _hk_hint(self, name):
        combo = (self.settings.get("hotkeys") or {}).get(name)
        return " " + _("Hotkey: {keys}", keys=pretty(combo)) if combo else ""

    def _tip_lookup(self, w):
        """Tooltips for buttons whose label changes or repeats (the rest: tooltip.TIPS by label)."""
        hk = {b: k for k, b in self.hk_buttons.items()}
        if w is self.toggle_btn:
            return lambda: (_("Karte ausblenden (die automatische Erkennung läuft weiter).")
                            if self.toggle_btn.cget("text") == _("Overlay ausblenden") else
                            _("Karte wieder einblenden.")) + self._hk_hint("toggle_overlay")
        if w is self.layout_btn:
            return lambda: (_("Die Erkennung war beim Layout nicht sicher – stimmt es nicht, hier weiterschalten.")
                            + " " if self._layout_unsure else "") + \
                _("Wechselt zum nächsten Layout dieser Map (z. B. Coal Tower ↔ Coal Tower II). Die Layouts ab II "
                  "gibt es seit Patch 8.6.0 nur noch in Custom Games.") + self._hk_hint("next_variant")
        if w is self.rotate_btn:
            return lambda: tooltip.tip_for_label(self.rotate_btn.cget("text")) + self._hk_hint("rotate_map")
        if w is self.test_btn:
            return lambda: (_("Test sofort beenden.") if self.test_btn.cget("text") == _("Test beenden") else
                            _("Zeigt die Karte 10 s an ihrer normalen Position – auch wenn sie gerade ausgeblendet "
                              "wäre. Nochmal drücken beendet den Test."))
        if w is self.adv_btn:
            return _("Technische Optionen für die Fehlersuche ein- oder ausklappen.")
        if w is self.edit_btn:
            return lambda: (_("Verschieben beenden.") if self.edit_btn.cget("text") == _("Fertig") else
                            _("Karte direkt mit der Maus ziehen, Mausrad ändert die Grösse.")
                            + self._hk_hint("edit_position"))
        if w in hk:
            return _("Klicken und die neue Tastenkombination drücken (Strg/Alt + Taste oder F-Taste). "
                     "Esc bricht ab, Entf schaltet den Hotkey aus.")
        text = str(w.cget("text"))
        if text in dict(LANGS).values():
            return _("Map-Namen in dieser Spielsprache erkennen. Nur die Sprachen anhaken, in denen du spielst – "
                     "weniger Sprachen, weniger Verwechslungen.")
        if i18n.source(text) in CATS:
            return _("Meldungen der Art „{category}“ im Log anzeigen.", category=text)
        return None

    def next_variant(self):
        if not self.current:
            return
        m = self.catalog.maps[self.current[0]]
        vs = [v for v in sorted(m.variants) if m.variants[v]]
        if len(vs) < 2:
            self._log(_("„{map}“ hat nur ein Layout.", map=m.name), "Overlay")
            return
        i = vs.index(self.current[1]) if self.current[1] in vs else 0
        self.show_map(m.id, vs[(i + 1) % len(vs)], "manual", _("Layout manuell gewechselt"))

    def step_map(self, step: int):
        items = list(self._list_items.values())
        if not items:
            return
        i = items.index(self.current) if self.current in items else -1
        mid, v = items[(i + step) % len(items)]
        self.show_map(mid, v, "manual")

    def scan_now(self):
        self._log(_("Scanne den Bildschirm nach Map- oder Realm-Namen …"), "Erkennung")
        self.worker.request_scan()

    def test_overlay(self):
        """Show the overlay at its normal place for 10 s, ignoring all reasons to hide it.
        Pressing the button again during the test ends it at once."""
        if time.time() < getattr(self, "_force_until", 0):
            self._force_until = 0
            self._tick_overlay(reschedule=False)
            return
        if not self.overlay.has_map():
            first = next(iter(self._list_items.values()), None)
            if first:
                self.show_map(first[0], first[1], "manual", _("Testanzeige"))
                self._test_map = True            # loaded only for the test: hidden again when it ends
        self._force_until = time.time() + 10
        self._log(_("Test: Overlay 10 s lang an seiner normalen Position – jetzt zu DBD wechseln "
                    "(nochmal drücken beendet den Test)."), "Overlay")
        self.test_btn.configure(text=_("Test beenden"))
        self._tick_overlay(reschedule=False)

    def show_diagnose(self):
        from .diagnose import collect
        try:
            text = collect(self)
        except Exception as e:  # pragma: no cover
            text = f"Diagnose fehlgeschlagen: {e}"
        try:
            with open(os.path.join(self.root_dir, "diagnose.txt"), "w", encoding="utf-8") as fh:
                fh.write(text)
        except OSError:
            pass
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._log(_("Diagnose in die Zwischenablage kopiert (auch als diagnose.txt gespeichert)."), "System")
        log.info(text)

    def toggle_edit(self):
        on = not self.overlay.editing
        if on and not self.overlay.has_map():
            self._log(_("Erst eine Map wählen, dann lässt sich das Overlay verschieben."), "Overlay")
            return
        self.overlay.set_editing(on)
        self.edit_btn.configure(text=_("Fertig") if on else _("Mit der Maus verschieben"))
        if on:
            self._log(_("Overlay mit der Maus ziehen, Mausrad = Grösse. Danach „Fertig“ oder Hotkey."), "Overlay")
        self._tick_overlay(reschedule=False)

    def _overlay_dragged(self, x, y):
        gx, gy, gw, gh = self._game_rect()
        w, h = (self._last_place or (0, 0, 1, 1))[2:]
        o = self.settings["overlay"]
        o["anchor"] = "custom"
        o["pos_x"] = min(1.0, max(0.0, (x - gx) / max(1, gw - w)))
        o["pos_y"] = min(1.0, max(0.0, (y - gy) / max(1, gh - h)))
        self.anchor_var.set(anchor_label("custom"))
        self._set_pos_sliders(o["pos_x"], o["pos_y"])
        self._save_soon()

    def _map_height(self):
        """Overlay size: the map's own size if one was set (hotkeys / mouse wheel), else the slider's."""
        o = self.settings["overlay"]
        own = (o.get("map_heights") or {}).get(self.current[0]) if self.current else None
        return own if own else o["height"]

    def _resize(self, delta):
        """Hotkeys and mouse wheel: size of the map on display (remembered for that map)."""
        o = self.settings["overlay"]
        new = round(min(0.9, max(0.15, self._map_height() + delta)), 3)
        if self.current:
            o.setdefault("map_heights", {})[self.current[0]] = new
        else:
            o["height"] = new
            self.size_var.set(new * 100)
            self.size_label.configure(text=f"{new * 100:.0f} %")
        self._show_map_size()
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _map_rotation(self, map_id=None):
        """Degrees (0/90/180/270) the map is turned clockwise – remembered per map."""
        map_id = map_id or (self.current[0] if self.current else None)
        deg = (self.settings["overlay"].get("map_rotations") or {}).get(map_id, 0) if map_id else 0
        return deg if deg in (0, 90, 180, 270) else 0

    def rotate_map(self):
        """Button/hotkey: turn the map on display by 90° clockwise (the name above it stays upright)."""
        if not self.current:
            self._log(_("Noch keine Map gewählt."), "Overlay")
            return
        deg = (self._map_rotation() + 90) % 360
        rots = self.settings["overlay"].setdefault("map_rotations", {})
        if deg:
            rots[self.current[0]] = deg
        else:
            rots.pop(self.current[0], None)
        self._reload_picture()
        m = self.catalog.maps.get(self.current[0])
        self._log(_("{map} um {deg}° gedreht.", map=m.name if m else self.current[0], deg=deg), "Overlay")
        self._show_map_size()
        self._save_soon()

    def _reload_picture(self):
        """Load the map on display again (rotation/caption changed) without touching visibility or timer."""
        if not self.current:
            return
        m = self.catalog.maps[self.current[0]]
        path, _v = self.catalog.image_path(*self.current)
        if path is None:
            return
        rotation = self._map_rotation()
        try:
            frames = load_frames(path, rotation)
        except Exception as e:
            self._log(_("Bild konnte nicht geladen werden: {path} ({error})", path=path, error=e), "Fehler")
            return
        self.overlay.set_map(path, m.label(self.current[1]), rotation)
        self._set_thumb(frames[0][0])
        self._tick_overlay(reschedule=False)

    def _show_map_size(self):
        """Hint below the size slider when the map on display has a size or rotation of its own."""
        o = self.settings["overlay"]
        own = (o.get("map_heights") or {}).get(self.current[0]) if self.current else None
        deg = self._map_rotation()
        if own or deg:
            m = self.catalog.maps.get(self.current[0])
            parts = ([_("eigene Grösse {n} % (Hotkeys/Mausrad)", n=f"{own * 100:.0f}")] if own else []) + \
                ([_("gedreht um {deg}°", deg=deg)] if deg else [])
            self.map_size_var.set((m.name if m else "") + ": " + " · ".join(parts))
            if not self.map_size_row.winfo_manager():
                self.map_size_row.pack(fill="x", pady=(0, 3), after=self._size_row_after)
        elif self.map_size_row.winfo_manager():
            self.map_size_row.pack_forget()

    def _reset_map_size(self):
        if not self.current:
            return
        o = self.settings["overlay"]
        m = self.catalog.maps.get(self.current[0])
        name = m.name if m else self.current[0]
        if (o.get("map_heights") or {}).pop(self.current[0], None):
            self._log(_("Eigene Grösse für {map} entfernt – es gilt wieder der Schieberegler.", map=name), "Overlay")
        if (o.get("map_rotations") or {}).pop(self.current[0], None):
            self._log(_("Drehung für {map} entfernt.", map=name), "Overlay")
            self._reload_picture()
        self._show_map_size()
        self._save_soon()
        self._tick_overlay(reschedule=False)

    # ============================================================= events
    def _poll(self):
        try:
            while True:
                ev = self.events.get_nowait()
                if isinstance(ev, tuple) and ev[0] == "hotkey":
                    self._hotkey(ev[1])
                elif isinstance(ev, tuple) and ev[0] == "srv_ping":
                    self._srv_ping_done(ev[1])
                elif isinstance(ev, tuple) and ev[0] == "srv_fw":
                    if ev[1]:
                        self._log(_("Firewall-Regeln von Make Your Choice („Enforced“) gefunden – sie sperren "
                                    "Regionen unabhängig von der hosts-Datei. In Make Your Choice „Revert to Default“ "
                                    "drücken."), "Fehler")
                        self.srv_status.set(_("Achtung: Firewall-Regeln von Make Your Choice aktiv (siehe Log).")
                                            + "  " + self.srv_status.get())
                elif isinstance(ev, tuple) and ev[0] == "tray":
                    {"open": self._show_window, "toggle": self.toggle_overlay,
                     "quit": self.quit}.get(ev[1], lambda: None)()
                elif isinstance(ev, tuple) and ev[0] == "autostart":
                    self._autostart_state(*ev[1:])
                elif isinstance(ev, tuple) and ev[0] == "setup_done":
                    self._setup_done(ev[1], ev[2])
                elif isinstance(ev, tuple) and ev[0] == "status_log":
                    self._log(ev[1], "System")
                elif isinstance(ev, tuple) and ev[0] == "conn_started":
                    self._conn_started(ev[1])
                elif isinstance(ev, tuple) and ev[0] == "upd_check":
                    self._update_checked(*ev[1:])
                elif isinstance(ev, tuple) and ev[0] == "srv_job":
                    self._srv_job_done(ev[1], ev[2])
                else:
                    self._event(ev)
        except queue.Empty:
            pass
        self.root.after(50, self._poll)

    def _hotkey(self, name):
        {"toggle_overlay": self.toggle_overlay, "next_variant": self.next_variant, "scan_now": self.scan_now,
         "next_map": lambda: self.step_map(1), "prev_map": lambda: self.step_map(-1),
         "bigger": lambda: self._resize(0.03), "smaller": lambda: self._resize(-0.03),
         "edit_position": self.toggle_edit, "rotate_map": self.rotate_map}.get(name, lambda: None)()

    def _event(self, ev):
        k, d = ev.kind, ev.data
        if k in ("menu", "match_end") and d.get("gen") not in (None, self._watch_gen):
            return                               # about a map that is no longer on display
        if k == "status":
            self._set_status(d["text"])
        elif k == "banner":
            self._log(_("Map-Banner gefunden, lese …"), "Erkennung")
        elif k == "detected":
            m = self.catalog.maps.get(d["map_id"])
            if not m:
                return
            same = (self.current == (d["map_id"], d["variant"]) and self.source == "auto"
                    and not self.hidden_after_match and not self.menu_paused and self.user_visible)
            vp = d["variant_probability"]
            detail = _("automatisch erkannt ({p})", p=f"{d['probability']:.0%}")
            if len(m.variants) > 1:
                detail += " · " + _("Layout {n} ({p})", n=roman(d["variant"]), p=f"{vp:.0%}")
            restarted = self.round.detected(time.time())
            if restarted:
                self._log(_("Rundentimer gestartet."), "Erkennung")
            if restarted or self._hist is None:
                self._hist_open(d["map_id"], d["variant"], "auto")
            if not same:
                self.show_map(d["map_id"], d["variant"], "auto", detail, keep_timer=True)
                self._log(_("Erkannt: {map} – gelesen „{name}“ / „{realm}“", map=m.label(d["variant"]),
                            name=d["name_text"], realm=d["realm_text"]), "Erkennung")
                if len(m.variants) > 1 and vp < 0.8:
                    self._layout_unsure = True
                    self._update_layout_btn()
                    self._log(_("Layout unsicher – falls falsch: Layout-Knopf oder {keys}.",
                                keys=pretty(self.settings["hotkeys"].get("next_variant") or "–")), "Erkennung")
        elif k == "unknown":
            txt = d.get("name_text") or "?"
            self._log(_("Banner gesehen, aber keine bekannte Map: „{text}“. Map manuell wählen "
                        "oder mit „Zuordnen …“ dauerhaft zuordnen.", text=txt), "Erkennung")
            if len(fold(txt)) >= self.catalog.MIN_ALIAS:
                self._unknown = (txt, d.get("realm_text") or "")
                self.unknown_var.set(_("Unbekannte Map gelesen: „{text}“", text=txt))
                self.unknown_bar.pack(fill="x", padx=10, pady=(0, 6), before=self.nb)
        elif k == "match_end":
            self._round_ended(d.get("t") or time.time())
            self._hist_close(d.get("t") or time.time())
            if self.overlay.has_map() and not self.hidden_after_match:
                was_visible = self.user_visible
                self.hidden_after_match = True
                self.menu_paused = False
                self._update_toggle_text()
                reason = _(d.get("reason") or "Ergebnisbildschirm")
                self._log(_("Runde vorbei ({reason}) – Overlay ausgeblendet.", reason=reason) if was_visible
                          else _("Runde vorbei ({reason}).", reason=reason), "Erkennung")
                self._tick_overlay(reschedule=False)
        elif k == "menu":
            if d.get("on"):
                if self.overlay.has_map() and not self.hidden_after_match and not self.menu_paused:
                    self.menu_paused = True
                    self._update_toggle_text()
                    self._log(_("Menü offen (Mauszeiger sichtbar) – Overlay pausiert."), "Overlay")
                    self._tick_overlay(reschedule=False)
            elif self.menu_paused:
                self.menu_paused = False
                self._update_toggle_text()
                self._log(_("Zurück im Spiel – Overlay wieder sichtbar."), "Overlay")
                self._tick_overlay(reschedule=False)
        elif k == "watch_info":
            self._log(d.get("text", ""), "Erkennung")
        elif k == "warn":
            self._log(_("{text} – Details in dbdmapscout.log", text=d.get("text", "")), "Fehler")
        elif k == "scan_result":
            self._scan_result(d)
        elif k == "error":
            self._log(_("Die Erkennung ist abgestürzt – Details in dbdmapscout.log"), "Fehler")
            log.error(d["text"])
            messagebox.showerror("DbD Map Scout", _("Die Erkennung ist abgestürzt:") + "\n\n" + d["text"][-1500:])

    # ---------------------------------------------------------- round history (tab Statistik)
    def _hist_open(self, map_id, variant, source):
        """A map was detected: a round starts. An open round whose end was never detected is dropped
        (its length would be wrong)."""
        m = self.catalog.maps.get(map_id)
        self._hist = {"t": time.time(), "map_id": map_id, "map": m.label(variant) if m else map_id,
                      "region": "", "source": source}

    def _hist_close(self, t):
        rec, self._hist = self._hist, None
        if rec is None:
            return
        seconds = max(0.0, t - rec["t"])
        if not history.should_record(seconds):
            return
        try:
            history.append(self._hist_path(), history.Round(seconds=seconds, **rec))
        except OSError as e:
            self._report_once("history", f"{e}")
            return
        if self.nb.select() == str(self.tab_stats):
            self._stats_render()

    def _hist_path(self):
        return os.path.join(self.root_dir, history.FILE)

    # ---------------------------------------------------------- round timer
    def _round_started(self, t):
        self.round.start(t)
        self._log(_("Rundentimer gestartet."), "Erkennung")

    def _round_ended(self, t):
        if self.round.stop(t):
            self._log(_("Rundentimer gestoppt: {time}.", time=fmt_duration(self.round.elapsed(t))), "Erkennung")

    def _tick_timer(self):
        r = self.round
        if r.start_t is None:
            text, overlay_text = "", ""
        elif r.running:
            overlay_text = fmt_duration(r.elapsed(time.time()))
            text = _("Runde läuft: {time}", time=overlay_text)
        else:
            text, overlay_text = _("Letzte Runde: {time}", time=fmt_duration(r.elapsed(0))), ""
        if text != self.timer_var.get():
            self.timer_var.set(text)
        self.overlay.set_timer(overlay_text if self.settings["overlay"].get("show_timer", True) else "")

    def _set_status(self, text):
        """Technical status from the worker: goes to the log; the status line shows a plain summary."""
        self._worker_status = text
        self._log(text, "System")
        self._update_state()

    def _update_state(self):
        st = user_state(self._worker_status, auto_detect=bool(self.settings.get("auto_detect", True)),
                        game_found=self.game is not None, simulate=bool(self.simulate),
                        has_map=self.overlay.has_map(), map_label=self.map_var.get() if self.current else "",
                        visible_wanted=self.user_visible, hidden_after_match=self.hidden_after_match,
                        menu_paused=self.menu_paused)
        if st.text != self.status_var.get():
            self.status_var.set(st.text)
            self.dot.configure(style=f"Dot{DOT_STYLE[st.kind].title()}.TLabel")

    def _scan_result(self, d):
        hits = d.get("hits") or []
        if d.get("error"):
            self._log(_("Scan fehlgeschlagen: {error}", error=d["error"]), "Fehler")
            return
        maps = [h for h in hits if h.kind == "map"]
        if maps:
            h = maps[0]
            m = self.catalog.maps[h.map_id]
            self.show_map(h.map_id, h.variant, "scan", _("per Scan gefunden: „{text}“", text=h.text))
            if self._hist is None:
                self._hist_open(h.map_id, h.variant, "scan")
            self._log(_("Scan ({s} s): {map}", s=f"{d['seconds']:.1f}", map=m.label(h.variant)), "Erkennung")
            return
        realms = [h for h in hits if h.kind == "realm" and h.realm]
        if realms:
            realm = realms[0].realm
            in_realm = [m for m in self.catalog.maps.values() if m.realm == realm]
            if len(in_realm) == 1:
                self.show_map(in_realm[0].id, 1, "scan", _("Realm „{realm}“ hat nur diese Map", realm=realms[0].text))
            else:
                self.search_var.set(self.catalog.realms.get(realm, {}).get("en", realm))
                self.nb.select(self.tab_maps)
                self._log(_("Scan: Realm „{realm}“ gefunden – bitte Map in der Liste wählen.", realm=realms[0].text), "Erkennung")
            return
        self._log(_("Scan ({s} s): kein Map- oder Realm-Name auf dem Bildschirm.", s=f"{d['seconds']:.1f}"), "Erkennung")

    # ============================================================ hotkeys
    def _start_hotkeys(self):
        t = HotkeyThread(self.settings["hotkeys"], lambda name: self.events.put(("hotkey", name)))
        t.start()
        self.root.after(300, lambda: self._report_hotkeys(t))
        return t

    def _report_hotkeys(self, t):
        if not t.ready.is_set():
            self.root.after(300, lambda: self._report_hotkeys(t))
            return
        labels = dict(HOTKEY_LABELS)
        for name, combo, why in t.failed:
            self._log(_("Hotkey {keys} ({action}) nicht verfügbar: {why}.", keys=pretty(combo),
                        action=_(labels.get(name, name)), why=why), "Fehler")
        if t.failed and hasattr(self, "hk_status"):
            self.hk_status.set(_("{n} Hotkey(s) nicht verfügbar – siehe Log.", n=len(t.failed)))

    # ---------------------------------------------------------- hotkeys: record by pressing
    def _hk_show_all(self):
        for key, b in self.hk_buttons.items():
            combo = self.settings["hotkeys"].get(key, "")
            b.configure(text=pretty(combo) if combo else _("– aus –"))

    def _hk_record(self, key):
        if self._hk_rec:
            self._hk_stop(save=False)
        self._hk_rec, self._hk_mods = key, set()
        b = self.hk_buttons[key]
        b.configure(text=_("Tasten drücken …"))
        b.focus_set()
        # registered global hotkeys never reach this window: release them while recording
        self.hotkeys.stop()
        self.hotkeys.join(timeout=1.5)
        self.hk_status.set(_("Neue Kombination drücken – Esc bricht ab, Entf schaltet den Hotkey aus."))
        b.bind("<KeyPress>", self._hk_key)
        b.bind("<KeyRelease>", self._hk_key_up)
        b.bind("<FocusOut>", lambda e: self._hk_stop(save=False))

    def _hk_key(self, e):
        key = self._hk_rec
        if key is None:
            return None
        if e.keysym == "Escape":
            self._hk_stop(save=False)
            return "break"
        if e.keysym in ("Delete", "BackSpace") and not self._hk_mods:
            self._hk_stop(save=True, combo="")
            return "break"
        m = modifier_name(e.keysym)
        if m:
            self._hk_mods.add(m)
            held = [m for m in ("ctrl", "alt", "shift") if m in self._hk_mods]
            self.hk_buttons[key].configure(text=pretty("+".join(held)) + "+ …")
            return "break"
        combo, why = combo_from_keys(self._hk_mods, e.keysym, e.keycode if IS_WIN else None)
        if combo is None:
            if why:
                self.hk_status.set(why)
            return "break"
        labels = dict(HOTKEY_LABELS)
        taken = [k for k, c in self.settings["hotkeys"].items() if c == combo and k != key]
        if taken:
            self.hk_status.set(_("{keys} ist schon „{action}“ – andere wählen.", keys=pretty(combo),
                                  action=_(labels.get(taken[0], taken[0]))))
            return "break"
        self._hk_stop(save=True, combo=combo)
        return "break"

    def _hk_key_up(self, e):
        m = modifier_name(e.keysym)
        if m:
            self._hk_mods.discard(m)
        return "break"

    def _hk_stop(self, save: bool, combo: str = ""):
        key, self._hk_rec = self._hk_rec, None
        if key is None:
            return
        b = self.hk_buttons[key]
        for seq in ("<KeyPress>", "<KeyRelease>", "<FocusOut>"):
            b.unbind(seq)
        if save:
            self.settings["hotkeys"][key] = combo
            self._save_soon()
            label = _(dict(HOTKEY_LABELS)[key])
            keys = pretty(combo) if combo else _("aus")
            self.hk_status.set(f"{label}: {keys}")
            self._log(_("Hotkey {action}: {keys}.", action=label, keys=keys), "System")
        else:
            self.hk_status.set(_("Zum Ändern anklicken und die neue Tastenkombination drücken."))
        self._hk_show_all()
        self.hotkeys = self._start_hotkeys()

    def _hk_defaults(self):
        from .config import DEFAULTS
        if self._hk_rec:
            self._hk_stop(save=False)
        self.settings["hotkeys"].update(DEFAULTS["hotkeys"])
        self._save_soon()
        self._hk_show_all()
        self.hotkeys.stop()
        self.hotkeys.join(timeout=1.5)
        self.hotkeys = self._start_hotkeys()
        self.hk_status.set(_("Standard-Hotkeys wiederhergestellt."))

    # ============================================================ overlay
    def _game_rect(self):
        now = time.time()
        if now - self._game_checked > 1.0:
            self.game = find_game_window()
            self._game_checked = now
        if self.game and not self.game.minimized and self.game.width > 100:
            return self.game.rect
        return (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())

    def _tick_overlay(self, reschedule=True):
        try:
            self._tick_timer()
            self._place_overlay()
        except Exception:
            self._report_once("overlay", traceback.format_exc())
        try:
            self._conn_tick()
        except Exception:
            self._report_once("verbindung", traceback.format_exc())
        try:
            self._update_state()
            self._layout_pages()
            self._to_tray_if_minimised()
        except Exception:
            self._report_once("status", traceback.format_exc())
        try:
            status = _("Rundenende-Erkennung: {state}", state=self.worker.watch_status)
            if status != self.watch_var.get():
                self.watch_var.set(status)
        except Exception:
            pass
        if reschedule:
            self.root.after(250, self._tick_overlay)

    def _report_once(self, key, text):
        """Log an unexpected error (the full text goes to the log file; the UI once per kind)."""
        log.error(text)
        if key not in self._errors_seen:
            self._errors_seen.add(key)
            last = text.strip().splitlines()[-1] if text.strip() else text
            self._log(_("{text} – Details in dbdmapscout.log", text=f"{key}: {last}"), "Fehler")

    def _tk_error(self, exc, val, tb):
        self._report_once(getattr(exc, "__name__", "tk"), "".join(traceback.format_exception(exc, val, tb)))

    def _place_overlay(self):
        o = self.settings["overlay"]
        self.worker.map_on_screen = self.overlay.has_map() and not self.hidden_after_match
        gx, gy, gw, gh = self._game_rect()               # keeps the game window info fresh
        # test: shown at its normal place, ignoring every reason to hide it
        forced = time.time() < getattr(self, "_force_until", 0) and self.overlay.has_map()
        if forced:
            self._pos_forced = True
        elif getattr(self, "_pos_forced", False):
            self._pos_forced = False
            if getattr(self, "_test_map", False):
                self._test_map = False
                self.user_visible = False
                self._round_ended(time.time())
                self._update_toggle_text()
            self._log(_("Test beendet."), "Overlay")
        if (time.time() >= getattr(self, "_force_until", 0) and hasattr(self, "test_btn")
                and self.test_btn.cget("text") != _("Overlay testen")):
            self.test_btn.configure(text=_("Overlay testen"))
        reason = None
        if forced:
            pass
        elif not self.overlay.has_map():
            reason = _("keine Map")
        elif not ((self.user_visible and not self.hidden_after_match) or self.overlay.editing):
            reason = _("ausgeblendet")
        elif self.menu_paused and not self.overlay.editing:
            reason = _("Menü offen")
        elif not o.get("show_map", True) and not self.overlay.has_info() and not self.overlay.editing:
            reason = _("nichts anzuzeigen")          # info only, but no timer/server yet
        elif (o["only_when_game_focused"] and IS_WIN and not self.overlay.editing and not self.simulate
              and self.game is not None):
            fg = foreground_root()
            own = {self.overlay.hwnd(), self._root_hwnd()}
            if fg not in own and not is_game_window(fg):
                reason = _("aktives Fenster ist {window}", window=describe_window(fg))
        if not forced:
            self._log_visibility(reason, (gx, gy, gw, gh))
        if reason:
            self.overlay.hide()
            self.worker.overlay_rect = None
            return
        if self.overlay.editing and self.overlay._drag:
            return                                           # user is dragging
        self.overlay.opacity = o["opacity"]
        margin = int(gh * o["margin"])
        height = int(gh * self._map_height())
        a = o["anchor"]
        bar = layout.bar_width(gw, gh)          # black bar left/right of a 16:9 picture (ultrawide)
        if a == "auto" and bar < layout.MIN_BAR:
            a = "top-left"

        def place(w, h):
            if a == "auto":
                return gx + max(margin, (bar - w) / 2), gy + margin
            if a == "custom":
                return gx + o.get("pos_x", 0.0) * max(0, gw - w), gy + o.get("pos_y", 0.0) * max(0, gh - h)
            return (gx + margin if a.endswith("left") else gx + gw - w - margin,
                    gy + margin if a.startswith("top") else gy + gh - h - margin)

        # Fit before rendering: only the final size may reach the screen (render() shows it at once).
        iw, ih = self.overlay.map_size()
        w_est = round(iw * height / ih) if ih else 0
        side = (layout.bar_side(a, place(w_est, 0)[0], w_est, gx, gw, bar)
                if a == "auto" or o.get("keep_in_bar", True) else None)
        avail = layout.max_width(bar, margin)
        if side:
            height = layout.fit_height(height, avail, iw, ih)
        w, h = self.overlay.render(height)
        if side and w > avail:                  # info block below is wider than the map (rare)
            w, h = self.overlay.render(max(80, int(height * avail / w)))
        x, y = place(w, h)
        if side:
            x = layout.clamp_x(side, x, w, gx, gw, bar, margin)
        self.overlay.show_at(int(x), int(y))
        self._last_place = (int(x), int(y), w, h)
        self.worker.overlay_rect = self._last_place if self.overlay.shown else None
        if a != "custom":                      # sliders follow the preset position
            self._set_pos_sliders((x - gx) / max(1, gw - w), (y - gy) / max(1, gh - h))

    def _log_visibility(self, reason, game_rect):
        """One log line whenever the overlay goes from visible to hidden or back."""
        if reason == _("keine Map"):
            self._vis_state = reason
            return
        if reason in (_("Menü offen"), _("nichts anzuzeigen")):                     # already logged by the menu event
            self._vis_state = reason
            return
        state = reason or "sichtbar"
        if state == getattr(self, "_vis_state", None):
            return
        self._vis_state = state
        if reason is None:
            src = (_("DBD-Fenster {w}×{h}", w=game_rect[2], h=game_rect[3]) if self.game
                   else _("Bildschirm"))
            self.root.after(300, lambda: self._log(
                _("Overlay sichtbar bei {pos} über {src}.", pos=(self._last_place or ("?", "?"))[:2], src=src),
                "Overlay"))
        elif reason != _("ausgeblendet"):
            self._log(_("Overlay pausiert: {reason}.", reason=reason), "Overlay")

    def _root_hwnd(self):
        if not IS_WIN:
            return 0
        try:
            return int(self.root.wm_frame(), 16)
        except (tk.TclError, ValueError):
            return 0

    # ============================================================ settings
    def _apply_overlay_settings(self):
        o = self.settings["overlay"]
        self.overlay.opacity = o["opacity"]
        self.overlay.show_caption = o["show_caption"]
        self.overlay.set_transparent(o.get("transparent", True))
        self.overlay.set_show_map(o.get("show_map", True))

    def _anchor_changed(self):
        rev = {_(v): k for k, v in ANCHORS}
        self.settings["overlay"]["anchor"] = rev.get(self.anchor_var.get(), "auto")
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _reset_position(self):
        self.anchor_var.set(anchor_label("auto"))
        self._anchor_changed()
        self._log(_("Position zurückgesetzt (automatisch)."), "Overlay")

    def _set_pos_sliders(self, fx, fy):
        fx, fy = min(1.0, max(0.0, fx)), min(1.0, max(0.0, fy))
        if abs(self.posx_var.get() - fx * 100) < 0.5 and abs(self.posy_var.get() - fy * 100) < 0.5:
            return
        self._syncing = True
        try:
            self.posx_var.set(round(fx * 100, 1))
            self.posy_var.set(round(fy * 100, 1))
            self.posx_label.configure(text=f"{fx * 100:.0f} %")
            self.posy_label.configure(text=f"{fy * 100:.0f} %")
        finally:
            self._syncing = False

    def _pos_changed(self):
        if self._syncing:
            return
        o = self.settings["overlay"]
        if o["anchor"] != "custom":
            o["anchor"] = "custom"
            self.anchor_var.set(anchor_label("custom"))
        o["pos_x"] = round(self.posx_var.get() / 100, 4)
        o["pos_y"] = round(self.posy_var.get() / 100, 4)
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _size_changed(self):
        self.settings["overlay"]["height"] = round(self.size_var.get() / 100, 3)
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _opacity_changed(self):
        self.settings["overlay"]["opacity"] = round(self.opacity_var.get() / 100, 2)
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _rate_changed(self):
        self.settings.set("scans_per_second", int(round(self.rate_var.get())))
        self._save_soon()

    def _overlay_flags_changed(self):
        o = self.settings["overlay"]
        o["only_when_game_focused"] = bool(self.focus_var.get())
        o["show_caption"] = bool(self.caption_var.get())
        o["show_timer"] = bool(self.timer_show_var.get())
        o["show_server"] = bool(self.server_show_var.get())
        o["keep_in_bar"] = bool(self.keep_bar_var.get())
        if bool(self.show_map_var.get()) != o.get("show_map", True):
            o["show_map"] = bool(self.show_map_var.get())
            self.overlay.set_show_map(o["show_map"])
            self._log(_("Karte im Overlay eingeblendet.") if o["show_map"] else
                      _("Karte im Overlay aus – es werden nur Timer, Ort und Ping angezeigt."), "Overlay")
        if bool(self.transp_var.get()) != o.get("transparent", True):
            o["transparent"] = bool(self.transp_var.get())
            self.overlay.set_transparent(o["transparent"])
        if self.current:
            self.overlay.show_caption = o["show_caption"]
            self._reload_picture()
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _detect_flags_changed(self):
        self.settings.set("auto_detect", bool(self.auto_var.get()))
        self.settings.set("hide_after_match", bool(self.hide_var.get()))
        self.settings.set("pause_in_menus", bool(self.menu_var.get()))
        self.settings.set("window_capture", bool(self.wgc_var.get()))
        if not self.menu_var.get() and self.menu_paused:
            self.menu_paused = False
            self._update_toggle_text()
            self._tick_overlay(reschedule=False)
        self.settings.set("save_debug_images", bool(self.debug_var.get()))
        self._save_soon()

    # ---------------------------------------------------------- tray and autostart
    def _tray_start(self):
        if not self.tray.active and not self.tray.start():
            self._log(_("Symbol im Infobereich nicht verfügbar ({error}) – Minimieren wie gewohnt.",
                        error=self.tray.error), "Fehler")

    def _tray_flag_changed(self):
        on = bool(self.tray_var.get())
        self.settings.set("tray", on)
        self._save_soon()
        if on and IS_WIN:
            self._tray_start()
        elif not on:
            self.tray.stop()

    def _on_unmap(self, e):
        # <Unmap> also arrives for child widgets (bindtags); only the main window being minimised counts
        if e.widget is self.root:
            self.root.after(10, self._to_tray_if_minimised)

    def _to_tray_if_minimised(self):
        """Minimised -> hide in the notification area. Also checked with the overlay tick, because not every
        way of minimising (taskbar click, Win+Down, "show desktop") sends <Unmap> reliably."""
        try:
            if self.tray.active and self.settings.get("tray", True) and self.root.state() == "iconic":
                self.root.withdraw()
        except tk.TclError:
            pass

    def _show_window(self):
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()
        try:
            self.root.focus_force()
        except tk.TclError:
            pass

    def _setup_then_read_autostart(self):
        """Thread: create/renew task, icon and desktop shortcut if needed (only as administrator,
        no prompt), then read the autostart state for the settings tab."""
        if IS_WIN and is_admin():
            try:
                res = autostart.ensure(self.root_dir, self.settings.get("setup_version"),
                                       self.settings.get("setup_root"))
            except Exception as e:
                res = (False, f"{type(e).__name__}: {e}")
            if res is not None:
                self.events.put(("setup_done", res[0], res[1]))
        elif IS_WIN and not autostart.task_exists(autostart.TASK):
            self.events.put(("setup_done", None, _(
                "Tipp: Einmal als Administrator starten (Rechtsklick auf start.bat → „Als Administrator ausführen“) "
                "– dann richtet das Programm die Desktop-Verknüpfung ein, die künftig ohne Windows-Abfrage startet.")))
        self._read_autostart()

    def _setup_done(self, ok, msg):
        if ok:
            self.settings.set("setup_version", autostart.SETUP_VERSION)
            self.settings.set("setup_root", os.path.abspath(self.root_dir))
            self._save_soon()
            self._log(_("Desktop-Verknüpfung eingerichtet/aktualisiert: startet ab jetzt ohne Windows-Abfrage."),
                      "System")
        elif ok is None:
            self._log(msg, "System")
        else:
            self._log(_("Einrichtung der Verknüpfung fehlgeschlagen: {error}", error=msg), "Fehler")

    def _read_autostart(self):
        """Runs in a thread: does the logon task exist, may we change it (administrator)?"""
        if not IS_WIN:
            self.events.put(("autostart", None, False, _("Nur unter Windows.")))
            return
        exists = autostart.task_exists(autostart.TASK_AUTO)
        admin = is_admin()
        info = ("" if admin else _("Änderbar, wenn das Programm über die Desktop-Verknüpfung gestartet wurde "
                                   "(verknuepfung_erstellen.bat einmal ausführen)."))
        self.events.put(("autostart", exists, admin, info))

    def _autostart_state(self, exists, can_change, info):
        self.autostart_var.set(bool(exists))
        self.autostart_cb.state(["!disabled"] if can_change else ["disabled"])
        self.autostart_info.set(info)

    def _autostart_changed(self):
        on = bool(self.autostart_var.get())
        self.autostart_cb.state(["disabled"])
        self.autostart_info.set(_("Wird eingerichtet …"))
        root_dir = self.root_dir

        def work():
            ok, out = autostart.set_autostart(root_dir, on)
            if ok:
                msg = (_("Startet ab jetzt mit Windows im Infobereich.") if on
                       else _("Startet nicht mehr mit Windows."))
            else:
                msg = _("Fehlgeschlagen: {error}", error=out)
            self.events.put(("autostart", on if ok else not on, True, msg))
            self.events.put(("status_log", msg))
        threading.Thread(target=work, daemon=True, name="autostart").start()

    # ---------------------------------------------------------- updates (done by start.bat)
    def check_update(self):
        """Button: ask GitHub (git fetch) whether there is something new – only on this click."""
        from . import update
        self.upd_btn.state(["disabled"])
        self.upd_apply_btn.pack_forget()
        self.upd_status.set(_("Suche nach Updates …"))

        def work():
            try:
                res = update.check(self.root_dir)
            except Exception as e:
                res = ("error", f"{type(e).__name__}: {e}", False)
            self.events.put(("upd_check",) + tuple(res))
        threading.Thread(target=work, daemon=True, name="update-check").start()

    def _update_checked(self, state, msg, can_apply):
        self.upd_btn.state(["!disabled"])
        self.upd_status.set(msg)
        self._log(msg.splitlines()[0] if msg else "", "System")
        if state == "available" and can_apply:
            self.upd_apply_btn.pack(side="left", padx=6)

    def apply_update(self):
        from . import restart
        try:
            ok = restart.spawn_helper(self.root_dir)
        except OSError as e:
            self.upd_status.set(_("Neustart nicht möglich: {error}", error=e))
            return
        if not ok:
            self.upd_status.set(_("Nur unter Windows: bitte das Programm über start.bat neu starten."))
            return
        self._log(_("Programm startet neu und installiert das Update …"), "System")
        self.quit()

    def _update_flag_changed(self):
        self.settings.set("auto_update", bool(self.update_var.get()))
        self.settings.save()                      # start.bat reads it at the next start

    def _show_update_status(self):
        """What start.bat / update.py did before this start (update installed, skipped, packages)."""
        path = os.path.join(self.root_dir, ".venv", "update_status.txt")
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read().strip()
            os.remove(path)
        except OSError:
            return
        for line in text.splitlines():
            if line.strip():
                self._log(line.rstrip(), "System")

    # ---------------------------------------------------------- own map assignments
    def _hide_unknown(self):
        self.unknown_bar.pack_forget()
        self._unknown = None

    def assign_unknown(self):
        """Dialog: which map was the banner that matched nothing? Saves the read text as an alias."""
        if not self._unknown:
            return
        name, realm = self._unknown
        entries = [m for m in self.catalog.sorted_entries() if not m.custom]
        labels = [f"{m.name} ({self.catalog.realm_display(m)})" for m in entries]
        guess = self.catalog.suggest(name, realm)
        dlg = tk.Toplevel(self.root)
        dlg.title(_("Map zuordnen"))
        dlg.transient(self.root)
        dlg.resizable(False, False)
        body = ttk.Frame(dlg, padding=12)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=_("Gelesen: „{text}“", text=name) + (f" / „{realm}“" if realm else ""),
                  wraplength=380).pack(anchor="w")
        ttk.Label(body, text=_("Welche Map war das? Der Name wird künftig automatisch erkannt."),
                  style="Dim.TLabel", wraplength=380).pack(anchor="w", pady=(2, 8))
        var = tk.StringVar(value=labels[[m.id for m in entries].index(guess)] if guess in
                           [m.id for m in entries] else "")
        cb = ttk.Combobox(body, textvariable=var, values=labels, state="readonly", width=44, height=18)
        cb.pack(fill="x")
        msg = tk.StringVar(value="")
        ttk.Label(body, textvariable=msg, style="Dim.TLabel", wraplength=380).pack(anchor="w", pady=(6, 0))

        def ok():
            if var.get() not in labels:
                msg.set(_("Bitte eine Map auswählen."))
                return
            m = entries[labels.index(var.get())]
            problem = self.catalog.alias_problem(name, m.id)
            if problem:
                msg.set(problem)
                return
            aliases = self.settings.get("user_aliases") or {}
            aliases.setdefault(m.id, [])
            if name not in aliases[m.id]:
                aliases[m.id].append(name)
            self.settings.set("user_aliases", aliases)
            self._save_soon()
            self._reload_catalog()
            dlg.destroy()
            self._hide_unknown()
            self._log(_("„{text}“ wird jetzt als {map} erkannt (eigene Zuordnung).", text=name, map=m.name),
                      "Erkennung")
            self.show_map(m.id, 1, "manual", _("zugeordnet: „{text}“", text=name))

        row = ttk.Frame(body)
        row.pack(fill="x", pady=(10, 0))
        ttk.Button(row, text=_("Zuordnen"), command=ok).pack(side="right")
        ttk.Button(row, text=_("Abbrechen"), command=dlg.destroy).pack(side="right", padx=6)
        dlg.bind("<Return>", lambda e: ok())
        dlg.bind("<Escape>", lambda e: dlg.destroy())
        tooltip.attach_all(dlg)
        cb.focus_set()
        dlg.grab_set()

    def add_picture(self, from_unknown: bool = False):
        """Dialog: own picture for a known map, or a new map (prefilled from an unknown banner)."""
        from .picturedlg import PictureDialog
        name, realm = self._unknown if from_unknown and self._unknown else ("", "")
        self._picture_from_unknown = bool(name)
        PictureDialog(self, name, realm)

    def picture_saved(self, path: str, map_id, variant: int):
        self._reload_catalog()
        if map_id is None:                       # new map: the catalog made it from the file
            map_id = next((m.id for m in self.catalog.maps.values()
                           if m.custom and self.catalog.image_path(m.id)[0]
                           and os.path.normcase(os.path.abspath(self.catalog.image_path(m.id)[0]))
                           == os.path.normcase(os.path.abspath(path))), None)
            if getattr(self, "_picture_from_unknown", False):
                self._hide_unknown()
        rel = os.path.relpath(path, self.root_dir)
        if map_id is None:
            self._log(_("Kartenbild gespeichert: {path}", path=rel), "Overlay")
            return
        m = self.catalog.maps[map_id]
        self._log(_("Eigenes Kartenbild für {map} gespeichert: {path}", map=m.label(variant), path=rel)
                  + (" – " + _("wird ab jetzt automatisch erkannt.") if m.custom else ""), "Overlay")
        self.show_map(map_id, variant, "manual", _("eigenes Bild"))

    def picture_deleted(self, label: str):
        self._reload_catalog()
        self._log(_("Eigenes Kartenbild für {map} gelöscht – das mitgelieferte gilt wieder.", map=label), "Overlay")
        if self.current and self.current[0] in self.catalog.maps:
            self.show_map(self.current[0], self.current[1], self.source or "manual", keep_timer=True)

    def _reload_catalog(self):
        self.catalog = Catalog(self.root_dir, self.settings["languages"], self.settings.get("user_aliases"))
        self.worker.set_catalog(self.catalog)
        self._fill_list()
        self._show_aliases()

    def _show_aliases(self):
        aliases = self.settings.get("user_aliases") or {}
        items = [f"„{t}“ → {self.catalog.maps[mid].name}" for mid, ts in aliases.items() if mid in self.catalog.maps
                 for t in ts]
        self.alias_var.set("; ".join(items) if items else
                           _("Keine. Unbekannte Map-Namen lassen sich nach dem Match im Hauptfenster zuordnen."))

    def _clear_aliases(self):
        if not self.settings.get("user_aliases"):
            return
        if not messagebox.askokcancel(_("Eigene Zuordnungen"), _("Alle eigenen Map-Zuordnungen löschen?"),
                                      parent=self.root):
            return
        self.settings.set("user_aliases", {})
        self._save_soon()
        self._reload_catalog()
        self._log(_("Eigene Map-Zuordnungen gelöscht."), "System")

    def _langs_changed(self):
        langs = [c for c, _ in LANGS if self.lang_vars[c].get()] or ["en"]
        self.settings.set("languages", langs)
        self.catalog = Catalog(self.root_dir, langs, self.settings.get("user_aliases"))
        self.worker.set_catalog(self.catalog)
        self._fill_list()
        self._save_soon()
        self._log(_("Spielsprachen: {langs}", langs=", ".join(langs)), "System")

    def _apply_theme(self):
        dark = bool(self.dark_var.get())
        tooltip.Tooltip.colours = (("#2b2d31", "#e3e5e8", "#50535a") if dark else
                                   ("#ffffe1", "#1b1b1b", "#8a8a8a"))
        theme.apply(self.root, dark, text_widgets=(self.log_text,))
        page_bg = theme.DARK["bg"] if dark else (ttk.Style(self.root).lookup("TFrame", "background")
                                                 or self.root.cget("background"))
        for page in getattr(self, "_pages", []):
            page["canvas"].configure(background=page_bg)
        colors = theme.LOG_COLORS[dark]
        self.log_text.tag_configure("ts", foreground=colors["ts"])
        for c in CATS:
            self.log_text.tag_configure(f"cat_{c}", foreground=colors[c])
        self.log_text.tag_configure("msg", foreground=colors["text"])
        for tag, key in (("p_good", "Erkennung"), ("p_bad", "Fehler"), ("p_na", "ts")):
            self.srv_tree.tag_configure(tag, foreground=colors[key])
        self.srv_tree.tag_configure("p_mid", foreground="#d29922" if dark else "#9a6700")
        self.srv_tree.tag_configure("group", foreground=colors["text"])
        self.log_text.tag_configure("msg_Fehler", foreground=colors["Fehler"])
        self.root.after(50, lambda: theme._titlebar(self.root, dark))   # frame exists only after mapping

    def _dark_changed(self):
        self.settings.set("dark_mode", bool(self.dark_var.get()))
        self._apply_theme()
        self._save_soon()

    def _save_soon(self):
        if self._save_job:
            self.root.after_cancel(self._save_job)
        self._save_job = self.root.after(600, self.settings.save)

    # ================================================================= log
    def _log(self, text, cat="System"):
        entry = (time.strftime("%H:%M:%S"), cat if cat in CATS else "System", text)
        self._log_entries.append(entry)
        log.info(f"[{_(entry[1])}] {text}")
        if self.cat_vars[entry[1]].get():
            self._append_log(entry)
        if entry[1] == "Fehler" and self.nb.select() != str(self.tab_log):
            self.nb.tab(self.tab_log, text="Log ⚠")

    def _append_log(self, entry):
        ts, cat, text = entry
        t = self.log_text
        t.configure(state="normal")
        t.insert("end", ts + "  ", "ts")
        t.insert("end", f"{_(cat):<9}", f"cat_{cat}")
        t.insert("end", "  " + text + "\n", "msg_Fehler" if cat == "Fehler" else "msg")
        lines = int(t.index("end-1c").split(".")[0])
        if lines > 1200:
            t.delete("1.0", f"{lines - 1200}.0")
        t.see("end")
        t.configure(state="disabled")

    def _render_log(self):
        t = self.log_text
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.configure(state="disabled")
        for entry in self._log_entries:
            if self.cat_vars[entry[1]].get():
                self._append_log(entry)

    def _log_filter_changed(self):
        self.settings.set("log_categories", [c for c in CATS if self.cat_vars[c].get()])
        self._save_soon()
        self._render_log()

    def _clear_log(self):
        self._log_entries.clear()
        self._render_log()

    def _tab_changed(self):
        if self.nb.select() == str(self.tab_stats):
            self._stats_render()
        if self.nb.select() == str(self.tab_log):
            self.nb.tab(self.tab_log, text="Log")
        if self.nb.select() == str(self.tab_server):
            self._srv_refresh()
            if not getattr(self, "_fw_checked", False):
                self._fw_checked = True
                threading.Thread(target=lambda: self.events.put(("srv_fw", regions.myc_firewall_active())),
                                 daemon=True).start()
            if time.time() - self._srv_last_ping > 60 and not self._srv_busy:
                self.srv_measure()

    def _open_logfile(self):
        self._open(os.path.join(self.root_dir, "dbdmapscout.log"))

    def _open(self, path):
        try:
            if IS_WIN:
                os.startfile(path)                     # noqa: S606 – opens Explorer / editor
            else:
                self._log(_("Öffnen nur unter Windows: {path}", path=path), "System")
        except OSError as e:
            self._log(_("Kann {path} nicht öffnen: {error}", path=path, error=e), "Fehler")

    # ======================================================== window state
    def _restore_geometry(self):
        geo = self.settings.get("window_geometry") or ""
        m = re.fullmatch(r"(\d+)x(\d+)([+-])(-?\d+)([+-])(-?\d+)", geo)
        if not m:
            return
        try:
            w, h = int(m.group(1)), int(m.group(2))
            x = int(m.group(4)) * (-1 if m.group(3) == "-" else 1)
            y = int(m.group(6)) * (-1 if m.group(5) == "-" else 1)
        except ValueError:
            return
        try:                                   # never narrower than the content (e.g. after new tabs)
            self.root.update_idletasks()
            w, h = max(w, self.root.winfo_reqwidth()), max(h, 600)
        except tk.TclError:
            pass
        vx, vy, vw, vh = 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        if IS_WIN:
            try:
                import ctypes
                u = ctypes.windll.user32
                vx, vy, vw, vh = u.GetSystemMetrics(76), u.GetSystemMetrics(77), u.GetSystemMetrics(78), u.GetSystemMetrics(79)
            except Exception:
                pass
        if vx - 50 <= x <= vx + vw - 100 and vy - 10 <= y <= vy + vh - 100:
            self.root.geometry(f"{w}x{h}+{x}+{y}")
        else:
            self.root.geometry(f"{w}x{h}")

    def quit(self):
        try:
            if self.root.state() == "normal":
                self.settings.set("window_geometry", self.root.geometry())
            self.settings.save()
            self.tray.stop()
            self.conn.stop()
            self.worker.stop()
            self.hotkeys.stop()
            self.worker.join(timeout=4)      # let a running OCR call finish cleanly
            if hasattr(self.overlay, "destroy"):
                self.overlay.destroy()
        finally:
            self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":  # pragma: no cover
    sys.exit("Start mit: python -m dbdmapscout")
