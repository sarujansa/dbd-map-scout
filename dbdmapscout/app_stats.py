"""Tab „Statistik“ and the round history (detected map -> detected end of the match).

Mixin of App (app.py) – the methods use App's attributes; split out of app.py unchanged."""
from __future__ import annotations

import logging
import os
import time
import tkinter as tk
from tkinter import messagebox, ttk

from . import history, regions
from .i18n import N_, _
from .lobby import killer_label
from .textnorm import fmt_duration

log = logging.getLogger("dbdmapscout")

STATS_ROLES = [("all", N_("Alle Rollen")), ("killer", N_("Killer")), ("survivor", N_("Survivor")),
               ("custom", N_("Custom Games"))]
STATS_WAIT_GROUPS = [("weekday", N_("nach Wochentag")), ("hour", N_("nach Uhrzeit")), ("region", N_("nach Region"))]
WEEKDAYS = [N_("Montag"), N_("Dienstag"), N_("Mittwoch"), N_("Donnerstag"), N_("Freitag"), N_("Samstag"),
            N_("Sonntag")]
STATS_PERIODS = [("all", N_("Alle")), ("day", N_("Heute")), ("week", N_("Diese Woche")), ("month", N_("Dieser Monat")),
                 ("year", N_("Dieses Jahr"))]


