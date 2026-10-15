"""Control window (Qt) + overlay + hotkeys, glued together."""
from __future__ import annotations

import collections
import logging
import os
import queue
import sys
import threading
import time
import traceback

from . import i18n, layout, mapimage, regions, tooltip
from . import uimodel as ui
from .capture import IS_WIN, describe_window, find_game_window, foreground_root, is_game_window
from .catalog import Catalog
from .config import Settings
from .toast import Toast
from .connwatch import ConnectionWatch, IdlePause
from .official import OpenAfterGame
from .i18n import N_, _
from .hotkeys import pretty
from .overlay import load_frames
from .overlay_win32 import make_overlay
from .roundtimer import RoundTimer
from .textnorm import fmt_duration, fold, roman
from .worker import DetectionWorker
from .app_server import ServerTab
from .app_stats import StatsTab
from .app_lobby import LobbyInfo
from .app_hotkeys import Hotkeys
from .app_settings import SettingsTab
from .app_sysinfo import HUD_SIDES, SysInfo
from .app_qt import QtShell

LANGS = [("en", "EN"), ("de", "DE"), ("fr", "FR"), ("es", "ES"), ("es-MX", "ES-MX"), ("it", "IT"),
         ("pl", "PL"), ("pt-BR", "PT"), ("tr", "TR")]
REJECT_HOLD = 60.0        # s: a rejected map is not shown again by the same banner
UNSURE_DELAY = 2.5        # s: a doubtful read is shown only if the banner did not read cleanly meanwhile
SMALL_PICTURE = 1080      # 16:9 picture lines below which detection gets less reliable (log hint)
MAX_HEIGHT = 0.9          # overlay at most this share of the game height (room for the timer below)
ANCHORS = [("auto", N_("automatisch")), ("top-left", N_("oben links")), ("top-right", N_("oben rechts")),
           ("bottom-left", N_("unten links")), ("bottom-right", N_("unten rechts")), ("custom", N_("eigene Position"))]
CATS = [N_("Erkennung"), N_("Overlay"), N_("System"), N_("Fehler")]   # log categories (keys; shown translated)


def _event_name(ev) -> str:
    """Short name of an event for the lag list of the diagnosis ("ui page stats", "detected" …)."""
    if isinstance(ev, tuple):
        parts = [str(x) for x in ev[:3] if isinstance(x, str)]
        return " ".join(parts)[:60]
    return str(getattr(ev, "kind", type(ev).__name__))


def anchor_label(key: str) -> str:
    return _(dict(ANCHORS).get(key, "automatisch"))

log = logging.getLogger("dbdmapscout")


