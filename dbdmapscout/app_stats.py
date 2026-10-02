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
from .lobby import KILLERS, killer_label
from .textnorm import fold
from .textnorm import fmt_duration

log = logging.getLogger("dbdmapscout")

STATS_ROLES = [("all", N_("Alle Rollen")), ("killer", N_("Killer")), ("survivor", N_("Survivor")),
               ("custom", N_("Custom Games"))]
STATS_WAIT_GROUPS = [("weekday", N_("nach Wochentag")), ("hour", N_("nach Uhrzeit")), ("region", N_("nach Region"))]
WEEKDAYS = [N_("Montag"), N_("Dienstag"), N_("Mittwoch"), N_("Donnerstag"), N_("Freitag"), N_("Samstag"),
            N_("Sonntag")]
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
        self.stats_lost_var = tk.StringVar(value="")
        self.stats_lost_label = ttk.Label(f, textvariable=self.stats_lost_var, wraplength=540)   # only when needed
        ttk.Label(f, text=_("Gezählt werden Runden mit automatisch erkannter Map, vom Map-Banner bis zum erkannten "
                            "Rundenende (mindestens 1 Minute). Gespeichert nur lokal in rounds.jsonl."),
                  style="Dim.TLabel", wraplength=540).pack(anchor="w", pady=(2, 6))
        # one table at a time: sub-tabs instead of five tables below each other
        self.stats_nb = ttk.Notebook(f)
        self.stats_nb.pack(fill="both", expand=True)
        box = self._stats_page(_("Maps"))
        self.stats_maps = self._stats_tree(box, (("map", _("Map"), 160, "w"), ("n", _("Runden"), 75, "e"),
                                                 ("k", _("Killer"), 60, "e"), ("s", _("Survivor"), 85, "e"),
                                                 ("avg", _("Ø Dauer"), 85, "e"), ("max", _("Längste"), 75, "e")), 9)
        box_k = self._stats_page(_("Killer"))
        self.stats_kill = self._stats_tree(box_k, (("killer", _("Killer"), 150, "w"), ("n", _("Runden"), 70, "e"),
                                                   ("avg", _("Ø Dauer"), 80, "e"), ("map", _("Häufigste Map"), 160, "w")),
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
        ttk.Label(box_k, text=_("Name unter dem Lobby-Knopf, nur wenn du Killer spielst. Manche Skins zeigen dort ihren "
                                "eigenen Namen – dann Zeile markieren und dem Killer zuordnen (gilt auch rückwirkend). "
                                "Killer auswählen (oben) zeigt Maps und Dauer nur für ihn."),
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
        self.stats_last = self._stats_tree(box2, (("when", _("Wann"), 120, "w"), ("map", _("Map"), 140, "w"),
                                                  ("dur", _("Dauer"), 60, "e"), ("wait", _("Warten"), 65, "e"),
                                                  ("role", _("Rolle"), 115, "w"), ("srv", _("Server"), 115, "w")), 7,
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
        row = ttk.Frame(f)
        row.pack(fill="x", pady=(8, 0))
        ttk.Button(row, text=_("Verlauf löschen"), command=self._stats_clear).pack(side="left")
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

    def _today_text(self, d):
        if not d["count"]:
            return _("Heute: noch keine Runde.")
        parts = [_("Heute: {n} Runden ({time})", n=d["count"], time=fmt_duration(d["total"]))]
        if d["killer"] or d["survivor"]:
            parts.append(_("{k} Killer / {s} Survivor", k=d["killer"], s=d["survivor"]))
        if d["wait"] is not None:
            parts.append(_("Ø Wartezeit {time}", time=fmt_duration(d["wait"])))
        if d["top_killer"]:
            parts.append(_("meist {killer}", killer=killer_label(d["top_killer"])))
        if d["ping"] is not None:
            parts.append(_("Ping {ms} ms", ms=f"{d['ping']:.0f}"))
        return " · ".join(parts)

    def _stats_render(self):
        all_rounds = history.load(self._hist_path())
        for r in all_rounds:                         # skins / new killers: the user's assignment
            r.killer = self._killer_of(r.killer)
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
        self.stats_today_var.set(self._today_text(history.today(all_rounds, time.time())))
        since = history.period_start(period, time.time())
        rounds = history.select(all_rounds, since=since, region=wanted, role=role, killer=killer)
        s = history.summary(rounds)
        lost = [x for x in history.load_lost(self._hist_path()) if since is None or x[0] >= since]
        self.stats_lost_var.set(_("⚠ Nicht gezählt: {n} × Rundenende nicht erkannt (die nächste Map kam, bevor das Ende "
                                  "erkannt wurde). Zuletzt: {map}, {when}.", n=len(lost), map=lost[-1][1],
                                  when=time.strftime("%d.%m.%y %H:%M", time.localtime(lost[-1][0])))
                                if lost else "")
        if lost:
            self.stats_lost_label.pack(anchor="w", after=self.stats_sum_label)
        else:
            self.stats_lost_label.pack_forget()
        if not all_rounds:
            self.stats_var.set(_("Noch keine Runden gespeichert."))
        elif not s["count"]:
            self.stats_var.set(_("Keine Runden in dieser Auswahl."))
        else:
            self.stats_var.set(_("{n} Runden · Ø {avg} · gesamt {total}", n=s["count"], avg=fmt_duration(s["avg"]),
                                 total=fmt_duration(s["total"])))
        roles = history.roles_per_map(rounds)               # rounds = killer + survivor + custom/unknown
        rows = [(name, n, *roles.get(name, (0, 0)), avg, longest) for name, n, avg, longest in history.per_map(rounds)]
        col, desc = self._stats_sort
        idx = {"map": 0, "n": 1, "k": 2, "s": 3, "avg": 4, "max": 5}[col]
        rows.sort(key=lambda r: r[idx].lower() if idx == 0 else r[idx], reverse=desc)
        t = self.stats_maps
        t.delete(*t.get_children())
        for name, n, k, s, avg, longest in rows:
            t.insert("", "end", values=(name, n, k, s, fmt_duration(avg), fmt_duration(longest)))
        t = self.stats_kill
        t.delete(*t.get_children())
        keep = t.selection()
        for name, n, avg, top in history.per_killer(rounds):
            t.insert("", "end", iid=name, values=(killer_label(name), n, fmt_duration(avg), top))
        if keep and t.exists(keep[0]):
            t.selection_set(keep[0])
        self._stats_alias_buttons()
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
