"""Tab "Aufnahmen" (1.5, user's wish: see the recorded rounds in the program, like Medal): the recording index
of the OBS folder as a table with filters, play / show in Explorer / keep / delete, the F8 marks of the marked
row. Only the index in the recording folder is read and – through the recorder thread – written; files are
deleted only when they are named in it.

Mixin of App (app.py) – uses App's attributes; never imports app.py."""
from __future__ import annotations

import os
import subprocess
import time

from . import history, obsrec, uimodel as ui
from .app_stats import STATS_PERIODS
from .capture import IS_WIN
from .i18n import N_, _
from .lobby import killer_label
from .textnorm import fmt_duration

REC_ROLES = [("all", N_("Alle Rollen")), ("killer", N_("Killer")), ("survivor", N_("Survivor")),
             ("farming", N_("Farming"))]
REC_ONLY = [("all", N_("Alle Aufnahmen")), ("marked", N_("Mit Marke")), ("kept", N_("Behalten")),
            ("bad", N_("Beschädigt"))]
REC_REFRESH_S = 20            # the table re-reads the index this often while the tab is on display


def fmt_bytes(n: float) -> str:
    gb = n / 1024 ** 3
    if gb >= 1000:
        return f"{gb / 1024:.2f} TB"
    if gb >= 10:
        return f"{gb:.0f} GB"
    if gb >= 1:
        return f"{gb:.1f} GB"
    if n >= 1024 ** 2:
        return f"{n / 1024 ** 2:.0f} MB"
    return f"{n / 1024:.0f} KB"


def show_in_explorer(path: str):
    """Windows Explorer with the file marked (nothing else runs the file)."""
    subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])     # noqa: S603, S607


