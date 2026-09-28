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

from . import __version__, regions, theme
from .capture import IS_WIN, describe_window, find_game_window, foreground_root, is_game_window
from .catalog import Catalog
from .config import Settings
from .connwatch import ConnectionWatch
from .hotkeys import HotkeyThread, parse, pretty
from .overlay import load_frames
from .overlay_win32 import make_overlay
from .roundtimer import RoundTimer
from .textnorm import fmt_duration, fold, roman
from .worker import DetectionWorker

LANGS = [("en", "EN"), ("de", "DE"), ("fr", "FR"), ("es", "ES"), ("es-MX", "ES-MX"), ("it", "IT"),
         ("pl", "PL"), ("pt-BR", "PT"), ("tr", "TR")]
ANCHORS = [("auto", "automatisch"), ("top-left", "oben links"), ("top-right", "oben rechts"),
           ("bottom-left", "unten links"), ("bottom-right", "unten rechts"), ("custom", "eigene Position")]
HOTKEY_LABELS = [("toggle_overlay", "Overlay ein/aus"), ("next_variant", "Layout-Variante"),
                 ("scan_now", "Bildschirm scannen"), ("prev_map", "Vorherige Map"), ("next_map", "Nächste Map"),
                 ("bigger", "Grösser"), ("smaller", "Kleiner"), ("edit_position", "Mit Maus verschieben")]
CATS = ["Erkennung", "Overlay", "System", "Fehler"]

log = logging.getLogger("dbdmapscout")


