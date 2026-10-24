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

from . import i18n, layout, mapimage, mapnotes, mapstyle, obsrec, regions, restart, tooltip
from . import uimodel as ui
from .capture import IS_WIN, find_game_window
from .catalog import Catalog
from .config import DEFAULTS as CONFIG_DEFAULTS, Settings
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
from .app_layout import LayoutMemory
from .app_sysinfo import TEXT_BASE, text_scale
from .app_sysinfo import HUD_SHOWN, OPACITY_KEYS, SysInfo
from .app_qt import QtShell
from .app_overlay import OverlayTab, anchor_label
from .app_place import MAX_HEIGHT, OverlayPlacement
from .app_recordings import RecordingsTab
from .app_export import ExportDialog
from .app_discord import DiscordPresence
from .app_spotify import SpotifyUpNext
from .app_youtube import YouTubeUpload

LANGS = [("en", "EN"), ("de", "DE"), ("fr", "FR"), ("es", "ES"), ("es-MX", "ES-MX"), ("it", "IT"),
         ("pl", "PL"), ("pt-BR", "PT"), ("tr", "TR")]
REJECT_HOLD = 60.0        # s: a rejected map is not shown again by the same banner
UNSURE_DELAY = 2.5        # s: a doubtful read is shown only if the banner did not read cleanly meanwhile
QUIT_WATCHDOG_S = 15     # s: quitting takes longer than this -> the process ends anyway (1.65.1)
QUIT_RECORDER_S = 8      # s: quitting waits this long for OBS to stop a round still running (1.8.38)
STYLE_CACHE = os.path.join("cache", "maps_dark")      # below the program folder, made from maps/ (gitignored)
CATS = [N_("Erkennung"), N_("Overlay"), N_("System"), N_("Fehler")]   # log categories (keys; shown translated)


def _event_name(ev) -> str:
    """Short name of an event for the lag list of the diagnosis ("ui page stats", "detected" …)."""
    if isinstance(ev, tuple):
        parts = [str(x) for x in ev[:3] if isinstance(x, str)]
        return " ".join(parts)[:60]
    return str(getattr(ev, "kind", type(ev).__name__))


log = logging.getLogger("fogscout")