class StatsTab:
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
        self.stats_region_cb = ttk.Combobox(fr, textvariable=self.stats_region_var, state="readonly", width=18,
                                            values=[lbl for _c, lbl in self._stats_regions])
        self.stats_region_cb.pack(side="left", padx=(6, 14))
        self.stats_region_cb.bind("<<ComboboxSelected>>", lambda e: self._stats_render())
        ttk.Label(fr, text=_("Rolle")).pack(side="left")
        self._stats_roles = [(k, _(label)) for k, label in STATS_ROLES]
        self.stats_role_var = tk.StringVar(value=self._stats_roles[0][1])
        cb = ttk.Combobox(fr, textvariable=self.stats_role_var, values=[lbl for _k, lbl in self._stats_roles],
                          state="readonly", width=13)
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self._stats_render())
        fr = ttk.Frame(f)                                    # second row: the filter row is already the widest
        fr.pack(fill="x", pady=(0, 6))
        ttk.Label(fr, text=_("Killer")).pack(side="left")
        self._stats_killers = [(None, _("Alle Killer"))]
        self.stats_killer_var = tk.StringVar(value=self._stats_killers[0][1])
        self.stats_killer_cb = ttk.Combobox(fr, textvariable=self.stats_killer_var, state="readonly", width=14,
                                            values=[lbl for _k, lbl in self._stats_killers])
        self.stats_killer_cb.pack(side="left", padx=6)
        self.stats_killer_cb.bind("<<ComboboxSelected>>", lambda e: self._stats_render())
        self.stats_var = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.stats_var, style="Big.TLabel", wraplength=540).pack(anchor="w")
        self.stats_lost_var = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.stats_lost_var, wraplength=540).pack(anchor="w")
        ttk.Label(f, text=_("Gezählt werden Runden mit automatisch erkannter Map, vom Map-Banner bis zum erkannten "
                            "Rundenende (mindestens 1 Minute). Gespeichert nur lokal in rounds.jsonl."),
                  style="Dim.TLabel", wraplength=540).pack(anchor="w", pady=(2, 6))
        box = ttk.LabelFrame(f, text=_("Maps"), padding=6)
        box.pack(fill="both", expand=True)
        self.stats_maps = self._stats_tree(box, (("map", _("Map"), 230, "w"), ("n", _("Runden"), 70, "e"),
                                                 ("avg", _("Ø Dauer"), 80, "e"), ("max", _("Längste"), 80, "e")), 9)
        box_k = ttk.LabelFrame(f, text=_("Killer"), padding=6)
        box_k.pack(fill="both", expand=True, pady=(8, 0))
        self.stats_kill = self._stats_tree(box_k, (("killer", _("Killer"), 150, "w"), ("n", _("Runden"), 70, "e"),
                                                   ("avg", _("Ø Dauer"), 80, "e"), ("map", _("Häufigste Map"), 160, "w")),
                                           5)
        ttk.Label(box_k, text=_("Name unter dem Lobby-Knopf, nur wenn du Killer spielst. Killer auswählen (oben) zeigt "
                                "Maps und Dauer nur für ihn."), style="Dim.TLabel", wraplength=520).pack(anchor="w",
                                                                                                       pady=(4, 0))
        box_r = ttk.LabelFrame(f, text=_("Serverregionen"), padding=6)
        box_r.pack(fill="both", expand=True, pady=(8, 0))
        self.stats_regs = self._stats_tree(box_r, (("reg", _("Region"), 190, "w"), ("n", _("Runden"), 65, "e"),
                                                   ("avg", _("Ø Dauer"), 75, "e"), ("share", _("Anteil"), 65, "e"),
                                                   ("ping", _("Ø Ping"), 70, "e")), 5)
        ttk.Label(box_r, text=_("Region nur bekannt, wenn im Tab Server „Verbundener Spielserver“ an war."),
                  style="Dim.TLabel", wraplength=520).pack(anchor="w", pady=(4, 0))
        box_w = ttk.LabelFrame(f, text=_("Wartezeit in der Lobby"), padding=6)
        box_w.pack(fill="both", expand=True, pady=(8, 0))
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
        box2 = ttk.LabelFrame(f, text=_("Letzte Runden"), padding=6)
        box2.pack(fill="both", expand=True, pady=(8, 0))
        self.stats_last = self._stats_tree(box2, (("when", _("Wann"), 110, "w"), ("map", _("Map"), 120, "w"),
                                                  ("dur", _("Dauer"), 55, "e"), ("wait", _("Warten"), 55, "e"),
                                                  ("role", _("Rolle"), 90, "w"), ("srv", _("Server"), 105, "w")), 9,
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
        row = ttk.Frame(f)
        row.pack(fill="x", pady=(8, 0))
        ttk.Button(row, text=_("Verlauf löschen"), command=self._stats_clear).pack(side="left")
        self._stats_sort = ("n", True)
        return outer

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
        role = next((k for k, lbl in self._stats_roles if lbl == self.stats_role_var.get()), "all")
        killer = next((k for k, lbl in self._stats_killers if lbl == self.stats_killer_var.get()), None)
        self._stats_killers = [(None, _("Alle Killer"))] + [(k, killer_label(k))
                                                             for k in history.killers_used(all_rounds)]
        if killer not in [k for k, _lbl in self._stats_killers]:
            killer = None
        self.stats_killer_cb.configure(values=[lbl for _k, lbl in self._stats_killers])
        self.stats_killer_var.set(dict(self._stats_killers)[killer])
        since = history.period_start(period, time.time())
        rounds = history.select(all_rounds, since=since, region=wanted, role=role, killer=killer)
        s = history.summary(rounds)
        lost = [x for x in history.load_lost(self._hist_path()) if since is None or x[0] >= since]
        self.stats_lost_var.set(_("⚠ Nicht gezählt: {n} × Rundenende nicht erkannt (die nächste Map kam, bevor das Ende "
                                  "erkannt wurde). Zuletzt: {map}, {when}.", n=len(lost), map=lost[-1][1],
                                  when=time.strftime("%d.%m.%y %H:%M", time.localtime(lost[-1][0])))
                                if lost else "")
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
        t = self.stats_kill
        t.delete(*t.get_children())
        for name, n, avg, top in history.per_killer(rounds):
            t.insert("", "end", values=(killer_label(name), n, fmt_duration(avg), top))
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
                                                       (_(regions.NAMES.get(r.region, r.region))
                                                        + (f" · {r.ping:.0f} ms" if r.ping is not None else ""))
                                                       if r.region else "–"))
        if keep and t.exists(keep[0]):
            t.selection_set(keep[0])
        self._stats_role_buttons()

    def _stats_role_buttons(self):
        state = "normal" if self.stats_last.selection() else "disabled"
        for b in self.stats_role_btns:
            b.configure(state=state)

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
                history.append_lost(self._hist_path(), old["t"], old["map"], "banner")
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
        if self.nb.select() == str(self.tab_stats):
            self._stats_render()

    def _hist_path(self):
        return os.path.join(self.root_dir, history.FILE)