class App(ServerTab, StatsTab, LobbyInfo, Hotkeys, SettingsTab, SysInfo, QtShell):
    def __init__(self, root_dir: str, simulate: str | None = None, start_in_tray: bool = False):
        self.root_dir = root_dir
        self.simulate = simulate
        self.settings = Settings(os.path.join(root_dir, "settings.json"))
        i18n.set_language(self.settings.get("ui_language", "auto"))
        self.catalog = Catalog(root_dir, self.settings["languages"], self.settings.get("user_aliases"))
        self._unknown = None             # (name text, realm text) of the last banner that matched no map
        self.events: queue.Queue = queue.Queue()
        self._quitting = False
        self._errors_seen = set()
        self._log_entries = collections.deque(maxlen=1500)
        self._qt_init()                  # Qt application; self.root = its main loop (timers, clipboard …)
        ico = os.path.join(root_dir, "dbdmapscout.ico")        # also made by the shortcut setup
        if IS_WIN and not os.path.exists(ico):
            try:
                from .icon import save_ico
                save_ico(ico)                                  # the taskbar button shows this icon
            except OSError:
                pass

        self.current = None            # (map_id, variant)
        self._floor = None             # maps with floors (Midwich): position of the floor shown, None = all of them
        self.source = None             # "auto" | "manual" | "scan"
        self._detail = ""              # how the map on display was found ("automatisch erkannt (97 %)" …)
        self.user_visible = True       # overlay toggle
        self.hidden_after_match = False  # match over -> hidden until the next map
        self.menu_paused = False         # a DBD menu is open (pointer visible) -> hidden for now
        self._watch_gen = 0
        self.round = RoundTimer()        # runs while a map is on display
        self._hist = None                # round for the statistics: detected map -> detected end of the match
        self._off_open = OpenAfterGame()  # official match data: open the stats page once DBD was closed
        self._off_next = self._off_fast_until = 0.0     # next look into the download folder / look often until
        self._off_script = 0             # version of the userscript that saved the last file
        self._off_told = set()           # files / statuses already reported in the log
        self.toast = Toast(self.root)
        self._queue = {"state": "idle"}  # lobby (worker "queue" events): search since / role / found lobby
        self.game = None
        self._game_checked = 0.0
        self._save_job = None
        self._list_items = {}
        self._syncing = False
        self._last_place = None
        self._log_alert = False          # an error in the log the user has not looked at yet
        self._worker_status = ""
        self._layout_unsure = False
        self._unsure = None              # doubtful detection: {"label", "t", "shown", "fit", "name"}
        self._rejected = None            # (map_id, time) thrown away with "Falsch erkannt"
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
        # window procedures: hand over to _poll (one place, in order with the other events)
        self.overlay.on_moved = lambda x, y: self.events.put(("call", self._overlay_dragged, (x, y)))
        self.overlay.on_wheel = lambda d: self.events.put(("call", self._resize, (0.02 * d,)))
        self._hud_init()                 # system values at the top of a black bar (CPU/GPU temperature …)

        self._build_ui()
        self._apply_overlay_settings()

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
        self._qt_build(start_in_tray)
        threading.Thread(target=self._setup_then_read_autostart, daemon=True, name="autostart").start()

    # ================================================================== UI
    def _build_ui(self):
        """The tabs as a UI model (uimodel.py); the Qt window draws them (app_qt.py, qt_window.py)."""
        self.ui_root = ui.Root()
        self.nb = ui.Notebook(self.ui_root)
        self.tab_maps = self._tab_maps()
        self.tab_overlay = self._tab_overlay()
        self.tab_detect = self._tab_detect()
        self.tab_server = self._tab_server()
        self.tab_log = self._tab_log()
        self.tab_stats = self._tab_stats()
        self.tab_settings = self._tab_settings()
        self.nb.add(self.tab_maps, text="Maps")
        self.nb.add(self.tab_overlay, text=_("Overlay"))
        self.nb.add(self.tab_stats, text=_("Statistik"))
        self.nb.add(self.tab_server, text=_("Server"))
        self.nb.add(self.tab_settings, text=_("Einstellungen"))
        self.nb.add(self.tab_detect, text=_("Erkennung"))
        self.nb.add(self.tab_log, text="Log")
        self.nb.bind("<<NotebookTabChanged>>", lambda e: self._tab_changed())
        self._apply_theme()
        tooltip.attach_all(self.ui_root, self._tip_lookup)

    def _scroll_tab(self):
        """(outer, inner) of a tab page (the Qt page scrolls by itself: both are the same frame)."""
        f = ui.Frame(self.nb)
        return f, f

    _fixed_tab = _scroll_tab

    # ------------------------------------------------------------ tab: maps
    def _tab_maps(self):
        """The maps page is Qt's own (qt_window.MapsPage: search + list); here only the list for the hotkeys."""
        outer, _f = self._scroll_tab()
        self._fill_list()
        return outer

    # --------------------------------------------------------- tab: overlay
    def _slider(self, parent, label, var, lo, hi, cmd, fmt="{:.0f} %", key=None):
        row = ui.Frame(parent)
        row.pack(fill="x", pady=3)
        ui.Label(row, text=label, width=12).pack(side="left")
        val = ui.Label(row, text=fmt.format(var.get()), width=6, anchor="e")
        val.pack(side="right")

        def changed(_=None):
            val.configure(text=fmt.format(var.get()))
            cmd()
        scale = ui.Scale(row, from_=lo, to=hi, variable=var, command=changed)
        scale.pack(side="left", fill="x", expand=True, padx=6)
        scale._dbdms_label, scale._dbdms_fmt = label, fmt          # for the window (app_qt.ui_state)
        if key:
            self._reg(key, scale)
        return val

    def _tab_overlay(self):
        outer, f = self._scroll_tab()
        o = self.settings["overlay"]
        pos = self._reg("ov.pos", ui.LabelFrame(f, text=_("Position"), padding=8))
        pos.pack(fill="x")
        # 1.61: the screen with the map on it – where and how big, live; a click or drag places it there
        self._reg("ov.preview", ui.Preview(pos, source=self._preview_data, command=self._preview_pick)).pack(fill="x")
        r = ui.Frame(pos)
        r.pack(fill="x", pady=(0, 4))
        self._reg("ov.anchor.label", ui.Label(r, text=_("Vorgabe"), width=12)).pack(side="left")
        self.anchor_var = ui.StringVar(value=anchor_label(o["anchor"]))
        cb = self._reg("ov.anchor", ui.Combobox(r, textvariable=self.anchor_var, values=[_(a[1]) for a in ANCHORS],
                                                 state="readonly", width=16))
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self._anchor_changed())
        self._reg("ov.reset", ui.Button(r, text=_("Zurücksetzen"), command=self._reset_position)).pack(side="right")
        self.posx_var = ui.DoubleVar(value=o.get("pos_x", 0.0) * 100)
        self.posy_var = ui.DoubleVar(value=o.get("pos_y", 0.0) * 100)
        self.posx_label = self._slider(pos, _("Horizontal"), self.posx_var, 0, 100, self._pos_changed, key="ov.posx")
        self.posy_label = self._slider(pos, _("Vertikal"), self.posy_var, 0, 100, self._pos_changed, key="ov.posy")
        r2 = ui.Frame(pos)
        r2.pack(fill="x", pady=(4, 0))
        self.edit_btn = self._reg("ov.edit", ui.Button(r2, text=_("Mit der Maus verschieben"), command=self.toggle_edit))
        self.edit_btn.pack(side="left")
        self.test_btn = self._reg("ov.test", ui.Button(r2, text=_("Overlay testen"), command=self.test_overlay))
        self.test_btn.pack(side="left", padx=(6, 0))
        self.pos_hint_var = ui.StringVar(value="")
        self._reg("ov.pos_hint", ui.Label(pos, textvariable=self.pos_hint_var, style="Dim.TLabel",
                                           wraplength=520)).pack(anchor="w", pady=(4, 0))
        self._pos_hint()

        look = self._reg("ov.look", ui.LabelFrame(f, text=_("Darstellung"), padding=8))
        look.pack(fill="x", pady=(8, 0))
        self.size_var = ui.DoubleVar(value=o["height"] * 100)
        self.size_label = self._slider(look, _("Grösse"), self.size_var, 15, 90, self._size_changed, key="ov.size")
        self.map_size_row = ui.Frame(look)
        self.map_size_var = ui.StringVar(value="")
        self._reg("ov.map_size", ui.Label(self.map_size_row, textvariable=self.map_size_var, style="Dim.TLabel",
                                           wraplength=330)).pack(side="left")
        self._reg("ov.map_size_reset", ui.Button(self.map_size_row, text=_("Für diese Map zurücksetzen"),
                                                  command=self._reset_map_size)).pack(side="right")
        self._size_row_after = self.size_label.master
        self.opacity_var = ui.DoubleVar(value=o["opacity"] * 100)
        self._slider(look, _("Deckkraft"), self.opacity_var, 25, 100, self._opacity_changed, key="ov.opacity")
        self.focus_var = ui.BooleanVar(value=o["only_when_game_focused"])
        self.caption_var = ui.BooleanVar(value=o["show_caption"])
        self.transp_var = ui.BooleanVar(value=o.get("transparent", True))
        self.timer_show_var = ui.BooleanVar(value=o.get("show_timer", True))
        self.server_show_var = ui.BooleanVar(value=o.get("show_server", True))
        self.keep_bar_var = ui.BooleanVar(value=o.get("keep_in_bar", True))
        self.show_map_var = ui.BooleanVar(value=o.get("show_map", True))
        self.waiting_var = ui.BooleanVar(value=o.get("show_waiting", True))
        self.floor_auto_var = ui.BooleanVar(value=o.get("floor_auto", True))
        self.record_var = ui.BooleanVar(value=o.get("show_record", True))
        self._reg("ov.keep_bar", ui.Checkbutton(
            pos, text=_("Karte im schwarzen Rand halten (Ultrawide: nie ins Spielbild ragen)"),
            variable=self.keep_bar_var, command=self._overlay_flags_changed)).pack(anchor="w", pady=(4, 0))
        for key, text, var in (("show_map", N_("Karte anzeigen (aus: nur Timer, Ort und Ping)"), self.show_map_var),
                               ("focus", N_("Nur zeigen, wenn DBD das aktive Fenster ist"), self.focus_var),
                               ("caption", N_("Map-Namen über der Karte anzeigen"), self.caption_var),
                               ("timer", N_("Rundentimer unter der Karte anzeigen"), self.timer_show_var),
                               ("server", N_("Verbundenen Server unter der Karte anzeigen (Tab Server)"),
                                self.server_show_var),
                               ("waiting", N_("Ohne Karte: „Warte auf Map“ und Lobby-Status anzeigen"), self.waiting_var),
                               ("floors", N_("Etagen (Midwich) untereinander zeigen (aus: nur die untere)"),
                                self.floor_auto_var),
                               ("record", N_("Eigene Bilanz auf der Map unter dem Timer (Stats-Seite)"), self.record_var),
                               ("transparent", N_("Transparenter Rand um die Karte"), self.transp_var)):
            self._reg(f"ov.{key}", ui.Checkbutton(look, text=_(text), variable=var,
                                                   command=self._overlay_flags_changed)).pack(anchor="w", pady=1)
        sysf = self._reg("ov.sys", ui.LabelFrame(f, text=_("Systemwerte (CPU/GPU-Temperatur, Auslastung, VRAM, RAM)"),
                                                  padding=8))
        sysf.pack(fill="x", pady=(8, 0))
        r = ui.Frame(sysf)
        r.pack(fill="x")
        self._reg("ov.sysinfo.label", ui.Label(r, text=_("Anzeige"), width=12)).pack(side="left")
        labels = dict(HUD_SIDES)
        self.sysinfo_var = ui.StringVar(value=_(labels.get(self.settings.get("sysinfo", "off"), labels["off"])))
        cb = self._reg("ov.sysinfo", ui.Combobox(r, textvariable=self.sysinfo_var, values=[_(t) for _k, t in HUD_SIDES],
                                                  state="readonly", width=38))
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self._sysinfo_changed())
        self._reg("ov.sys_text", ui.Label(sysf, text=_("Oben im schwarzen Rand, solange eine Karte im Match zu sehen ist. „Eigene Position“: "
                               "mit „Mit der Maus verschieben“ (Tab Overlay) zusammen mit der Karte ziehen; im "
                               "schmalen Fenster bleibt die Anzeige im Balken oben. GPU-Werte von NVIDIA-Karten "
                               "(Treiber), CPU-Temperatur nur mit HWiNFO („Shared Memory Support“ an) – das "
                               "Programm lädt keinen eigenen Treiber."),
                  style="Dim.TLabel", wraplength=520)).pack(anchor="w", pady=(4, 0))
        self.sysinfo_hint_var = ui.StringVar(value="")
        self._reg("ov.sys_hint", ui.Label(sysf, textvariable=self.sysinfo_hint_var, style="Dim.TLabel",
                                           wraplength=520)).pack(anchor="w")
        return outer

    # ------------------------------------------------------- tab: detection
    def _tab_detect(self):
        outer, f = self._scroll_tab()
        auto = ui.LabelFrame(f, text=_("Automatik"), padding=8)
        auto.pack(fill="x")
        self.auto_var = ui.BooleanVar(value=self.settings["auto_detect"])
        self.hide_var = ui.BooleanVar(value=self.settings["hide_after_match"])
        ui.Checkbutton(auto, text=_("Map beim Match-Start automatisch erkennen"), variable=self.auto_var,
                        command=self._detect_flags_changed).pack(anchor="w", pady=1)
        ui.Checkbutton(auto, text=_("Overlay ausblenden, sobald ich nicht mehr in der Runde bin"),
                        variable=self.hide_var, command=self._detect_flags_changed).pack(anchor="w", pady=1)
        ui.Label(auto, text=_("erkennt Ergebnisbildschirm, Lobby/Menüs, Ladebildschirm und geschlossenes DBD"),
                  style="Dim.TLabel", wraplength=400).pack(anchor="w", padx=(22, 0))
        self.menu_var = ui.BooleanVar(value=self.settings.get("pause_in_menus", True))
        ui.Checkbutton(auto, text=_("Overlay pausieren, solange ein DBD-Menü offen ist"),
                        variable=self.menu_var, command=self._detect_flags_changed).pack(anchor="w", pady=(4, 1))
        ui.Label(auto, text=_("erkannt am sichtbaren Mauszeiger (ESC-Menü, Ergebnisbildschirm, Lobby)"),
                  style="Dim.TLabel", wraplength=400).pack(anchor="w", padx=(22, 0))
        lang = ui.LabelFrame(f, text=_("Spielsprache (Map-Namen)"), padding=8)
        lang.pack(fill="x", pady=(8, 0))
        grid = ui.Frame(lang)
        grid.pack(anchor="w")
        self.lang_vars = {}
        for i, (code, label) in enumerate(LANGS):
            v = ui.BooleanVar(value=code in self.settings["languages"])
            self.lang_vars[code] = v
            self._reg(f"det.lang.{code}", ui.Checkbutton(grid, text=label, variable=v, command=self._langs_changed)).grid(
                row=i // 5, column=i % 5, sticky="w", padx=(0, 12), pady=1)

        chk = ui.LabelFrame(f, text=_("Abgleich mit der Stats-Seite"), padding=8)
        chk.pack(fill="x", pady=(8, 0))
        self.off_check_var = ui.StringVar(value="")         # filled when the tab is opened (_official_check_render)
        ui.Label(chk, textvariable=self.off_check_var, wraplength=420, justify="left").pack(anchor="w")

        # technical options: folded away, only needed when something does not work
        self.adv_open = ui.BooleanVar(value=bool(self.settings.get("show_advanced", False)))
        self.adv_btn = ui.Button(f, command=self._toggle_advanced)
        self.adv_btn.pack(anchor="w", pady=(10, 0))
        adv = self.adv_frame = ui.LabelFrame(f, text=_("Erweitert"), padding=8)
        self.wgc_var = ui.BooleanVar(value=self.settings.get("window_capture", True))
        ui.Checkbutton(adv, text=_("Auch erkennen, wenn andere Fenster über DBD liegen"),
                        variable=self.wgc_var, command=self._detect_flags_changed).pack(anchor="w", pady=1)
        ui.Label(adv, text=_("Fensteraufnahme wie bei OBS, nur solange DBD im Hintergrund ist"),
                  style="Dim.TLabel", wraplength=400).pack(anchor="w", padx=(22, 0))
        self.rate_var = ui.DoubleVar(value=float(self.settings.get("scans_per_second", 5)))
        self._slider(adv, _("Scans/Sek."), self.rate_var, 2, 10, self._rate_changed, fmt="{:.0f}")
        self.watch_var = ui.StringVar(value=_("Rundenende-Erkennung: {state}", state=_("keine Map angezeigt")))
        ui.Label(adv, textvariable=self.watch_var, style="Dim.TLabel", wraplength=420).pack(anchor="w", pady=(4, 6))
        self.debug_var = ui.BooleanVar(value=self.settings["save_debug_images"])
        ui.Checkbutton(adv, text=_("Debug-Bilder speichern (Ordner debug/)"), variable=self.debug_var,
                        command=self._detect_flags_changed).pack(anchor="w")
        r = ui.Frame(adv)
        r.pack(fill="x", pady=(6, 0))
        ui.Button(r, text=_("Bildschirm jetzt scannen"), command=self.scan_now).pack(side="left")
        ui.Button(r, text=_("Diagnose kopieren"), command=self.show_diagnose).pack(side="left", padx=6)
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

    # -------------------------------------------------------------- tab: log
    def _tab_log(self):
        outer, f = self._fixed_tab()
        top = ui.Frame(f)
        top.pack(fill="x", pady=(0, 6))
        ui.Label(top, text=_("Anzeigen:")).pack(side="left")
        enabled = set(self.settings.get("log_categories", CATS))
        self.cat_vars = {}
        for c in CATS:
            v = ui.BooleanVar(value=c in enabled)
            self.cat_vars[c] = v
            ui.Checkbutton(top, text=_(c), variable=v, command=self._log_filter_changed).pack(side="left", padx=(6, 0))
        # the Qt window shows the entries itself (coloured by category): (entries, dark mode)
        self.log_text = ui.Log(f, lines=lambda: ([e for e in self._log_entries if self.cat_vars[e[1]].get()][-400:],
                                                 bool(self.settings.get("dark_mode", True))))
        self.log_text.pack(fill="both", expand=True)
        bottom = ui.Frame(f)
        bottom.pack(fill="x", pady=(6, 0))
        ui.Button(bottom, text=_("Leeren"), command=self._clear_log).pack(side="left")
        ui.Button(bottom, text=_("Log-Datei öffnen"), command=self._open_logfile).pack(side="left", padx=6)
        ui.Button(bottom, text=_("Diagnose kopieren"), command=self.show_diagnose).pack(side="left")
        return outer

    # ----------------------------------------------------------- map list
    def _fill_list(self):
        """The maps as listed on the maps page (search applied): order for the hotkeys next/previous map."""
        self._list_items = {i: (mid, v) for i, (_r, _l, mid, v) in enumerate(self._qt_map_items())}

    def _search_maps(self, text):
        """Show the maps page with this search (a scan found only the realm)."""
        self._qt_search = text
        self._qt_maps_rev = getattr(self, "_qt_maps_rev", 0) + 1
        self._fill_list()
        if self.qt is not None:
            self.qt.show_page("maps", search=text)

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
        same_map = was_on and self.current is not None and self.current[0] == map_id
        self._test_map = False                   # a real/manual choice replaces the test picture
        self._clear_unsure()                     # another map on display: the doubt was about the old one
        self._layout_unsure = False
        self.current = (map_id, shown)
        self.source = source
        self.overlay.set_map(path, m.label(shown), rotation)
        if not same_map:                         # a new map/round starts as set, the same one keeps its floor
            self._floor = None if self.settings["overlay"].get("floor_auto", True) else 0
        self._apply_floor()
        self._update_record()
        if not was_on and not keep_timer:
            self._round_started(time.time())     # map appears -> timer from zero (a switch while on keeps it)
        self.user_visible = True
        self.hidden_after_match = False
        self.menu_paused = False
        self._watch(source)
        self.tray.set_title(f"DbD Map Scout – {m.label(shown)}")
        self._detail = detail or {"manual": _("manuell gewählt"), "scan": _("per Scan gefunden")}.get(source, "")
        self._set_thumb(frames[0][0])
        self._show_map_size()
        if source == "manual":
            self._log(_("Map gewählt: {map}", map=m.label(shown)), "Overlay")
        self._tick_overlay(reschedule=False)

    def _set_thumb(self, img):
        src = img.copy()                          # for the overview page
        src.thumbnail((480, 480))
        self._thumb_src = src
        self._thumb_rev = getattr(self, "_thumb_rev", 0) + 1

    def _current_label(self) -> str:
        m = self.catalog.maps.get(self.current[0]) if self.current else None
        return m.label(self.current[1]) if m else ""

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

    def _layouts(self):
        """Layouts with a picture of the map on display ([] without a map)."""
        m = self.catalog.maps.get(self.current[0]) if self.current else None
        return [v for v in sorted(m.variants) if m.variants[v]] if m else []

    def next_floor(self):
        """Button/hotkey: maps with floors (Midwich) – all one below the other -> bottom -> ... -> top -> all."""
        floors = self.overlay.floors() if self.current else []
        if not floors:
            self._log(_("Diese Map hat nur eine Etage."), "Overlay")
            return
        self._floor = mapimage.next_floor(floors, self._floor)
        self._apply_floor()
        self._tick_overlay(reschedule=False)          # the size changes: place it again right away

    def _apply_floor(self):
        """Hand the chosen floor to the overlay (after loading a map); the button only shows for maps with floors."""
        floors = self.overlay.floors() if self.current else []
        if not floors:
            self._floor = None
        elif self._floor is not None:
            self._floor %= len(floors)
        self.overlay.set_floor(floors[self._floor] if self._floor is not None else None)

    def _hk_hint(self, name):
        combo = (self.settings.get("hotkeys") or {}).get(name)
        return " " + _("Hotkey: {keys}", keys=pretty(combo)) if combo else ""

    def _button_tip(self, key):
        """Tooltips of the overview's buttons whose label changes (None: tooltip.TIPS by label)."""
        if key == "toggle":
            on = self.user_visible and not self.hidden_after_match and not self.menu_paused
            return (_("Karte ausblenden (die automatische Erkennung läuft weiter).") if on else
                    _("Karte wieder einblenden.")) + self._hk_hint("toggle_overlay")
        if key == "layout":
            return (_("Die Erkennung war beim Layout nicht sicher – stimmt es nicht, hier weiterschalten.")
                    + " " if self._layout_unsure else "") + \
                _("Wechselt zum nächsten Layout dieser Map (z. B. Coal Tower ↔ Coal Tower II). Die Layouts ab II "
                  "gibt es seit Patch 8.6.0 nur noch in Custom Games.") + self._hk_hint("next_variant")
        if key == "rotate":
            return tooltip.tip_for_label("Drehen ↻") + self._hk_hint("rotate_map")
        if key == "floor":
            return _("Wechselt die Anzeige bei Karten mit Etagen (Midwich): beide untereinander → "
                     "unten → oben → beide. Gilt bis zur nächsten Map.") + self._hk_hint("next_floor")
        return None

    def _tip_lookup(self, w):
        """Tooltips for buttons whose label changes or repeats (the rest: tooltip.TIPS by label)."""
        hk = {b: k for k, b in self.hk_buttons.items()}
        if w is self.test_btn:
            return lambda: (_("Test sofort beenden.") if self.test_btn.cget("text") == _("Test beenden") else
                            _("Zeigt die Karte 10 s an ihrer normalen Position – auch wenn sie gerade ausgeblendet "
                              "wäre. Nochmal drücken beendet den Test."))
        if w is self.adv_btn:
            return _("Technische Optionen für die Fehlersuche ein- oder ausklappen.")
        if w is self.more_btn:
            return _("Selten gebrauchte Einstellungen ein- oder ausklappen.")
        if w is self.edit_btn:
            return lambda: (_("Verschieben beenden.") if self.edit_btn.cget("text") == _("Fertig") else
                            _("Karte direkt mit der Maus ziehen, Mausrad ändert die Grösse.")
                            + self._hk_hint("edit_position"))
        if w in hk:
            return _("Klicken und die neue Tastenkombination drücken: Strg/Alt + Taste, oder eine Taste allein "
                     "(F1–F12, Numpad, Pause, Rollen, Einfg, Pos1, Ende, Bild↑/↓ – die gilt nur, solange DBD vorne "
                     "ist). Esc bricht ab, Entf schaltet den Hotkey aus.")
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
        self.root.clipboard_set(text)
        self._log(_("Diagnose in die Zwischenablage kopiert (auch als diagnose.txt gespeichert)."), "System")
        log.info(text)

    def toggle_edit(self):
        """Edit mode: the map (and system values with an own position) can be dragged."""
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
        new = round(min(MAX_HEIGHT, max(0.15, self._map_height() + delta)), 3)
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
        self._apply_floor()
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
        """Every 50 ms: the events of the detection, the hotkeys, the tray and the window, in order. One failing
        event is reported and the rest still runs (the loop must never stop)."""
        while not self._quitting:
            try:
                ev = self.events.get_nowait()
            except queue.Empty:
                break
            t0 = time.perf_counter()
            try:
                self._dispatch(ev)
            except Exception:
                self._report_once("Ereignis", traceback.format_exc())
            took = (time.perf_counter() - t0) * 1000
            if took >= 30:
                self.root.note("Ereignis " + _event_name(ev), took)
        if not self._quitting:
            self.root.after(50, self._poll)

    def _dispatch(self, ev):
        if isinstance(ev, tuple) and ev[0] == "hotkey":
            self._hotkey(ev[1])
        elif isinstance(ev, tuple) and ev[0] == "hotkey_failed":
            self._hotkey_failed(*ev[1:])
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
            {"open": self._show_main, "toggle": self.toggle_overlay,
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
        elif isinstance(ev, tuple) and ev[0] == "ui":
            self._qt_event(ev[1], ev[2])
        elif isinstance(ev, tuple) and ev[0] == "call":       # from a window procedure (overlay, HUD)
            ev[1](*ev[2])
        else:
            self._event(ev)

    def _hotkey(self, name):
        {"toggle_overlay": self.toggle_overlay, "next_variant": self.next_variant, "scan_now": self.scan_now,
         "next_map": lambda: self.step_map(1), "prev_map": lambda: self.step_map(-1),
         "bigger": lambda: self._resize(0.03), "smaller": lambda: self._resize(-0.03),
         "edit_position": self.toggle_edit, "rotate_map": self.rotate_map, "next_floor": self.next_floor,
         "reject_map": self.reject_detection}.get(name, lambda: None)()

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
            rej = self._rejected
            if rej and rej[0] == d["map_id"] and time.time() - rej[1] < REJECT_HOLD:
                return                              # the same banner again: the user said it is wrong
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
            if self._unsure and not d.get("unsure") and same:
                self._clear_unsure(confirmed=True)  # later frames of the banner read it cleanly
            if not same:
                self.show_map(d["map_id"], d["variant"], "auto", detail, keep_timer=True)
                if d.get("unsure"):
                    self._unsure = {"label": m.label(d["variant"]), "t": time.time(), "shown": False,
                                    "fit": d.get("name_fit", 0.0), "name": d["name_text"]}
                self._log(_("Erkannt: {map} – gelesen „{name}“ / „{realm}“", map=m.label(d["variant"]),
                            name=d["name_text"], realm=d["realm_text"]), "Erkennung")
                if len(m.variants) > 1 and vp < 0.8:
                    self._layout_unsure = True
                    self._log(_("Layout unsicher – falls falsch: Layout-Knopf oder {keys}.",
                                keys=pretty(self.settings["hotkeys"].get("next_variant") or "–")), "Erkennung")
        elif k == "ignored":                       # banner-like text well into a round (worker: strict reading)
            m = self.catalog.maps.get(d.get("map_id") or "")
            if m is None or (self.current and self.current[0] == m.id):
                return                              # nothing that looked like another map
            self._log(_("Mitten in der Runde „{name}“ / „{realm}“ gelesen (am ehesten {map}) – ignoriert: Map-Banner "
                        "gibt es nur am Rundenstart, und die Lesung war nicht eindeutig.", name=d.get("name_text") or "",
                        realm=d.get("realm_text") or "", map=m.label(1)), "Erkennung")
        elif k == "unknown":
            txt = d.get("name_text") or "?"
            self._log(_("Banner gesehen, aber keine bekannte Map: „{text}“. Map manuell wählen "
                        "oder mit „Zuordnen …“ dauerhaft zuordnen.", text=txt), "Erkennung")
            if len(fold(txt)) >= self.catalog.MIN_ALIAS:
                self._unknown = (txt, d.get("realm_text") or "")
        elif k == "queue":
            self._queue_event(d)
        elif k == "match_end":
            self._clear_unsure()                  # a whole round on that map: it was real
            self._round_ended(d.get("t") or time.time())
            if d.get("role"):
                self._log(_("Ergebnisbildschirm: gespielt als {role}.", role=self._role_name(d["role"])), "Erkennung")
                self._queue = dict(self._queue, role=d["role"])
            self._hist_close(d.get("t") or time.time(), d.get("role"))
            if self.overlay.has_map() and not self.hidden_after_match:
                was_visible = self.user_visible
                self.hidden_after_match = True
                self.menu_paused = False
                reason = _(d.get("reason") or "Ergebnisbildschirm")
                self._log(_("Runde vorbei ({reason}) – Overlay ausgeblendet.", reason=reason) if was_visible
                          else _("Runde vorbei ({reason}).", reason=reason), "Erkennung")
                self._tick_overlay(reschedule=False)
        elif k == "menu":
            if d.get("on"):
                if self.overlay.has_map() and not self.hidden_after_match and not self.menu_paused:
                    self.menu_paused = True
                    self._log(_("Menü offen (Mauszeiger sichtbar) – Overlay pausiert."), "Overlay")
                    self._tick_overlay(reschedule=False)
            elif self.menu_paused:
                self.menu_paused = False
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
            self._inform("DbD Map Scout", _("Die Erkennung ist abgestürzt:") + "\n\n" + d["text"][-1500:])

    # ---------------------------------------------------------- round timer
    def _round_started(self, t):
        self.round.start(t)
        self._log(_("Rundentimer gestartet."), "Erkennung")

    def _round_ended(self, t):
        if self.round.stop(t):
            self._log(_("Rundentimer gestoppt: {time}.", time=fmt_duration(self.round.elapsed(t))), "Erkennung")

    def _tick_timer(self):
        r = self.round
        overlay_text = fmt_duration(r.elapsed(time.time())) if r.start_t is not None and r.running else ""
        self.overlay.set_timer(overlay_text if self.settings["overlay"].get("show_timer", True) else "")

    def _set_status(self, text):
        """Technical status from the worker: goes to the log; the status line shows a plain summary."""
        self._worker_status = text
        self._log(text, "System")

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
                self._search_maps(self.catalog.realms.get(realm, {}).get("en", realm))
                self._log(_("Scan: Realm „{realm}“ gefunden – bitte Map in der Liste wählen.", realm=realms[0].text), "Erkennung")
            return
        self._log(_("Scan ({s} s): kein Map- oder Realm-Name auf dem Bildschirm.", s=f"{d['seconds']:.1f}"), "Erkennung")

    # ============================================================ overlay
    def _game_rect(self):
        now = time.time()
        if now - self._game_checked > 1.0:
            self.game = find_game_window()
            self._game_checked = now
            self._note_window()
        if self.game and not self.game.minimized and self.game.width > 100:
            return self.game.rect
        return (0, 0) + self.root.screen_size()

    def _tick_overlay(self, reschedule=True):
        try:
            self._tick_unsure()
            self._tick_timer()
            self._place_overlay()
        except Exception:
            self._report_once("overlay", traceback.format_exc())
        try:
            self._conn_tick()
        except Exception:
            self._report_once("verbindung", traceback.format_exc())
        try:
            self._official_tick()
        except Exception:
            self._report_once("offizielle Daten", traceback.format_exc())
        try:
            self._hotkeys_tick()
        except Exception:
            self._report_once("hotkeys", traceback.format_exc())
        try:
            self._qt_refresh()
        except Exception:
            self._report_once("Qt", traceback.format_exc())
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
            self._log(_("Test beendet."), "Overlay")
        if (time.time() >= getattr(self, "_force_until", 0) and hasattr(self, "test_btn")
                and self.test_btn.cget("text") != _("Overlay testen")):
            self.test_btn.configure(text=_("Overlay testen"))
        wait = [] if forced else self._waiting_lines()
        self.overlay.set_waiting(wait)
        reason = None
        if forced:
            pass
        elif wait:
            reason = self._focus_reason(o)                  # only the "DBD in front" rule applies
        elif not self.overlay.has_map():
            reason = _("keine Map")
        elif not ((self.user_visible and not self.hidden_after_match) or self.overlay.editing):
            reason = _("ausgeblendet")
        elif self.menu_paused and not self.overlay.editing:
            reason = _("Menü offen")
        elif not o.get("show_map", True) and not self.overlay.has_info() and not self.overlay.editing:
            reason = _("nichts anzuzeigen")          # info only, but no timer/server yet
        else:
            reason = self._focus_reason(o)
        if wait:
            self._vis_state = "wartet"                      # the waiting card is not logged
        elif not forced:
            self._log_visibility(reason, (gx, gy, gw, gh))
        hud = self._hud_place(gx, gy, gw, gh, show=not reason and not wait)
        self._sysinfo_status()
        if reason:
            self.overlay.hide()
            self.worker.overlay_rect = None
            return
        if self.overlay.editing and self.overlay.dragging:
            return                                           # user is dragging
        self.overlay.opacity = o["opacity"]
        margin = int(gh * o["margin"])
        # floors one below the other (Midwich): each as big as one map, as far as the screen allows
        height = int(gh * min(MAX_HEIGHT, self._map_height() * self.overlay.stacked()))
        a = o["anchor"]
        drop = hud[1] + margin if hud and layout.below_hud(hud[0], a) else 0     # map below the system values
        height = min(height, gh - drop - 2 * margin)
        bar = layout.bar_width(gw, gh)          # black bar left/right of a 16:9 picture (ultrawide)
        # window narrower than 16:9: the trial has bars above/below – the map goes there whatever the position
        # setting says (user: own position at 1440p, the bar in the small window); not while dragging it
        vb = None if self.overlay.editing else layout.vbars(self.worker.vbars, gw, gh, time.time())
        self.overlay.info_beside = bool(vb)
        if vb:
            self._place_in_bottom_bar(gx, gy, gw, gh, vb[1], margin, height, sliders=a != "custom")
            return
        slot = None
        if a == "auto" and bar < layout.MIN_BAR:
            slot = self._outside_slot()          # window mode: free desktop beside the DBD window
            if slot is None:
                a = "top-left"

        def place(w, h):
            if slot is not None:
                return layout.slot_x(slot, w, margin), gy + margin
            if a == "auto":
                return gx + max(margin, (bar - w) / 2), gy + margin + drop
            if a == "custom":
                return gx + o.get("pos_x", 0.0) * max(0, gw - w), gy + o.get("pos_y", 0.0) * max(0, gh - h)
            return (gx + margin if a.endswith("left") else gx + gw - w - margin,
                    gy + margin + drop if a.startswith("top") else gy + gh - h - margin)

        # Fit before rendering: only the final size may reach the screen (render() shows it at once).
        iw, ih = self.overlay.map_size()
        w_est = round(iw * height / ih) if ih else 0
        side = (layout.bar_side(a, place(w_est, 0)[0], w_est, gx, gw, bar)
                if slot is None and (a == "auto" or o.get("keep_in_bar", True)) else None)
        avail = layout.max_width(bar, margin)
        if slot is not None:                     # the free space works like a bar: fit, never cover DBD
            side, avail = "slot", layout.max_width(slot[2], margin)
        if side:
            height = layout.fit_height(height, avail, iw, ih)
        w, h = self.overlay.render(height)
        if side and w > avail:                  # info block below is wider than the map (rare)
            w, h = self.overlay.render(max(80, int(height * avail / w)))
        x, y = place(w, h)
        if side and side != "slot":
            x = layout.clamp_x(side, x, w, gx, gw, bar, margin)
        self.overlay.show_at(int(x), int(y))
        self._last_place = (int(x), int(y), w, h)
        self.worker.overlay_rect = self._last_place if self.overlay.shown else None
        self._hud_follow_map(self._last_place, gx, gy, gw, gh, margin)       # system values "above the map"
        if a != "custom":                      # sliders follow the preset position
            self._set_pos_sliders((x - gx) / max(1, gw - w), (y - gy) / max(1, gh - h))

    def _place_in_bottom_bar(self, gx, gy, gw, gh, bottom, margin, height, sliders=True):
        """Map (+ timer, server) in the black bar below the picture, left, as big as the bar allows."""
        avail_w, avail_h = gw - 2 * margin, bottom - 2 * margin
        height = min(height, avail_h)
        w, h = self.overlay.render(height)
        for _try in range(3):                    # the info block below the map needs room too (not quite linear)
            f = layout.fit_scale(w, h, avail_w, avail_h)
            if f >= 1 or height <= 40:
                break
            height = max(40, int(height * f))
            w, h = self.overlay.render(height)
        x, y = gx + margin, gy + gh - bottom + margin
        self.overlay.show_at(int(x), int(y))
        self._last_place = (int(x), int(y), w, h)
        self.worker.overlay_rect = self._last_place if self.overlay.shown else None
        self._hud_follow_map(self._last_place, gx, gy, gw, gh, margin)       # "above the map": right of it here
        if sliders:                              # an own position stays as it is (it applies again at 1440p)
            self._set_pos_sliders((x - gx) / max(1, gw - w), (y - gy) / max(1, gh - h))

    def _outside_slot(self):
        """Free desktop space beside a DBD window that does not fill its monitor, or None."""
        g = self.game
        if g is None or g.minimized or not g.monitor:
            return None
        frame = g.outer or g.window or g.client
        if not frame:
            return None
        return layout.outside_slot(frame[0], frame[2], g.monitor[0], g.monitor[2])

    def _note_window(self):
        """Log once when DBD runs in a way that makes detection weaker (small window, narrower than 16:9)."""
        g = self.game
        if g is None or g.minimized or not g.client:
            return
        flags = (min(g.height, g.width * 9 / 16) < SMALL_PICTURE, g.width * 9 < g.height * 16 - 32)
        told = getattr(self, "_window_told", (False, False))
        if flags[0] and not told[0]:
            self._log(_("DBD läuft mit {w}×{h}, kleiner als 1920×1080: die Erkennung ist unsicherer (vor allem "
                        "Lobby-Knopf und Killername). Fenster größer ziehen oder „Fenster-Vollbild“ nutzen.",
                        w=g.width, h=g.height), "Erkennung")
        if flags[1] and not told[1]:
            self._log(_("DBD-Fenster ist schmaler als 16:9 ({w}×{h}): diese Form ist ungetestet, Map- und "
                        "Rundenende-Erkennung können danebenliegen. Am sichersten: 16:9 oder breiter.",
                        w=g.width, h=g.height), "Erkennung")
        self._window_told = flags

    def _focus_reason(self, o):
        """Reason to hide while another window is in front ("Nur zeigen, wenn DBD das aktive Fenster ist")."""
        if (o["only_when_game_focused"] and IS_WIN and not self.overlay.editing and not self.simulate
                and self.game is not None):
            fg = foreground_root()
            own = {self.overlay.hwnd(), self._qt_hwnd()}
            if fg not in own and not is_game_window(fg):
                return _("aktives Fenster ist {window}", window=describe_window(fg))
        return None

    def _waiting_lines(self):
        """The waiting card while DBD runs and no map is on screen: what the program is waiting for, and
        the lobby state below it. Never over a map the user hid on purpose, never while editing."""
        o = self.settings["overlay"]
        if (not o.get("show_waiting", True) or not self.settings.get("auto_detect", True)
                or (self.game is None and not self.simulate) or self.overlay.editing):
            return []
        if self.overlay.has_map() and not self.hidden_after_match:
            return []                                        # map shown, paused in a menu or hidden by hand
        lines = [_("Warte auf Map")]
        q = self._queue
        if q.get("state") == "search" or q.get("found") is not None:      # searching / lobby found (not yet used)
            lines += [t for t in [self._queue_text(time.time())] if t]
        elif self.hidden_after_match and self.round.start_t is not None and not self.round.running:
            lines.append(_("Letzte Runde: {time}", time=fmt_duration(self.round.elapsed(0))))
        return lines

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

    # ============================================================ settings
    def _apply_overlay_settings(self):
        o = self.settings["overlay"]
        self.overlay.opacity = o["opacity"]
        self.overlay.show_caption = o["show_caption"]
        self.overlay.set_transparent(o.get("transparent", True))
        self.overlay.set_show_map(o.get("show_map", True))

    def _pos_hint(self):
        """The sliders always work: moving one switches to "eigene Position" – say so while a preset is set."""
        if self.settings["overlay"].get("anchor", "auto") == "custom":
            text = _("0 % = links/oben, 100 % = rechts/unten")
        elif self.settings["overlay"].get("anchor", "auto") == "auto":
            text = _("Automatisch: im schwarzen Rand neben dem Spielbild, im Fenstermodus neben dem DBD-Fenster "
                     "(falls dort Platz ist). Regler bewegen = eigene Position.")
        else:
            text = _("Regler bewegen = eigene Position.")
        self.pos_hint_var.set(text)

    def _anchor_changed(self):
        rev = {_(v): k for k, v in ANCHORS}
        self.settings["overlay"]["anchor"] = rev.get(self.anchor_var.get(), "auto")
        self._pos_hint()
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
            self._pos_hint()
        o["pos_x"] = round(self.posx_var.get() / 100, 4)
        o["pos_y"] = round(self.posy_var.get() / 100, 4)
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _preview_data(self) -> dict:
        """What the overlay tab's preview draws: the screen DBD runs on (full screen), the map where
        _place_overlay would put it (layout.preview_rect), as big and transparent as set, the lines below it."""
        o = self.settings["overlay"]
        _gx, _gy, gw, gh = self._game_rect()
        pic = None
        if o.get("show_map", True):
            pic = getattr(self, "_thumb_src", None) if self.current else None
            pic = pic or self._preview_sample()
        lines = []
        if o.get("show_timer", True):
            lines.append("03:27")
        if o.get("show_server", True) and self.settings.get("show_connection"):
            lines.append(_("FRANKFURT · PING 31 MS"))
        if o.get("show_record", True):
            lines.append(_("Ø 2,8 KILLS · 12 RUNDEN"))
        aspect = pic.width / pic.height if pic is not None else 0.8
        rows = (len(lines) + 1) if lines and o.get("show_timer", True) else len(lines)
        x, y, w, h, mh = layout.preview_rect(gw, gh, o["anchor"], o.get("pos_x", 0.0), o.get("pos_y", 0.0),
                                             self._map_height(), o["margin"], o.get("keep_in_bar", True),
                                             aspect, rows)
        if pic is None:
            mh = 0
        return {"screen": (gw, gh), "bar": layout.bar_width(gw, gh), "rect": (x, y, w, h, mh), "pic": pic,
                "lines": lines, "opacity": o["opacity"], "transparent": o.get("transparent", True)}

    def _preview_sample(self):
        """A map picture for the preview while none is on display (the first one of the catalog), loaded once."""
        if getattr(self, "_preview_pic", None) is None:
            from PIL import Image
            for mid in self.catalog.maps:
                path, _v = self.catalog.image_path(mid, 1)
                if path:
                    try:
                        with Image.open(path) as im:
                            im.seek(0)
                            pic = im.convert("RGBA")
                        pic.thumbnail((480, 480))
                        self._preview_pic = pic
                        break
                    except (OSError, ValueError):
                        continue
        return getattr(self, "_preview_pic", None)

    def _preview_pick(self, value):
        """A click or drag on the preview: the map's centre goes there – an own position (like the sliders)."""
        what, cx, cy = value
        if what != "move":
            return
        _x, _y, w, h, _mh = self._preview_data()["rect"]
        _gx, _gy, gw, gh = self._game_rect()
        fx, fy = layout.pos_from_point(gw, gh, w, h, cx, cy)
        self._syncing = True
        try:
            self.posx_var.set(round(fx * 100, 1))
            self.posy_var.set(round(fy * 100, 1))
            self.posx_label.configure(text=f"{fx * 100:.0f} %")
            self.posy_label.configure(text=f"{fy * 100:.0f} %")
        finally:
            self._syncing = False
        self._pos_changed()

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
        o["show_waiting"] = bool(self.waiting_var.get())
        if bool(self.record_var.get()) != o.get("show_record", True):
            o["show_record"] = bool(self.record_var.get())
            self._update_record()
        if bool(self.floor_auto_var.get()) != o.get("floor_auto", True):
            o["floor_auto"] = bool(self.floor_auto_var.get())
            self._floor = None if o["floor_auto"] else 0          # the map on display follows right away
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
            self._tick_overlay(reschedule=False)
        self.settings.set("save_debug_images", bool(self.debug_var.get()))
        self._save_soon()

    # ---------------------------------------------------------- own map assignments
    # ---------------------------------------------------------- doubtful detection
    def _tick_unsure(self):
        """Show the doubt only if the banner did not read cleanly a moment later (fade-in frames fit worse)."""
        u = self._unsure
        if not u or u["shown"] or time.time() - u["t"] < UNSURE_DELAY:
            return
        u["shown"] = True
        keys = pretty(self.settings["hotkeys"].get("reject_map") or "–")
        self.overlay.set_note(_("? unsicher – {keys} = falsch", keys=keys))
        self._log(_("Unsicher erkannt: {map} – gelesen „{name}“, Passung {fit}. Falls falsch: {keys} oder "
                    "„Falsch erkannt“.", map=u["label"], name=u["name"], fit=f"{u['fit']:.1f}", keys=keys),
                  "Erkennung")

    def _clear_unsure(self, confirmed=False):
        u, self._unsure = self._unsure, None
        if u is None:
            return
        self.overlay.set_note("")
        if confirmed and u["shown"]:
            self._log(_("{map} bestätigt.", map=u["label"]), "Erkennung")

    def _confirm_unsure(self):
        self._clear_unsure(confirmed=True)

    def reject_detection(self):
        """The detected map is wrong: hide it, stop the timer and do not count the round."""
        if self.current is None or self.source != "auto" or self.hidden_after_match:
            self._log(_("Nichts zu verwerfen: keine automatisch erkannte Map eingeblendet."), "Erkennung")
            return
        label = self._current_label()
        self._rejected = (self.current[0], time.time())
        self._clear_unsure()
        if self._hist is not None:
            self._hist = None
            used = self._queue.get("used")           # the lobby goes to the next (real) round
            if used is not None and self._queue.get("found") is None:
                self._queue = dict(self._queue, found=used, used=None)
        self.round.clear()
        self.hidden_after_match = True              # waiting card again; the next banner shows its map
        self.menu_paused = False
        self._detail = _("als falsch verworfen")
        self._log(_("Verworfen: {map} – die Runde wird nicht gezählt.", map=label), "Erkennung")
        self._tick_overlay(reschedule=False)

    def _hide_unknown(self):
        self._unknown = None

    def assign_unknown(self):
        """Dialog: which map was the banner that matched nothing? Saves the read text as an alias."""
        if not self._unknown:
            return
        name, realm = self._unknown
        entries = [m for m in self.catalog.sorted_entries() if not m.custom]
        labels = [f"{m.name} ({self.catalog.realm_display(m)})" for m in entries]
        guess = self.catalog.suggest(name, realm)
        dlg = ui.Toplevel(self.ui_root)
        dlg.title(_("Map zuordnen"))
        dlg.transient(self.root)
        dlg.resizable(False, False)
        body = ui.Frame(dlg, padding=12)
        body.pack(fill="both", expand=True)
        ui.Label(body, text=_("Gelesen: „{text}“", text=name) + (f" / „{realm}“" if realm else ""),
                  wraplength=380).pack(anchor="w")
        ui.Label(body, text=_("Welche Map war das? Der Name wird künftig automatisch erkannt."),
                  style="Dim.TLabel", wraplength=380).pack(anchor="w", pady=(2, 8))
        var = ui.StringVar(value=labels[[m.id for m in entries].index(guess)] if guess in
                           [m.id for m in entries] else "")
        cb = ui.Combobox(body, textvariable=var, values=labels, state="readonly", width=44, height=18)
        cb.pack(fill="x")
        msg = ui.StringVar(value="")
        ui.Label(body, textvariable=msg, style="Dim.TLabel", wraplength=380).pack(anchor="w", pady=(6, 0))

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

        row = ui.Frame(body)
        row.pack(fill="x", pady=(10, 0))
        ui.Button(row, text=_("Zuordnen"), command=ok).pack(side="right")
        ui.Button(row, text=_("Abbrechen"), command=dlg.destroy).pack(side="right", padx=6)
        dlg.bind("<Return>", lambda e: ok())
        dlg.bind("<Escape>", lambda e: dlg.destroy())
        tooltip.attach_all(dlg)
        cb.focus_set()
        self._dialog(dlg)                       # grab here, or the Qt window shows it

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
        if not self._ask(_("Eigene Zuordnungen"), _("Alle eigenen Map-Zuordnungen löschen?"), self._clear_aliases):
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
        """Dark/light: the Qt window's colours, the server table's ping colours and the charts."""
        from .theme import LOG_COLORS
        dark = bool(self.dark_var.get()) if hasattr(self, "dark_var") else bool(self.settings.get("dark_mode", True))
        colors = LOG_COLORS[dark]
        for tag, key in (("p_good", "Erkennung"), ("p_bad", "Fehler"), ("p_na", "ts")):
            self.srv_tree.tag_configure(tag, foreground=colors[key])
        self.srv_tree.tag_configure("p_mid", foreground="#d29922" if dark else "#9a6700")
        self.srv_tree.tag_configure("group", foreground=colors["text"])
        for chart in (getattr(self, "trend", None), getattr(self, "sys_trend", None)):
            if chart is not None:
                chart.dark = dark
        if getattr(self, "stats_dash", None) is not None:
            self.stats_dash.dark = dark
        self._qt_theme()

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
        q = getattr(self, "qt", None)
        if entry[1] == "Fehler" and (q is None or not q.isVisible() or q.current_key() != "log"):
            self._log_alert = True                # "Log ⚠" in the window until the log is opened

    def _log_filter_changed(self):
        self.settings.set("log_categories", [c for c in CATS if self.cat_vars[c].get()])
        self._save_soon()
        self.log_text._dbdms_rev = getattr(self.log_text, "_dbdms_rev", 0) + 1     # the window shows it anew

    def _clear_log(self):
        self._log_entries.clear()
        self.log_text._dbdms_rev = getattr(self.log_text, "_dbdms_rev", 0) + 1

    def _tab_changed(self):
        if self.nb.select() == str(self.tab_stats):
            self._stats_render()
        if self.nb.select() == str(self.tab_detect):
            self._official_check_render()
        if self.nb.select() == str(self.tab_log):
            self._log_alert = False
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

    # ================================================================ quit
    def quit(self):
        if self._quitting:                       # e.g. tray "Beenden" and the window's X in the same poll
            return
        self._quitting = True
        try:
            self._qt_close()
            self.settings.save()
            self.tray.stop()
            self.conn.stop()
            self.sysmon.stop()
            self.worker.stop()
            self.hotkeys.stop()
            self.worker.join(timeout=4)      # let a running OCR call finish cleanly
            if hasattr(self.overlay, "destroy"):
                self.overlay.destroy()
            if self.hud is not None:
                self.hud.destroy()
            self.toast.close()
        finally:
            self.root.quit()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":  # pragma: no cover
    sys.exit("Start mit: python -m dbdmapscout")