class App(ServerTab, StatsTab, ExportDialog, RecordingsTab, DiscordPresence, SpotifyUpNext, YouTubeUpload, LobbyInfo,
          Hotkeys, SettingsTab,
          SysInfo, OverlayPlacement, LayoutMemory, OverlayTab, QtShell):
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
        if IS_WIN:
            try:
                from .icon import ensure_ico
                ensure_ico(root_dir)             # the taskbar button shows this icon (1.9.1: renewed per version)
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
        self.recorder = obsrec.Recorder(lambda kind, **d: self.events.put(("obs", kind, d)))   # 1.4: OBS on this PC
        self.recorder.start()
        self._conn_busy = False
        self._conn_next = 0.0
        self._conn_last = None
        self._conn_idle = IdlePause()    # capture paused while DBD is not running

        self.overlay = make_overlay(self.root, prefer_native=self.settings["overlay"].get("native_window", True))
        self.overlay.edit_label = _("KARTE · Strg+Mausrad = Grösse")       # names on the edit frames (1.64.7)
        self.overlay.game_hwnd = lambda: self.game.hwnd if self.game else None
        # window procedures: hand over to _poll (one place, in order with the other events)
        self.overlay.on_moved = lambda x, y: self.events.put(("call", self._overlay_dragged, (x, y)))
        self.overlay.on_wheel = lambda d: self.events.put(("call", self._resize, (0.02 * d,)))
        self._layout_init()              # undo + one layout per DBD window size (1.65)
        self._hud_init()                 # system values at the top of a black bar (CPU/GPU temperature …)

        self._build_ui()
        self._apply_overlay_settings()
        self._style_warm()

        self.worker = DetectionWorker(root_dir, self.settings, self.catalog, self.events, simulate=simulate)
        self.toast.on_rect = lambda r: setattr(self.worker, "toast_rect", r)    # 1.8.13: never read as the game
        self.worker.start()
        self.hotkeys = self._start_hotkeys()
        self.root.after(50, self._poll)
        self.root.after(250, self._tick_overlay)
        self._log(_("Bereit. {n} Maps geladen, Spielsprachen: {langs}.", n=len(self.catalog.maps),
                    langs=", ".join(self.settings["languages"])), "System")
        if self.settings.load_error:            # 1.8.38: say it – before, the defaults replaced the file unnoticed
            self._log(_("settings.json war nicht lesbar ({error}) – Standardwerte geladen. Bis zum Neustart wird "
                        "nichts gespeichert.", error=self.settings.load_error) if self.settings.frozen else
                      _("settings.json war nicht lesbar ({error}) – Standardwerte geladen, die alte Datei liegt als "
                        "settings.json.broken daneben.", error=self.settings.load_error), "Fehler")
        self._srv_refresh(log_summary=True)
        self._show_update_status()
        self._news_check()                      # 1.8.79: "Neu seit …" on the overview after an update
        self._backup_start()                    # 1.8.80: daily copy of rounds.jsonl/official.jsonl → backup/
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
        # 1.65.1: a second start (shortcut while this one sits in the tray) asks for the window instead of
        # only saying "läuft bereits"
        self._show_event = restart.show_event_create() if IS_WIN else None
        threading.Thread(target=self._setup_then_read_autostart, daemon=True, name="autostart").start()

    # ================================================================== UI
    def _build_ui(self):
        """The tabs as a UI model (uimodel.py); the Qt window draws them (app_qt.py, qt_window.py)."""
        self.ui_root = ui.Root()
        self.nb = ui.Notebook(self.ui_root)
        self.tab_maps = self._tab_maps()
        self.tab_overlay = self._tab_overlay()
        self.tab_server = self._tab_server()
        self.tab_log = self._tab_log()
        self.tab_stats = self._tab_stats()
        self.tab_recordings = self._tab_recordings()          # 1.5
        self.tab_settings = self._tab_settings()
        self.nb.add(self.tab_maps, text="Maps")
        self.nb.add(self.tab_overlay, text=_("Overlay"))
        self.nb.add(self.tab_stats, text=_("Statistik"))
        self.nb.add(self.tab_recordings, text=_("Aufnahmen"))
        self.nb.add(self.tab_server, text=_("Server"))
        self.nb.add(self.tab_settings, text=_("Einstellungen"))
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
        name = ui.Label(row, text=label, width=12)
        name.pack(side="left")
        val = ui.Label(row, text=fmt.format(var.get()), width=6, anchor="e")
        val.pack(side="right")
        name._dbdms_slider_part = val._dbdms_slider_part = True    # 1.2.15: the Qt slider draws both itself

        def changed(_=None):
            val.configure(text=fmt.format(var.get()))
            cmd()
        scale = ui.Scale(row, from_=lo, to=hi, variable=var, command=changed)
        scale.pack(side="left", fill="x", expand=True, padx=6)
        scale._dbdms_label, scale._dbdms_fmt = label, fmt          # for the window (app_qt.ui_state)
        if key:
            self._reg(key, scale)
        return val


    # ------------------------------------------- detection (1.8.78: cards of the settings and the log page)
    def _detect_cards(self, f):
        """The detection's cards on the settings page (until 1.8.77 a page "Erkennung" of its own): the automatic
        mode and the game languages. The technical part is "Erweitert" on the log page (_advanced_card)."""
        auto = self._reg("st.detect", ui.LabelFrame(f, text=_("Erkennung"), padding=8))
        auto.pack(fill="x", pady=(8, 0))
        self.auto_var = ui.BooleanVar(value=self.settings["auto_detect"])
        self.hide_var = ui.BooleanVar(value=self.settings["hide_after_match"])
        self._reg("st.det_auto", ui.Checkbutton(auto, text=_("Map beim Match-Start automatisch erkennen"),
                                                 variable=self.auto_var,
                                                 command=self._detect_flags_changed)).pack(anchor="w", pady=1)
        self._reg("st.det_hide", ui.Checkbutton(auto, text=_("Overlay ausblenden, sobald ich nicht mehr in der Runde bin"),
                                                 variable=self.hide_var,
                                                 command=self._detect_flags_changed)).pack(anchor="w", pady=1)
        self._reg("st.det_hide_hint", ui.Label(
            auto, text=_("erkennt Ergebnisbildschirm, Lobby/Menüs, Ladebildschirm und geschlossenes DBD"),
            style="Dim.TLabel", wraplength=400)).pack(anchor="w", padx=(22, 0))
        self.menu_var = ui.BooleanVar(value=self.settings.get("pause_in_menus", True))
        self._reg("st.det_menu", ui.Checkbutton(auto, text=_("Overlay pausieren, solange ein DBD-Menü offen ist"),
                                                 variable=self.menu_var,
                                                 command=self._detect_flags_changed)).pack(anchor="w", pady=(4, 1))
        self._reg("st.det_menu_hint", ui.Label(
            auto, text=_("erkannt am sichtbaren Mauszeiger (ESC-Menü, Ergebnisbildschirm, Lobby)"),
            style="Dim.TLabel", wraplength=400)).pack(anchor="w", padx=(22, 0))
        lang = self._reg("st.langs", ui.LabelFrame(f, text=_("Spielsprache (Map-Namen)"), padding=8))
        lang.pack(fill="x", pady=(8, 0))
        grid = ui.Frame(lang)
        grid.pack(anchor="w")
        self.lang_vars = {}
        for i, (code, label) in enumerate(LANGS):
            v = ui.BooleanVar(value=code in self.settings["languages"])
            self.lang_vars[code] = v
            self._reg(f"det.lang.{code}", ui.Checkbutton(grid, text=label, variable=v, command=self._langs_changed)).grid(
                row=i // 5, column=i % 5, sticky="w", padx=(0, 12), pady=1)

    def _advanced_card(self, f):
        """"Erweitert" at the foot of the log page: technical options, folded away – only needed when something
        does not work (window capture, scan rate, the live state of the end-of-round watcher, debug pictures)."""
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
        ui.Checkbutton(adv, text=_("Debug-Bilder speichern"), variable=self.debug_var,
                        command=self._detect_flags_changed).pack(anchor="w")
        r = ui.Frame(adv)
        r.pack(fill="x", pady=(6, 0))
        ui.Button(r, text=_("Bildschirm jetzt scannen"), command=self.scan_now).pack(side="left")
        self._show_advanced()

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
        self.log_search_var = ui.StringVar(value="")       # 1.2.19: a text filter over the lines
        self._log_search_last = ""
        search = ui.Entry(top, textvariable=self.log_search_var, width=22)
        search.pack(side="right")
        search._dbdms_placeholder = _("Suchen …")
        # the Qt window shows the entries itself (coloured by category): (entries, dark mode)
        self.log_text = ui.Log(f, lines=self._log_lines)
        self.log_text.pack(fill="both", expand=True)
        bottom = ui.Frame(f)
        bottom.pack(fill="x", pady=(6, 0))
        ui.Button(bottom, text=_("Leeren"), command=self._clear_log).pack(side="left")
        ui.Button(bottom, text=_("Log-Datei öffnen"), command=self._open_logfile).pack(side="left", padx=6)
        ui.Button(bottom, text=_("Diagnose kopieren"), command=self.show_diagnose).pack(side="left")
        self._advanced_card(f)                       # 1.8.78: the technical options, folded (was: page Erkennung)
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
        path, shown = self._map_file(map_id, variant)
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
        prev, self.current = self.current, (map_id, shown)
        self.source = source
        if prev is not None:                     # 1.8.39: another map/layout in the same round – the round follows
            self._hist_follow(map_id, m.label(shown))
        self.overlay.set_map(path, m.label(shown), rotation, realm=self._realm_name(m), frames=frames)
        if not same_map:                         # a new map/round starts as set, the same one keeps its floor
            self._floor = None if self.settings["overlay"].get("floor_auto", True) else 0
        self._apply_floor()
        self._update_record()
        self._update_memo()
        if not was_on and not keep_timer:
            self._round_started(time.time())     # map appears -> timer from zero (a switch while on keeps it)
        self.user_visible = True
        self.hidden_after_match = False
        self.menu_paused = False
        self._watch(source)
        self.tray.set_title(f"Fog Scout – {m.label(shown)}")
        self._detail = detail or {"manual": _("manuell gewählt"), "scan": _("per Scan gefunden")}.get(source, "")
        self._set_thumb(frames[0][0])
        self._show_map_size()
        if source == "manual":
            self._log(_("Map gewählt: {map}", map=m.label(shown)), "Overlay")
        self._tick_overlay(reschedule=False)

    def _unload_test_map(self):
        """The test map (Overlay testen / moving without a map) is gone completely afterwards – as if none had
        been shown (1.65.2, user: after the test "Warte auf Map" no longer came in the game: the hidden test map
        counted as a map the user hid on purpose, and the detector still watched it as a map on screen)."""
        self._test_map = False
        self.overlay.set_map(None)
        self.overlay.hide()
        self.current = self.source = None
        self.user_visible = True
        self.hidden_after_match = self.menu_paused = False
        self.round.clear()                       # no timer, no "Letzte Runde" from the test
        self._watch_gen += 1                     # late menu/match_end events of the test are ignored
        self.worker.watch_gen = None
        self.worker.map_on_screen = False
        self._detail = ""
        self._thumb_src = None
        self._thumb_rev = getattr(self, "_thumb_rev", 0) + 1
        self.tray.set_title("Fog Scout")
        self._show_map_size()

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

    def set_overlay_on(self, on: bool):
        """1.8.18 (user: "eine Einstellung, dass man das Overlay deaktiviert, evtl. im Overview"): the master switch.
        Off hides every overlay window (map, system values, "today", music); detection, statistics and recordings
        go on, so switching it on again shows the running round at once."""
        on = bool(on)
        if bool(self.settings.get("overlay_on", True)) == on:
            return
        self.settings.set("overlay_on", on)
        if hasattr(self, "master_var"):
            self.master_var.set(on)
        self._log(_("Overlay eingeschaltet.") if on else _("Overlay ausgeschaltet – die Erkennung läuft weiter."),
                  "Overlay")
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def toggle_overlay_master(self):
        self.set_overlay_on(not self.settings.get("overlay_on", True))

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
        if key == "power":
            return (_("Blendet alles aus, was das Programm im Spiel zeigt – Karte, Systemwerte, Heute, Musik. Die "
                      "Erkennung, Statistik und Aufnahmen laufen weiter.") if self.settings.get("overlay_on", True)
                    else _("Zeigt das Overlay im Spiel wieder an."))
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
        if key == "scan":                              # 1.2.17: the hotkeys show up where the buttons are
            return tooltip.tip_for_label("Scannen") + self._hk_hint("scan_now")
        if key == "reject":
            return tooltip.tip_for_label("Falsch erkannt") + self._hk_hint("reject_map")
        return None

    def _tip_lookup(self, w):
        """Tooltips for buttons whose label changes or repeats (the rest: tooltip.TIPS by label)."""
        hk = {b: k for k, b in self.hk_buttons.items()}
        if w is self.test_btn:
            return lambda: (_("Test sofort beenden.") if self.test_btn.cget("text") == _("Test beenden") else
                            _("Zeigt 10 s lang alles, was das Overlay im Match zeigt – Karte, Systemwerte, „Heute“ "
                              "und Musik (Beispielwerte, wenn nichts anliegt) – an den eingestellten Stellen, auch "
                              "ohne DBD. Nochmal drücken beendet den Test."))
        if w is self.adv_btn:
            return _("Technische Optionen für die Fehlersuche ein- oder ausklappen.")
        if w in getattr(self, "_export_col_checks", ()):            # 1.8.91: the export dialog's columns
            return lambda: _("Spalte „{name}“ mit ausgeben.", name=w.cget("text"))
        if w is self.edit_btn:
            return lambda: (_("Verschieben beenden.") if self.edit_btn.cget("text") == _("Fertig") else
                            _("Karte direkt mit der Maus ziehen, Strg+Mausrad ändert die Grösse.")
                            + self._hk_hint("edit_position")
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
        self._log(_("Test: Overlay 10 s lang an seiner normalen Position, mit Systemwerten, „Heute“ und Musik "
                    "(Beispielwerte, wenn nichts anliegt) – nochmal drücken beendet den Test."), "Overlay")
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
        if on and not self.overlay.has_map():     # 1.64.3 (user): a test map to grab, also in the game
            first = next(iter(self._list_items.values()), None)
            if first:
                self.show_map(first[0], first[1], "manual", _("Testanzeige"))
                self._test_map = True            # loaded only for moving: hidden again by "Fertig"
        self.overlay.set_editing(on)
        if not on and getattr(self, "_test_map", False) and time.time() >= getattr(self, "_force_until", 0):
            self._unload_test_map()              # still the test map (no map chosen meanwhile): away again
        self.edit_btn.configure(text=_("Fertig") if on else _("Mit der Maus verschieben"))
        if on:                     # 1.64.1: also without a map – the preview (tab Overlay) shows everything
            self._log(_("Karte, Systemwerte und Musik mit der Maus ziehen (im Spiel oder in der Vorschau), "
                        "Strg+Mausrad = Grösse. Danach „Fertig“ oder Hotkey."), "Overlay")
        self._tick_overlay(reschedule=False)

    def _overlay_dragged(self, x, y):
        self._layout_mark()
        gx, gy, gw, gh = self._game_rect()
        w, h = (self._last_place or (0, 0, 1, 1))[2:]
        o = self.settings["overlay"]
        o["anchor"] = "custom"
        extra, shift = layout.own_block(o, self._info_size, layout.stack_gap(o, gh))     # 1.8.24: with its lines
        o["pos_x"] = min(1.0, max(0.0, (x - gx) / max(1, gw - w)))
        o["pos_y"] = min(1.0, max(0.0, (y - gy - shift) / max(1, gh - h - extra)))
        self.anchor_var.set(anchor_label("custom"))
        self._set_pos_sliders(o["pos_x"], o["pos_y"])
        self._pos_hint()
        self._save_soon()

    def _text_height(self, gh):
        """Size of the map's name and the lines below it (1.65, user: "nur die Map grösser, die Schrift gleich"):
        as at the standard map size, times its own factor – no longer tied to the map's size."""
        return max(40, int(gh * TEXT_BASE * text_scale(self.settings["overlay"])))

    def _map_height(self):
        """Overlay size: the map's own size if one was set (hotkeys / mouse wheel), else the slider's."""
        o = self.settings["overlay"]
        own = (o.get("map_heights") or {}).get(self.current[0]) if self.current else None
        return own if own else o["height"]

    def _resize(self, delta):
        """Hotkeys and mouse wheel: size of the map on display (remembered for that map)."""
        self._layout_mark()
        o = self.settings["overlay"]
        new = round(min(MAX_HEIGHT, max(0.15, self._map_height() + delta)), 3)
        mid = self._own_size_map()               # the test map changes the size of all maps (1.65.5)
        if mid:
            o.setdefault("map_heights", {})[mid] = new
        else:
            o["height"] = new
            self.size_var.set(new * 100)
            self.size_label.configure(text=f"{new * 100:.0f} %")
        self._show_map_size()
        self._sel_sync()
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _map_rotation(self, map_id=None):
        """Degrees (0/90/180/270) the map is turned clockwise – remembered per map."""
        map_id = map_id or (self.current[0] if self.current else None)
        deg = (self.settings["overlay"].get("map_rotations") or {}).get(map_id, 0) if map_id else 0
        return deg if deg in (0, 90, 180, 270) else 0

    def rotate_map(self, map_id=None):
        """Button/hotkey: turn the map on display by 90° clockwise (the name above it stays upright); 1.2.18:
        ``map_id`` from the maps page's right click – any map, shown or not."""
        map_id = map_id or (self.current[0] if self.current else None)
        if not map_id:
            self._log(_("Noch keine Map gewählt."), "Overlay")
            return
        rots = self.settings["overlay"].setdefault("map_rotations", {})
        deg = (int(rots.get(map_id, 0)) + 90) % 360
        if deg:
            rots[map_id] = deg
        else:
            rots.pop(map_id, None)
        if self.current and self.current[0] == map_id:
            self._reload_picture()
        m = self.catalog.maps.get(map_id)
        self._log(_("{map} um {deg}° gedreht.", map=m.name if m else map_id, deg=deg), "Overlay")
        self._show_map_size()
        self._save_soon()

    # ------------------------------------------------------------ map style (1.66)
    def _map_file(self, map_id, variant=1, request=True):
        """(picture path, variant shown) – in a map style the converted picture from the cache; own pictures
        (user_maps/) always as they are. 1.8.21 (user: the maps page was very slow when clicking between the
        buttons – a floor style took ~2 s per picture in the window thread): never made here; until it is there
        the original, and with ``request`` a background job makes it (``_style_ready`` loads it then)."""
        path, shown = self.catalog.image_path(map_id, variant)
        style = self.settings["overlay"].get("map_style", "classic")
        if path and style in mapstyle.STYLES and not self.catalog.is_own(map_id, variant):    # 1.8.16: + floors
            styled = mapstyle.styled_path(path, os.path.join(self.root_dir, STYLE_CACHE), False, style)
            if styled == path and request:
                self._style_request(path, style)
            path = styled
        return path, shown

    def _style_request(self, path, style):
        """1.8.21: one styled picture made in a thread (once per picture and style – one of another kind stays the
        original), then ``_style_ready`` in the window thread."""
        asked = self.__dict__.setdefault("_style_asked", set())
        if (path, style) in asked:
            return
        asked.add((path, style))
        cache = os.path.join(self.root_dir, STYLE_CACHE)

        def run():
            if mapstyle.styled_path(path, cache, True, style) != path:
                self.events.put(("call", self._style_ready, (path,)))
        threading.Thread(target=run, daemon=True, name="mapstyle-one").start()

    def _style_ready(self, path):
        """A styled picture is there now: the previews take it, the map on display is loaded again."""
        self._preview_drop()
        self._qt_preview_cache = None
        self._qt_maps_rev = getattr(self, "_qt_maps_rev", 0) + 1
        if self.current and self.catalog.image_path(*self.current)[0] == path:
            self._reload_picture()

    def _style_warm(self):
        """Dark style on: make all pictures ahead in a thread (~30 s once, then cached)."""
        style = self.settings["overlay"].get("map_style", "classic")
        if style not in mapstyle.STYLES:
            return
        paths = sorted({p for m in self.catalog.maps.values() for v in m.variants
                        if not self.catalog.is_own(m.id, v) for p in [self.catalog.image_path(m.id, v)[0]] if p})
        cache = os.path.join(self.root_dir, STYLE_CACHE)
        stop = lambda: self.settings["overlay"].get("map_style", "classic") != style   # noqa: E731

        def run():
            mapstyle.warm(paths, cache, stop, style)
            self._qt_maps_rev = getattr(self, "_qt_maps_rev", 0) + 1     # the tiles of the maps page: dark now
        threading.Thread(target=run, daemon=True, name="mapstyle").start()


    def _reload_picture(self):
        """Load the map on display again (rotation/caption changed) without touching visibility or timer."""
        if not self.current:
            return
        m = self.catalog.maps[self.current[0]]
        path, _v = self._map_file(*self.current)
        if path is None:
            return
        rotation = self._map_rotation()
        try:
            frames = load_frames(path, rotation)
        except Exception as e:
            self._log(_("Bild konnte nicht geladen werden: {path} ({error})", path=path, error=e), "Fehler")
            return
        self.overlay.set_map(path, m.label(self.current[1]), rotation, realm=self._realm_name(m), frames=frames)
        self._apply_floor()
        self._set_thumb(frames[0][0])
        self._tick_overlay(reschedule=False)


    # ============================================================= events
    def _poll(self):
        """Every 50 ms: the events of the detection, the hotkeys, the tray and the window, in order. One failing
        event is reported and the rest still runs (the loop must never stop). 1.3.4 (user: "wenn ich einen Button
        wähle, wechselt die Farbe erst nach 1 s"): after a click in the window the window is refreshed at once –
        before, the new state waited for the next _tick_overlay (up to 250 ms)."""
        clicked = False
        while not self._quitting:
            try:
                ev = self.events.get_nowait()
            except queue.Empty:
                break
            t0 = time.perf_counter()
            clicked = clicked or (isinstance(ev, tuple) and ev[0] == "ui")
            try:
                self._dispatch(ev)
            except Exception:
                self._report_once("Ereignis", traceback.format_exc())
            took = (time.perf_counter() - t0) * 1000
            if took >= 30:
                self.root.note("Ereignis " + _event_name(ev), took)
        if clicked and not self._quitting:
            try:
                self._qt_refresh()
            except Exception:
                self._report_once("Fenster", traceback.format_exc())
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
        elif isinstance(ev, tuple) and ev[0] == "obs":
            self._rec_event(ev[1], ev[2])
        elif isinstance(ev, tuple) and ev[0] == "discord":          # 1.7: status of the Rich Presence
            self._discord_status(ev[1], ev[2])
        elif isinstance(ev, tuple) and ev[0] == "spotify":          # 1.8: status / token of "Als nächstes"
            self._spotify_event(ev[1], ev[2])
        elif isinstance(ev, tuple) and ev[0] == "youtube":          # 1.10: upload status / queue / done
            self._youtube_event(ev[1], ev[2])
        elif isinstance(ev, tuple) and ev[0] == "call":       # from a window procedure (overlay, HUD)
            ev[1](*ev[2])
        elif isinstance(ev, tuple) and ev[0] == "backup":     # 1.8.80: the daily copy is done
            self._backup_done(ev[1])
        else:
            self._event(ev)

    def _hotkey(self, name):
        {"toggle_overlay": self.toggle_overlay, "next_variant": self.next_variant, "scan_now": self.scan_now,
         "next_map": lambda: self.step_map(1), "prev_map": lambda: self.step_map(-1),
         "bigger": lambda: self._resize(0.03), "smaller": lambda: self._resize(-0.03),
         "edit_position": self.toggle_edit, "rotate_map": self.rotate_map, "next_floor": self.next_floor,
         "reject_map": self.reject_detection, "mark_clip": self.mark_clip}.get(name, lambda: None)()

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
                self._hist_open(d["map_id"], d["variant"], "auto", lobby=d.get("lobby"))
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
        elif k == "match_start":                  # 1.6: end of the loading screen (recording from the spawn)
            self._match_started(d)
        elif k == "match_end":
            self._clear_unsure()                  # a whole round on that map: it was real
            self._round_ended(d.get("t") or time.time())
            if d.get("role"):
                self._log(_("Ergebnisbildschirm: gespielt als {role}.", role=self._role_name(d["role"])), "Erkennung")
                self._queue = dict(self._queue, role=d["role"])
            if self.overlay.has_map() and not self.hidden_after_match:
                was_visible = self.user_visible
                self.hidden_after_match = True
                self.menu_paused = False
                reason = _(d.get("reason") or "Ergebnisbildschirm")
                self._log(_("Runde vorbei ({reason}) – Overlay ausgeblendet.", reason=reason) if was_visible
                          else _("Runde vorbei ({reason}).", reason=reason), "Erkennung")
                self._tick_overlay(reschedule=False)
            # 1.8.38: the round is saved after the overlay is hidden – an error in the statistics (history file,
            # stats page) must not keep the map up: the worker sends no second match_end
            self._closed_round = (d.get("gen"), (self._hist or {}).get("t"))      # 1.11.8: for a later role
            try:
                self._hist_close(d.get("t") or time.time(), d.get("role"))
            except Exception:
                self._report_once("Rundenverlauf", traceback.format_exc())
        elif k == "result_role":                  # 1.11.8: the result screen's role on a second look
            self._result_role(d)
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
            self._log(_("{text} – Details in fogscout.log", text=d.get("text", "")), "Fehler")
        elif k == "scan_result":
            self._scan_result(d)
        elif k == "error":
            self._log(_("Die Erkennung ist abgestürzt – Details in fogscout.log"), "Fehler")
            log.error(d["text"])
            # 1.8.38: the status line and the tray dot say it too (the window is mostly hidden while playing)
            self._worker_status = _("Die Erkennung ist abgestürzt – bitte Fog Scout neu starten.")
            self._inform("Fog Scout", _("Die Erkennung ist abgestürzt:") + "\n\n" + d["text"][-1500:])

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

    # the tick's steps: (name for errors and the lag list, methods) – each in its own try
    TICK_STEPS = (("overlay", ("_tick_unsure", "_tick_timer", "_place_overlay")), ("layout", ("_layout_size_tick",)),
                  ("verbindung", ("_conn_tick",)), ("offizielle Daten", ("_official_tick",)), ("show", ("_show_tick",)),
                  ("hotkeys", ("_hotkeys_tick",)), ("tray", ("_tray_tick", "_rec_tick")),
                  ("discord", ("_discord_tick",)), ("youtube", ("_youtube_tick",)),
                  ("eigene Last", ("_selfload_tick",)), ("Qt", ("_qt_refresh",)))

    def _tick_overlay(self, reschedule=True):
        # 1.8.67 (user: "Statistik dauert ewig zum Laden"; the diagnosis only said "App._tick_overlay 6005 ms"): each
        # step that holds the window up gets its own line in the lag list ("Takt: Qt", "Takt: offizielle Daten" …)
        for key, names in self.TICK_STEPS:
            t0 = time.perf_counter()
            try:
                for name in names:
                    getattr(self, name)()
            except Exception:
                self._report_once(key, traceback.format_exc())
            self.root.note(f"Takt: {key}", (time.perf_counter() - t0) * 1000)
        try:
            status = _("Rundenende-Erkennung: {state}", state=self.worker.watch_status)
            if status != self.watch_var.get():
                self.watch_var.set(status)
        except Exception:
            pass
        if reschedule:
            self.root.after(250, self._tick_overlay)

    def _show_tick(self):
        if restart.show_requested(getattr(self, "_show_event", None)):
            self._show_main()

    def _report_once(self, key, text):
        """Log an unexpected error (the full text goes to the log file; the UI once per kind)."""
        log.error(text)
        if key not in self._errors_seen:
            self._errors_seen.add(key)
            last = text.strip().splitlines()[-1] if text.strip() else text
            self._log(_("{text} – Details in fogscout.log", text=f"{key}: {last}"), "Fehler")

    # ============================================================ settings

    def _preview_data(self) -> dict:
        """What the overlay tab's preview draws (1.64: every element, rendered like in the game): the screen DBD
        runs on (full screen) with the map + timer/record/server, the system values with "today" and the music
        card where the game would show them (preview.layers). Rendered again only when something changed."""
        from . import preview, sysinfo
        o = self.settings["overlay"]
        _gx, _gy, gw, gh = self._game_rect()
        pic = None
        if o.get("show_map", True):
            pic = getattr(self, "_thumb_src", None) if self.current else None
            pic = pic or self._preview_sample()
        m = self.catalog.maps.get(self.current[0]) if self.current else None
        if m is None and pic is not None:                  # the sample picture: the catalog's first map
            m = next((e for e in self.catalog.maps.values() if self._map_file(e.id, 1, request=False)[0]), None)
        name = m.label(self.current[1] if self.current else 1) if m else _("Map-Name")
        caption = name if o.get("show_caption", True) and pic is not None else ""
        info = {"timer": "3:27" if o.get("show_timer", True) else "",
                "server": _("Frankfurt") if o.get("show_server", True) and self.settings.get("show_connection") else "",
                "ping": 31.0,
                "record": _("Bilanz: Ø 2,8 Kills · 12 Runden") if o.get("show_record", True) else "",
                "memo": mapnotes.lines(mapnotes.get(self.settings.get(mapnotes.KEY), self.current[0]))
                if self.current and o.get("show_notes", True) else (),          # 1.8.54: the own note
                "name": name if pic is not None else "",             # 1.3.1: the styled card's header
                "realm": self._realm_name(m) if m and pic is not None else ""}
        side = self.settings.get("sysinfo", "off")
        sys_on, today = side in HUD_SHOWN, bool(o.get("show_today", True))
        now = time.time()
        rows = []
        if sys_on:
            snap = self.sysmon.snapshot
            rows = sysinfo.hud_rows(snap if now - snap.t < 3 else preview.sample_snapshot(), o.get("hud_rows"))
        today_rows = self._today_rows(now) if today else None
        hud_side = side if sys_on else ""
        music = preview.music_rows(self.media.now, now) if o.get("show_media", True) else None
        upnext = self._upnext(self.media.now, sample=True) if music else None      # 1.8: the Spotify queue
        accent = self._skin_accent()                     # 1.3: the modern styles use the theme's colour
        key = (gw, gh, repr(sorted((k, v) for k, v in o.items() if not isinstance(v, dict))), hud_side,
               bool(self.overlay.editing), accent,
               repr(rows), repr(today_rows), repr(self.settings.get("sysinfo_pos")), id(pic), caption, repr(info),
               self._map_height(), repr(music[0]) if music else None, id(music[1]) if music else None, repr(upnext))
        cached = getattr(self, "_preview_cache", None)
        if cached is None or cached[0] != key:
            # rendered at a smaller game height (everything scales with it) and drawn back at screen size
            f = min(1.0, preview.RENDER_H / max(1, gh))
            fits = {}                                    # 1.8.24: how much the bar holds each element back
            layers, rect = preview.layers(round(gw * f), round(gh * f), o, hud_side, rows,
                                          self.settings.get("sysinfo_pos"), pic, caption, info, self._map_height(),
                                          music, today_rows, bool(self.overlay.editing), accent, upnext, fits)
            self._preview_cache = cached = (key, layers, tuple(round(v / f) for v in rect), f, fits)
        _key, layers, (x, y, w, h), f, fits = cached
        return {"screen": (gw, gh), "bar": layout.bar_width(gw, gh), "rect": (x, y, w, h, h),
                "layers": [(name, round(lx / f), round(ly / f), round(img.width / f), round(img.height / f))
                           for name, img, lx, ly in layers],
                "pics": {name: img for name, img, _lx, _ly in layers}, "opacity": o["opacity"], "fits": dict(fits),
                "opacities": {n: float(o.get(k, o["opacity"])) for n, k in OPACITY_KEYS.items()},
                "editing": bool(self.overlay.editing), "selected": getattr(self, "_sel", "map"),
                # 1.8.14; 1.8.15 (user: "ich sehe die Balken nicht beim Bearbeiten"): while moving the lines show
                # even when the limiter is off – faint, dragging one switches it on
                "limits": layout.bar_bands(o if o.get("bar_limits_on") or not self.overlay.editing
                                           else dict(o, bar_limits_on=True), (0, 0, gw, gh), int(gh * o["margin"]),
                                           zones=False),
                "zones": layout.keep_out_boxes(o, (0, 0, gw, gh)),        # 1.8.25: Discord's overlay
                "limits_on": bool(o.get("bar_limits_on")),
                "limits_same": bool(o.get("bar_limits_same", False))}

    def _preview_sample(self):
        """A map picture for the preview while none is on display (the first one of the catalog), loaded once –
        1.8.21: the original until the map style's picture is made (``_style_ready`` drops it then). 1.11.1 (user
        diagnosis "Takt: layout 74 ms" at the start; measured 250 ms here: WebP decode + convert + thumbnail): loaded
        in a thread – the preview goes without a map picture for the few ticks until it is there."""
        pic = getattr(self, "_preview_pic", None)
        if pic is None and getattr(self, "_preview_token", None) is None:
            path = next((p for p in (self._map_file(mid, 1)[0] for mid in self.catalog.maps) if p), None)
            if path:
                token = self._preview_token = object()
                threading.Thread(target=self._preview_load, args=(path, token), daemon=True,
                                 name="preview-sample").start()
        return pic

    def _preview_load(self, path, token):
        from PIL import Image
        try:
            with Image.open(path) as im:
                im.seek(0)
                pic = im.convert("RGBA")
            pic.thumbnail((480, 480))
        except (OSError, ValueError):
            pic = None
        if self._preview_token is token:            # not dropped meanwhile (map style changed)
            self._preview_pic = pic

    def _preview_drop(self):
        """The sample picture anew (map style changed / its styled picture is there)."""
        self._preview_pic, self._preview_token = None, None

    def _preview_pick(self, value):
        if value[0] == "menu":                    # 1.8.10: right click on an element
            self._preview_menu(value[1], (value[2], value[3]))
            return
        if value[0] == "select":                  # 1.64.9: a click on an element picks it for the size slider
            self._select(value[1])
            return
        if not self.overlay.editing:              # only after "Mit der Maus verschieben" (user, 1.64.1)
            return
        if value[0] == "resize":                  # corner of the picked element / wheel over it
            self._resize_to(value[1], value[2])
            return
        if value[0] == "limit":                   # 1.8.14: a limiter line of a black bar
            self._limit_dragged(value[1], value[2], value[3])
            return
        if value[0] == "nudge":                   # arrow keys (1.65)
            self._nudge(value[1], value[2])
            return
        self._preview_pick_now(value)

    def _preview_menu(self, name, pos):
        """1.8.10: quick actions of one overlay element (right click in the preview): size back to the default,
        dark area behind it, hide ("Heute"/music) – the same switches as on the page."""
        self._select(name)
        reg = self.__dict__.get("_qt_reg", {})
        dark = reg.get({"map": "ov.map_backdrop", "text": "ov.map_backdrop", "hud": "ov.hud_backdrop",
                        "today": "ov.today_backdrop",
                        "music": "ov.media_backdrop"}.get(name, ""))
        hide = reg.get({"today": "ov.today", "music": "ov.media"}.get(name, ""))
        items = [("size", _("Grösse zurücksetzen"), True)]
        if dark is not None:
            items.append(("dark", _("Dunkle Fläche dahinter"), True, dark.instate(["selected"])))
        if hide is not None:
            items += [None, ("hide", _("Ausblenden"), hide.instate(["selected"]))]

        def act(ident):
            if ident == "size":
                if name == "map" and self._own_size_map() and self._own_size_map() in \
                        self.settings["overlay"].get("map_heights", {}):
                    self._reset_map_size()
                elif name == "map":
                    self._set_size("map", round(CONFIG_DEFAULTS["overlay"]["height"] * 100))
                else:
                    self._set_size(name, 100)
            elif ident == "dark" and dark is not None:
                dark.invoke()
            elif ident == "hide" and hide is not None and hide.instate(["selected"]):
                hide.invoke()
        self._context_menu(items, pos, act)

    def _preview_pick_now(self, value):
        """A click or drag on the preview: an element dragged by the mouse goes where it was dropped ("place",
        1.64.1 – map, system values/"today" or music card, each to its own place); a click on an empty spot puts
        the map's centre there ("move"). Always an own position, like dragging in the game."""
        self._layout_mark()
        data = self._preview_data()
        _gx, _gy, gw, gh = self._game_rect()
        if value[0] == "place":
            _what, name, x, y = value
            size = {n: (w, h) for n, _x, _y, w, h in data["layers"]}.get(name)
            if size is None:
                return
            fx = round(min(1.0, max(0.0, x / max(1, gw - size[0]))), 4)
            fy = round(min(1.0, max(0.0, y / max(1, gh - size[1]))), 4)
            if name == "map":                                        # 1.8.24: map + its lines one block
                lines = {n: (w, h) for n, _x, _y, w, h in data["layers"]}.get("text")
                extra, shift = layout.own_block(dict(self.settings["overlay"], anchor="custom"), lines,
                                                layout.stack_gap(self.settings["overlay"], gh))
                fy = round(min(1.0, max(0.0, (y - shift) / max(1, gh - size[1] - extra))), 4)
            if name in ("music", "today", "text"):
                fx, fy = layout.media_own(gw, gh, size, x, y)       # by its centre (1.2.5)
            if name == "hud":
                self._hud_own_place(fx, fy)
            elif name == "music":
                self._music_own_place(fx, fy)
            elif name == "today":
                self._today_own_place(fx, fy)
            elif name == "text":                                     # 1.8.24: the map's lines apart
                self._info_own_place(fx, fy)
            elif name == "map":
                self._map_own_place(fx, fy)
            return
        what, cx, cy = value
        if what != "move":
            return
        _x, _y, w, h, _mh = data["rect"]
        fx, fy = layout.pos_from_point(gw, gh, w, h, cx, cy)
        self._map_own_place(fx, fy)

    def _map_own_place(self, fx, fy):
        """The map's own position (0..1 of the free room), through the sliders like before."""
        self._syncing = True
        try:
            self.posx_var.set(round(fx * 100, 1))
            self.posy_var.set(round(fy * 100, 1))
            self.posx_label.configure(text=f"{fx * 100:.0f} %")
            self.posy_label.configure(text=f"{fy * 100:.0f} %")
        finally:
            self._syncing = False
        self._pos_changed()


    def _rate_changed(self):
        self.settings.set("scans_per_second", int(round(self.rate_var.get())))
        self._save_soon()


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
            self.recorder.stop_round()               # 1.4: the recording ends with the round
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
        if hasattr(self, "swatches"):
            self.swatches.dark = dark
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

    def _log_lines(self):
        """The log lines the window shows: the categories ticked, and (1.2.19) only lines with the search text."""
        needle = fold(self.log_search_var.get().strip())
        if needle != self._log_search_last:                # a new search: the window draws everything anew
            self._log_search_last = needle
            self.log_text._dbdms_rev = getattr(self.log_text, "_dbdms_rev", 0) + 1
        lines = [e for e in self._log_entries if self.cat_vars[e[1]].get()
                 and (not needle or needle in fold(e[2]))]
        return lines[-400:], bool(self.settings.get("dark_mode", True))

    def _log_filter_changed(self):
        self.settings.set("log_categories", [c for c in CATS if self.cat_vars[c].get()])
        self._save_soon()
        self.log_text._dbdms_rev = getattr(self.log_text, "_dbdms_rev", 0) + 1     # the window shows it anew

    def _clear_log(self):
        self._log_entries.clear()
        self.log_text._dbdms_rev = getattr(self.log_text, "_dbdms_rev", 0) + 1

    def _tab_changed(self):
        if self.nb.select() != str(self.tab_recordings):
            self._rec_preview_stop()                   # 1.8.8: the clip preview does not play on in the background
        if self.nb.select() == str(self.tab_stats):
            self._stats_render()
        if self.nb.select() == str(self.tab_settings):
            self._official_check_render()             # 1.8.78: "Abgleich mit der Stats-Seite" under Mehr
        if self.nb.select() == str(self.tab_recordings):
            self._rec_render()
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
        self._open(os.path.join(self.root_dir, "fogscout.log"))

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
        if getattr(self, "exit_watchdog", False):  # 1.65.1: a step below that hangs must not keep the process
            t = threading.Timer(QUIT_WATCHDOG_S, lambda: os._exit(0))
            t.daemon = True
            t.start()
        try:
            # 1.8.38: every step on its own – one that raises must not skip saving or the other stops
            wins = [w for w in (self.media_win, getattr(self, "today_win", None), getattr(self, "info_win", None))
                    if w is not None]
            steps = [self._qt_close, self.settings.save, self.tray.stop, self.conn.stop, self.sysmon.stop,
                     self.media.stop, self.recorder.quit, self.presence.quit, self.spotify.quit, self.youtube.quit,
                     self.worker.stop,
                     self.hotkeys.stop,
                     lambda: self.worker.join(timeout=4),        # let a running OCR call finish cleanly
                     # 1.8.38: OBS stops a round still running – else it records on and blocks the next start
                     lambda: self.recorder.join(timeout=QUIT_RECORDER_S)]
            if hasattr(self.overlay, "destroy"):
                steps.append(self.overlay.destroy)
            if self.hud is not None:
                steps.append(self.hud.destroy)
            steps += [w.destroy for w in wins] + [g.destroy for g in getattr(self, "_guides", ())]
            steps.append(self.toast.close)
            for step in steps:
                try:
                    step()
                except Exception:
                    log.exception("Beenden")
        finally:
            self.root.quit()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":  # pragma: no cover
    sys.exit("Start mit: python -m fogscout")
