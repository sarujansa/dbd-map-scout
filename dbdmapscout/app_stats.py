"""Tab „Statistik“ and the round history (detected map -> detected end of the match).

Mixin of App (app.py) – the methods use App's attributes; split out of app.py unchanged."""
from __future__ import annotations

import datetime
import logging
import os
import time
import webbrowser
from types import SimpleNamespace

from . import builds, dashboard, history, official, records, regions, sysinfo
from . import uimodel as ui
from .capture import foreground_root, is_game_window
from .i18n import N_, _
from .lobby import KILLERS, killer_label
from .textnorm import fold
from .textnorm import fmt_duration
from .dashboard import Tile, _bp
from .theme import DOT
from .trendchart import TrendChart

log = logging.getLogger("dbdmapscout")

STATS_ROLES = [("all", N_("Alle Rollen")), ("killer", N_("Killer")), ("survivor", N_("Survivor")),
               ("custom", N_("Custom Games")), ("farming", N_("Farming"))]
BUILD_KINDS = {"perk": N_("Perk"), "addon": N_("Add-on"), "offering": N_("Opfergabe"), "power": N_("Kraft/Item")}
# 1.8.51: the stats page's mode ids as the user's matches showed them (others keep the page's name)
MODE_LABELS = {"Online": N_("Öffentlich"), "SeasonalEvent": N_("Event-Modus")}
QUALITY_LABELS = (N_("keins"), N_("Bronze"), N_("Silber"), N_("Gold"), N_("Iri"))   # builds.QUALITIES, worst first
STATS_WAIT_GROUPS = [("weekday", N_("nach Wochentag")), ("hour", N_("nach Uhrzeit")), ("region", N_("nach Region"))]
WEEKDAYS = [N_("Montag"), N_("Dienstag"), N_("Mittwoch"), N_("Donnerstag"), N_("Freitag"), N_("Samstag"),
            N_("Sonntag")]
STATS_SYS_GROUPS = [("map", N_("nach Map")), ("hour", N_("nach Uhrzeit")), ("weekday", N_("nach Wochentag")),
                    ("killer", N_("nach Killer"))]
SYS_PEAK_ROWS = {"gpu_temp_max": (N_("GPU-Temperatur"), " °C"), "gpu_hot_max": (N_("Hotspot"), " °C"),
                 "gpu_mem_max": (N_("GPU-Speicher"), " °C"), "cpu_temp_max": (N_("CPU-Temperatur"), " °C"),
                 "gpu_power_max": (N_("GPU-Leistung"), " W"), "vram_used_max": (N_("VRAM"), " GB"),
                 "ram_used_max": (N_("RAM"), " GB"), "throttle_s": (N_("GPU gedrosselt"), ""),
                 "cpu_power_max": (N_("CPU-Leistung"), " W"), "cpu_throttle_s": (N_("CPU gedrosselt"), ""),
                 "fps_low": (N_("Niedrigstes FPS-Tief"), " FPS")}


def sys_tiles(avg) -> list:
    """Tiles of the System sub-tab from history.sys_average(): averages over the rounds, throttling."""
    n = avg["n"]
    rounds = _("über {n} Runden", n=n)
    out = []
    for key, title, unit in (("gpu_temp", N_("Ø GPU-Temperatur"), " °C"), ("cpu_temp", N_("Ø CPU-Temperatur"), " °C"),
                             ("gpu_load", N_("Ø GPU-Last"), " %"), ("gpu_power", N_("Ø GPU-Leistung"), " W"),
                             ("core_max", N_("Ø stärkster CPU-Kern"), " %"), ("cpu_power", N_("Ø CPU-Leistung"), " W"),
                             ("fps", N_("Ø FPS"), ""), ("fps_low", N_("Ø FPS-Tief"), "")):
        if key in avg:
            out.append(Tile(_(title), f"{avg[key]:.0f}{unit}", rounds,
                            frac=avg[key] / 100 if key in ("gpu_load", "core_max") else None))
    thr = avg["throttle_rounds"]
    out.append(Tile(_("GPU gedrosselt"), _("{n} von {total}", n=thr, total=n),
                    _("Runden, zusammen {time}", time=fmt_duration(avg["throttle_s"])) if thr else _("Runden"),
                    colour=DOT["warn"] if thr else None))
    if avg.get("cpu_known"):                         # only rounds with HWiNFO know whether the CPU throttled
        thr = avg["cpu_throttle_rounds"]
        out.append(Tile(_("CPU gedrosselt"), _("{n} von {total}", n=thr, total=avg["cpu_known"]),
                        _("Runden, zusammen {time}", time=fmt_duration(avg["cpu_throttle_s"])) if thr else _("Runden"),
                        colour=DOT["warn"] if thr else None))
    return out


RESULTS = {"escaped": N_("entkommen"), "dead": N_("tot"), "abandoned": N_("aufgegeben"), "gone": N_("verlassen")}




RECORD_MIN = 3        # rounds with official results on a map before the overlay shows the own record there
STATS_PERIODS = [("all", N_("Gesamter Zeitraum")), ("day", N_("Heute")), ("7d", N_("Letzte 7 Tage")),
                 ("30d", N_("Letzte 30 Tage")), ("week", N_("Diese Woche")), ("month", N_("Dieser Monat")),
                 ("year", N_("Dieses Jahr"))]
TREND_UNIT = {"day": "hour", "7d": "day", "30d": "day", "week": "day", "month": "day"}   # else: week
LAST_ROUNDS_STEP = 100                      # "Letzte Runden": rows shown, +100 per "Weitere" (1.2.16)


