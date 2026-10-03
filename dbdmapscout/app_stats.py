"""Tab „Statistik“ and the round history (detected map -> detected end of the match).

Mixin of App (app.py) – the methods use App's attributes; split out of app.py unchanged."""
from __future__ import annotations

import datetime
import logging
import os
import time
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk
from types import SimpleNamespace

from . import history, official, regions
from .capture import foreground_root, is_game_window
from .i18n import N_, _
from .lobby import KILLERS, killer_label
from .textnorm import fold
from .textnorm import fmt_duration
from .trendchart import TrendChart

log = logging.getLogger("dbdmapscout")

STATS_ROLES = [("all", N_("Alle Rollen")), ("killer", N_("Killer")), ("survivor", N_("Survivor")),
               ("custom", N_("Custom Games"))]
STATS_WAIT_GROUPS = [("weekday", N_("nach Wochentag")), ("hour", N_("nach Uhrzeit")), ("region", N_("nach Region"))]
WEEKDAYS = [N_("Montag"), N_("Dienstag"), N_("Mittwoch"), N_("Donnerstag"), N_("Freitag"), N_("Samstag"),
            N_("Sonntag")]
RESULTS = {"escaped": N_("entkommen"), "dead": N_("tot"), "abandoned": N_("aufgegeben"), "gone": N_("verlassen")}


def _bp(n) -> str:
    """Bloodpoints short: 215k, 3.45 Mio."""
    if n >= 1e6:
        return _("{n} Mio.", n=f"{n / 1e6:.2f}")
    return f"{n / 1000:.0f}k" if n >= 1000 else f"{n:.0f}"


STATS_PERIODS = [("all", N_("Gesamter Zeitraum")), ("day", N_("Heute")), ("week", N_("Diese Woche")), ("month", N_("Dieser Monat")),
                 ("year", N_("Dieses Jahr"))]