class RecordingsTab:
    # ============================================================ tab
    def _tab_recordings(self):
        outer, f = self._scroll_tab()
        self._rec_dirty = True
        self._rec_rows = {}                       # iid -> Recording on display
        self._rec_rendered = 0.0
        self.rec_summary_var = ui.StringVar(value="")
        ui.Label(f, textvariable=self.rec_summary_var, style="Big.TLabel", wraplength=560).pack(anchor="w")
        self.rec_hint_var = ui.StringVar(value="")
        ui.Label(f, textvariable=self.rec_hint_var, style="Dim.TLabel", wraplength=560).pack(anchor="w")

        fr = ui.Frame(f)
        fr.pack(fill="x", pady=(8, 6))
        self._rec_periods = [(k, _(label)) for k, label in STATS_PERIODS]
        self.rec_period_var = ui.StringVar(value=self._rec_periods[0][1])
        cb = ui.Combobox(fr, textvariable=self.rec_period_var, values=[lbl for _k, lbl in self._rec_periods],
                         state="readonly", width=16)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: self._rec_render(force=True))
        self._rec_maps = [(None, _("Alle Maps"))]
        self.rec_map_var = ui.StringVar(value=self._rec_maps[0][1])
        self.rec_map_cb = ui.Combobox(fr, textvariable=self.rec_map_var, state="readonly", width=20,
                                      values=[lbl for _m, lbl in self._rec_maps])
        self.rec_map_cb.pack(side="left", padx=(8, 0))
        self.rec_map_cb.bind("<<ComboboxSelected>>", lambda e: self._rec_render(force=True))
        self._rec_roles = [(k, _(label)) for k, label in REC_ROLES]
        self.rec_role_var = ui.StringVar(value=self._rec_roles[0][1])
        cb = ui.Combobox(fr, textvariable=self.rec_role_var, values=[lbl for _k, lbl in self._rec_roles],
                         state="readonly", width=13)
        cb.pack(side="left", padx=(8, 0))
        cb.bind("<<ComboboxSelected>>", lambda e: self._rec_render(force=True))
        self._rec_onlys = [(k, _(label)) for k, label in REC_ONLY]
        self.rec_only_var = ui.StringVar(value=self._rec_onlys[0][1])
        cb = ui.Combobox(fr, textvariable=self.rec_only_var, values=[lbl for _k, lbl in self._rec_onlys],
                         state="readonly", width=15)
        cb.pack(side="left", padx=(8, 0))
        cb.bind("<<ComboboxSelected>>", lambda e: self._rec_render(force=True))

        row = ui.Frame(f)
        row.pack(fill="x", pady=(0, 6))          # above the table, like the server tab: seen without scrolling
        self.rec_play_btn = ui.Button(row, text=_("Abspielen"), command=self._rec_play, state="disabled")
        self.rec_play_btn.pack(side="left")
        self.rec_show_btn = ui.Button(row, text=_("Im Explorer zeigen"), command=self._rec_explorer, state="disabled")
        self.rec_show_btn.pack(side="left", padx=(6, 0))
        self.rec_keep_btn = ui.Button(row, text=_("Behalten"), command=self._rec_keep, state="disabled")
        self.rec_keep_btn.pack(side="left", padx=(6, 0))
        self.rec_delete_btn = ui.Button(row, text=_("Aufnahme löschen"), command=self._rec_delete, state="disabled")
        self.rec_delete_btn.pack(side="left", padx=(6, 0))
        self.rec_folder_btn = ui.Button(row, text=_("Aufnahmeordner öffnen"), command=self._rec_open_folder)
        self.rec_folder_btn.pack(side="right")

        tf = ui.Frame(f)
        tf.pack(fill="both", expand=True)
        cols = (("when", _("Wann"), 100, "w"), ("map", _("Map"), 130, "w"), ("role", _("Rolle/Killer"), 110, "w"),
                ("res", _("Ergebnis"), 65, "w"), ("dur", _("Dauer"), 55, "e"), ("size", _("Grösse"), 65, "e"),
                ("marks", _("Marken"), 50, "e"), ("keep", _("Behalten"), 60, "w"), ("file", _("Datei"), 110, "w"))
        self.rec_table = ui.Treeview(tf, columns=[c[0] for c in cols], show="headings", height=12, selectmode="browse")
        for key, title, width, anchor in cols:
            self.rec_table.heading(key, text=title, anchor=anchor)
            self.rec_table.column(key, width=width, anchor=anchor, stretch=key == "file")
        self.rec_table.pack(side="left", fill="both", expand=True)
        self.rec_table.bind("<<TreeviewSelect>>", lambda e: self._rec_buttons())
        self.rec_marks_var = ui.StringVar(value="")
        ui.Label(f, textvariable=self.rec_marks_var, style="Dim.TLabel", wraplength=560).pack(anchor="w", pady=(6, 0))
        ui.Label(f, text=_("OBS nimmt jede Runde auf (Einstellungen → Mehr → Aufnahmen mit OBS). F8 setzt während "
                            "der Runde eine Marke; „Behalten“ schützt eine Aufnahme vor dem Aufräumen, wenn die "
                            "Platte Platz braucht."),
                 style="Dim.TLabel", wraplength=560).pack(anchor="w", pady=(6, 0))
        return outer

    # ============================================================ data
    def _rec_filters(self):
        period = next((k for k, lbl in self._rec_periods if lbl == self.rec_period_var.get()), "all")
        map_label = next((m for m, lbl in self._rec_maps if lbl == self.rec_map_var.get()), None)
        role = next((k for k, lbl in self._rec_roles if lbl == self.rec_role_var.get()), "all")
        only = next((k for k, lbl in self._rec_onlys if lbl == self.rec_only_var.get()), "all")
        return period, map_label, None if role == "all" else role, None if only == "all" else only

    def _rec_tab_tick(self):
        """From App._rec_tick (4×/s): a change from the recorder or the refresh interval re-reads the index –
        only while the tab is on display."""
        if self.nb.select() != str(self.tab_recordings):
            return
        if self._rec_dirty or time.time() - self._rec_rendered > REC_REFRESH_S:
            self._rec_render()

    def _rec_render(self, force=False):
        self._rec_dirty, self._rec_rendered = False, time.time()
        folder = self.recorder.folder() if self.settings.get("rec_on", False) or self.settings.get("rec_folder") else None
        recs = obsrec.load_index(folder) if folder else []
        sp = self.recorder.space
        if not self.settings.get("rec_on", False) and not recs:
            self.rec_summary_var.set(_("Aufnahme ist aus."))
            self.rec_hint_var.set(_("Einschalten unter Einstellungen → Mehr → Aufnahmen mit OBS."))
        elif folder is None:
            self.rec_summary_var.set(_("Aufnahme-Laufwerk nicht angeschlossen.") if self.settings.get("rec_folder")
                                     else _("Noch kein Aufnahmeordner gewählt."))
            self.rec_hint_var.set(str(self.settings.get("rec_folder", "")))
        else:
            bits = [_("{n} Aufnahmen", n=len(recs)) if len(recs) != 1 else _("1 Aufnahme"),
                    fmt_bytes(sum(r.size for r in recs))]
            if sp.total and sp.folder == folder:
                bits.append(_("{size} frei", size=fmt_bytes(sp.free)))
            self.rec_summary_var.set(" · ".join(bits))
            self.rec_hint_var.set(folder)
        # the map list follows the index
        labels = sorted({r.label for r in recs if r.label})
        maps = [(None, _("Alle Maps"))] + [(lbl, lbl) for lbl in labels]
        if maps != self._rec_maps:
            self._rec_maps = maps
            self.rec_map_cb.configure(values=[lbl for _m, lbl in maps])
            if self.rec_map_var.get() not in [lbl for _m, lbl in maps]:
                self.rec_map_var.set(maps[0][1])
        period, map_label, role, only = self._rec_filters()
        since = history.period_start(period, time.time()) if period != "all" else None
        shown = obsrec.select_recordings(recs, since=since, map_label=map_label, role=role, only=only)
        j = self._joined()
        by_t = {r.t: r for r in j.rounds}
        t = self.rec_table
        keep = t.selection()
        t.delete(*t.get_children())
        self._rec_rows = {}
        for r in shown:
            rnd = by_t.get(r.t)
            res = self._official_result(j.off.get(id(rnd))) if rnd is not None else "–"
            role_txt = self._rec_role(r, rnd)
            exists = bool(folder) and os.path.exists(os.path.join(folder, r.file))
            size = fmt_bytes(r.size) if exists else _("fehlt")
            if (r.extra or {}).get("bad"):
                size += " ⚠"
            iid = repr(r.t)
            self._rec_rows[iid] = r
            t.insert("", "end", iid=iid, values=(time.strftime("%d.%m.%y %H:%M", time.localtime(r.t)), r.label or "–",
                                                 role_txt, res, fmt_duration(r.end - r.t) if r.end > r.t else "–",
                                                 size, str(len(r.marks)) if r.marks else "", "✓" if r.keep else "",
                                                 r.file))
        if keep and t.exists(keep[0]):
            t.selection_set(keep[0])
        self._rec_buttons()

    def _rec_role(self, r, rnd):
        role, killer = r.role or (rnd.role if rnd else ""), r.killer or (rnd.killer if rnd else "")
        txt = killer_label(self._killer_of(killer)) if role == "killer" and killer else self._role_name(role) or "–"
        if r.farming:
            txt += " · " + _("Farming")
        return txt

    def _rec_selected(self):
        sel = self.rec_table.selection()
        return self._rec_rows.get(sel[0]) if sel else None

    def _rec_buttons(self):
        r = self._rec_selected()
        state = "normal" if r is not None else "disabled"
        for b in (self.rec_play_btn, self.rec_show_btn, self.rec_keep_btn, self.rec_delete_btn):
            b.configure(state=state)
        self.rec_keep_btn.configure(text=_("Nicht mehr behalten") if r is not None and r.keep else _("Behalten"))
        if r is None:
            self.rec_marks_var.set("")
        elif r.marks:
            self.rec_marks_var.set(_("Marken: {list}", list=" · ".join(fmt_duration(m) for m in r.marks)))
        else:
            self.rec_marks_var.set(_("Keine Marken – F8 während der Runde setzt eine."))

    def _rec_path(self, r):
        folder = self.recorder.folder()
        return os.path.join(folder, r.file) if folder else None

    # ============================================================ actions
    def _rec_play(self):
        r = self._rec_selected()
        path = self._rec_path(r) if r is not None else None
        if path is None:
            return
        if not os.path.exists(path):
            self._log(_("Aufnahme fehlt: {file}", file=r.file), "Fehler")
            return
        self._open(path)

    def _rec_explorer(self):
        r = self._rec_selected()
        path = self._rec_path(r) if r is not None else None
        if path is None:
            return
        if not IS_WIN:
            self._log(_("Öffnen nur unter Windows: {path}", path=path), "System")
            return
        try:
            show_in_explorer(path)
        except OSError as e:
            self._log(_("Kann {path} nicht öffnen: {error}", path=path, error=e), "Fehler")

    def _rec_open_folder(self):
        folder = self.recorder.folder()
        if folder:
            self._open(folder)
        else:
            self._log(_("Aufnahme-Laufwerk nicht angeschlossen."), "Fehler")

    def _rec_keep(self):
        r = self._rec_selected()
        if r is not None:
            self.recorder.set_keep(r.t, not r.keep)

    def _rec_delete(self):
        r = self._rec_selected()
        if r is None:
            return
        if not self._ask(_("Aufnahme löschen"), _("{file} von der Platte löschen?", file=r.file), self._rec_delete):
            return
        self.recorder.delete(r.t)

    def _rec_changed(self, d):
        """Recorder → "changed" (keep / delete from this tab): re-read on the next tick, log the deletion."""
        self._rec_dirty = True
        if d.get("what") == "keep":
            self._log(_("Aufnahme wird behalten: {file}", file=d.get("file", "")) if d.get("on")
                      else _("Aufnahme wird nicht mehr behalten: {file}", file=d.get("file", "")), "System")