class App:
    def __init__(self, root_dir: str, simulate: str | None = None):
        self.root_dir = root_dir
        self.simulate = simulate
        self.settings = Settings(os.path.join(root_dir, "settings.json"))
        self.catalog = Catalog(root_dir, self.settings["languages"], self.settings.get("user_aliases"))
        self._unknown = None             # (name text, realm text) of the last banner that matched no map
        self.events: queue.Queue = queue.Queue()

        self.root = tk.Tk()
        self.root.title(f"DbD Map Scout {__version__}")
        self.root.minsize(470, 600)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.report_callback_exception = self._tk_error

        self.current = None            # (map_id, variant)
        self.source = None             # "auto" | "manual" | "scan"
        self.user_visible = True       # overlay toggle
        self.hidden_after_match = False  # match over -> hidden until the next map
        self.menu_paused = False         # a DBD menu is open (pointer visible) -> hidden for now
        self._watch_gen = 0
        self.round = RoundTimer()        # runs while a map is on display
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
        self._log(f"Bereit. {len(self.catalog.maps)} Maps geladen, Spielsprachen: "
                  f"{', '.join(self.settings['languages'])}.", "System")
        self._srv_refresh(log_summary=True)
        if self.settings.get("show_connection"):
            self.root.after(1500, self._conn_start)
        if not IS_WIN and not simulate:
            self._log("Kein Windows: Fenstersuche, Hotkeys und Click-Through sind nur unter Windows aktiv.", "System")

    # ================================================================== UI
    def _build_ui(self):
        theme.apply(self.root, False)             # base styles; dark mode is applied at the end
        # ---------------------------------------------------------- header
        head = ttk.Frame(self.root)
        head.pack(fill="x", padx=10, pady=(8, 2))
        self.dot = ttk.Label(head, text="●", style="DotWarn.TLabel")
        self.dot.pack(side="left")
        self.status_var = tk.StringVar(value="Starte …")
        ttk.Label(head, textvariable=self.status_var, wraplength=430).pack(side="left", padx=(4, 0))

        card = ttk.Frame(self.root)
        card.pack(fill="x", padx=10, pady=4)
        self.thumb_label = ttk.Label(card)
        self.thumb_label.pack(side="left", padx=(0, 10))
        info = ttk.Frame(card)
        info.pack(side="left", fill="x", expand=True)
        self.map_var = tk.StringVar(value="Noch keine Map")
        self.realm_var = tk.StringVar(value="")
        self.detail_var = tk.StringVar(value="Wird beim Match-Start automatisch erkannt.")
        ttk.Label(info, textvariable=self.map_var, style="Big.TLabel").pack(anchor="w")
        ttk.Label(info, textvariable=self.realm_var).pack(anchor="w")
        ttk.Label(info, textvariable=self.detail_var, style="Dim.TLabel", wraplength=320).pack(anchor="w")
        self.timer_var = tk.StringVar(value="")
        ttk.Label(info, textvariable=self.timer_var).pack(anchor="w")
        self.conn_var = tk.StringVar(value="")
        ttk.Label(info, textvariable=self.conn_var).pack(anchor="w")

        btns = ttk.Frame(self.root)
        btns.pack(fill="x", padx=10, pady=(2, 6))
        self.toggle_btn = ttk.Button(btns, text="Overlay ausblenden", command=self.toggle_overlay)
        self.toggle_btn.pack(side="left")
        ttk.Button(btns, text="Layout ▸", command=self.next_variant).pack(side="left", padx=4)
        ttk.Button(btns, text="Scannen", command=self.scan_now).pack(side="left")
        ttk.Button(btns, text="Overlay testen", command=self.test_overlay).pack(side="left", padx=4)

        # shown when a banner matched no map: assign the read name to a map with one click
        self.unknown_bar = ttk.Frame(self.root)
        self.unknown_var = tk.StringVar(value="")
        ttk.Button(self.unknown_bar, text="✕", width=3, command=self._hide_unknown).pack(side="right")
        ttk.Button(self.unknown_bar, text="Zuordnen …", command=self.assign_unknown).pack(side="right", padx=4)
        ttk.Label(self.unknown_bar, textvariable=self.unknown_var, wraplength=300).pack(side="left", fill="x")

        # ------------------------------------------------------- tab menu
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        self.tab_maps = self._tab_maps()
        self.tab_overlay = self._tab_overlay()
        self.tab_detect = self._tab_detect()
        self.tab_server = self._tab_server()
        self.tab_log = self._tab_log()
        self.tab_settings = self._tab_settings()
        self.nb.add(self.tab_maps, text="Maps")
        self.nb.add(self.tab_overlay, text="Overlay")
        self.nb.add(self.tab_detect, text="Erkennung")
        self.nb.add(self.tab_server, text="Server")
        self.nb.add(self.tab_log, text="Log")
        self.nb.add(self.tab_settings, text="Einstellungen")
        self.nb.bind("<<NotebookTabChanged>>", lambda e: self._tab_changed())

        # ---------------------------------------------------------- footer
        self.last_var = tk.StringVar(value="")
        ttk.Label(self.root, textvariable=self.last_var, style="Dim.TLabel", wraplength=450).pack(
            fill="x", padx=10, pady=(0, 8))
        self._apply_theme()

    # ------------------------------------------------------------ tab: maps
    def _tab_maps(self):
        f = ttk.Frame(self.nb, padding=8)
        srow = ttk.Frame(f)
        srow.pack(fill="x", pady=(0, 6))
        ttk.Label(srow, text="Suche").pack(side="left")
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
        ttk.Label(f, text="Doppelklick zeigt die Map. Die Erkennung übernimmt beim nächsten Match wieder.",
                  style="Dim.TLabel", wraplength=420).pack(anchor="w", pady=(6, 0))
        self._fill_list()
        return f

    # --------------------------------------------------------- tab: overlay
    def _slider(self, parent, label, var, lo, hi, cmd, fmt="{:.0f} %"):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=3)
        ttk.Label(row, text=label, width=11).pack(side="left")
        val = ttk.Label(row, text=fmt.format(var.get()), width=6, anchor="e")
        val.pack(side="right")

        def changed(_=None):
            val.configure(text=fmt.format(var.get()))
            cmd()
        scale = ttk.Scale(row, from_=lo, to=hi, variable=var, command=changed)
        scale.pack(side="left", fill="x", expand=True, padx=6)
        return val

    def _tab_overlay(self):
        f = ttk.Frame(self.nb, padding=8)
        o = self.settings["overlay"]
        pos = ttk.LabelFrame(f, text="Position", padding=8)
        pos.pack(fill="x")
        r = ttk.Frame(pos)
        r.pack(fill="x", pady=(0, 4))
        ttk.Label(r, text="Vorgabe", width=11).pack(side="left")
        self.anchor_var = tk.StringVar(value=dict(ANCHORS).get(o["anchor"], "automatisch"))
        cb = ttk.Combobox(r, textvariable=self.anchor_var, values=[a[1] for a in ANCHORS], state="readonly", width=16)
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self._anchor_changed())
        ttk.Button(r, text="Zurücksetzen", command=self._reset_position).pack(side="right")
        self.posx_var = tk.DoubleVar(value=o.get("pos_x", 0.0) * 100)
        self.posy_var = tk.DoubleVar(value=o.get("pos_y", 0.0) * 100)
        self.posx_label = self._slider(pos, "Horizontal", self.posx_var, 0, 100, self._pos_changed)
        self.posy_label = self._slider(pos, "Vertikal", self.posy_var, 0, 100, self._pos_changed)
        r2 = ttk.Frame(pos)
        r2.pack(fill="x", pady=(4, 0))
        self.edit_btn = ttk.Button(r2, text="Mit der Maus verschieben", command=self.toggle_edit)
        self.edit_btn.pack(side="left")
        ttk.Label(r2, text="0 % = links/oben, 100 % = rechts/unten", style="Dim.TLabel").pack(side="right")

        look = ttk.LabelFrame(f, text="Darstellung", padding=8)
        look.pack(fill="x", pady=(8, 0))
        self.size_var = tk.DoubleVar(value=o["height"] * 100)
        self.size_label = self._slider(look, "Grösse", self.size_var, 15, 90, self._size_changed)
        self.opacity_var = tk.DoubleVar(value=o["opacity"] * 100)
        self._slider(look, "Deckkraft", self.opacity_var, 25, 100, self._opacity_changed)
        self.focus_var = tk.BooleanVar(value=o["only_when_game_focused"])
        self.caption_var = tk.BooleanVar(value=o["show_caption"])
        self.transp_var = tk.BooleanVar(value=o.get("transparent", True))
        self.timer_show_var = tk.BooleanVar(value=o.get("show_timer", True))
        self.server_show_var = tk.BooleanVar(value=o.get("show_server", True))
        for text, var in (("Nur zeigen, wenn DBD das aktive Fenster ist", self.focus_var),
                          ("Map-Namen über der Karte anzeigen", self.caption_var),
                          ("Rundentimer unter der Karte anzeigen", self.timer_show_var),
                          ("Verbundenen Server unter der Karte anzeigen (Tab Server)", self.server_show_var),
                          ("Transparenter Rand um die Karte", self.transp_var)):
            ttk.Checkbutton(look, text=text, variable=var, command=self._overlay_flags_changed).pack(anchor="w", pady=1)
        return f

    # ------------------------------------------------------- tab: detection
    def _tab_detect(self):
        f = ttk.Frame(self.nb, padding=8)
        auto = ttk.LabelFrame(f, text="Automatik", padding=8)
        auto.pack(fill="x")
        self.auto_var = tk.BooleanVar(value=self.settings["auto_detect"])
        self.hide_var = tk.BooleanVar(value=self.settings["hide_after_match"])
        ttk.Checkbutton(auto, text="Map beim Match-Start automatisch erkennen", variable=self.auto_var,
                        command=self._detect_flags_changed).pack(anchor="w", pady=1)
        ttk.Checkbutton(auto, text="Overlay ausblenden, sobald ich nicht mehr in der Runde bin",
                        variable=self.hide_var, command=self._detect_flags_changed).pack(anchor="w", pady=1)
        ttk.Label(auto, text="erkennt Ergebnisbildschirm, Lobby/Menüs, Ladebildschirm und geschlossenes DBD",
                  style="Dim.TLabel", wraplength=400).pack(anchor="w", padx=(22, 0))
        self.menu_var = tk.BooleanVar(value=self.settings.get("pause_in_menus", True))
        ttk.Checkbutton(auto, text="Overlay pausieren, solange ein DBD-Menü offen ist",
                        variable=self.menu_var, command=self._detect_flags_changed).pack(anchor="w", pady=(4, 1))
        ttk.Label(auto, text="erkannt am sichtbaren Mauszeiger (ESC-Menü, Ergebnisbildschirm, Lobby)",
                  style="Dim.TLabel", wraplength=400).pack(anchor="w", padx=(22, 0))
        self.wgc_var = tk.BooleanVar(value=self.settings.get("window_capture", True))
        ttk.Checkbutton(auto, text="Auch erkennen, wenn andere Fenster über DBD liegen",
                        variable=self.wgc_var, command=self._detect_flags_changed).pack(anchor="w", pady=(4, 1))
        ttk.Label(auto, text="Fensteraufnahme wie bei OBS (Windows Graphics Capture), nur solange DBD im "
                             "Hintergrund ist", style="Dim.TLabel", wraplength=400).pack(anchor="w", padx=(22, 0))
        self.watch_var = tk.StringVar(value="Rundenende-Erkennung: keine Map angezeigt")
        ttk.Label(auto, textvariable=self.watch_var, style="Dim.TLabel", wraplength=420).pack(anchor="w", pady=(6, 2))
        self.rate_var = tk.DoubleVar(value=float(self.settings.get("scans_per_second", 5)))
        self._slider(auto, "Scans/Sek.", self.rate_var, 2, 10, self._rate_changed, fmt="{:.0f}")

        lang = ttk.LabelFrame(f, text="Spielsprache (Map-Namen)", padding=8)
        lang.pack(fill="x", pady=(8, 0))
        grid = ttk.Frame(lang)
        grid.pack(anchor="w")
        self.lang_vars = {}
        for i, (code, label) in enumerate(LANGS):
            v = tk.BooleanVar(value=code in self.settings["languages"])
            self.lang_vars[code] = v
            ttk.Checkbutton(grid, text=label, variable=v, command=self._langs_changed).grid(
                row=i // 5, column=i % 5, sticky="w", padx=(0, 12), pady=1)

        dbg = ttk.LabelFrame(f, text="Fehlersuche", padding=8)
        dbg.pack(fill="x", pady=(8, 0))
        self.debug_var = tk.BooleanVar(value=self.settings["save_debug_images"])
        ttk.Checkbutton(dbg, text="Debug-Bilder speichern (Ordner debug/)", variable=self.debug_var,
                        command=self._detect_flags_changed).pack(anchor="w")
        r = ttk.Frame(dbg)
        r.pack(fill="x", pady=(6, 0))
        ttk.Button(r, text="Bildschirm jetzt scannen", command=self.scan_now).pack(side="left")
        ttk.Button(r, text="Diagnose kopieren", command=self.show_diagnose).pack(side="left", padx=6)
        return f

    # ----------------------------------------------------------- tab: server
    def _tab_server(self):
        f = ttk.Frame(self.nb, padding=8)
        ttk.Label(f, text="DBD sucht Matches nur auf den angehakten Serverregionen. Die übrigen werden in der "
                          "Windows-hosts-Datei gesperrt (wie bei „Make Your Choice“). Das Spiel selbst wird "
                          "dabei nicht verändert.", style="Dim.TLabel", wraplength=440).pack(anchor="w")
        tf = ttk.Frame(f)
        tf.pack(fill="both", expand=True, pady=(6, 0))
        t = ttk.Treeview(tf, columns=("ping", "state"), show="tree headings", height=11, selectmode="browse")
        t.heading("#0", text="Region", anchor="w")
        t.heading("ping", text="Ping", anchor="e")
        t.heading("state", text="hosts-Datei", anchor="w")
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
            t.insert("", "end", iid=f"g:{g}", text=g, open=True, tags=("group",))
            for code, name, grp in regions.REGIONS:
                if grp == g:
                    t.insert(f"g:{g}", "end", iid=f"r:{code}", text=name, values=("", ""))
        t.bind("<Button-1>", self._srv_click)
        t.bind("<space>", lambda e: self._srv_toggle(t.focus()))
        row = ttk.Frame(f)
        row.pack(fill="x", pady=(6, 0))
        self.srv_btns = [ttk.Button(row, text="Ping messen", command=self.srv_measure),
                         ttk.Button(row, text="Auswahl anwenden", command=self.srv_apply),
                         ttk.Button(row, text="Alles freigeben", command=self.srv_release)]
        self.srv_btns[0].pack(side="left")
        self.srv_btns[1].pack(side="left", padx=6)
        self.srv_btns[2].pack(side="left")
        self.srv_status = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.srv_status, wraplength=440).pack(anchor="w", pady=(6, 0))
        conn = ttk.Frame(f)
        conn.pack(fill="x", pady=(8, 0))
        self.conn_show_var = tk.BooleanVar(value=bool(self.settings.get("show_connection")))
        ttk.Checkbutton(conn, text="Verbundenen Spielserver anzeigen (Administratorrechte)",
                        variable=self.conn_show_var, command=self._conn_toggled).pack(anchor="w")
        self.conn_tab_var = tk.StringVar(value="")
        ttk.Label(conn, textvariable=self.conn_tab_var, style="Big.TLabel").pack(anchor="w")
        ttk.Label(f, text="Windows fragt beim Anwenden nach Administratorrechten. Danach DBD neu starten. "
                          "Mit VPN unzuverlässig. BHVR hat solche Region-Tools weder erlaubt noch verboten – "
                          "Nutzung auf eigene Verantwortung.", style="Dim.TLabel", wraplength=440).pack(
            anchor="w", pady=(4, 0))
        self._srv_render()
        return f

    # ---------------------------------------------------------- connected server
    def _conn_toggled(self):
        on = bool(self.conn_show_var.get())
        self.settings.set("show_connection", on)
        self._save_soon()
        if on:
            self._conn_start()
        else:
            self.conn.stop()
            self._log("Anzeige des Spielservers beendet.", "System")
            self._conn_tick(force=True)

    def _conn_start(self):
        if self.conn.running or self._conn_busy:
            return
        self._conn_busy = True
        self.conn_tab_var.set("Warte auf Windows (Administratorrechte) …")
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
            self._log(f"Spielserver-Anzeige: {err.get('error', 'Fehler')}", "Fehler")
            self.conn.error = err.get("error", "")
            if err.get("cancelled") or not IS_WIN:
                self.conn_show_var.set(False)
                self.settings.set("show_connection", False)
                self._save_soon()
                self.conn.error = ""
        else:
            self._log("Spielserver-Anzeige läuft (liest nur Paketköpfe, keine Inhalte).", "System")
        self._conn_tick(force=True)

    def _conn_tick(self, force=False):
        now = time.time()
        if not force and now < self._conn_next:
            return
        self._conn_next = now + 1.0
        was_running = self.conn.running
        self.conn.poll(now)
        if was_running and not self.conn.running and self.conn.error:
            self._log(f"Spielserver-Anzeige beendet: {self.conn.error}", "Fehler")
        srv = self.conn.server
        key = (srv["ip"], srv["region"]) if srv else None
        if key != self._conn_last:
            self._conn_last = key
            if srv:
                note = "" if srv["region"] in self.srv_sel else " – nicht in deiner Regionsauswahl"
                # region only: the log file is kept on disk, the server address is shown live in the window only
                self._log(f"Verbunden mit Spielserver: {regions.NAMES.get(srv['region'], srv['region'])}{note}.",
                          "System")
        text = self.conn.text()
        if self._conn_busy:
            text = "Warte auf Windows (Administratorrechte) …"
        self.conn_tab_var.set(f"Verbunden mit: {text}" if text and self.conn.running else text)
        show = self.settings["overlay"].get("show_server", True)
        self.overlay.set_server(regions.NAMES.get(srv["region"], srv["region"]) if srv and show else "",
                                self.conn.ping_ms)
        main = f"Verbunden mit: {text}" if self.conn.running else ""
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
            t.item(f"g:{g}", text=f"{box}  {g}")
            for c in codes:
                p = self.srv_ping.get(c)
                ms = p.get("ms") if p else None
                ping = "…" if self._srv_busy and p is None else ("–" if ms is None else f"{ms:.0f} ms")
                tag = ("p_na" if ms is None else "p_good" if ms < 80 else "p_mid" if ms < 130 else "p_bad")
                t.item(f"r:{c}", text=f"{'☑' if c in self.srv_sel else '☐'}  {regions.NAMES[c]}",
                       values=(ping, states.get(c, "?")), tags=(tag,))

    def _srv_refresh(self, log_summary=False):
        """Read the hosts file (no administrator rights needed)."""
        self.srv_state = regions.current_state()
        st = self.srv_state
        if st.get("error"):
            self.srv_status.set(f"hosts-Datei nicht lesbar: {st['error']}")
            self._srv_render()
            return
        rs = st["regions"]
        visible = [c for c, _, _ in regions.REGIONS]
        free = [c for c in visible if rs.get(c) == "frei"]
        if st["own"] and not self.settings.get("regions_selected"):
            self.srv_sel = set(free)                          # show what is actually active
        if st["own"]:
            text = f"Aktiv: nur {', '.join(regions.NAMES[c] for c in free) or '(keine)'} erlaubt."
        elif any(v != "frei" for v in rs.values()):
            text = "Keine eigene Auswahl aktiv, aber andere Einträge sperren Regionen."
        else:
            text = "Keine Region gesperrt – DBD wählt selbst."
        if st["foreign"]:
            who = "Make Your Choice" if st["myc"] else "anderen Programmen"
            text += f" Es gibt {st['foreign']} Einträge von {who} für DBD-Server (werden beim Anwenden ersetzt)."
        self.srv_status.set(text)
        self._srv_render()
        if log_summary and (st["own"] or st["foreign"]):
            self._log(f"Serverregionen: {text}", "System")

    def srv_measure(self):
        if self._srv_busy:
            return
        self._srv_busy = True
        self.srv_ping = {}
        self._srv_render()
        self.srv_status.set("Messe Ping zu den Serverregionen …")
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
            self.srv_status.set(f"Ping fehlgeschlagen: {res['_error']}")
            return
        self.srv_ping = res
        ok = {c: r["ms"] for c, r in res.items() if r.get("ms") is not None}
        self._srv_refresh()
        if ok:
            best = sorted(ok, key=ok.get)[:3]
            self.srv_status.set(self.srv_status.get() + "  Am schnellsten: " +
                                ", ".join(f"{regions.NAMES[c]} {ok[c]:.0f} ms" for c in best) + ".")
        else:
            self.srv_status.set("Keine Region hat geantwortet (Internet/Firewall/VPN?).")

    def srv_apply(self):
        if self._srv_busy:
            return
        sel = [c for c, _, _ in regions.REGIONS if c in self.srv_sel]
        if not sel:
            messagebox.showinfo("Serverregionen", "Bitte mindestens eine Region anhaken.")
            return
        if len(sel) == len(regions.REGIONS):
            self.srv_release()
            return
        names = ", ".join(regions.NAMES[c] for c in sel)
        foreign = self.srv_state.get("foreign", 0)
        msg = (f"Erlaubt bleiben: {names}.\n\nAlle anderen DBD-Serverregionen werden in der Windows-hosts-Datei "
               f"gesperrt. Windows fragt gleich nach Administratorrechten.")
        if foreign:
            msg += f"\n\n{foreign} vorhandene Einträge anderer Programme (z. B. Make Your Choice) für DBD-Server " \
                   f"werden dabei entfernt."
        msg += "\n\nDanach DBD neu starten, damit es wirkt."
        if not messagebox.askokcancel("Serverregionen anwenden", msg, parent=self.root):
            return
        self._srv_run({"block": regions.block_list(sel), "allowed": sel, "remove_foreign": True},
                      f"Nur noch {names} erlaubt")

    def srv_release(self):
        if self._srv_busy:
            return
        st = self.srv_state
        if not st.get("own") and not st.get("foreign"):
            self.srv_status.set("Es ist nichts gesperrt.")
            return
        msg = "Alle Sperren für DBD-Serverregionen aus der hosts-Datei entfernen"
        msg += " (auch die von Make Your Choice)?" if st.get("myc") else "?"
        msg += "\n\nWindows fragt gleich nach Administratorrechten. Danach DBD neu starten."
        if not messagebox.askokcancel("Serverregionen freigeben", msg, parent=self.root):
            return
        self._srv_run({"block": [], "remove_foreign": True}, "Alle Regionen freigegeben")

    def _srv_run(self, job, label):
        self._srv_busy = True
        for b in self.srv_btns:
            b.state(["disabled"])
        self.srv_status.set("Warte auf Windows (Administratorrechte) …")
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
                self._log(f"Serverregionen: {label}. DBD neu starten, damit es wirkt.", "System")
                self.srv_status.set(f"{label}. DBD jetzt neu starten.  " + self.srv_status.get())
            else:
                self.srv_status.set("Keine Änderung nötig.  " + self.srv_status.get())
        else:
            err = res.get("error", "unbekannter Fehler")
            self._log(f"Serverregionen: {err}", "System" if res.get("cancelled") else "Fehler")
            self.srv_status.set(err)

    # -------------------------------------------------------------- tab: log
    def _tab_log(self):
        f = ttk.Frame(self.nb, padding=8)
        top = ttk.Frame(f)
        top.pack(fill="x", pady=(0, 6))
        ttk.Label(top, text="Anzeigen:").pack(side="left")
        enabled = set(self.settings.get("log_categories", CATS))
        self.cat_vars = {}
        for c in CATS:
            v = tk.BooleanVar(value=c in enabled)
            self.cat_vars[c] = v
            ttk.Checkbutton(top, text=c, variable=v, command=self._log_filter_changed).pack(side="left", padx=(6, 0))
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
        ttk.Button(bottom, text="Leeren", command=self._clear_log).pack(side="left")
        ttk.Button(bottom, text="Log-Datei öffnen", command=self._open_logfile).pack(side="left", padx=6)
        ttk.Button(bottom, text="Diagnose kopieren", command=self.show_diagnose).pack(side="left")
        return f

    # --------------------------------------------------------- tab: settings
    def _tab_settings(self):
        f = ttk.Frame(self.nb, padding=8)
        look = ttk.LabelFrame(f, text="Darstellung", padding=8)
        look.pack(fill="x")
        self.dark_var = tk.BooleanVar(value=self.settings.get("dark_mode", True))
        ttk.Checkbutton(look, text="Dark Mode", variable=self.dark_var, command=self._dark_changed).pack(anchor="w")

        hk = ttk.LabelFrame(f, text="Hotkeys", padding=8)
        hk.pack(fill="x", pady=(8, 0))
        self.hk_entries = {}
        grid = ttk.Frame(hk)
        grid.pack(fill="x")
        for i, (key, label) in enumerate(HOTKEY_LABELS):
            ttk.Label(grid, text=label).grid(row=i, column=0, sticky="w", pady=1)
            e = ttk.Entry(grid, width=22)
            e.insert(0, self.settings["hotkeys"].get(key, ""))
            e.grid(row=i, column=1, sticky="w", padx=(10, 0), pady=1)
            self.hk_entries[key] = e
        r = ttk.Frame(hk)
        r.pack(fill="x", pady=(6, 0))
        ttk.Button(r, text="Übernehmen", command=self._apply_hotkeys).pack(side="left")
        self.hk_status = tk.StringVar(value="Format: ctrl+alt+m, shift+f8, ctrl+alt+up …")
        ttk.Label(r, textvariable=self.hk_status, style="Dim.TLabel", wraplength=300).pack(side="left", padx=8)

        own = ttk.LabelFrame(f, text="Eigene Map-Zuordnungen", padding=8)
        own.pack(fill="x", pady=(8, 0))
        self.alias_var = tk.StringVar(value="")
        ttk.Label(own, textvariable=self.alias_var, style="Dim.TLabel", wraplength=300).pack(side="left", fill="x")
        ttk.Button(own, text="Alle löschen", command=self._clear_aliases).pack(side="right")
        self._show_aliases()

        folders = ttk.LabelFrame(f, text="Ordner", padding=8)
        folders.pack(fill="x", pady=(8, 0))
        ttk.Button(folders, text="Programmordner öffnen", command=lambda: self._open(self.root_dir)).pack(side="left")
        ttk.Button(folders, text="Karten-Ordner öffnen",
                   command=lambda: self._open(os.path.join(self.root_dir, "maps"))).pack(side="left", padx=6)
        ttk.Label(f, text=f"DbD Map Scout {__version__} · liest nur Bildschirmpixel, sendet keine Eingaben ans Spiel.",
                  style="Dim.TLabel", wraplength=430).pack(anchor="w", pady=(10, 0))
        return f

    # ----------------------------------------------------------- map list
    def _fill_list(self):
        self.tree.delete(*self.tree.get_children())
        self._list_items = {}
        realms = {}
        for m in self.catalog.search(self.search_var.get()):
            realm = self.catalog.realm_display(m) or "Eigene Bilder"
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
            self._log(f"Für „{m.label(variant)}“ gibt es kein Bild.", "Overlay")
            return
        try:
            frames = load_frames(path)
        except Exception as e:
            self._log(f"Bild konnte nicht geladen werden: {path} ({e})", "Fehler")
            return
        was_on = self._map_on()
        self.current = (map_id, shown)
        self.source = source
        self.overlay.set_map(path, m.label(shown))
        if not was_on and not keep_timer:
            self._round_started(time.time())     # map appears -> timer from zero (a switch while on keeps it)
        self.user_visible = True
        self.hidden_after_match = False
        self.menu_paused = False
        self._watch(source)
        self.map_var.set(m.label(shown))
        self.realm_var.set(self.catalog.realm_display(m))
        self.detail_var.set(detail or {"manual": "manuell gewählt", "scan": "per Scan gefunden"}.get(source, ""))
        thumb = frames[0][0].copy()
        thumb.thumbnail((88, 88))
        bg = Image.new("RGBA", thumb.size, (40, 40, 44, 255))
        bg.alpha_composite(thumb)
        self._thumb = ImageTk.PhotoImage(bg)
        self.thumb_label.configure(image=self._thumb)
        self._update_toggle_text()
        if source == "manual":
            self._log(f"Map gewählt: {m.label(shown)}", "Overlay")
        self._tick_overlay(reschedule=False)

    def toggle_overlay(self):
        if not self.overlay.has_map():
            self._log("Noch keine Map gewählt.", "Overlay")
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
        self._log("Overlay eingeblendet." if self.user_visible else "Overlay ausgeblendet.", "Overlay")
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
        self.toggle_btn.configure(text="Overlay ausblenden" if on else "Overlay einblenden")

    def next_variant(self):
        if not self.current:
            return
        m = self.catalog.maps[self.current[0]]
        vs = [v for v in sorted(m.variants) if m.variants[v]]
        if len(vs) < 2:
            self._log(f"„{m.name}“ hat nur ein Layout.", "Overlay")
            return
        i = vs.index(self.current[1]) if self.current[1] in vs else 0
        self.show_map(m.id, vs[(i + 1) % len(vs)], "manual", "Layout manuell gewechselt")

    def step_map(self, step: int):
        items = list(self._list_items.values())
        if not items:
            return
        i = items.index(self.current) if self.current in items else -1
        mid, v = items[(i + step) % len(items)]
        self.show_map(mid, v, "manual")

    def scan_now(self):
        self._log("Scanne den Bildschirm nach Map- oder Realm-Namen …", "Erkennung")
        self.worker.request_scan()

    def test_overlay(self):
        """Show the overlay in the middle of the game/screen for 10 s, ignoring all filters."""
        if not self.overlay.has_map():
            first = next(iter(self._list_items.values()), None)
            if first:
                self.show_map(first[0], first[1], "manual", "Testanzeige")
        self._force_until = time.time() + 10
        self._log("Test: Overlay 10 s lang in der Bildschirmmitte – jetzt zu DBD wechseln.", "Overlay")
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
        self._log("Diagnose in die Zwischenablage kopiert (auch als diagnose.txt gespeichert).", "System")
        log.info(text)

    def toggle_edit(self):
        on = not self.overlay.editing
        if on and not self.overlay.has_map():
            self._log("Erst eine Map wählen, dann lässt sich das Overlay verschieben.", "Overlay")
            return
        self.overlay.set_editing(on)
        self.edit_btn.configure(text="Fertig" if on else "Mit der Maus verschieben")
        if on:
            self._log("Overlay mit der Maus ziehen, Mausrad = Grösse. Danach „Fertig“ oder Hotkey.", "Overlay")
        self._tick_overlay(reschedule=False)

    def _overlay_dragged(self, x, y):
        gx, gy, gw, gh = self._game_rect()
        w, h = (self._last_place or (0, 0, 1, 1))[2:]
        o = self.settings["overlay"]
        o["anchor"] = "custom"
        o["pos_x"] = min(1.0, max(0.0, (x - gx) / max(1, gw - w)))
        o["pos_y"] = min(1.0, max(0.0, (y - gy) / max(1, gh - h)))
        self.anchor_var.set(dict(ANCHORS)["custom"])
        self._set_pos_sliders(o["pos_x"], o["pos_y"])
        self._save_soon()

    def _resize(self, delta):
        o = self.settings["overlay"]
        o["height"] = min(0.9, max(0.15, o["height"] + delta))
        self.size_var.set(o["height"] * 100)
        self.size_label.configure(text=f"{o['height'] * 100:.0f} %")
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
                        self._log("Firewall-Regeln von Make Your Choice („Enforced“) gefunden – sie sperren Regionen "
                                  "unabhängig von der hosts-Datei. In Make Your Choice „Revert to Default“ drücken.",
                                  "Fehler")
                        self.srv_status.set("Achtung: Firewall-Regeln von Make Your Choice aktiv (siehe Log).  "
                                            + self.srv_status.get())
                elif isinstance(ev, tuple) and ev[0] == "conn_started":
                    self._conn_started(ev[1])
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
         "edit_position": self.toggle_edit}.get(name, lambda: None)()

    def _event(self, ev):
        k, d = ev.kind, ev.data
        if k in ("menu", "match_end") and d.get("gen") not in (None, self._watch_gen):
            return                               # about a map that is no longer on display
        if k == "status":
            self._set_status(d["text"])
        elif k == "banner":
            self._log("Map-Banner gefunden, lese …", "Erkennung")
        elif k == "detected":
            m = self.catalog.maps.get(d["map_id"])
            if not m:
                return
            same = (self.current == (d["map_id"], d["variant"]) and self.source == "auto"
                    and not self.hidden_after_match and not self.menu_paused and self.user_visible)
            vp = d["variant_probability"]
            detail = f"automatisch erkannt ({d['probability']:.0%})"
            if len(m.variants) > 1:
                detail += f" · Layout {roman(d['variant'])} ({vp:.0%})"
            if self.round.detected(time.time()):
                self._log("Rundentimer gestartet.", "Erkennung")
            if not same:
                self.show_map(d["map_id"], d["variant"], "auto", detail, keep_timer=True)
                self._log(f"Erkannt: {m.label(d['variant'])} – gelesen „{d['name_text']}“ / „{d['realm_text']}“",
                          "Erkennung")
                if len(m.variants) > 1 and vp < 0.8:
                    self._log(f"Layout unsicher – falls falsch: {pretty(self.settings['hotkeys']['next_variant'])}.",
                              "Erkennung")
        elif k == "unknown":
            txt = d.get("name_text") or "?"
            self._log(f"Banner gesehen, aber keine bekannte Map: „{txt}“. Map manuell wählen "
                      "oder mit „Zuordnen …“ dauerhaft zuordnen.", "Erkennung")
            if len(fold(txt)) >= self.catalog.MIN_ALIAS:
                self._unknown = (txt, d.get("realm_text") or "")
                self.unknown_var.set(f"Unbekannte Map gelesen: „{txt}“")
                self.unknown_bar.pack(fill="x", padx=10, pady=(0, 6), before=self.nb)
        elif k == "match_end":
            self._round_ended(d.get("t") or time.time())
            if self.overlay.has_map() and not self.hidden_after_match:
                was_visible = self.user_visible
                self.hidden_after_match = True
                self.menu_paused = False
                self._update_toggle_text()
                self._log(f"Runde vorbei ({d.get('reason', 'Ergebnisbildschirm')})"
                          + (" – Overlay ausgeblendet." if was_visible else "."), "Erkennung")
                self._tick_overlay(reschedule=False)
        elif k == "menu":
            if d.get("on"):
                if self.overlay.has_map() and not self.hidden_after_match and not self.menu_paused:
                    self.menu_paused = True
                    self._update_toggle_text()
                    self._log("Menü offen (Mauszeiger sichtbar) – Overlay pausiert.", "Overlay")
                    self._tick_overlay(reschedule=False)
            elif self.menu_paused:
                self.menu_paused = False
                self._update_toggle_text()
                self._log("Zurück im Spiel – Overlay wieder sichtbar.", "Overlay")
                self._tick_overlay(reschedule=False)
        elif k == "watch_info":
            self._log(d.get("text", ""), "Erkennung")
        elif k == "warn":
            self._log(f"{d.get('text', '')} – Details in dbdmapscout.log", "Fehler")
        elif k == "scan_result":
            self._scan_result(d)
        elif k == "error":
            self._log("Die Erkennung ist abgestürzt – Details in dbdmapscout.log", "Fehler")
            log.error(d["text"])
            messagebox.showerror("DbD Map Scout", "Die Erkennung ist abgestürzt:\n\n" + d["text"][-1500:])

    # ---------------------------------------------------------- round timer
    def _round_started(self, t):
        self.round.start(t)
        self._log("Rundentimer gestartet.", "Erkennung")

    def _round_ended(self, t):
        if self.round.stop(t):
            self._log(f"Rundentimer gestoppt: {fmt_duration(self.round.elapsed(t))}.", "Erkennung")

    def _tick_timer(self):
        r = self.round
        if r.start_t is None:
            text, overlay_text = "", ""
        elif r.running:
            overlay_text = fmt_duration(r.elapsed(time.time()))
            text = f"Runde läuft: {overlay_text}"
        else:
            text, overlay_text = f"Letzte Runde: {fmt_duration(r.elapsed(0))}", ""
        if text != self.timer_var.get():
            self.timer_var.set(text)
        self.overlay.set_timer(overlay_text if self.settings["overlay"].get("show_timer", True) else "")

    def _set_status(self, text):
        self.status_var.set(text)
        low = text.lower()
        kind = ("err" if ("fehl" in low or "schwarz" in low) else
                "info" if low.startswith("simulation") else
                "ok" if "gefunden (" in low else "warn")
        self.dot.configure(style=f"Dot{kind.title()}.TLabel")
        self._log(text, "System")

    def _scan_result(self, d):
        hits = d.get("hits") or []
        if d.get("error"):
            self._log(f"Scan fehlgeschlagen: {d['error']}", "Fehler")
            return
        maps = [h for h in hits if h.kind == "map"]
        if maps:
            h = maps[0]
            m = self.catalog.maps[h.map_id]
            self.show_map(h.map_id, h.variant, "scan", f"per Scan gefunden: „{h.text}“")
            self._log(f"Scan ({d['seconds']:.1f} s): {m.label(h.variant)}", "Erkennung")
            return
        realms = [h for h in hits if h.kind == "realm" and h.realm]
        if realms:
            realm = realms[0].realm
            in_realm = [m for m in self.catalog.maps.values() if m.realm == realm]
            if len(in_realm) == 1:
                self.show_map(in_realm[0].id, 1, "scan", f"Realm „{realms[0].text}“ hat nur diese Map")
            else:
                self.search_var.set(self.catalog.realms.get(realm, {}).get("en", realm))
                self.nb.select(self.tab_maps)
                self._log(f"Scan: Realm „{realms[0].text}“ gefunden – bitte Map in der Liste wählen.", "Erkennung")
            return
        self._log(f"Scan ({d['seconds']:.1f} s): kein Map- oder Realm-Name auf dem Bildschirm.", "Erkennung")

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
            self._log(f"Hotkey {pretty(combo)} ({labels.get(name, name)}) nicht verfügbar: {why}.", "Fehler")
        if t.failed and hasattr(self, "hk_status"):
            self.hk_status.set(f"{len(t.failed)} Hotkey(s) nicht verfügbar – siehe Log.")

    def _apply_hotkeys(self):
        new, errors = {}, []
        labels = dict(HOTKEY_LABELS)
        for key, entry in self.hk_entries.items():
            combo = re.sub(r"\s+", "", entry.get().strip().lower())
            if combo:
                try:
                    parse(combo)
                except ValueError as e:
                    errors.append(f"{labels[key]}: {e}")
            new[key] = combo
        if errors:
            self.hk_status.set("; ".join(errors))
            return
        self.settings["hotkeys"].update(new)
        self._save_soon()
        self.hotkeys.stop()
        self.hotkeys.join(timeout=1.5)            # old registrations must be gone first
        self.hotkeys = self._start_hotkeys()
        self.hk_status.set("Übernommen.")
        self._log("Hotkeys neu registriert.", "System")

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
            status = f"Rundenende-Erkennung: {self.worker.watch_status}"
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
            self._log(f"{key}: {last} – Details in dbdmapscout.log", "Fehler")

    def _tk_error(self, exc, val, tb):
        self._report_once(getattr(exc, "__name__", "tk"), "".join(traceback.format_exception(exc, val, tb)))

    def _place_overlay(self):
        o = self.settings["overlay"]
        self.worker.map_on_screen = self.overlay.has_map() and not self.hidden_after_match
        gx, gy, gw, gh = self._game_rect()               # keeps the game window info fresh
        if time.time() < getattr(self, "_force_until", 0) and self.overlay.has_map():
            self.overlay.opacity = 1.0
            w, h = self.overlay.render(int(gh * o["height"]))
            self.overlay.show_at(gx + (gw - w) // 2, gy + (gh - h) // 2)
            self._last_place = (gx + (gw - w) // 2, gy + (gh - h) // 2, w, h)
            self.worker.overlay_rect = self._last_place
            self._pos_forced = True
            return
        if getattr(self, "_pos_forced", False):
            self._pos_forced = False
            self._log("Test beendet.", "Overlay")
        reason = None
        if not self.overlay.has_map():
            reason = "keine Map"
        elif not ((self.user_visible and not self.hidden_after_match) or self.overlay.editing):
            reason = "ausgeblendet"
        elif self.menu_paused and not self.overlay.editing:
            reason = "Menü offen"
        elif (o["only_when_game_focused"] and IS_WIN and not self.overlay.editing and not self.simulate
              and self.game is not None):
            fg = foreground_root()
            own = {self.overlay.hwnd(), self._root_hwnd()}
            if fg not in own and not is_game_window(fg):
                reason = f"aktives Fenster ist {describe_window(fg)}"
        self._log_visibility(reason, (gx, gy, gw, gh))
        if reason:
            self.overlay.hide()
            self.worker.overlay_rect = None
            return
        if self.overlay.editing and self.overlay._drag:
            return                                           # user is dragging
        self.overlay.opacity = o["opacity"]
        margin = int(gh * o["margin"])
        height = int(gh * o["height"])
        w, h = self.overlay.render(height)
        a = o["anchor"]
        bar = (gw - gh * 16 / 9) / 2          # black bar left/right of a 16:9 picture (ultrawide)
        if a == "auto" and bar >= 200:
            avail = bar - 2 * margin
            if w > avail:                       # shrink until it fits into the bar
                height = max(80, int(height * avail / w))
                w, h = self.overlay.render(height)
            x = gx + max(margin, (bar - w) / 2)
            y = gy + margin
        elif a == "custom":
            x = gx + o.get("pos_x", 0.0) * max(0, gw - w)
            y = gy + o.get("pos_y", 0.0) * max(0, gh - h)
        else:
            a = "top-left" if a == "auto" else a
            x = gx + margin if a.endswith("left") else gx + gw - w - margin
            y = gy + margin if a.startswith("top") else gy + gh - h - margin
        self.overlay.show_at(int(x), int(y))
        self._last_place = (int(x), int(y), w, h)
        self.worker.overlay_rect = self._last_place if self.overlay.shown else None
        if a != "custom":                      # sliders follow the preset position
            self._set_pos_sliders((x - gx) / max(1, gw - w), (y - gy) / max(1, gh - h))

    def _log_visibility(self, reason, game_rect):
        """One log line whenever the overlay goes from visible to hidden or back."""
        if reason == "keine Map":
            self._vis_state = reason
            return
        if reason == "Menü offen":                     # already logged by the menu event
            self._vis_state = reason
            return
        state = reason or "sichtbar"
        if state == getattr(self, "_vis_state", None):
            return
        self._vis_state = state
        if reason is None:
            src = f"DBD-Fenster {game_rect[2]}×{game_rect[3]}" if self.game else "Bildschirm"
            self.root.after(300, lambda: self._log(
                f"Overlay sichtbar bei {(self._last_place or ('?', '?'))[:2]} über {src}.", "Overlay"))
        elif reason != "ausgeblendet":
            self._log(f"Overlay pausiert: {reason}.", "Overlay")

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

    def _anchor_changed(self):
        rev = {v: k for k, v in ANCHORS}
        self.settings["overlay"]["anchor"] = rev.get(self.anchor_var.get(), "auto")
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _reset_position(self):
        self.anchor_var.set(dict(ANCHORS)["auto"])
        self._anchor_changed()
        self._log("Position zurückgesetzt (automatisch).", "Overlay")

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
            self.anchor_var.set(dict(ANCHORS)["custom"])
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
        if bool(self.transp_var.get()) != o.get("transparent", True):
            o["transparent"] = bool(self.transp_var.get())
            self.overlay.set_transparent(o["transparent"])
        if self.current:
            m = self.catalog.maps[self.current[0]]
            path, _ = self.catalog.image_path(*self.current)
            self.overlay.show_caption = o["show_caption"]
            self.overlay.set_map(path, m.label(self.current[1]))
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
        dlg.title("Map zuordnen")
        dlg.transient(self.root)
        dlg.resizable(False, False)
        body = ttk.Frame(dlg, padding=12)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=f"Gelesen: „{name}“" + (f" / „{realm}“" if realm else ""),
                  wraplength=380).pack(anchor="w")
        ttk.Label(body, text="Welche Map war das? Der Name wird künftig automatisch erkannt.",
                  style="Dim.TLabel", wraplength=380).pack(anchor="w", pady=(2, 8))
        var = tk.StringVar(value=labels[[m.id for m in entries].index(guess)] if guess in
                           [m.id for m in entries] else "")
        cb = ttk.Combobox(body, textvariable=var, values=labels, state="readonly", width=44, height=18)
        cb.pack(fill="x")
        msg = tk.StringVar(value="")
        ttk.Label(body, textvariable=msg, style="Dim.TLabel", wraplength=380).pack(anchor="w", pady=(6, 0))

        def ok():
            if var.get() not in labels:
                msg.set("Bitte eine Map auswählen.")
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
            self._log(f"„{name}“ wird jetzt als {m.name} erkannt (eigene Zuordnung).", "Erkennung")
            self.show_map(m.id, 1, "manual", f"zugeordnet: „{name}“")

        row = ttk.Frame(body)
        row.pack(fill="x", pady=(10, 0))
        ttk.Button(row, text="Zuordnen", command=ok).pack(side="right")
        ttk.Button(row, text="Abbrechen", command=dlg.destroy).pack(side="right", padx=6)
        dlg.bind("<Return>", lambda e: ok())
        dlg.bind("<Escape>", lambda e: dlg.destroy())
        cb.focus_set()
        dlg.grab_set()

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
                           "Keine. Unbekannte Map-Namen lassen sich nach dem Match im Hauptfenster zuordnen.")

    def _clear_aliases(self):
        if not self.settings.get("user_aliases"):
            return
        if not messagebox.askokcancel("Eigene Zuordnungen", "Alle eigenen Map-Zuordnungen löschen?", parent=self.root):
            return
        self.settings.set("user_aliases", {})
        self._save_soon()
        self._reload_catalog()
        self._log("Eigene Map-Zuordnungen gelöscht.", "System")

    def _langs_changed(self):
        langs = [c for c, _ in LANGS if self.lang_vars[c].get()] or ["en"]
        self.settings.set("languages", langs)
        self.catalog = Catalog(self.root_dir, langs, self.settings.get("user_aliases"))
        self.worker.set_catalog(self.catalog)
        self._fill_list()
        self._save_soon()
        self._log(f"Spielsprachen: {', '.join(langs)}", "System")

    def _apply_theme(self):
        dark = bool(self.dark_var.get())
        theme.apply(self.root, dark, text_widgets=(self.log_text,))
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
        log.info(f"[{entry[1]}] {text}")
        self.last_var.set(f"{entry[0]}  {text}")
        if self.cat_vars[entry[1]].get():
            self._append_log(entry)
        if entry[1] == "Fehler" and self.nb.select() != str(self.tab_log):
            self.nb.tab(self.tab_log, text="Log ⚠")

    def _append_log(self, entry):
        ts, cat, text = entry
        t = self.log_text
        t.configure(state="normal")
        t.insert("end", ts + "  ", "ts")
        t.insert("end", f"{cat:<9}", f"cat_{cat}")
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
                self._log(f"Öffnen nur unter Windows: {path}", "System")
        except OSError as e:
            self._log(f"Kann {path} nicht öffnen: {e}", "Fehler")

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