class StatsTab:
    # -------------------------------------------------------------- tab: statistics
    def _tab_stats(self):
        outer, f = self._scroll_tab()
        self.stats_today_var = tk.StringVar(value="")       # today at a glance, independent of the filters
        ttk.Label(f, textvariable=self.stats_today_var, wraplength=540).pack(anchor="w", pady=(0, 6))
        fr = ttk.Frame(f)
        fr.pack(fill="x", pady=(0, 6))
        self._stats_periods = [(k, _(label)) for k, label in STATS_PERIODS]
        self.stats_period_var = tk.StringVar(value=self._stats_periods[0][1])
        cb = ttk.Combobox(fr, textvariable=self.stats_period_var, values=[lbl for _k, lbl in self._stats_periods],
                          state="readonly", width=16)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: self._stats_render())
        self._stats_regions = [(None, _("Alle Regionen"))]
        self.stats_region_var = tk.StringVar(value=self._stats_regions[0][1])
        self.stats_region_cb = ttk.Combobox(fr, textvariable=self.stats_region_var, state="readonly", width=20,
                                            values=[lbl for _c, lbl in self._stats_regions])
        self.stats_region_cb.pack(side="left", padx=(8, 0))
        self.stats_region_cb.bind("<<ComboboxSelected>>", lambda e: self._stats_render())
        self._stats_roles = [(k, _(label)) for k, label in STATS_ROLES]
        self.stats_role_var = tk.StringVar(value=self._stats_roles[0][1])
        cb = ttk.Combobox(fr, textvariable=self.stats_role_var, values=[lbl for _k, lbl in self._stats_roles],
                          state="readonly", width=13)
        cb.pack(side="left", padx=(8, 0))
        cb.bind("<<ComboboxSelected>>", lambda e: self._stats_render())
        self._stats_killers = [(None, _("Alle Killer"))]
        self.stats_killer_var = tk.StringVar(value=self._stats_killers[0][1])
        self.stats_killer_cb = ttk.Combobox(fr, textvariable=self.stats_killer_var, state="readonly", width=14,
                                            values=[lbl for _k, lbl in self._stats_killers])
        self.stats_killer_cb.pack(side="left", padx=(8, 0))
        self.stats_killer_cb.bind("<<ComboboxSelected>>", lambda e: self._stats_render())
        self.stats_var = tk.StringVar(value="")
        self.stats_sum_label = ttk.Label(f, textvariable=self.stats_var, style="Big.TLabel", wraplength=540)
        self.stats_sum_label.pack(anchor="w")
        self.stats_res_var = tk.StringVar(value="")       # kills / escapes / bloodpoints (official data)
        self.stats_res_label = ttk.Label(f, textvariable=self.stats_res_var, wraplength=540)     # only when needed
        self.stats_lost_var = tk.StringVar(value="")
        self.stats_lost_label = ttk.Label(f, textvariable=self.stats_lost_var, wraplength=540)   # only when needed
        ttk.Label(f, text=_("Runden vom Map-Banner bis zum Rundenende (ab 1 min), nur lokal gespeichert. Kills, Escapes "
                            "und Bloodpoints laut stats.deadbydaylight.com, sobald eine Runde dort zugeordnet ist."),
                  style="Dim.TLabel", wraplength=540).pack(anchor="w", pady=(2, 6))
        row = ttk.Frame(f)                              # above the tables: they fill the rest of the tab
        row.pack(fill="x", pady=(0, 6))
        ttk.Button(row, text=_("Stats-Seite öffnen"), command=lambda: self._official_open(False)).pack(side="left")
        ttk.Button(row, text=_("Verlauf löschen"), command=self._stats_clear).pack(side="left", padx=(6, 0))
        # one table at a time: sub-tabs instead of five tables below each other
        self.stats_nb = ttk.Notebook(f)
        self.stats_nb.pack(fill="both", expand=True)
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
        ar = ttk.Frame(box_k)
        ar.pack(fill="x", pady=(6, 0))
        self._stats_alias_choices = sorted(KILLERS, key=killer_label)
        self.stats_alias_var = tk.StringVar(value="")
        self.stats_alias_cb = ttk.Combobox(ar, textvariable=self.stats_alias_var, state="disabled", width=16,
                                           values=[killer_label(k) for k in self._stats_alias_choices])
        self.stats_alias_cb.pack(side="left")
        self.stats_alias_btn = ttk.Button(ar, text=_("Zuordnen"), command=self._stats_alias_set, state="disabled")
        self.stats_alias_btn.pack(side="left", padx=(6, 0))
        self.stats_alias_clear = ttk.Button(ar, text=_("Zuordnungen löschen"), command=self._stats_alias_reset)
        self.stats_alias_clear.pack(side="left", padx=(6, 0))
        ttk.Label(box_k, text=_("Ein Skin oder neuer Killer steht unter seinem eigenen Namen? Zeile markieren, Killer "
                                "wählen, „Zuordnen“ – gilt auch rückwirkend."),
                  style="Dim.TLabel", wraplength=520).pack(anchor="w", pady=(4, 0))
        box_v = self._stats_page(_("Verlauf"))
        self.trend = TrendChart(box_v, bool(self.settings.get("dark_mode", True)),
                                ttk.Style().lookup("TFrame", "background") or "#1e1f22")
        ttk.Label(box_v, text=_("Nur Runden, die einem Match auf der Stats-Seite zugeordnet sind. Die Maus über einer "
                                "Säule zeigt Wert und Anzahl der Runden."),
                  style="Dim.TLabel", wraplength=520).pack(anchor="w", pady=(4, 0))
        box_r = self._stats_page(_("Serverregionen"))
        self.stats_regs = self._stats_tree(box_r, (("reg", _("Region"), 190, "w"), ("n", _("Runden"), 65, "e"),
                                                   ("avg", _("Ø Dauer"), 75, "e"), ("share", _("Anteil"), 65, "e"),
                                                   ("ping", _("Ø Ping"), 70, "e")), 5)
        ttk.Label(box_r, text=_("Region nur bekannt, wenn im Tab Server „Verbundener Spielserver“ an war."),
                  style="Dim.TLabel", wraplength=520).pack(anchor="w", pady=(4, 0))
        box_w = self._stats_page(_("Wartezeit in der Lobby"))
        wr = ttk.Frame(box_w)
        wr.pack(fill="x", pady=(0, 4))
        self.stats_wait_var = tk.StringVar(value="")
        ttk.Label(wr, textvariable=self.stats_wait_var, wraplength=360).pack(side="left")
        self._stats_wait_groups = [(k, _(label)) for k, label in STATS_WAIT_GROUPS]
        self.stats_wait_by_var = tk.StringVar(value=self._stats_wait_groups[0][1])
        cb = ttk.Combobox(wr, textvariable=self.stats_wait_by_var, values=[lbl for _k, lbl in self._stats_wait_groups],
                          state="readonly", width=16)
        cb.pack(side="right")
        cb.bind("<<ComboboxSelected>>", lambda e: self._stats_render())
        self.stats_wait = self._stats_tree(box_w, (("grp", _("Wann/Wo"), 230, "w"), ("n", _("Runden"), 70, "e"),
                                                   ("avg", _("Ø Wartezeit"), 90, "e"), ("min", _("Kürzeste"), 80, "e")),
                                           7)
        ttk.Label(box_w, text=_("Gemessen von „CANCEL“ (Suche läuft) bis zur gefundenen Lobby – nur wenn das Programm "
                                "die Suche gesehen hat. Custom Games haben keine Wartezeit."),
                  style="Dim.TLabel", wraplength=520).pack(anchor="w", pady=(4, 0))
        box2 = self._stats_page(_("Letzte Runden"))
        self.stats_last = self._stats_tree(box2, (("when", _("Wann"), 120, "w"), ("map", _("Map"), 130, "w"),
                                                  ("dur", _("Dauer"), 60, "e"), ("wait", _("Warten"), 65, "e"),
                                                  ("role", _("Rolle"), 115, "w"), ("res", _("Ergebnis"), 75, "w"),
                                                  ("srv", _("Server"), 100, "w")), 7,
                                           select=True)
        self.stats_last.bind("<<TreeviewSelect>>", lambda e: self._stats_role_buttons())
        rr = ttk.Frame(box2)
        rr.pack(fill="x", pady=(6, 0))
        ttk.Label(rr, text=_("Rolle der markierten Runde:")).pack(side="left")
        self.stats_role_btns = []
        for role, label in (("killer", N_("Killer")), ("survivor", N_("Survivor")), ("custom", N_("Custom Game"))):
            b = ttk.Button(rr, text=_(label), command=lambda r=role: self._stats_set_role(r), state="disabled")
            b.pack(side="left", padx=(6, 0))
            self.stats_role_btns.append(b)
        kr = ttk.Frame(box2)
        kr.pack(fill="x", pady=(6, 0))
        ttk.Label(kr, text=_("Killer der markierten Runde:")).pack(side="left")
        self.stats_round_killer_var = tk.StringVar(value="")
        self.stats_round_killer_cb = ttk.Combobox(kr, textvariable=self.stats_round_killer_var, state="disabled",
                                                  width=16, values=[killer_label(k) for k in self._stats_alias_choices])
        self.stats_round_killer_cb.pack(side="left", padx=(6, 0))
        self.stats_round_killer_btn = ttk.Button(kr, text=_("Killer setzen"), command=self._stats_set_killer,
                                                 state="disabled")
        self.stats_round_killer_btn.pack(side="left", padx=(6, 0))
        self._stats_sort = ("n", True)
        return outer

    def _stats_page(self, title):
        page = ttk.Frame(self.stats_nb, padding=6)
        self.stats_nb.add(page, text=title)
        return page

    def _stats_tree(self, parent, cols, height, select=False):
        tf = ttk.Frame(parent)
        tf.pack(fill="both", expand=True)
        t = ttk.Treeview(tf, columns=[c[0] for c in cols], show="headings", height=height,
                         selectmode="browse" if select else "none")
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

    def _today_text(self, d, s=None):
        """``s``: official.summary() of today's rounds with official data (kills, escapes, bloodpoints)."""
        if not d["count"]:
            return _("Heute: noch keine Runde.")
        parts = [_("Heute: {n} Runden ({time})", n=d["count"], time=fmt_duration(d["total"]))]
        if d["killer"] or d["survivor"]:
            parts.append(_("{k} Killer / {s} Survivor", k=d["killer"], s=d["survivor"]))
        if s and s["killer"]:
            parts.append(_("Ø {kills} Kills", kills=f"{s['kills']:.1f}"))
        if s and s["survivor"]:
            parts.append(_("{share} entkommen", share=f"{s['escaped']:.0%}"))
        if s and s["bp_matches"]:
            parts.append(_("{bp} BP", bp=_bp(s["bp"])))
        if d["wait"] is not None:
            parts.append(_("Ø Wartezeit {time}", time=fmt_duration(d["wait"])))
        if d["top_killer"]:
            parts.append(_("meist {killer}", killer=killer_label(d["top_killer"])))
        if d["ping"] is not None:
            parts.append(_("Ping {ms} ms", ms=f"{d['ping']:.0f}"))
        return " · ".join(parts)

    def _official_join(self):
        """The rounds (rounds.jsonl) with their official matches – the base of the statistics and the check.
        Rounds whose end was never detected count with the page's length once a match fits them."""
        all_rounds = history.load(self._hist_path())
        lost_rounds = history.load_lost_rounds(self._hist_path())
        for r in all_rounds + lost_rounds:           # skins / new killers: the user's assignment
            r.killer = self._killer_of(r.killer)
        for r in lost_rounds:                        # lines from before 1.35 know only the label
            r.map_id = r.map_id or self._official_map_id(r.map) or ""
        matches = official.load(self._official_path())
        candidates = all_rounds + lost_rounds
        tied, other = official.link(candidates, matches, self._official_map_id)
        fixed = official.correct_maps([(candidates[i], m) for i, m in tied.items()], self._official_map_id,
                                      lambda mid: self.catalog.maps[mid].label(1) if mid in self.catalog.maps else None)
        off = {}                                     # id(round) -> its official match
        rescued = []                                 # end never detected: counts with the page's length
        for i, m in tied.items():
            r = candidates[i]
            if i >= len(all_rounds):
                seconds = official.rescued_seconds(r, m)
                if seconds is None:
                    continue
                r.seconds = seconds
                rescued.append(r)
            off[id(r)] = m
            if m.role and not r.role:                # the page knows it for sure
                r.role = m.role
            r.custom = m.custom
            k = self._killer_of(m.character)
            if m.role == "killer" and r.role == "killer" and k in KILLERS:
                r.killer = k                         # exact name instead of the lobby reading (skins!)
        return SimpleNamespace(rounds=sorted(all_rounds + rescued, key=lambda r: r.t), off=off, tied=tied,
                               other=other, fixed=fixed, rescued=rescued, matches=matches, candidates=candidates)

    def _stats_render(self):
        j = self._official_join()
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
        day = history.period_start("day", time.time())
        today = [off[id(r)] for r in all_rounds if r.t >= day and id(r) in off and not r.custom]
        self.stats_today_var.set(self._today_text(history.today(all_rounds, time.time()), official.summary(today)))
        since = history.period_start(period, time.time())
        rounds = history.select(all_rounds, since=since, region=wanted, role=role, killer=killer)
        s = history.summary(rounds)
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
        pairs = [(r, off[id(r)]) for r in rounds if id(r) in off and (role == "custom" or not r.custom)]
        self.stats_res_var.set(self._results_text(official.summary([m for _r, m in pairs])))
        self.stats_lost_var.set("\n".join(notes))
        below = self.stats_sum_label
        for label, var in ((self.stats_res_label, self.stats_res_var), (self.stats_lost_label, self.stats_lost_var)):
            if var.get():
                label.pack(anchor="w", after=below)
                below = label
            else:
                label.pack_forget()
        if not all_rounds:
            self.stats_var.set(_("Noch keine Runden gespeichert."))
        elif not s["count"]:
            self.stats_var.set(_("Keine Runden in dieser Auswahl."))
        else:
            self.stats_var.set(_("{n} Runden · Ø {avg} · gesamt {total}", n=s["count"], avg=fmt_duration(s["avg"]),
                                 total=fmt_duration(s["total"])))
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
        self._trend_render(pairs, {"day": "hour", "week": "day", "month": "day"}.get(period, "week"))
        t = self.stats_regs
        t.delete(*t.get_children())
        pings = history.ping_by_region(rounds)
        for code, n, avg, share in history.per_region(rounds):
            p = pings.get(code)
            t.insert("", "end", values=(self._stats_region_name(code), n, fmt_duration(avg), f"{share:.0%}",
                                        f"{p:.0f} ms" if p is not None else "–"))
        ws = history.wait_summary(rounds)
        self.stats_wait_var.set(_("Ø {avg} · Median {median} · kürzeste {min} · längste {max} ({n} Runden)",
                                  avg=fmt_duration(ws["avg"]), median=fmt_duration(ws["median"]),
                                  min=fmt_duration(ws["min"]), max=fmt_duration(ws["max"]), n=ws["count"])
                                if ws["count"] else _("Noch keine Wartezeiten in dieser Auswahl."))
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
        t = self.stats_last
        keep = t.selection()                     # the marked round stays marked (e.g. after changing its role)
        t.delete(*t.get_children())
        for r in sorted(rounds, key=lambda r: r.t, reverse=True)[:100]:
            role = _("Custom Game") if r.custom else (killer_label(r.killer) if r.role == "killer" and r.killer
                                                      else self._role_name(r.role) or "–")
            t.insert("", "end", iid=repr(r.t), values=(time.strftime("%d.%m.%y %H:%M", time.localtime(r.t)), r.map,
                                                       fmt_duration(r.seconds),
                                                       fmt_duration(r.wait) if r.wait is not None else "–", role,
                                                       self._official_result(off.get(id(r))),
                                                       (_(regions.NAMES.get(r.region, r.region))
                                                        + (f" · {r.ping:.0f} ms" if r.ping is not None else ""))
                                                       if r.region else "–"))
        if keep and t.exists(keep[0]):
            t.selection_set(keep[0])
        self._stats_role_buttons()

    def _stats_role_buttons(self):
        sel = self.stats_last.selection()
        state = "normal" if sel and sel[0] not in getattr(self, "_off_rescued", ()) else "disabled"
        for b in self.stats_role_btns:
            b.configure(state=state)
        self.stats_round_killer_cb.configure(state="readonly" if state == "normal" else "disabled")
        self.stats_round_killer_btn.configure(state=state)

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
        if not messagebox.askokcancel(_("Zuordnungen löschen"), _("Alle eigenen Killer-Zuordnungen löschen?"),
                                      parent=self.root):
            return
        self.settings.set("killer_aliases", {})
        self._save_soon()
        self._log(_("Killer-Zuordnungen gelöscht."), "System")
        self._stats_render()

    def _stats_set_role(self, role):
        """Correct the role of the round marked in "Letzte Runden" (detection wrong or unknown)."""
        sel = self.stats_last.selection()
        if not sel:
            return
        try:
            r = history.set_role(self._hist_path(), float(sel[0]), role)
        except OSError as e:
            self._log(_("Rolle konnte nicht gespeichert werden: {error}", error=e), "Fehler")
            return
        if r is not None:
            self._log(_("Rolle für {map} ({when}) auf {role} geändert.", map=r.map,
                        when=time.strftime("%d.%m.%y %H:%M", time.localtime(r.t)),
                        role=_("Custom Game") if role == "custom" else self._role_name(role)), "System")
        self._stats_render()

    def _stats_set_killer(self):
        """Killer of the round marked in "Letzte Runden" (wrongly read, or the round was counted as survivor)."""
        sel = self.stats_last.selection()
        target = next((k for k in self._stats_alias_choices if killer_label(k) == self.stats_round_killer_var.get()),
                      None)
        if not sel or target is None:
            return
        try:
            r = history.set_killer(self._hist_path(), float(sel[0]), target)
        except OSError as e:
            self._log(_("Killer konnte nicht gespeichert werden: {error}", error=e), "Fehler")
            return
        if r is not None:
            self._log(_("Killer für {map} ({when}) auf {killer} gesetzt.", map=r.map,
                        when=time.strftime("%d.%m.%y %H:%M", time.localtime(r.t)), killer=killer_label(target)),
                      "System")
        self.stats_round_killer_var.set("")
        self._stats_render()

    def _stats_clear(self):
        if not os.path.exists(self._hist_path()):
            return
        if not messagebox.askokcancel(_("Verlauf löschen"), _("Alle gespeicherten Runden löschen?"), parent=self.root):
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
                                    **{k: v for k, v in old.items() if k in history.LOST_KEYS})
                self._log(_("Runde auf {map} nicht gezählt: ihr Ende wurde nicht erkannt.", map=old["map"]),
                          "Erkennung")
            except OSError:
                pass
        self._hist = {"t": now, "map_id": map_id, "map": m.label(variant) if m else map_id,
                      "region": "", "source": source}
        f = self._queue.get("found")                  # the lobby this match came from (once, max. 15 min old)
        if f is not None and 0 <= now - f.t <= 900:
            self._hist.update(wait=f.wait, role=f.role or "", custom=f.custom, killer=f.killer)
            self._queue = dict(self._queue, found=None, used=f)

    def _hist_close(self, t, role=None):
        rec, self._hist = self._hist, None
        if rec is None:
            return
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

    # ---------------------------------------------------------- official match data (stats.deadbydaylight.com)
    def _official_path(self):
        return os.path.join(self.root_dir, official.FILE)

    def _official_folder(self):
        if not getattr(self, "_off_downloads", None):
            self._off_downloads = official.downloads_dir()
        return self.settings.get("official_dir") or self._off_downloads

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
        self.trend.canvas.configure(background=ttk.Style().lookup("TFrame", "background") or "#1e1f22")
        self.trend.draw({
            "killer": {"title": _("Killer – Ø Kills {per}", per=per), "bars": kb, "max": 4,
                       "ticks": [(v, str(v)) for v in range(5)], "last": f"{last_k:.1f}" if last_k is not None else "",
                       "empty": _("Keine Killer-Runden mit offiziellen Daten in dieser Auswahl.")},
            "survivor": {"title": _("Survivor – entkommen {per}", per=per), "bars": sb, "max": 100,
                         "ticks": [(v, f"{v} %") for v in (0, 50, 100)],
                         "last": f"{last_s:.0f} %" if last_s is not None else "",
                         "empty": _("Keine Survivor-Runden mit offiziellen Daten in dieser Auswahl.")}})

    def _results_text(self, s):
        """Line below the number of rounds: kills, escapes, bloodpoints of the rounds with official data."""
        parts = []
        if s["killer"]:
            text = _("Killer: Ø {kills} Kills, {four}× 4K ({n} Runden)", kills=f"{s['kills']:.2f}", four=s["four"],
                     n=s["killer"])
            if s["abandons"]:
                text += " · " + _("{n}× Abandon", n=s["abandons"])
            parts.append(text)
        if s["survivor"]:
            parts.append(_("Survivor: {share} entkommen ({n} Runden)", share=f"{s['escaped']:.0%}", n=s["survivor"]))
        if s["bp_matches"]:
            parts.append(_("Bloodpoints: {total} (Ø {avg})", total=_bp(s["bp"]), avg=_bp(s["bp"] / s["bp_matches"])))
        return "\n".join(parts)

    def _official_check_render(self):
        """Tab Erkennung, "Abgleich mit der Stats-Seite": how well the program's rounds fit the page (all data)."""
        j = self._official_join()
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

    def _official_copy_script(self):
        path = os.path.join(os.path.dirname(official.__file__), official.SCRIPT)
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError as e:
            self._log(_("Userscript nicht gefunden: {error}", error=e), "Fehler")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        msg = _("Userscript in die Zwischenablage kopiert. In Tampermonkey: „Neues Skript erstellen“ → alles ersetzen "
                "(Strg+A, Strg+V) → Speichern. Danach stats.deadbydaylight.com öffnen und anmelden.")
        self._log(msg, "System")
        messagebox.showinfo(_("Userscript kopieren"), msg, parent=self.root)

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
            self._official_toast(_("{n} Matches gelesen, davon {new} neu. Die Datei wurde gelöscht.", n=res.matches,
                                   new=res.new))
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