class StatsTab:
    # -------------------------------------------------------------- tab: statistics
    def _tab_stats(self):
        outer, f = self._scroll_tab()
        fr = ui.Frame(f)
        fr.pack(fill="x", pady=(0, 6))
        self._stats_periods = [(k, _(label)) for k, label in STATS_PERIODS]
        self.stats_period_var = ui.StringVar(value=self._stats_periods[0][1])
        cb = ui.Combobox(fr, textvariable=self.stats_period_var, values=[lbl for _k, lbl in self._stats_periods],
                          state="readonly", width=16)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: self._stats_render())
        self._stats_regions = [(None, _("Alle Regionen"))]
        self.stats_region_var = ui.StringVar(value=self._stats_regions[0][1])
        self.stats_region_cb = ui.Combobox(fr, textvariable=self.stats_region_var, state="readonly", width=20,
                                            values=[lbl for _c, lbl in self._stats_regions])
        self.stats_region_cb.pack(side="left", padx=(8, 0))
        self.stats_region_cb.bind("<<ComboboxSelected>>", lambda e: self._stats_render())
        self._stats_roles = [(k, _(label)) for k, label in STATS_ROLES]
        self.stats_role_var = ui.StringVar(value=self._stats_roles[0][1])
        cb = ui.Combobox(fr, textvariable=self.stats_role_var, values=[lbl for _k, lbl in self._stats_roles],
                          state="readonly", width=13)
        cb.pack(side="left", padx=(8, 0))
        cb.bind("<<ComboboxSelected>>", lambda e: self._stats_render())
        self._stats_killers = [(None, _("Alle Killer"))]
        self.stats_killer_var = ui.StringVar(value=self._stats_killers[0][1])
        self.stats_killer_cb = ui.Combobox(fr, textvariable=self.stats_killer_var, state="readonly", width=14,
                                            values=[lbl for _k, lbl in self._stats_killers])
        self.stats_killer_cb.pack(side="left", padx=(8, 0))
        self.stats_killer_cb.bind("<<ComboboxSelected>>", lambda e: self._stats_render())
        # 1.2.16: map filter – set by hand or by a click on the dashboard (map bar, heatmap cell)
        self._stats_maps_f = [(None, _("Alle Maps"))]
        self.stats_map_var = ui.StringVar(value=self._stats_maps_f[0][1])
        self.stats_map_cb = ui.Combobox(fr, textvariable=self.stats_map_var, state="readonly", width=18,
                                         values=[lbl for _k, lbl in self._stats_maps_f])
        self.stats_map_cb.pack(side="left", padx=(8, 0))
        self.stats_map_cb.bind("<<ComboboxSelected>>", lambda e: self._stats_render())
        # 1.8.49: game mode as the stats page names it (userscript 3) – only shown once a mode is known
        self._stats_modes = [(None, _("Alle Modi"))]
        self.stats_mode_var = ui.StringVar(value=self._stats_modes[0][1])
        self.stats_mode_cb = ui.Combobox(fr, textvariable=self.stats_mode_var, state="readonly", width=16,
                                          values=[lbl for _k, lbl in self._stats_modes])
        self.stats_mode_cb.bind("<<ComboboxSelected>>", lambda e: self._stats_mode_pick())
        self._stats_mode_want = self.settings.get("stats_mode") or None      # 1.8.51: the pick is remembered
        ui.Button(fr, text=_("Stats-Seite öffnen"),
                  command=lambda: self._official_open(False)).pack(side="right")
        self._stats_last_limit = LAST_ROUNDS_STEP
        self._stats_filter_key = None
        # one thing at a time: the dashboard and each table on a sub-tab of its own, filling the window's height
        # (1.58.1 – before, dashboard and buttons stood above the tables and left them a few rows)
        self.stats_nb = ui.Notebook(f)
        self.stats_nb.pack(fill="both", expand=True)
        self.stats_nb.bind("<<NotebookTabChanged>>", lambda e: self._stats_render_tab())
        self._stats_ctx = None                   # 1.3.5: the selection, worked out once per filter change
        self._stats_dirty = set()                # sub-tabs (index) not drawn for it yet
        box_d = self._stats_page(_("Übersicht"))
        self.stats_dash = ui.Dashboard(box_d, command=self._dash_clicked)   # 1.58: key figures, maps, killer × map
        self.stats_dash.pack(fill="x")
        self.stats_lost_var = ui.StringVar(value="")
        self.stats_lost_label = ui.Label(box_d, textvariable=self.stats_lost_var, wraplength=540)  # only when needed
        self.stats_farm_row = ui.Frame(box_d)        # 1.6.1: old farming rounds saved as custom games
        self.stats_farm_var = ui.StringVar(value="")
        ui.Label(self.stats_farm_row, textvariable=self.stats_farm_var, wraplength=540).pack(anchor="w")
        fr = ui.Frame(self.stats_farm_row)
        fr.pack(anchor="w", pady=(4, 0))
        ui.Button(fr, text=_("Als Farming markieren"), command=self._stats_farm_found).pack(side="left")
        ui.Button(fr, text=_("Ignorieren"), command=self._stats_farm_ignore).pack(side="left", padx=(6, 0))
        ui.Label(box_d, text=_("Runden vom Map-Banner bis zum Rundenende (ab 1 min), nur lokal gespeichert. Kills, "
                                "Escapes und Bloodpoints laut stats.deadbydaylight.com, sobald eine Runde dort "
                                "zugeordnet ist."),
                  style="Dim.TLabel", wraplength=540).pack(anchor="w", pady=(6, 0))
        self._stats_alias_choices = sorted(KILLERS, key=killer_label)
        box2 = self._stats_page(_("Letzte Runden"))      # 1.8.2: second tab – the most used after the overview
        self.stats_last = self._stats_tree(box2, (("when", _("Wann"), 120, "w"), ("map", _("Map"), 130, "w"),
                                                  ("dur", _("Dauer"), 60, "e"), ("wait", _("Warten"), 65, "e"),
                                                  ("role", _("Rolle/Killer"), 115, "w"), ("res", _("Ergebnis"), 75, "w"),
                                                  ("srv", _("Server"), 100, "w")), 7,
                                           select=True, multi=True)      # 1.5.4: several rows (Ctrl/Shift)
        self._table_menu(self.stats_last, self._stats_last_menu_items, self._stats_last_menu_act)   # 1.8.10
        self.stats_last.bind("<<TreeviewSelect>>", lambda e: self._stats_role_buttons())
        self.stats_more_btn = ui.Button(box2, text=_("Weitere 100 Runden anzeigen"), command=self._stats_more_rounds)
        rr = ui.Frame(box2)
        rr.pack(fill="x", pady=(6, 0))
        self._stats_last_rr = rr
        ui.Label(rr, text=_("Markierte Runde:")).pack(side="left")
        self.stats_role_btns = []
        for role, label in (("killer", N_("Killer")), ("survivor", N_("Survivor")), ("custom", N_("Custom Game"))):
            b = ui.Button(rr, text=_(label), command=lambda r=role: self._stats_set_role(r), state="disabled")
            b.pack(side="left", padx=(6, 0))
            self.stats_role_btns.append(b)
        b = ui.Button(rr, text=_("Farming an/aus"), command=self._stats_toggle_farming, state="disabled")   # 1.2.20
        b.pack(side="left", padx=(6, 0))
        self.stats_role_btns.append(b)
        self.stats_delete_btn = ui.Button(rr, text=_("Runde löschen"), command=self._stats_delete_round,
                                           state="disabled")
        self.stats_delete_btn.pack(side="left", padx=(6, 0))
        kr = ui.Frame(box2)                                 # 1.8.2: two tidy rows (the delete button stood alone)
        kr.pack(fill="x", pady=(6, 0))
        ui.Label(kr, text=_("Killer der Runde:")).pack(side="left")
        self.stats_round_killer_var = ui.StringVar(value="")
        self.stats_round_killer_cb = ui.Combobox(kr, textvariable=self.stats_round_killer_var, state="disabled",
                                                  width=16, values=[killer_label(k) for k in self._stats_alias_choices])
        self.stats_round_killer_cb.pack(side="left", padx=(6, 0))
        self.stats_round_killer_btn = ui.Button(kr, text=_("Killer setzen"), command=self._stats_set_killer,
                                                 state="disabled")
        self.stats_round_killer_btn.pack(side="left", padx=(6, 0))
        ui.Button(kr, text=_("Als CSV exportieren …"), command=self._stats_export_csv).pack(side="right")
        box = self._stats_page(_("Maps"))
        self.stats_maps = self._stats_tree(box, (("map", _("Map"), 130, "w"), ("n", _("Runden"), 62, "e"),
                                                 ("k", _("Killer"), 58, "e"), ("kills", _("Ø Kills"), 62, "e"),
                                                 ("s", _("Survivor"), 75, "e"), ("esc", _("Entkommen"), 90, "e"),
                                                 ("avg", _("Ø Dauer"), 70, "e"), ("bp", _("Ø BP"), 62, "e")), 9)
        box_k = self._stats_page(_("Killer"))
        self.stats_kill = self._stats_tree(box_k, (("killer", _("Killer"), 130, "w"), ("n", _("Runden"), 60, "e"),
                                                   ("kills", _("Ø Kills"), 60, "e"), ("four", _("4K"), 40, "e"),
                                                   ("avg", _("Ø Dauer"), 65, "e"), ("map", _("Häufigste Map"), 150, "w")),
                                           5, select=True)
        self.stats_kill.bind("<<TreeviewSelect>>", lambda e: self._stats_alias_buttons())
        ar = ui.Frame(box_k)
        ar.pack(fill="x", pady=(6, 0))
        self.stats_alias_var = ui.StringVar(value="")
        self.stats_alias_cb = ui.Combobox(ar, textvariable=self.stats_alias_var, state="disabled", width=16,
                                           values=[killer_label(k) for k in self._stats_alias_choices])
        self.stats_alias_cb.pack(side="left")
        self.stats_alias_btn = ui.Button(ar, text=_("Zuordnen"), command=self._stats_alias_set, state="disabled")
        self.stats_alias_btn.pack(side="left", padx=(6, 0))
        self.stats_alias_clear = ui.Button(ar, text=_("Zuordnungen löschen"), command=self._stats_alias_reset)
        self.stats_alias_clear.pack(side="left", padx=(6, 0))
        ui.Label(box_k, text=_("Ein Skin oder neuer Killer steht unter seinem eigenen Namen? Zeile markieren, Killer "
                                "wählen, „Zuordnen“ – gilt auch rückwirkend."),
                  style="Dim.TLabel", wraplength=520).pack(anchor="w", pady=(4, 0))
        box_b = self._stats_page(_("Bloodpoints"))   # 1.6.3: with the role filter "Farming" = the farming evaluation
        self.stats_bp_tiles = ui.Tiles(box_b)          # 1.7.1: a small dashboard above the table
        self.stats_bp_tiles.pack(fill="x", pady=(0, 6))
        self.bp_trend = TrendChart(box_b, bool(self.settings.get("dark_mode", True)), panels=("bp",))
        self.stats_bp = self._stats_tree(box_b, (("group", _("Rolle/Killer"), 140, "w"), ("n", _("Runden"), 60, "e"),
                                                 ("round", _("Ø BP"), 70, "e"), ("hour", _("BP/h"), 70, "e"),
                                                 ("hourw", _("BP/h mit Wartezeit"), 120, "e"),
                                                 ("sum", _("Summe"), 80, "e")), 8)
        ui.Label(box_b, text=_("Bloodpoints laut Stats-Seite. BP/h = je Stunde im Match; mit Wartezeit = je Stunde aus "
                                "Match und Suche zusammen. Mit dem Rollen-Filter „Farming“ steht hier, was das Farmen "
                                "bringt."), style="Dim.TLabel", wraplength=520).pack(anchor="w", pady=(4, 0))
        box_rk = self._stats_page(_("Rekorde"))    # 1.7: streaks, best week, busiest day, longest session
        self.stats_records_var = ui.StringVar(value="")
        ui.Label(box_rk, textvariable=self.stats_records_var, wraplength=400).pack(anchor="w")
        self.stats_records = ui.Tiles(box_rk)
        self.stats_records.pack(fill="x")
        ui.Label(box_rk, text=_("Serien zählen Runden mit Ergebnis laut Stats-Seite in zeitlicher Reihenfolge – „aktuell“ "
                                 "ist die Serie der neuesten Runden der Auswahl. Beste Woche ab {n} Runden mit Ergebnis. "
                                 "Eine Sitzung endet nach 45 Minuten ohne Runde.", n=records.WEEK_MIN),
                  style="Dim.TLabel", wraplength=520).pack(anchor="w", pady=(6, 0))
        box_v = self._stats_page(_("Verlauf"))
        self.trend = TrendChart(box_v, bool(self.settings.get("dark_mode", True)))
        ui.Label(box_v, text=_("Nur Runden, die einem Match auf der Stats-Seite zugeordnet sind. Die Maus über einer "
                                "Säule zeigt Wert und Anzahl der Runden."),
                  style="Dim.TLabel", wraplength=520).pack(anchor="w", pady=(4, 0))
        box_s = self._stats_page(_("System"))       # 1.60: tiles, highest values, table, trend (was a text block)
        self.stats_sys_var = ui.StringVar(value="")       # only when there are no values
        ui.Label(box_s, textvariable=self.stats_sys_var, wraplength=400).pack(anchor="w")
        self.stats_sys_tiles = ui.Tiles(box_s)
        self.stats_sys_tiles.pack(fill="x")
        self.stats_sys_peaks_box = ui.LabelFrame(box_s, text=_("Höchstwerte"), padding=8)
        self.stats_sys_peaks = ui.Treeview(self.stats_sys_peaks_box, columns=("what", "value", "when", "map"),
                                           show="headings", selectmode="none")
        for key, title, width, anchor in (("what", _("Wert"), 150, "w"), ("value", _("Höchstwert"), 90, "e"),
                                          ("when", _("Wann"), 110, "w"), ("map", _("Map"), 180, "w")):
            self.stats_sys_peaks.heading(key, text=title, anchor=anchor)
            self.stats_sys_peaks.column(key, width=width, anchor=anchor, stretch=key == "map")
        self.stats_sys_peaks.pack(fill="x")               # as tall as its rows
        grp = ui.LabelFrame(box_s, text=_("Aufgeteilt"), padding=8)
        grp.pack(fill="both", expand=True, pady=(8, 0))
        sr = ui.Frame(grp)
        sr.pack(fill="x", pady=(0, 4))
        self._stats_sys_groups = [(k, _(label)) for k, label in STATS_SYS_GROUPS]
        self.stats_sys_by_var = ui.StringVar(value=self._stats_sys_groups[0][1])
        cb = ui.Combobox(sr, textvariable=self.stats_sys_by_var, values=[lbl for _k, lbl in self._stats_sys_groups],
                          state="readonly", width=16)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: self._stats_render())
        self.stats_sys = self._stats_tree(grp, (("grp", _("Wann/Wo"), 125, "w"), ("n", _("Runden"), 52, "e"),
                                                ("gpu", _("GPU Ø °C"), 64, "e"), ("gpumax", _("GPU max"), 60, "e"),
                                                ("hot", _("Hotspot max"), 82, "e"),
                                                ("cpu", _("CPU Ø °C"), 64, "e"), ("cpumax", _("CPU max"), 60, "e"),
                                                ("load", _("GPU Ø Last"), 72, "e"), ("pwr", _("Ø Watt"), 56, "e"),
                                                ("thr", _("GPU gedr."), 70, "e"),
                                                ("core", _("Kern Ø %"), 64, "e"), ("cpupwr", _("CPU Ø W"), 60, "e"),
                                                ("cputhr", _("CPU gedr."), 70, "e"),
                                                ("fps", _("FPS Ø"), 56, "e"), ("fpslow", _("FPS Tief"), 60, "e")), 6)
        self.sys_trend = TrendChart(box_s, bool(self.settings.get("dark_mode", True)), panels=("temp",))
        ui.Label(box_s, text=_("Werte der Systemwerte-Anzeige (Tab Overlay) während der Runden – nur Runden, in denen "
                                "sie eingeschaltet war. CPU-Temperatur nur mit HWiNFO. „Wann/Wo“ zeigt, auf welchen "
                                "Maps oder zu welcher Tageszeit der PC am heißesten läuft. „Gedrosselt“: Sekunden, in "
                                "denen die GPU wegen Temperatur oder Hardware langsamer lief (nur NVIDIA)."),
                  style="Dim.TLabel", wraplength=520).pack(anchor="w", pady=(6, 0))
        box_r = self._stats_page(_("Regionen"))           # 1.8.2: short names – all ten tabs fit
        self.stats_regs = self._stats_tree(box_r, (("reg", _("Region"), 190, "w"), ("n", _("Runden"), 65, "e"),
                                                   ("avg", _("Ø Dauer"), 75, "e"), ("share", _("Anteil"), 65, "e"),
                                                   ("ping", _("Ø Ping"), 70, "e")), 5)
        ui.Label(box_r, text=_("Region nur bekannt, wenn im Tab Server „Verbundener Spielserver“ an war."),
                  style="Dim.TLabel", wraplength=520).pack(anchor="w", pady=(4, 0))
        box_w = self._stats_page(_("Wartezeit"))
        self.stats_wait_tiles = ui.Tiles(box_w)          # 1.2.16: Ø / median / shortest / longest as tiles
        self.stats_wait_tiles.pack(fill="x", pady=(0, 6))
        wr = ui.Frame(box_w)
        wr.pack(fill="x", pady=(0, 4))
        self.stats_wait_var = ui.StringVar(value="")
        ui.Label(wr, textvariable=self.stats_wait_var, wraplength=360).pack(side="left")
        self._stats_wait_groups = [(k, _(label)) for k, label in STATS_WAIT_GROUPS]
        self.stats_wait_by_var = ui.StringVar(value=self._stats_wait_groups[0][1])
        cb = ui.Combobox(wr, textvariable=self.stats_wait_by_var, values=[lbl for _k, lbl in self._stats_wait_groups],
                          state="readonly", width=16)
        cb.pack(side="right")
        cb.bind("<<ComboboxSelected>>", lambda e: self._stats_render())
        self.stats_wait = self._stats_tree(box_w, (("grp", _("Wann/Wo"), 230, "w"), ("n", _("Runden"), 70, "e"),
                                                   ("avg", _("Ø Wartezeit"), 90, "e"), ("min", _("Kürzeste"), 80, "e")),
                                           7)
        ui.Label(box_w, text=_("Gemessen von „CANCEL“ (Suche läuft) bis zur gefundenen Lobby – nur wenn das Programm "
                                "die Suche gesehen hat. Custom Games haben keine Wartezeit."),
                  style="Dim.TLabel", wraplength=520).pack(anchor="w", pady=(4, 0))
        # 1.8.46: the characters met and how the survivors' matches ended (page data that was read but unused)
        box_o = self._stats_page(_("Gegner"))
        self.stats_opp_var = ui.StringVar(value="")       # only when there is nothing to show
        ui.Label(box_o, textvariable=self.stats_opp_var, wraplength=400).pack(anchor="w")
        self.stats_opp_tiles = ui.Tiles(box_o)
        self.stats_opp_tiles.pack(fill="x", pady=(0, 6))
        self.stats_opp = self._stats_tree(box_o, (("who", _("Charakter"), 150, "w"), ("as", _("Rolle"), 75, "w"),
                                                  ("n", _("Begegnungen"), 90, "e"), ("esc", _("Entkommen"), 80, "e"),
                                                  ("sac", _("Geopfert"), 75, "e"), ("kill", _("Getötet"), 70, "e"),
                                                  ("dc", _("Aufgegeben"), 85, "e")), 8)
        ui.Label(box_o, text=_("Laut Stats-Seite: als Killer die Survivor gegen dich und wie ihr Match endete, als "
                                "Survivor der Killer und wie dein Match endete. „Getötet“ = vom Killer direkt "
                                "getötet (z. B. Mori), „Aufgegeben“ schließt verlassene Matches ein. „Ø Kills ohne "
                                "Aufgaben“ zählt nur Matches, in denen kein Survivor aufgab oder ging."),
                  style="Dim.TLabel", wraplength=520).pack(anchor="w", pady=(4, 0))
        # 1.8.48: the own loadouts from the stats page (userscript 3) and how those matches ended
        box_bu = self._stats_page(_("Builds"))
        self.stats_build_var = ui.StringVar(value="")
        ui.Label(box_bu, textvariable=self.stats_build_var, wraplength=520).pack(anchor="w")
        self.stats_items = self._stats_tree(box_bu, (("name", _("Name"), 190, "w"), ("kind", _("Art"), 85, "w"),
                                                     ("role", _("Rolle"), 70, "w"), ("n", _("Runden"), 60, "e"),
                                                     ("share", _("Anteil"), 60, "e"), ("res", _("Ergebnis"), 75, "e"),
                                                     ("without", _("ohne"), 65, "e")), 9)
        self.stats_builds = self._stats_tree(box_bu, (("build", _("Build (4 Perks)"), 360, "w"),
                                                      ("who", _("Killer"), 110, "w"), ("n", _("Runden"), 60, "e"),
                                                      ("res", _("Ergebnis"), 75, "e")), 5)
        # 1.8.51: emblems, score categories and the killer's rating (user's pick: here, no tab of their own)
        self.stats_emblems = self._stats_tree(box_bu, (("name", _("Emblem"), 150, "w"), ("role", _("Rolle"), 70, "w"),
                                                       ("n", _("Runden"), 60, "e"), ("mean", _("Ø Stufe"), 90, "e"),
                                                       ("iri", _("Iri"), 55, "e"), ("gold", _("Gold"), 55, "e"),
                                                       ("silver", _("Silber"), 60, "e"),
                                                       ("bronze", _("Bronze"), 60, "e")), 4)
        self.stats_scores = self._stats_tree(box_bu, (("name", _("Punktekategorie"), 150, "w"),
                                                      ("role", _("Rolle"), 70, "w"), ("n", _("Runden"), 60, "e"),
                                                      ("mean", _("Ø Punkte"), 85, "e"), ("full", _("voll"), 60, "e")),
                                             4)
        self.stats_rating_var = ui.StringVar(value="")
        ui.Label(box_bu, textvariable=self.stats_rating_var, wraplength=520).pack(anchor="w", pady=(4, 0))
        ui.Label(box_bu, text=_("Dein Loadout laut Stats-Seite (ab Userscript Version 3). „Ergebnis“ = als Killer "
                                 "Ø Kills, als Survivor Anteil entkommen; „ohne“ = dasselbe in deinen Runden derselben "
                                 "Rolle ohne diesen Eintrag. Builds ab {n} Runden. Embleme: Ø Stufe von keins (0) bis "
                                 "Iri (4); „voll“ = Kategorie mit {max} Punkten.", n=builds.BUILD_MIN,
                                 max=f"{builds.SCORE_MAX:,}".replace(",", ".")),
                  style="Dim.TLabel", wraplength=520).pack(anchor="w", pady=(4, 0))
        self._stats_sort = ("n", True)
        return outer

    def _stats_page(self, title):
        page = ui.Frame(self.stats_nb, padding=6)
        self.stats_nb.add(page, text=title)
        return page

    def _stats_tree(self, parent, cols, height, select=False, multi=False):
        tf = ui.Frame(parent)
        tf.pack(fill="both", expand=True)
        t = ui.Treeview(tf, columns=[c[0] for c in cols], show="headings", height=height,
                         selectmode=("extended" if multi else "browse") if select else "none")
        for key, title, width, anchor in cols:
            t.heading(key, text=title, anchor=anchor, command=lambda k=key, tr=t: self._stats_sort_by(tr, k))
            t.column(key, width=width, anchor=anchor, stretch=key in ("map", "reg"))
        t.pack(side="left", fill="both", expand=True)
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

    def _official_join(self):
        """The rounds (rounds.jsonl) with their official matches – the base of the statistics and the check.
        Rounds whose end was never detected count with the page's length once a match fits them."""
        all_rounds = history.load(self._hist_path())
        lost_rounds = history.load_lost_rounds(self._hist_path())
        farm_region = self.settings.get("farming_region") or ""
        for r in all_rounds + lost_rounds:           # skins / new killers: the user's assignment
            r.killer = self._killer_of(r.killer)
            if farm_region and r.region == farm_region:
                r.farming = True                     # 1.2.20: every round on that server region (display only)
        for r in lost_rounds:                        # lines from before 1.35 know only the label
            r.map_id = r.map_id or self._official_map_id(r.map) or ""
        matches = official.load(self._official_path())
        candidates = all_rounds + lost_rounds
        tied, other = official.link(candidates, matches, self._official_map_id)
        fixed = official.correct_maps([(candidates[i], m) for i, m in tied.items()], self._official_map_id,
                                      lambda mid: self.catalog.maps[mid].label(1) if mid in self.catalog.maps else None)
        off = {}                                     # id(round) -> its official match
        rescued = []                                 # end never detected: counts with the page's length
        public_custom = []                           # 1.6.1: saved as custom game, a public match on the page
        for i, m in tied.items():
            r = candidates[i]
            if i >= len(all_rounds):
                seconds = official.rescued_seconds(r, m)
                if seconds is None:
                    continue
                r.seconds = seconds
                rescued.append(r)
            off[id(r)] = m
            if m.role:                               # the page knows it for sure (1.8.36: also over a lobby
                r.role = m.role                      # or result screen reading – user: "Rolle nicht sauber")
            if i < len(all_rounds) and r.custom and not m.custom and not r.farming:
                public_custom.append(r)              # before 1.5.5 instant (cross-play off) lobbies looked custom
            r.custom = m.custom
            k = self._killer_of(m.character)
            if m.role == "killer" and (k in KILLERS or k.startswith("The ")):
                r.killer = k                         # exact name instead of the lobby reading (skins!) – 1.8.36:
            elif m.role == "survivor":               # also a killer not on our list yet ("Aeaiily" read from it)
                r.killer = ""
        # a second "round" inside a match that already has one: a mid-match false detection – not counted
        ghost = official.phantoms(candidates[:len(all_rounds)], tied)
        phantoms = [all_rounds[i] for i in sorted(ghost)]
        kept = [r for i, r in enumerate(all_rounds) if i not in ghost]
        return SimpleNamespace(rounds=sorted(kept + rescued, key=lambda r: r.t), off=off, tied=tied,
                               other=other, fixed=fixed, rescued=rescued, matches=matches, candidates=candidates,
                               phantoms=phantoms, public_custom=public_custom)

    def _stats_render(self):
        j = self._joined()
        all_rounds, off, rescued = j.rounds, j.off, j.rescued
        self._off_rescued = {repr(r.t) for r in rescued}   # rows in "Letzte Runden" not in rounds.jsonl
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
        role = next((k for k, lbl in self._stats_roles if lbl == self.stats_role_var.get()), "all")
        killer = next((k for k, lbl in self._stats_killers if lbl == self.stats_killer_var.get()), None)
        self._stats_killers = [(None, _("Alle Killer"))] + [(k, killer_label(k))
                                                             for k in history.killers_used(all_rounds)]
        if killer not in [k for k, _lbl in self._stats_killers]:
            killer = None
        self.stats_killer_cb.configure(values=[lbl for _k, lbl in self._stats_killers])
        self.stats_killer_var.set(dict(self._stats_killers)[killer])
        wmap = next((k for k, lbl in self._stats_maps_f if lbl == self.stats_map_var.get()), None)
        self._stats_maps_f = [(None, _("Alle Maps"))] + [(m, m) for m in sorted({r.map for r in all_rounds},
                                                                                 key=str.lower)]
        if wmap not in [k for k, _lbl in self._stats_maps_f]:
            wmap = None
        self.stats_map_cb.configure(values=[lbl for _k, lbl in self._stats_maps_f])
        self.stats_map_var.set(dict(self._stats_maps_f)[wmap])
        since = history.period_start(period, time.time())
        rounds = history.select(all_rounds, since=since, region=wanted, role=role, killer=killer, map_label=wmap)
        wmode = next((k for k, lbl in self._stats_modes if lbl == self.stats_mode_var.get()), None)
        self._stats_modes = [(None, _("Alle Modi"))] + [
            (k, _(MODE_LABELS[k]) if k in MODE_LABELS else lbl)
            for k, lbl in official.modes_seen(off[id(r)] for r in all_rounds if id(r) in off)]
        seen = [k for k, _lbl in self._stats_modes]
        if wmode is None and self._stats_mode_want in seen:     # the saved pick, once its mode is there
            wmode = self._stats_mode_want
        if wmode not in seen:
            wmode = None
        self.stats_mode_cb.configure(values=[lbl for _k, lbl in self._stats_modes])
        self.stats_mode_var.set(dict(self._stats_modes)[wmode])
        if len(self._stats_modes) > 1 and not self.stats_mode_cb.winfo_manager():
            self.stats_mode_cb.pack(side="left", padx=(8, 0), after=self.stats_map_cb)
        if wmode is not None:        # a round without the page's mode is not known to be in it
            rounds = [r for r in rounds if official.mode_key(off.get(id(r))) == wmode]
        fkey = (period, wanted, role, killer, wmap, wmode)
        if fkey != self._stats_filter_key:                 # other filters: the round list starts short again
            self._stats_filter_key, self._stats_last_limit = fkey, LAST_ROUNDS_STEP
        self._stats_rounds_shown = rounds
        ids = {id(r) for r in rounds}
        saved = {r.t for r in rescued}
        lost = [x for x in history.load_lost(self._hist_path()) if (since is None or x[0] >= since)
                and x[0] not in saved]
        notes = [_("⚠ Nicht gezählt: {n} × Rundenende nicht erkannt (die nächste Map kam, bevor das Ende "
                   "erkannt wurde). Zuletzt: {map}, {when}.", n=len(lost), map=lost[-1][1],
                   when=time.strftime("%d.%m.%y %H:%M", time.localtime(lost[-1][0])))] if lost else []
        n_saved = sum(1 for r in rescued if id(r) in ids)
        if n_saved:
            notes.append(_("✓ {n} × Rundenende nicht erkannt, aber mit der Dauer laut Stats-Seite gezählt.",
                           n=n_saved))
        ghosts = [r for r in j.phantoms if since is None or r.t >= since]
        if ghosts:
            notes.append(_("✓ {n} × Map mitten im Match falsch erkannt (laut Stats-Seite lief da schon ein Match) – "
                           "nicht gezählt. Zuletzt: {map}, {when}.", n=len(ghosts), map=ghosts[-1].map,
                           when=time.strftime("%d.%m.%y %H:%M", time.localtime(ghosts[-1].t))))
        pairs = [(r, off[id(r)]) for r in rounds if id(r) in off and (role in ("custom", "farming") or history.normal(r))]
        # 1.3.5: only the sub-tab on display is drawn now, the others when they are opened – with 5000 rounds all
        # of them together took 360 ms per filter click (system and trend alone 170 ms)
        self._stats_ctx = SimpleNamespace(rounds=rounds, pairs=pairs, off=off, period=period, notes=notes,
                                          all_rounds=all_rounds)
        self._stats_dirty = set(range(len(self.stats_nb.tabs())))
        self._stats_render_tab()

    def _stats_render_tab(self, index=None):
        """Draw a sub-tab of the statistics for the current selection, if it has not been drawn for it yet."""
        c = self._stats_ctx
        i = self.stats_nb.index("current") if index is None else index
        if c is None or i not in self._stats_dirty:
            return
        self._stats_dirty.discard(i)
        part = (self._stats_part_dash, self._stats_part_last, self._stats_part_maps, self._stats_part_killers,
                self._stats_part_bp, self._stats_part_records, self._stats_part_trend,
                self._stats_part_sys, self._stats_part_regions, self._stats_part_wait,      # tab order (1.8.2)
                self._stats_part_opponents,                                                 # 1.8.46
                self._stats_part_builds)                                                    # 1.8.48
        if i < len(part):
            part[i](c)

    def _stats_part_dash(self, c):
        rounds, pairs, notes, all_rounds = c.rounds, c.pairs, c.notes, c.all_rounds
        self.stats_lost_var.set("\n".join(notes))
        if self.stats_lost_var.get():
            self.stats_lost_label.pack(anchor="w", after=self.stats_dash, pady=(6, 0))
        else:
            self.stats_lost_label.pack_forget()
        found = self._stats_farm_candidates()
        if found:
            self.stats_farm_var.set(_("{n} Runden sind als Custom Game gespeichert, laut Stats-Seite waren es aber "
                                      "öffentliche Matches – vermutlich Farming mit Crossplay aus (vor 1.5.5 als Custom "
                                      "Game erkannt). Zuletzt: {map}, {when}.", n=len(found), map=found[-1].map,
                                      when=time.strftime("%d.%m.%y %H:%M", time.localtime(found[-1].t))))
            self.stats_farm_row.pack(anchor="w", fill="x", after=self.stats_dash, pady=(6, 0))
        else:
            self.stats_farm_row.pack_forget()
        dash = dashboard.build(rounds, pairs, lambda k: killer_label(k))
        if not all_rounds:
            dash.empty = _("Noch keine Runden gespeichert.")
        self.stats_dash.data = dash
        self.stats_dash.dark = bool(self.settings.get("dark_mode", True))

    def _stats_part_maps(self, c):
        rounds, pairs = c.rounds, c.pairs
        roles = history.roles_per_map(rounds)               # rounds = killer + survivor + custom/unknown
        res = official.results(pairs, lambda r: r.map)
        rows = []
        for name, n, avg, _longest in history.per_map(rounds):
            g = res.get(name, {})
            rows.append((name, n, *roles.get(name, (0, 0)), official.mean(g.get("kills")),
                         official.mean(g.get("escaped")), avg, official.mean(g.get("bp"))))
        col, desc = self._stats_sort
        idx = {"map": 0, "n": 1, "k": 2, "s": 3, "kills": 4, "esc": 5, "avg": 6, "bp": 7}[col]
        rows.sort(key=lambda r: r[0].lower() if idx == 0 else (-1 if r[idx] is None else r[idx]), reverse=desc)
        t = self.stats_maps
        t.delete(*t.get_children())
        for name, n, k, s_, kills, esc, avg, bp in rows:
            t.insert("", "end", values=(name, n, k, f"{kills:.2f}" if kills is not None else "–", s_,
                                        f"{esc:.0%}" if esc is not None else "–", fmt_duration(avg),
                                        _bp(bp) if bp is not None else "–"))

    def _stats_part_killers(self, c):
        rounds, pairs = c.rounds, c.pairs
        res = official.results([(r, m) for r, m in pairs if r.role == "killer"], lambda r: r.killer)
        t = self.stats_kill
        t.delete(*t.get_children())
        keep = t.selection()
        for name, n, avg, top in history.per_killer(rounds):
            ks = res.get(name, {}).get("kills") or []
            t.insert("", "end", iid=name, values=(killer_label(name), n, f"{sum(ks) / len(ks):.2f}" if ks else "–",
                                                  ks.count(4) if ks else "–", fmt_duration(avg), top))
        if keep and t.exists(keep[0]):
            t.selection_set(keep[0])
        self._stats_alias_buttons()

    def _stats_part_bp(self, c):
        """1.6.3: bloodpoints per round and per hour – all, by role, by killer (filters apply)."""
        self.stats_bp_tiles.data = dashboard.bp_tiles(c.pairs, self._role_name)
        self._bp_trend_render(c.pairs, TREND_UNIT.get(c.period, "week"))
        t = self.stats_bp
        t.delete(*t.get_children())
        for i, (group, b) in enumerate(dashboard.bp_rows(c.pairs, killer_label)):
            t.insert("", "end", iid=str(i), values=(
                group, b.rounds, dashboard._bp(b.per_round), dashboard._bp(b.per_hour) if b.per_hour else "–",
                dashboard._bp(b.per_hour_waiting) if b.per_hour_waiting else "–", dashboard._bp(b.bp)))

    def _bp_trend_render(self, pairs, unit):
        """1.7.1: Ø bloodpoints per round per hour / day / week above the bloodpoints table."""
        def label(b):
            if unit == "week":
                return _("KW {n}", n=datetime.date.fromtimestamp(b).isocalendar()[1])
            return time.strftime("%H:00" if unit == "hour" else "%d.%m.", time.localtime(b))

        per = {"hour": _("pro Stunde"), "day": _("pro Tag"), "week": _("pro Woche")}[unit]
        bars = []
        for b, bps in dashboard.bp_trend(pairs, unit):
            v = sum(bps) / len(bps) if bps else None
            bars.append((v, label(b), _("{when}: Ø {bp} BP · {n} Runden · Summe {sum}", when=label(b),
                                        bp=dashboard._bp(v), n=len(bps), sum=dashboard._bp(sum(bps))) if bps else ""))
        values = [v for v, _l, _t in bars if v is not None]
        top = max(values) if values else 0
        step = 10000 if top <= 40000 else 20000 if top <= 100000 else 50000
        hi = max(step, (int(top) // step + 1) * step) if values else 40000
        self.bp_trend.dark = bool(self.settings.get("dark_mode", True))
        self.bp_trend.draw({"bp": {
            "title": _("Ø Bloodpoints pro Runde {per}", per=per), "bars": bars, "max": hi,
            "ticks": [(v, dashboard._bp(v)) for v in range(0, hi + 1, step)],
            "last": dashboard._bp(values[-1]) if values else "",
            "empty": _("Keine Runden mit Bloodpoints in dieser Auswahl.")}})

    def _stats_part_records(self, c):
        self.stats_records_var.set("" if c.rounds else _("Noch keine Runden in dieser Auswahl."))
        self.stats_records.data = records.tiles(c.rounds, c.pairs, killer_label) if c.rounds else []

    def _stats_part_opponents(self, c):
        """1.8.46: how the survivors' matches ended (tiles) and the characters met (table)."""
        pct = lambda v: f"{v:.0%}" if v is not None else "–"
        counts = official.fates(c.pairs)
        tiles = []
        if counts:
            n_txt = _("{n} Survivor", n=sum(counts.values()))
            for title, keys in ((N_("Geopfert"), ("sacrificed",)), (N_("Getötet"), ("killed",)),
                                (N_("Aufgegeben"), ("abandoned", "gone")), (N_("Entkommen"), ("escaped",))):
                v = official.share(counts, *keys)
                tiles.append(Tile(_(title), pct(v), n_txt, frac=v))
            all_kills = [k for k in (official.kills(m) for _r, m in c.pairs) if k is not None]
            clean = official.clean_kills(c.pairs)
            tiles.append(Tile(_("Ø Kills ohne Aufgaben"), f"{sum(clean) / len(clean):.2f}" if clean else "–",
                              _("{n} von {total} Runden", n=len(clean), total=len(all_kills)),
                              frac=sum(clean) / len(clean) / 4 if clean else None))
        self.stats_opp_tiles.data = tiles
        found = official.opponents(c.pairs)
        self.stats_opp_var.set("" if found else _("Noch keine Runden mit Daten der Stats-Seite in dieser Auswahl."))
        t = self.stats_opp
        t.delete(*t.get_children())
        for o in found:
            name = killer_label(self._killer_of(o.name)) if o.role == "killer" else o.name
            t.insert("", "end", values=(name, self._role_name(o.role), o.n, pct(official.share(o.fates, "escaped")),
                                        pct(official.share(o.fates, "sacrificed")),
                                        pct(official.share(o.fates, "killed")),
                                        pct(official.share(o.fates, "abandoned", "gone"))))

    def _stats_part_builds(self, c):
        """1.8.48: perks, add-ons, offerings and powers/items of the own loadouts, and the four-perk builds."""
        def res(role, v):
            if v is None:
                return "–"
            return f"Ø {v:.2f}" if role == "killer" else f"{v:.0%}"

        n = builds.with_loadout(c.pairs)
        self.stats_build_var.set("" if n else _("Noch keine Matches mit Loadout in dieser Auswahl – die Stats-Seite "
                                                 "liefert es ab Userscript Version 3 (Einstellungen → Mehr → Offizielle "
                                                 "Match-Daten → „Userscript kopieren“)."))
        t = self.stats_items
        t.delete(*t.get_children())
        for it in builds.items(c.pairs):
            t.insert("", "end", values=(it.name, _(BUILD_KINDS[it.kind]), self._role_name(it.role), it.n,
                                        f"{it.share:.0%}", res(it.role, it.mean), res(it.role, it.mean_without)))
        t = self.stats_builds
        t.delete(*t.get_children())
        for b in builds.builds(c.pairs):
            who = killer_label(self._killer_of(b.character)) if b.character else self._role_name(b.role)
            t.insert("", "end", values=(" · ".join(b.perks), who, b.n, res(b.role, b.mean)))
        t = self.stats_emblems
        t.delete(*t.get_children())
        for e in builds.emblems(c.pairs):
            t.insert("", "end", values=(e.name, self._role_name(e.role), e.n,
                                        f"{_(QUALITY_LABELS[round(e.mean)])} ({e.mean:.1f})",
                                        *(f"{e.share(q):.0%}" for q in ("Iridescent", "Gold", "Silver", "Bronze"))))
        t = self.stats_scores
        t.delete(*t.get_children())
        for sc in builds.scores(c.pairs):
            t.insert("", "end", values=(sc.name, self._role_name(sc.role), sc.n,
                                        f"{sc.mean:,.0f}".replace(",", "."), f"{sc.full:.0%}"))
        rated = builds.ratings(c.pairs)
        self.stats_rating_var.set(_("Killer-Wertung: {list}", list=" · ".join(f"{name} {n}×" for name, n in rated))
                                  if rated else "")

    def _stats_mode_pick(self):
        """1.8.51 (user: "Merken"): the picked mode is saved and applies again after a restart."""
        key = next((k for k, lbl in self._stats_modes if lbl == self.stats_mode_var.get()), None)
        self._stats_mode_want = key
        self.settings.set("stats_mode", key or "")
        self.settings.save()
        self._stats_render()

    def _stats_part_trend(self, c):
        self._trend_render(c.pairs, TREND_UNIT.get(c.period, "week"))

    def _stats_part_sys(self, c):
        self._stats_sys_render(c.rounds, TREND_UNIT.get(c.period, "week"))

    def _stats_part_regions(self, c):
        rounds = c.rounds
        t = self.stats_regs
        t.delete(*t.get_children())
        pings = history.ping_by_region(rounds)
        for code, n, avg, share in history.per_region(rounds):
            p = pings.get(code)
            t.insert("", "end", values=(self._stats_region_name(code), n, fmt_duration(avg), f"{share:.0%}",
                                        f"{p:.0f} ms" if p is not None else "–"))

    def _stats_part_wait(self, c):
        rounds = c.rounds
        ws = history.wait_summary(rounds)
        self.stats_wait_var.set("" if ws["count"] else _("Noch keine Wartezeiten in dieser Auswahl."))
        n_txt = _("{n} Runden", n=ws["count"])
        self.stats_wait_tiles.data = [Tile(_("Ø Wartezeit"), fmt_duration(ws["avg"]), n_txt),
                                      Tile(_("Median"), fmt_duration(ws["median"]), n_txt),
                                      Tile(_("Kürzeste"), fmt_duration(ws["min"]), ""),
                                      Tile(_("Längste"), fmt_duration(ws["max"]), "")] if ws["count"] else []
        by = next((k for k, lbl in self._stats_wait_groups if lbl == self.stats_wait_by_var.get()), "weekday")
        t = self.stats_wait
        t.delete(*t.get_children())
        for key, n, avg, shortest in history.wait_by(rounds, by):
            if by == "weekday":
                label = _(WEEKDAYS[key])
            elif by == "hour":
                label = f"{key:02d}–{key + history.HOUR_BLOCK:02d} " + _("Uhr")
            else:
                label = self._stats_region_name(key)
            t.insert("", "end", values=(label, n, fmt_duration(avg), fmt_duration(shortest)))

    def _stats_part_last(self, c):
        rounds, off = c.rounds, c.off
        t = self.stats_last
        keep = t.selection()                     # the marked round stays marked (e.g. after changing its role)
        t.delete(*t.get_children())
        newest = sorted(rounds, key=lambda r: r.t, reverse=True)
        if len(newest) > self._stats_last_limit:          # 1.2.16: more on request instead of a silent cut at 100
            if not self.stats_more_btn.winfo_manager():
                self.stats_more_btn.pack(anchor="w", pady=(4, 0), before=self._stats_last_rr)
        elif self.stats_more_btn.winfo_manager():
            self.stats_more_btn.pack_forget()
        for r in newest[:self._stats_last_limit]:
            role = _("Custom Game") if r.custom else (killer_label(r.killer) if r.role == "killer" and r.killer
                                                      else self._role_name(r.role) or "–")
            if r.farming and not r.custom:
                role += " · " + _("Farming")
            t.insert("", "end", iid=repr(r.t), values=(time.strftime("%d.%m.%y %H:%M", time.localtime(r.t)), r.map,
                                                       fmt_duration(r.seconds),
                                                       fmt_duration(r.wait) if r.wait is not None else "–", role,
                                                       self._official_result(off.get(id(r))),
                                                       (_(regions.NAMES.get(r.region, r.region))
                                                        + (f" · {r.ping:.0f} ms" if r.ping is not None else ""))
                                                       if r.region else "–"))
        kept = [k for k in keep if t.exists(k)]              # 1.5.4: every marked row stays marked
        if kept:
            t.selection_set(kept)
        self._stats_role_buttons()

    def _stats_sys_render(self, rounds, unit):
        """Sub-tab System: averages, highest values (when and where) and the table by map/time/killer."""
        avg = history.sys_average(rounds)
        self.stats_sys_var.set("" if avg["n"] else _("Noch keine Systemwerte in dieser Auswahl (Tab Overlay → "
                                                     "Systemwerte einschalten)."))
        self.stats_sys_tiles.data = sys_tiles(avg) if avg["n"] else []
        peaks = history.sys_peaks(rounds)
        t = self.stats_sys_peaks
        t.delete(*t.get_children())
        for key, v, r in peaks:
            name, suffix = SYS_PEAK_ROWS[key]
            value = fmt_duration(v) if key in history.SYS_SUMS else (f"{v:.1f}" if "_used" in key else f"{v:.0f}") + suffix
            t.insert("", "end", values=(_(name), value, time.strftime("%d.%m. %H:%M", time.localtime(r.t)), r.map))
        if peaks:
            self.stats_sys_peaks_box.pack(fill="x", pady=(8, 0), after=self.stats_sys_tiles)
        else:
            self.stats_sys_peaks_box.pack_forget()
        by = next((k for k, lbl in self._stats_sys_groups if lbl == self.stats_sys_by_var.get()), "map")
        t = self.stats_sys
        t.delete(*t.get_children())

        def num(vals, key, unit=""):
            return f"{vals[key]:.0f}{unit}" if key in vals else "–"

        def secs(vals, key):
            return fmt_duration(vals[key]) if vals.get(key) else ("0" if key in vals else "–")
        for key, n, vals in history.sys_by(rounds, by):
            if by == "weekday":
                label = _(WEEKDAYS[key])
            elif by == "hour":
                label = f"{key:02d}–{key + history.HOUR_BLOCK:02d} " + _("Uhr")
            elif by == "killer":
                label = killer_label(key)
            else:
                label = key
            t.insert("", "end", values=(label, n, num(vals, "gpu_temp"), num(vals, "gpu_temp_max"),
                                        num(vals, "gpu_hot_max"), num(vals, "cpu_temp"), num(vals, "cpu_temp_max"),
                                        num(vals, "gpu_load", " %"), num(vals, "gpu_power"), secs(vals, "throttle_s"),
                                        num(vals, "core_max", " %"), num(vals, "cpu_power"),
                                        secs(vals, "cpu_throttle_s"), num(vals, "fps"), num(vals, "fps_low")))
        self._sys_trend_render(rounds, unit)

    def _sys_trend_render(self, rounds, unit):
        """Line under the System table: Ø GPU temperature per hour / day / week (dust, paste, fan over time)."""
        def label(b):
            if unit == "week":
                return _("KW {n}", n=datetime.date.fromtimestamp(b).isocalendar()[1])
            return time.strftime("%H:00" if unit == "hour" else "%d.%m.", time.localtime(b))

        per = {"hour": _("pro Stunde"), "day": _("pro Tag"), "week": _("pro Woche")}[unit]
        data = history.sys_trend(rounds, unit)
        bars = []
        for b, avgs, maxs, hots in data:
            if not avgs:
                bars.append((None, label(b), ""))
                continue
            v = sum(avgs) / len(avgs)
            tip = _("{when}: Ø {avg} °C · max {max} °C · {n} Runden", when=label(b), avg=f"{v:.0f}",
                    max=f"{max(maxs):.0f}", n=len(avgs))
            if hots:
                tip += " · " + _("Hotspot max {v} °C", v=f"{max(hots):.0f}")
            bars.append((v, label(b), tip))
        values = [v for v, _l, _t in bars if v is not None]
        lo = (int(min(values)) // 10 - 1) * 10 if values else 0      # degrees have no zero: axis around the data
        hi = (int(max(values)) // 10 + 1) * 10 if values else 100
        last = values[-1] if values else None
        self.sys_trend.dark = bool(self.settings.get("dark_mode", True))
        self.sys_trend.draw({"temp": {
            "title": _("GPU-Temperatur – Ø {per}", per=per), "bars": bars, "kind": "line", "min": lo, "max": hi,
            "ticks": [(v, f"{v} °C") for v in range(lo, hi + 1, 10)],
            "last": f"{last:.0f} °C" if last is not None else "",
            "empty": _("Noch keine GPU-Temperaturen in dieser Auswahl.")}})

    def _stats_role_buttons(self):
        sel = self.stats_last.selection()
        rescued = getattr(self, "_off_rescued", ())
        state = "normal" if sel and not any(s in rescued for s in sel) else "disabled"
        for b in self.stats_role_btns:
            b.configure(state=state)
        self.stats_round_killer_cb.configure(state="readonly" if state == "normal" else "disabled")
        self.stats_round_killer_btn.configure(state=state)
        self.stats_delete_btn.configure(state=state)

    def _stats_alias_buttons(self):
        sel = self.stats_kill.selection()
        free = bool(sel) and sel[0] not in KILLERS           # only names that are not a listed killer
        self.stats_alias_cb.configure(state="readonly" if free else "disabled")
        self.stats_alias_btn.configure(state="normal" if free else "disabled")
        self.stats_alias_clear.configure(state="normal" if self.settings.get("killer_aliases") else "disabled")

    def _stats_alias_set(self):
        """Marked name (skin, new killer) -> the killer picked in the list; applies to all rounds."""
        sel = self.stats_kill.selection()
        label = self.stats_alias_var.get()
        target = next((k for k in self._stats_alias_choices if killer_label(k) == label), None)
        if not sel or target is None:
            return
        aliases = dict(self.settings.get("killer_aliases") or {})
        aliases[fold(sel[0])] = target
        self.settings.set("killer_aliases", aliases)
        self._save_soon()
        self._log(_("„{name}“ zählt jetzt als {killer}.", name=sel[0], killer=killer_label(target)), "System")
        self.stats_alias_var.set("")
        self._stats_render()

    def _stats_alias_reset(self):
        if not self._ask(_("Zuordnungen löschen"), _("Alle eigenen Killer-Zuordnungen löschen?"),
                         self._stats_alias_reset):
            return
        self.settings.set("killer_aliases", {})
        self._save_soon()
        self._log(_("Killer-Zuordnungen gelöscht."), "System")
        self._stats_render()

    def _stats_last_menu_items(self):
        """1.8.10: right click on "Letzte Runden" – role, farming, stats page, delete for the marked rounds."""
        sel = self.stats_last.selection()
        if not sel:
            return []
        ok = self.stats_delete_btn.instate(["!disabled"])         # not for rounds rescued from the stats page
        n = len(sel)
        return [("killer", _("Als Killer-Runde"), ok), ("survivor", _("Als Survivor-Runde"), ok),
                ("custom", _("Als Custom Game"), ok), None,
                ("farming", _("Farming an/aus"), ok), None,
                ("site", _("Stats-Seite öffnen"), True), None,
                ("delete", _("Runde löschen") if n == 1 else _("{n} Runden löschen", n=n), ok)]

    def _stats_last_menu_act(self, ident):
        if ident in ("killer", "survivor", "custom"):
            self._stats_set_role(ident)
        elif ident == "farming":
            self._stats_toggle_farming()
        elif ident == "site":
            self._official_open(False)
        elif ident == "delete":
            self._stats_delete_round()

    def _stats_selected_ts(self) -> list:
        """Banner times of the rows marked in "Letzte Runden" (1.5.4: several at once)."""
        out = []
        for iid in self.stats_last.selection():
            try:
                out.append(float(iid))
            except ValueError:
                continue
        return out

    def _stats_set_role(self, role):
        """Correct the role of the rounds marked in "Letzte Runden" (detection wrong or unknown)."""
        ts = self._stats_selected_ts()
        if not ts:
            return
        done = []
        try:
            for t in ts:
                r = history.set_role(self._hist_path(), t, role)
                if r is not None:
                    done.append(r)
        except OSError as e:
            self._log(_("Rolle konnte nicht gespeichert werden: {error}", error=e), "Fehler")
            return
        name = _("Custom Game") if role == "custom" else self._role_name(role)
        if len(done) == 1:
            r = done[0]
            self._log(_("Rolle für {map} ({when}) auf {role} geändert.", map=r.map,
                        when=time.strftime("%d.%m.%y %H:%M", time.localtime(r.t)), role=name), "System")
        elif done:
            self._log(_("Rolle für {n} Runden auf {role} geändert.", n=len(done), role=name), "System")
        self._stats_render()

    def _stats_toggle_farming(self):
        """1.2.20: mark / unmark the rounds marked in "Letzte Runden" as farming rounds – all of them become
        farming unless every one already is (then all become normal). The recording follows (1.5.4)."""
        ts = self._stats_selected_ts()
        if not ts:
            return
        rounds = {r.t: r for r in history.load(self._hist_path())}
        picked = [rounds[t] for t in ts if t in rounds]
        if not picked:
            return
        on = not all(r.farming for r in picked)
        done = []
        try:
            for r0 in picked:
                r = history.set_farming(self._hist_path(), r0.t, on)
                if r is not None:
                    done.append(r)
                    self.recorder.set_farming(r0.t, on)          # the recording moves into/out of "Farming"
        except OSError as e:
            self._log(_("Rolle konnte nicht gespeichert werden: {error}", error=e), "Fehler")
            return
        if len(done) == 1:
            r = done[0]
            when = time.strftime("%d.%m.%y %H:%M", time.localtime(r.t))
            self._log(_("{map} ({when}) zählt jetzt als Farming-Runde.", map=r.map, when=when) if r.farming
                      else _("{map} ({when}) zählt wieder als normale Runde.", map=r.map, when=when), "System")
        elif done:
            self._log(_("{n} Runden zählen jetzt als Farming-Runden.", n=len(done)) if on
                      else _("{n} Runden zählen wieder als normale Runden.", n=len(done)), "System")
        farm_region = self.settings.get("farming_region") or None
        if not on and any(r.region and r.region == farm_region for r in done):
            self._log(_("Hinweis: Runden auf {region} zählen laut Einstellung weiter als Farming.",
                        region=self._stats_region_name(farm_region)), "System")
        self._stats_render()

    def _stats_farm_candidates(self):
        """1.6.1: rounds saved as custom games that the stats page lists as public matches (not ignored)."""
        ignored = set(self.settings.get("farming_ignored") or [])
        return [r for r in self._joined().public_custom if repr(r.t) not in ignored]

    def _stats_farm_found(self):
        """1.6.1: mark them all as farming rounds (that also drops "custom game"); the recordings follow."""
        found = self._stats_farm_candidates()
        if not found or not self._ask(_("Als Farming markieren"),
                                      _("{n} Runden als Farming-Runden markieren?", n=len(found)),
                                      self._stats_farm_found):
            return
        done = 0
        try:
            for r in found:
                if history.set_farming(self._hist_path(), r.t, True) is not None:
                    self.recorder.set_farming(r.t, True)
                    done += 1
        except OSError as e:
            self._log(_("Runden nicht geändert: {error}", error=e), "Fehler")
        self._log(_("{n} Runden als Farming markiert.", n=done), "System")
        self._stats_render()

    def _stats_farm_ignore(self):
        ignored = list(self.settings.get("farming_ignored") or [])
        ignored += [repr(r.t) for r in self._stats_farm_candidates()]
        self.settings.set("farming_ignored", ignored[-5000:])
        self._save_soon()
        self._stats_render()

    def _stats_delete_round(self):
        """Remove the rounds marked in "Letzte Runden" (e.g. a map read wrongly in the middle of a match)."""
        sel = self.stats_last.selection()
        if not sel:
            return
        if len(sel) == 1:
            values = self.stats_last.item(sel[0], "values")
            what = f"{values[1]} ({values[0]})" if len(values) > 1 else sel[0]
            question = _("Runde {what} aus der Statistik löschen?", what=what)
        else:
            question = _("{n} Runden aus der Statistik löschen?", n=len(sel))
        if not self._ask(_("Runde löschen"), question, self._stats_delete_round):
            return
        gone = []
        try:
            for t in self._stats_selected_ts():
                r = history.delete(self._hist_path(), t)
                if r is not None:
                    gone.append(r)
        except OSError as e:
            self._log(_("Runde konnte nicht gelöscht werden: {error}", error=e), "Fehler")
            return
        if len(gone) == 1:
            self._log(_("Runde gelöscht: {map} ({when}).", map=gone[0].map,
                        when=time.strftime("%d.%m.%y %H:%M", time.localtime(gone[0].t))), "System")
        elif gone:
            self._log(_("{n} Runden gelöscht.", n=len(gone)), "System")
        self._stats_render()

    def _stats_set_killer(self):
        """Killer of the rounds marked in "Letzte Runden" (wrongly read, or the round was counted as survivor)."""
        ts = self._stats_selected_ts()
        target = next((k for k in self._stats_alias_choices if killer_label(k) == self.stats_round_killer_var.get()),
                      None)
        if not ts or target is None:
            return
        try:
            r = None
            for t in ts:
                r = history.set_killer(self._hist_path(), t, target) or r
        except OSError as e:
            self._log(_("Killer konnte nicht gespeichert werden: {error}", error=e), "Fehler")
            return
        if r is not None:
            self._log(_("Killer für {map} ({when}) auf {killer} gesetzt.", map=r.map,
                        when=time.strftime("%d.%m.%y %H:%M", time.localtime(r.t)), killer=killer_label(target)),
                      "System")
        self.stats_round_killer_var.set("")
        self._stats_render()

    def _dash_clicked(self, value):
        """1.2.16: a click on the dashboard filters – a map bar sets the map, a heatmap cell map and killer."""
        if not value or value[0] not in ("map", "cell"):
            return
        labels = dict(self._stats_maps_f)
        if value[1] in labels:
            self.stats_map_var.set(labels[value[1]])
        if value[0] == "cell" and value[2] in [lbl for _k, lbl in self._stats_killers]:
            self.stats_killer_var.set(value[2])
        self._stats_render()

    def _stats_more_rounds(self):
        self._stats_last_limit += LAST_ROUNDS_STEP
        self._stats_render()

    def _stats_export_csv(self, path=None):
        """1.2.16: the rounds of the current filters as CSV (semicolon; the official result where tied)."""
        if path is None:
            self._qt_file("save", _("Runden exportieren"), "dbdmapscout-runden.csv", self._stats_export_csv,
                          pattern="CSV (*.csv)")
            return
        off = getattr(self._joined(), "off", {})
        rows = []
        for r in sorted(getattr(self, "_stats_rounds_shown", []), key=lambda r: r.t):
            m = off.get(id(r))
            rows.append({"start": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r.t)), "map": r.map,
                         "seconds": round(r.seconds), "wait_seconds": round(r.wait) if r.wait is not None else None,
                         "role": r.role, "custom": int(bool(r.custom)), "farming": int(bool(r.farming)),
                         "killer": r.killer, "region": r.region,
                         "ping_ms": round(r.ping) if r.ping is not None else None,
                         "kills": official.kills(m) if m else None, "escaped": official.escaped(m) if m else None,
                         "bloodpoints": m.bp if m else None})
        try:
            n = history.export_csv(path, rows)
        except OSError as e:
            self._log(_("Export fehlgeschlagen: {error}", error=e), "Fehler")
            return
        self._log(_("{n} Runden exportiert: {path}", n=n, path=path), "System")

    def _stats_clear(self):
        if not os.path.exists(self._hist_path()):
            return
        if not self._ask(_("Verlauf löschen"), _("Alle gespeicherten Runden löschen?"), self._stats_clear):
            return
        history.clear(self._hist_path())
        self._stats_render()
        self._log(_("Rundenverlauf gelöscht."), "System")

    # ---------------------------------------------------------- round history (tab Statistik)
    def _hist_open(self, map_id, variant, source):
        """A map was detected: a round starts. An open round whose end was never detected is dropped
        (its length would be wrong)."""
        m = self.catalog.maps.get(map_id)
        now = time.time()
        old = self._hist
        if old is not None and history.should_record(now - old["t"]):
            try:                                     # its end was never detected: note it, do not count it
                history.append_lost(self._hist_path(), old["t"], old["map"], "banner",
                                    ping=history.median(old.get("pings", [])),
                                    sys=self._sysrec.summary() if self._sysrec else None,
                                    **{k: v for k, v in old.items() if k in history.LOST_KEYS})
                self._log(_("Runde auf {map} nicht gezählt: ihr Ende wurde nicht erkannt.", map=old["map"]),
                          "Erkennung")
            except OSError:
                pass
        self._hist = {"t": now, "map_id": map_id, "map": m.label(variant) if m else map_id,
                      "region": "", "source": source}
        self._sysrec = sysinfo.SysRecorder()          # system values during this round
        f = self._queue.get("found")                  # the lobby this match came from (once, max. 15 min old)
        farm_on = bool(self.settings.get("farming_crossplay", True))
        if f is not None and 0 <= now - f.t <= 900:
            # 1.8.36 (user: "Farming-Runden rutschen immer noch als normale Runden in die Statistik"): cross-play
            # off makes a farming round even when the lobby looked like a custom game (READY without countdown –
            # an instant lobby); the stats page decides later: a public match is farming, a custom game stays one
            self._hist.update(wait=f.wait, role=f.role or "", custom=f.custom, killer=f.killer,
                              farming=bool(f.crossplay_off) and farm_on)
            self._queue = dict(self._queue, found=None, used=f)
            if self._hist["farming"] and f.custom:
                self._log(_("Crossplay war aus, die Lobby sah aus wie ein Custom Game – die Runde zählt als "
                            "Farming-Runde, sobald die Stats-Seite sie als öffentliches Match zeigt."), "Erkennung")
            elif self._hist["farming"]:
                self._log(_("Crossplay war aus – die Runde zählt als Farming-Runde."), "Erkennung")
            elif farm_on and f.custom:               # 1.5.5: say why a round is no farming round (user diagnosis)
                self._log(_("Als Custom Game erkannt – die Runde zählt nicht als Farming (unter „Letzte Runden“ "
                            "mit „Farming an/aus“ korrigierbar)."), "Erkennung")
        elif farm_on and (self._queue.get("crossplay_off") or f is not None):
            self._log(_("Keine Lobby zur Runde ({why}) – sie zählt nicht als Farming.",
                        why=_("Lobby zu alt") if f is not None else _("Lobby nicht gesehen")), "Erkennung")
        self.recorder.start_round(t=now, map_id=map_id, label=self._hist["map"], role=self._hist.get("role", ""),
                                  killer=self._hist.get("killer", ""),         # 1.4: OBS records the round
                                  farming=bool(self._hist.get("farming"))      # 1.4.2: goes first when room is needed
                                  and not self._hist.get("custom"))

    def _hist_follow(self, map_id, label):
        """1.8.39 (QA audit): the map on display changed while a round is open – a later banner frame read the other
        layout (Coal Tower I → II), or the user corrected it (layout button, a map picked). Before, the round and
        its recording kept the first reading; now both follow, without a new round or a new recording."""
        rec = self._hist
        if rec is None or (rec.get("map_id"), rec.get("map")) == (map_id, label):
            return
        old = rec.get("map")
        rec.update(map_id=map_id, map=label)
        self.recorder.relabel(map_id=map_id, label=label)
        self._log(_("Runde gilt jetzt für {map} (vorher {old}).", map=label, old=old), "Erkennung")

    def _hist_close(self, t, role=None):
        rec, self._hist = self._hist, None
        farm_region = self.settings.get("farming_region") or None       # 1.5.3: the region counts as farming too
        self.recorder.stop_round(role=role or (rec or {}).get("role", ""), killer=(rec or {}).get("killer", ""),
                                 farming=bool(rec and ((rec.get("farming") and not rec.get("custom"))
                                                       or (rec.get("region") and rec.get("region") == farm_region))))
        sysrec, self._sysrec = self._sysrec, None
        if rec is None:
            return
        if sysrec is not None and sysrec.summary():
            rec["sys"] = sysrec.summary()
        if role in history.ROLES:
            rec["role"] = role                        # the result screen is the surest source
        ping = history.median(rec.pop("pings", []))
        if ping is not None:
            rec["ping"] = round(ping, 1)
        seconds = max(0.0, t - rec["t"])
        if not history.should_record(seconds):
            return
        try:
            history.append(self._hist_path(), history.Round(seconds=seconds, **rec))
        except OSError as e:
            self._report_once("history", f"{e}")
            return
        self._off_open.round_recorded()              # worth opening the stats page once DBD is closed
        if self.nb.select() == str(self.tab_stats):
            self._stats_render()

    def _hist_path(self):
        return os.path.join(self.root_dir, history.FILE)

    # ---------------------------------------------------------- own record on the map on display (overlay)
    def _map_records(self):
        """{map_id: {"kills": [...], "escaped": [...]}} of the rounds with official results (no custom games);
        rebuilt only when rounds.jsonl or official.jsonl changed, so a detection never waits for it."""
        key = tuple(os.path.getmtime(p) if os.path.exists(p) else 0.0
                    for p in (self._hist_path(), self._official_path()))
        key += (repr(sorted((self.settings.get("killer_aliases") or {}).items())),)
        if getattr(self, "_record_key", None) != key:
            j = self._joined()
            pairs = [(r, j.off[id(r)]) for r in j.rounds if id(r) in j.off and history.normal(r)]
            self._record_cache, self._record_key = official.results(pairs, lambda r: r.map_id), key
        return self._record_cache

    def _record_text(self, map_id, role):
        """Line under the timer: Ø kills (killer) or share escaped (survivor) on this map – the role of the
        round if known, else the one played more often there; "" with fewer than RECORD_MIN rounds."""
        g = self._map_records().get(map_id) or {}
        ks, es = g.get("kills") or [], g.get("escaped") or []
        if role not in ("killer", "survivor"):
            role = "killer" if len(ks) >= len(es) else "survivor"
        if role == "killer" and len(ks) >= RECORD_MIN:
            return _("Ø {kills} Kills · {n} Runden", kills=f"{sum(ks) / len(ks):.1f}", n=len(ks))
        if role == "survivor" and len(es) >= RECORD_MIN:
            return _("{share} entkommen · {n} Runden", share=f"{sum(es) / len(es):.0%}", n=len(es))
        return ""

    def _update_record(self):
        """Own record for the map on display into the overlay (setting overlay.show_record)."""
        text = ""
        hist = self._hist or {}
        if self.current and self.settings["overlay"].get("show_record", True) and not hist.get("custom"):
            try:
                text = self._record_text(self.current[0], hist.get("role") or self._queue.get("role"))
            except Exception:
                log.exception("record")
        self.overlay.set_record(text)

    # ---------------------------------------------------------- official match data (stats.deadbydaylight.com)
    def _official_path(self):
        return os.path.join(self.root_dir, official.FILE)

    def _official_folder(self):
        if not getattr(self, "_off_downloads", None):
            self._off_downloads = official.downloads_dir()
        return self.settings.get("official_dir") or self._off_downloads

    def _joined(self):
        """_official_join() cached until rounds.jsonl / official.jsonl, the killer assignments or the catalog
        change (the Qt overview asks 4×/s; a full join of 5000 + 5000 lines takes ~100 ms)."""
        key = [repr(sorted((self.settings.get("killer_aliases") or {}).items())), self.settings.get("farming_region")]
        for p in (self._hist_path(), self._official_path()):
            try:
                st = os.stat(p)
                key.append((st.st_mtime_ns, st.st_size))
            except OSError:
                key.append(None)
        cached = getattr(self, "_joined_cache", None)
        if cached is None or cached[0] != key or cached[1] is not self.catalog:    # rebuilt catalog: may reuse the id
            cached = self._joined_cache = (key, self.catalog, self._official_join())
        return cached[2]

    def _official_map_id(self, name):
        idx = getattr(self, "_off_index", None)
        if idx is None or idx[0] is not self.catalog:         # the catalog is rebuilt after own assignments
            idx = self._off_index = (self.catalog, official.map_index(self.catalog.maps))
        return idx[1].get(fold(name))

    def _official_result(self, m):
        """Column "Ergebnis" in "Letzte Runden": 3K / escaped / died / – (no official match)."""
        if m is None:
            return "–"
        if m.role == "killer":
            k = official.kills(m)
            return "?" if k is None else f"{k}K"
        if m.role == "survivor":
            kind = official.classify(m.status, m.img)
            return _(RESULTS[kind]) if kind else "?"
        return "–"

    def _trend_render(self, pairs, unit):
        """Page "Verlauf": Ø kills (killer) and share escaped (survivor) per hour / day / week."""
        def label(b):
            if unit == "week":
                return _("KW {n}", n=datetime.date.fromtimestamp(b).isocalendar()[1])
            return time.strftime("%H:00" if unit == "hour" else "%d.%m.", time.localtime(b))

        def when(b):
            if unit == "week":
                return f"{label(b)} ({time.strftime('%d.%m.', time.localtime(b))}–" \
                       f"{time.strftime('%d.%m.', time.localtime(b + 6 * 86400))})"
            if unit == "hour":
                return time.strftime("%d.%m. %H:00", time.localtime(b))
            return _(WEEKDAYS[time.localtime(b).tm_wday])[:2] + time.strftime(" %d.%m.", time.localtime(b))

        per = {"hour": _("pro Stunde"), "day": _("pro Tag"), "week": _("pro Woche")}[unit]
        data = official.trend(pairs, unit)
        kb, sb = [], []
        for b, ks, es in data:
            k, e = official.mean(ks), official.mean(es)
            kb.append((k, label(b), _("{when}: Ø {kills} Kills · {n} Runden", when=when(b), kills=f"{k:.2f}",
                                      n=len(ks)) if ks else ""))
            sb.append((None if e is None else 100 * e, label(b),
                       _("{when}: {share} entkommen · {n} Runden", when=when(b), share=f"{e:.0%}", n=len(es))
                       if es else ""))
        last_k = next((v for v, _l, _t in reversed(kb) if v is not None), None)
        last_s = next((v for v, _l, _t in reversed(sb) if v is not None), None)
        self.trend.dark = bool(self.settings.get("dark_mode", True))
        self.trend.draw({
            "killer": {"title": _("Killer – Ø Kills {per}", per=per), "bars": kb, "max": 4,
                       "ticks": [(v, str(v)) for v in range(5)], "last": f"{last_k:.1f}" if last_k is not None else "",
                       "empty": _("Keine Killer-Runden mit offiziellen Daten in dieser Auswahl.")},
            "survivor": {"title": _("Survivor – entkommen {per}", per=per), "bars": sb, "max": 100,
                         "ticks": [(v, f"{v} %") for v in (0, 50, 100)],
                         "last": f"{last_s:.0f} %" if last_s is not None else "",
                         "empty": _("Keine Survivor-Runden mit offiziellen Daten in dieser Auswahl.")}})

    def _official_check_render(self):
        """Tab Erkennung, "Abgleich mit der Stats-Seite": how well the program's rounds fit the page (all data)."""
        j = self._joined()
        if not j.matches:
            self.off_check_var.set(_("Noch keine offiziellen Daten. Einrichten: Einstellungen → Mehr → Offizielle "
                                     "Match-Daten."))
            return
        lines = []
        first = min((r.t for r in j.candidates), default=None)
        seen, missed = official.detection(j.matches, {id(m) for m in j.tied.values()},
                                          None if first is None else first - official.LINK_AFTER)
        if seen or missed:
            lines.append(_("Vom Programm erkannt: {seen} von {n} ({share})", seen=len(seen),
                           n=len(seen) + len(missed), share=f"{len(seen) / (len(seen) + len(missed)):.0%}"))
        if missed:
            lines.append(_("Nicht erkannt (oder das Programm lief nicht): {list}", list=", ".join(
                f"{m.map} {time.strftime('%d.%m. %H:%M', time.localtime(m.t))}" for m in missed[::-1][:5])
                + (" …" if len(missed) > 5 else "")))
        saved = {id(r) for r in j.rescued}
        ends = [official.end_offset(r, j.off[id(r)]) for r in j.rounds if id(r) in j.off and id(r) not in saved]
        if ends:
            lines.append(_("Rundenende erkannt: Median {off} gegenüber dem Ende laut Seite ({n} Runden; + = "
                           "später)", off=f"{history.median(ends):+.0f} s", n=len(ends)))
        if j.rescued:
            lines.append(_("✓ {n} × Rundenende nicht erkannt, aber mit der Dauer laut Stats-Seite gezählt.",
                           n=len(j.rescued)))
        unknown = official.unknown_statuses(j.matches)
        if unknown:
            lines.append(_("⚠ Unbekannter Status auf der Stats-Seite: {list} – zählt nicht. Bitte melden "
                           "(„Diagnose kopieren“).", list=", ".join(f"„{k}“ ({n}×)" for k, n in unknown.items())))
        gaps = official.load_gaps(self._official_path())
        if gaps:
            a, b = gaps[-1]
            lines.append(_("⚠ Lücke: zwischen {start} und {end} fehlen vielleicht Matches – die Seite zeigt nur die "
                           "letzten 30. Seite öfter öffnen.", start=time.strftime("%d.%m. %H:%M", time.localtime(a)),
                           end=time.strftime("%d.%m. %H:%M", time.localtime(b))))
        if j.other:
            r, m = j.other[-1]
            lines.append(_("⚠ {n}× andere Map als erkannt, zuletzt {when}: erkannt {ours}, laut Seite {theirs}.",
                           n=len(j.other), when=time.strftime("%d.%m. %H:%M", time.localtime(r.t)),
                           ours=j.fixed.get(id(r), r.map), theirs=m.map))
        bundled = official.script_version(os.path.join(os.path.dirname(official.__file__), official.SCRIPT))
        if 0 < getattr(self, "_off_script", 0) < bundled:
            lines.append(_("⚠ Das Userscript ist veraltet (Version {old}, aktuell {new}) – „Userscript kopieren“ und "
                           "in Tampermonkey ersetzen.", old=self._off_script, new=bundled))
        self.off_check_var.set("\n".join(lines))

    def _official_setting(self):
        self.settings.set("official_open_after_dbd", bool(self.off_open_var.get()))
        self.settings.set("official_notify", bool(self.off_notify_var.get()))
        self._save_soon()

    def _farming_setting(self):
        """1.2.20: farming rounds – cross-play off in the lobby and/or every round on one server region."""
        self.settings.set("farming_crossplay", bool(self.farm_cross_var.get()))
        label = self.farm_region_var.get()
        self.settings.set("farming_region", next((c for c, lbl in self._farm_regions if lbl == label), ""))
        self._save_soon()
        if self.nb.select() == str(self.tab_stats):
            self._stats_render()

    def _official_open(self, after_game):
        """Open the stats page in the browser; the userscript then saves the matches (download folder)."""
        try:
            webbrowser.open(official.URL)
        except Exception as e:
            self._log(_("Stats-Seite konnte nicht geöffnet werden: {error}", error=e), "Fehler")
            return
        self._off_fast_until = time.time() + 300      # look for the file more often for a while
        if after_game:
            self._log(_("DBD beendet – Stats-Seite geöffnet; das Userscript speichert die Matches."), "System")

    def _official_structure(self):
        """1.8.46: the stats page with the request for the structure of its answer (userscript from version 2):
        field names and types only – to decide which further fields are worth taking."""
        try:
            webbrowser.open(official.URL + official.STRUCTURE_HASH)
        except Exception as e:
            self._log(_("Stats-Seite konnte nicht geöffnet werden: {error}", error=e), "Fehler")
            return
        self._inform(_("Aufbau der Match-Daten speichern"),
                     _("Die Stats-Seite öffnet sich im Browser. Das Userscript (ab Version {n}) legt danach "
                       "„{file}“ in den Download-Ordner: nur die Namen und Arten der Felder, die die Seite liefert – "
                       "keine Werte, keine Namen, keine IDs. Das Programm liest diese Datei nicht; du kannst sie "
                       "weitergeben, um zu entscheiden, welche Felder zusätzlich übernommen werden sollen. Ältere "
                       "Userscripts: vorher „Userscript kopieren“ und in Tampermonkey ersetzen.",
                       n=official.STRUCTURE_SCRIPT, file=official.STRUCTURE_FILE))

    def _official_resave(self):
        """1.8.52: the stats page with the request to save its matches once more although none is new (userscript
        from version 4) – after a new install or a lost file; before, only the browser console could do that."""
        try:
            webbrowser.open(official.URL + official.RESAVE_HASH)
        except Exception as e:
            self._log(_("Stats-Seite konnte nicht geöffnet werden: {error}", error=e), "Fehler")
            return
        self._off_fast_until = time.time() + 300      # look for the file more often for a while
        self._inform(_("Alle Matches neu speichern"),
                     _("Die Stats-Seite öffnet sich im Browser. Das Userscript (ab Version {n}) speichert ihre "
                       "letzten 30 Matches noch einmal, auch wenn keines neu ist; das Programm übernimmt sie gleich – "
                       "bekannte zählen nur einmal. Kommt keine Datei: in der Console des Browsers (F12) steht, ob "
                       "das Skript läuft. Ältere Userscripts: vorher „Userscript kopieren“ und in Tampermonkey "
                       "ersetzen.", n=official.RESAVE_SCRIPT))

    def _official_copy_script(self):
        path = os.path.join(os.path.dirname(official.__file__), official.SCRIPT)
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError as e:
            self._log(_("Userscript nicht gefunden: {error}", error=e), "Fehler")
            return
        self.root.clipboard_set(text)
        msg = _("Userscript in die Zwischenablage kopiert. In Tampermonkey: „Neues Skript erstellen“ → alles ersetzen "
                "(Strg+A, Strg+V) → Speichern. Danach stats.deadbydaylight.com öffnen und anmelden.")
        self._log(msg, "System")
        self._inform(_("Userscript kopieren"), msg)

    def _official_tick(self):
        """Every tick: open the stats page once DBD was closed (if wanted), look for the userscript's files."""
        now = time.time()
        if self._off_open.update(now, self.game is not None) and self.settings.get("official_open_after_dbd") \
                and not self.simulate:
            self._official_open(True)
        if now >= self._off_next:
            self._off_next = now + (3.0 if now < self._off_fast_until else 20.0)
            self._official_take()

    def _official_take(self):
        res = official.take_downloads(self._official_folder(), self._official_path(), time.time())
        done = res.files - len(res.undeleted)
        if res.files:
            self._off_script = res.script
        if done:
            self._log(_("Offizielle Match-Daten: {n} Matches gelesen, {new} neu – Datei gelöscht.", n=res.matches,
                        new=res.new), "System")
        for a, b in res.gaps:
            self._log(_("Offizielle Match-Daten: zwischen {start} und {end} fehlen vielleicht Matches (die Seite "
                        "zeigt nur die letzten 30).", start=time.strftime("%d.%m. %H:%M", time.localtime(a)),
                        end=time.strftime("%d.%m. %H:%M", time.localtime(b))), "System")
        told = self._off_told
        for path, err in res.undeleted:
            if path not in told:
                told.add(path)
                self._log(_("{name} gelesen, aber nicht gelöscht: {error}", name=os.path.basename(path), error=err),
                          "Fehler")
                self._official_toast(_("{name} wurde gelesen, konnte aber nicht gelöscht werden – Details im Log.",
                                       name=os.path.basename(path)))
        if done:
            fresh = self._fresh_text(res.fresh)
            self._official_toast(_("{n} Matches gelesen, davon {new} neu. Die Datei wurde gelöscht.", n=res.matches,
                                   new=res.new) + ("\n" + fresh if fresh else ""))
        for path in res.foreign:
            if path not in told:
                told.add(path)
                self._log(_("{name} ist keine Match-Datei von DbD Map Scout – bleibt liegen.",
                            name=os.path.basename(path)), "System")
        if res.files:
            for key in official.unknown_statuses(official.load(self._official_path())):
                if key not in told:
                    told.add(key)
                    self._log(_("Unbekannter Status auf der Stats-Seite: „{status}“ – zählt nicht für Kills/Escapes. "
                                "Bitte melden.", status=key), "System")
            if self.nb.select() == str(self.tab_stats):
                self._stats_render()
            if self.nb.select() == str(self.tab_detect):
                self._official_check_render()

    def _fresh_text(self, matches):
        """Results of the newly read matches for the notification (custom games left out)."""
        s = official.summary([m for m in matches if not m.custom])
        parts = []
        if s["killer"] and s["kills"] is not None:
            parts.append(_("Killer: Ø {kills} Kills, {four}× 4K ({n})", kills=f"{s['kills']:.1f}", four=s["four"],
                           n=s["killer"]))
        if s["survivor"] and s["escaped"] is not None:
            parts.append(_("Survivor: {share} entkommen ({n})", share=f"{s['escaped']:.0%}", n=s["survivor"]))
        if s["bp_matches"]:
            parts.append(_("{bp} BP", bp=_bp(s["bp"])))
        return "\n".join(parts)

    def _official_toast(self, text):
        """Small notification bottom right (like "Lobby gefunden", no sound) – not while DBD is in front."""
        if not self.settings.get("official_notify", True):
            return
        if self.game is not None and not self.simulate and is_game_window(foreground_root()):
            return
        self.toast.show(_("Offizielle Match-Daten"), text)

    def _official_diag(self):
        """Lines for "Diagnose kopieren" (not translated): how well rounds and official matches fit."""
        matches = official.load(self._official_path())
        rounds = history.load(self._hist_path())
        tied, other = official.link(rounds, matches, self._official_map_id)
        offs = sorted(rounds[i].t - m.t for i, m in tied.items())
        ends = {}
        for i, m in tied.items():
            ends.setdefault(m.role or "?", []).append(official.end_offset(rounds[i], m))
        statuses = {}
        for m in matches:
            for p in [official.Player(role=m.role, status=m.status, img=m.img)] + m.opp:
                key = f"{p.role or '?'}: {p.status or '–'} / {p.img or '–'}"
                statuses[key] = statuses.get(key, 0) + 1
        bundled = official.script_version(os.path.join(os.path.dirname(official.__file__), official.SCRIPT))
        lines = [f"Offizielle Daten: {len(matches)} Matches, {len(tied)} von {len(rounds)} Runden zugeordnet, "
                 f"andere Map {len(other)}, Lücken {len(official.load_gaps(self._official_path()))}, "
                 f"Userscript {getattr(self, '_off_script', 0)}/{bundled}, Ordner {self._official_folder()}"]
        if offs:
            lines.append(f"  Banner minus Start: Median {history.median(offs):+.0f} s, {offs[0]:+.0f} … {offs[-1]:+.0f} s")
        for role, e in sorted(ends.items()):
            e.sort()
            late = sum(1 for x in e if abs(x) > 60)
            lines.append(f"  Rundenende minus Ende laut Seite ({role}, {len(e)}): Median {history.median(e):+.0f} s, "
                         f"{e[0]:+.0f} … {e[-1]:+.0f} s, über 60 s daneben: {late}")
        lost = history.load_lost_rounds(self._hist_path())
        for r in lost:
            r.map_id = r.map_id or self._official_map_id(r.map) or ""
        if lost:
            lt, _other = official.link(lost, matches, self._official_map_id)
            lines.append(f"  Runden ohne erkanntes Ende: {len(lost)}, davon mit offiziellem Match: {len(lt)}")
        lines.extend(f"  Status {k}: {n}×" for k, n in sorted(statuses.items(), key=lambda x: -x[1])[:20])
        return lines
