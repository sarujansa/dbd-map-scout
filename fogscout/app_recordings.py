"""Tab "Aufnahmen" (1.5, user's wish: see the recorded rounds in the program, like Medal): the recording index
of the OBS folder as a table with filters, play / show in Explorer / keep / delete, the F8 marks of the marked
row. Only the index in the recording folder is read and – through the recorder thread – written; files are
deleted only when they are named in it.

Mixin of App (app.py) – uses App's attributes; never imports app.py."""
from __future__ import annotations

import os
import subprocess
import time
from types import SimpleNamespace

from . import history, obsrec, uimodel as ui
from .app_stats import STATS_PERIODS
from .capture import IS_WIN
from .i18n import N_, _
from .lobby import killer_label
from .textnorm import fmt_duration

# 1.8.71 (user: "Farming und normale Runden sollen bei Aufnahmen separiert werden"): "Alle Rollen" = the normal
# rounds, as in the statistics; the farming rounds only under "Farming", both together only on request
REC_ROLES = [("all", N_("Alle Rollen")), ("killer", N_("Killer")), ("survivor", N_("Survivor")),
             ("farming", N_("Farming")), ("everything", N_("Alle inkl. Farming"))]
ROLE_ARG = {"all": "normal", "everything": None}
REC_ONLY = [("all", N_("Alle Aufnahmen")), ("marked", N_("Mit Marke")), ("kept", N_("Behalten")),
            ("bad", N_("Beschädigt"))]
CLIP_KINDS = [("all", N_("Alle Arten")), ("clip", N_("Clips")), ("instant", N_("Sofort-Clips (F8)")),
              ("still", N_("Standbilder"))]
CLIP_KIND_NAMES = {"clip": N_("Clip"), "instant": N_("Sofort-Clip"), "still": N_("Standbild")}
REC_REFRESH_S = 20            # the table re-reads the index this often while the tab is on display
PREVIEW_DELAY_MS = 180               # 1.8.11: the clip preview is built once the marking stays


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

        # 1.8.13 (user: clips list, "filtern nach Killer/Survivor"): the rounds and the clips on sub-tabs
        self.rec_nb = ui.Notebook(f)
        self.rec_nb.pack(fill="both", expand=True, pady=(8, 0))
        rp = ui.Frame(self.rec_nb, padding=6)
        self.rec_nb.add(rp, text=_("Runden"))
        self.rec_rounds_tab = rp
        cp = ui.Frame(self.rec_nb, padding=6)
        self.rec_nb.add(cp, text=_("Clips"))
        f = rp
        fr = ui.Frame(f)
        fr.pack(fill="x", pady=(0, 6))
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
        self.rec_clip_btn = ui.Button(row, text=_("Clip bearbeiten …"), command=self._rec_clip, state="disabled")   # 1.5.1
        self.rec_clip_btn.pack(side="left", padx=(6, 0))
        self.rec_yt_btn = ui.Button(row, text=_("Auf YouTube hochladen"), command=self._rec_youtube, state="disabled")  # 1.10
        self.rec_yt_btn.pack(side="left", padx=(6, 0))
        self._clip_windows = []
        self.rec_folder_btn = ui.Button(row, text=_("Aufnahmeordner öffnen"), command=self._rec_open_folder)
        self.rec_folder_btn.pack(side="right")

        tf = ui.Frame(f)
        tf.pack(fill="both", expand=True)
        cols = (("when", _("Wann"), 100, "w"), ("map", _("Map"), 130, "w"), ("role", _("Rolle/Killer"), 110, "w"),
                ("res", _("Ergebnis"), 65, "w"), ("dur", _("Dauer"), 55, "e"), ("size", _("Grösse"), 65, "e"),
                ("marks", _("Marken"), 50, "e"), ("keep", _("Behalten"), 60, "w"), ("yt", _("YouTube"), 60, "w"),
                ("file", _("Datei"), 110, "w"))
        self.rec_table = ui.Treeview(tf, columns=[c[0] for c in cols], show="headings", height=12, selectmode="browse")
        for key, title, width, anchor in cols:
            self.rec_table.heading(key, text=title, anchor=anchor)
            self.rec_table.column(key, width=width, anchor=anchor, stretch=key == "file")
        self.rec_table.pack(side="left", fill="both", expand=True)
        self.rec_table.bind("<<TreeviewSelect>>", lambda e: self._rec_buttons())
        # 1.8.8 (user: "click on it and a preview comes where I can play it and quickly edit, sound tracks on/off"):
        # the compact clip editor beside the table, shown once a recording is marked
        self.rec_host = ui.Host(tf)
        self._rec_preview_t = None
        self._table_menu(self.rec_table, self._rec_menu_items, self._rec_menu_act)       # 1.8.10: right click
        self.rec_marks_var = ui.StringVar(value="")
        ui.Label(f, textvariable=self.rec_marks_var, style="Dim.TLabel", wraplength=560).pack(anchor="w", pady=(6, 0))
        ui.Label(f, text=_("OBS nimmt jede Runde auf (Einstellungen → Aufnahmen). F8 setzt während "
                            "der Runde eine Marke; „Behalten“ schützt eine Aufnahme vor dem Aufräumen, wenn die "
                            "Platte Platz braucht."),
                 style="Dim.TLabel", wraplength=560).pack(anchor="w", pady=(6, 0))
        self._tab_clips(cp)
        return outer

    def _tab_clips(self, f):
        """1.8.13: everything in Clips/ the program made – editor clips, F8 instant clips, stills – with the round
        each came from (role, killer, map), filters and play / Explorer / delete."""
        self._clip_rows = {}
        fr = ui.Frame(f)
        fr.pack(fill="x", pady=(0, 6))
        self.clip_period_var = ui.StringVar(value=self._rec_periods[0][1])
        cb = ui.Combobox(fr, textvariable=self.clip_period_var, values=[lbl for _k, lbl in self._rec_periods],
                         state="readonly", width=16)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: self._clips_render())
        self.clip_role_var = ui.StringVar(value=self._rec_roles[0][1])
        cb = ui.Combobox(fr, textvariable=self.clip_role_var, values=[lbl for _k, lbl in self._rec_roles],
                         state="readonly", width=13)
        cb.pack(side="left", padx=(8, 0))
        cb.bind("<<ComboboxSelected>>", lambda e: self._clips_render())
        self._clip_killers = [(None, _("Alle Killer"))]
        self.clip_killer_var = ui.StringVar(value=self._clip_killers[0][1])
        self.clip_killer_cb = ui.Combobox(fr, textvariable=self.clip_killer_var, state="readonly", width=16,
                                          values=[lbl for _k, lbl in self._clip_killers])
        self.clip_killer_cb.pack(side="left", padx=(8, 0))
        self.clip_killer_cb.bind("<<ComboboxSelected>>", lambda e: self._clips_render())
        self._clip_kinds = [(k, _(label)) for k, label in CLIP_KINDS]
        self.clip_kind_var = ui.StringVar(value=self._clip_kinds[0][1])
        cb = ui.Combobox(fr, textvariable=self.clip_kind_var, values=[lbl for _k, lbl in self._clip_kinds],
                         state="readonly", width=17)
        cb.pack(side="left", padx=(8, 0))
        cb.bind("<<ComboboxSelected>>", lambda e: self._clips_render())

        row = ui.Frame(f)
        row.pack(fill="x", pady=(0, 6))
        self.clip_play_btn = ui.Button(row, text=_("Clip abspielen"), command=self._clip_play, state="disabled")
        self.clip_play_btn.pack(side="left")
        self.clip_edit_btn = ui.Button(row, text=_("Clip im Editor öffnen …"), command=self._clip_edit,
                                       state="disabled")                   # 1.8.60
        self.clip_edit_btn.pack(side="left", padx=(6, 0))
        self.clip_show_btn = ui.Button(row, text=_("Clip im Explorer zeigen"), command=self._clip_explorer,
                                       state="disabled")
        self.clip_show_btn.pack(side="left", padx=(6, 0))
        self.clip_delete_btn = ui.Button(row, text=_("Clip löschen"), command=self._clip_delete, state="disabled")
        self.clip_delete_btn.pack(side="left", padx=(6, 0))
        self.clip_yt_btn = ui.Button(row, text=_("Auf YouTube hochladen"), command=self._clip_youtube, state="disabled")
        self.clip_yt_btn.pack(side="left", padx=(6, 0))                                                      # 1.10
        self.clip_folder_btn = ui.Button(row, text=_("Clips-Ordner öffnen"), command=self._clip_open_folder)
        self.clip_folder_btn.pack(side="right")

        self.clip_summary_var = ui.StringVar(value="")
        ui.Label(f, textvariable=self.clip_summary_var, style="Dim.TLabel", wraplength=560).pack(anchor="w",
                                                                                                  pady=(0, 6))
        tf = ui.Frame(f)
        tf.pack(fill="both", expand=True)
        cols = (("when", _("Wann"), 100, "w"), ("map", _("Map"), 130, "w"), ("role", _("Rolle/Killer"), 110, "w"),
                ("kind", _("Art"), 85, "w"), ("dur", _("Länge"), 55, "e"), ("size", _("Grösse"), 65, "e"),
                ("yt", _("YouTube"), 60, "w"), ("file", _("Datei"), 140, "w"))
        self.clip_table = ui.Treeview(tf, columns=[c[0] for c in cols], show="headings", height=12,
                                      selectmode="browse")
        for key, title, width, anchor in cols:
            self.clip_table.heading(key, text=title, anchor=anchor)
            self.clip_table.column(key, width=width, anchor=anchor, stretch=key == "file")
        self.clip_table.pack(side="left", fill="both", expand=True)
        self.clip_table.bind("<<TreeviewSelect>>", lambda e: self._clip_buttons())
        self._table_menu(self.clip_table, self._clip_menu_items, self._clip_menu_act)
        ui.Label(f, text=_("Hier stehen die Clips aus dem Editor, die Sofort-Clips (F8) und die Standbilder – mit "
                            "der Runde, aus der sie stammen. Gelöscht werden nur Dateien, die das Programm selbst "
                            "angelegt hat."),
                 style="Dim.TLabel", wraplength=560).pack(anchor="w", pady=(6, 0))

    # ============================================================ data
    def _rec_filters(self):
        period = next((k for k, lbl in self._rec_periods if lbl == self.rec_period_var.get()), "all")
        map_label = next((m for m, lbl in self._rec_maps if lbl == self.rec_map_var.get()), None)
        role = next((k for k, lbl in self._rec_roles if lbl == self.rec_role_var.get()), "all")
        only = next((k for k, lbl in self._rec_onlys if lbl == self.rec_only_var.get()), "all")
        return period, map_label, ROLE_ARG.get(role, role), None if only == "all" else only

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
            self.rec_hint_var.set(_("Einschalten unter Einstellungen → Aufnahmen."))
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
            p = obsrec.rel_path(folder, r.file) if folder else None
            exists = bool(p) and os.path.exists(p)
            size = fmt_bytes(r.size) if exists else _("fehlt")
            if (r.extra or {}).get("bad"):
                size += " ⚠"
            iid = repr(r.t)
            self._rec_rows[iid] = r
            t.insert("", "end", iid=iid, values=(time.strftime("%d.%m.%y %H:%M", time.localtime(r.t)), r.label or "–",
                                                 role_txt, res, fmt_duration(r.end - r.t) if r.end > r.t else "–",
                                                 size, str(len(r.marks)) if r.marks else "", "✓" if r.keep else "",
                                                 self._yt_mark(r.file, r.yt), r.file))
        if keep and t.exists(keep[0]):
            t.selection_set(keep[0])
        self._rec_buttons()
        self._clips_render(folder, recs)

    # ============================================================ clips (1.8.13)
    def _clips_render(self, folder=None, recs=None):
        if folder is None:
            folder = self.recorder.folder() if self.settings.get("rec_on", False) or self.settings.get("rec_folder") \
                else None
            recs = obsrec.load_index(folder) if folder else []
        clips = obsrec.list_clips(obsrec.clips_dir(folder), recs) if folder else []
        j = self._joined()
        by_t = {r.t: r for r in j.rounds}
        for c in clips:                                    # the round knows the role when the recording did not
            rnd = by_t.get(c.source) if c.source else None
            if rnd is not None:
                c.role = c.role or rnd.role or ""
                c.killer = c.killer or rnd.killer or ""
                c.farming = c.farming or bool(rnd.farming)
        killers = sorted({self._killer_of(c.killer) for c in clips if c.role == "killer" and c.killer})
        opts = [(None, _("Alle Killer"))] + [(k, killer_label(k)) for k in killers]
        if opts != self._clip_killers:
            self._clip_killers = opts
            self.clip_killer_cb.configure(values=[lbl for _k, lbl in opts])
            if self.clip_killer_var.get() not in [lbl for _k, lbl in opts]:
                self.clip_killer_var.set(opts[0][1])
        period = next((k for k, lbl in self._rec_periods if lbl == self.clip_period_var.get()), "all")
        role = next((k for k, lbl in self._rec_roles if lbl == self.clip_role_var.get()), "all")
        killer = next((k for k, lbl in self._clip_killers if lbl == self.clip_killer_var.get()), None)
        kind = next((k for k, lbl in self._clip_kinds if lbl == self.clip_kind_var.get()), "all")
        since = history.period_start(period, time.time()) if period != "all" else None
        for c in clips:
            c.killer = self._killer_of(c.killer) if c.killer else ""
        shown = obsrec.select_clips(clips, since=since, role=ROLE_ARG.get(role, role), killer=killer,
                                    kind=None if kind == "all" else kind)
        if not folder:
            self.clip_summary_var.set(_("Kein Aufnahmeordner – die Clips liegen in seinem Ordner „Clips“."))
        elif not clips:
            self.clip_summary_var.set(_("Noch keine Clips – „Clip bearbeiten …“ bei einer Runde oder F8 im Spiel."))
        else:
            self.clip_summary_var.set(" · ".join([_("{n} von {total} Clips", n=len(shown), total=len(clips)),
                                                  fmt_bytes(sum(c.size for c in shown))]))
        t = self.clip_table
        keep = t.selection()
        t.delete(*t.get_children())
        self._clip_rows = {}
        for c in shown:
            self._clip_rows[c.file] = c
            if c.role == "killer" and c.killer:
                who = killer_label(c.killer)
            else:
                who = self._role_name(c.role) or "–"
            if c.farming:
                who += " · " + _("Farming")
            t.insert("", "end", iid=c.file, values=(
                time.strftime("%d.%m.%y %H:%M", time.localtime(c.t)), c.label or "–", who,
                _(CLIP_KIND_NAMES.get(c.kind, "Clip")), fmt_duration(c.seconds) if c.seconds else "–",
                fmt_bytes(c.size), self._yt_mark(self._clip_rel(c), c.yt), c.file))
        if keep and t.exists(keep[0]):
            t.selection_set(keep[0])
        self._clip_buttons()

    def _clip_selected(self):
        sel = self.clip_table.selection()
        return self._clip_rows.get(sel[0]) if sel else None

    def _clip_path(self, c):
        folder = self.recorder.folder()
        return os.path.join(obsrec.clips_dir(folder), c.file) if folder and c is not None else None

    def _clip_buttons(self):
        state = "normal" if self._clip_selected() is not None else "disabled"
        for b in (self.clip_play_btn, self.clip_show_btn, self.clip_delete_btn):
            b.configure(state=state)
        c = self._clip_selected()
        self.clip_edit_btn.configure(state="normal" if c is not None and c.kind != "still" else "disabled")
        self.clip_yt_btn.configure(state="normal" if c is not None and self._clip_uploadable(c) else "disabled")

    @staticmethod
    def _clip_rel(c) -> str:
        return f"{obsrec.CLIPS_DIR}/{c.file}"

    def _clip_uploadable(self, c) -> bool:
        return c.kind != "still" and self._yt_ready() and not c.yt and self._clip_rel(c) not in self._yt_queued

    def _clip_menu_items(self):
        if self._clip_selected() is None:
            return []
        c = self._clip_selected()
        items = [("play", _("Abspielen"), True), ("edit", _("Im Editor öffnen …"), c.kind != "still"),
                 ("explorer", _("Im Explorer zeigen"), True), ("copy", _("Datei kopieren (zum Einfügen)"), True),
                 ("round", _("Zur Runde springen"), bool(c.source)), None]
        if c.yt:                                                                   # 1.10
            items += [("yt_link", _("YouTube-Link kopieren"), True), ("yt_open", _("Auf YouTube öffnen"), True), None]
        elif c.kind != "still":
            items += [("youtube", _("Auf YouTube hochladen"), self._clip_uploadable(c)), None]
        return items + [("delete", _("Clip löschen"), True)]

    def _clip_menu_act(self, ident):
        c = self._clip_selected()
        act = {"play": self._clip_play, "edit": self._clip_edit, "explorer": self._clip_explorer,
               "copy": self._clip_copy, "round": self._clip_round_show, "delete": self._clip_delete,
               "youtube": self._clip_youtube,
               "yt_link": lambda: self._yt_copy_link(c.yt) if c is not None and c.yt else None,
               "yt_open": lambda: self._yt_open_link(c.yt) if c is not None and c.yt else None}.get(ident)
        if act is not None:
            act()

    def _clip_youtube(self):
        """1.10: the marked clip into the upload queue."""
        c = self._clip_selected()
        if c is not None and self._clip_uploadable(c):
            self._yt_enqueue("clip", self._clip_rel(c), c.label, c.role, c.killer, c.t, c.seconds)
            self._clip_buttons()

    def _clip_play(self):
        path = self._clip_path(self._clip_selected())
        if path is None:
            return
        if not os.path.exists(path):
            self._log(_("Clip fehlt: {file}", file=os.path.basename(path)), "Fehler")
            return
        self._open(path)

    def _clip_edit(self):
        """1.8.60 (user: "Clip soll auch bearbeitbar sein"): a clip – editor clip or F8 instant clip – opens in the
        same editor as a recording. What it saves is a new clip of the round the clip came from; the clip itself
        stays as it is."""
        c = self._clip_selected()
        path = self._clip_path(c)
        if path is None or c.kind == "still":
            return
        if not os.path.exists(path):
            self._log(_("Clip fehlt: {file}", file=c.file), "Fehler")
            return
        if obsrec.ffmpeg_exe() is None:
            self._log(_("ffmpeg fehlt (Paket imageio-ffmpeg) – start.bat installiert es beim nächsten Start."),
                      "Fehler")
            return
        win = self._clip_window(clip_round(c, obsrec.load_index(self.recorder.folder())), path)
        self._clip_windows = [w for w in self._clip_windows if w.isVisible()] + [win]
        win.show()
        win.raise_()
        win.activateWindow()

    def _copy_file(self, path, name):
        """1.8.60: the file onto the clipboard – Ctrl+V in Discord or Explorer pastes it."""
        if path is None:
            return
        if not os.path.exists(path):
            self._log(_("Datei fehlt: {file}", file=name), "Fehler")
            return
        self.root.clipboard_files([path])
        self._log(_("{file} kopiert – mit Strg+V z. B. in Discord einfügen.", file=os.path.basename(path)), "System")

    def _clip_copy(self):
        c = self._clip_selected()
        if c is not None:
            self._copy_file(self._clip_path(c), c.file)

    def _clip_round_show(self):
        """1.8.60: from a clip to the recording of its round – sub-tab Runden, filters opened up if they hide it."""
        c = self._clip_selected()
        if c is None or not c.source:
            return
        iid = repr(c.source)
        if not self.rec_table.exists(iid):
            for var, opts in ((self.rec_period_var, self._rec_periods), (self.rec_map_var, self._rec_maps),
                              (self.rec_role_var, self._rec_roles), (self.rec_only_var, self._rec_onlys)):
                var.set(opts[0][1])
            self.rec_role_var.set(dict(self._rec_roles)["everything"])    # 1.8.71: "all" leaves farming out
            self._rec_render()
        if not self.rec_table.exists(iid):
            self._log(_("Die Aufnahme dieser Runde gibt es nicht mehr."), "System")
            return
        self.rec_nb.select(self.rec_rounds_tab)
        self.rec_table.selection_set(iid)
        self.rec_table.see(iid)
        self._rec_buttons()

    def _clip_explorer(self):
        path = self._clip_path(self._clip_selected())
        if path is None:
            return
        if not IS_WIN:
            self._log(_("Öffnen nur unter Windows: {path}", path=path), "System")
            return
        try:
            show_in_explorer(path)
        except OSError as e:
            self._log(_("Kann {path} nicht öffnen: {error}", path=path, error=e), "Fehler")

    def _clip_delete(self):
        c = self._clip_selected()
        if c is None:
            return
        if not self._ask(_("Clip löschen"), _("{file} von der Platte löschen?", file=c.file), self._clip_delete):
            return
        self.recorder.delete_clip(c.file)

    def _clip_open_folder(self):
        folder = self.recorder.folder()
        if not folder:
            self._log(_("Aufnahme-Laufwerk nicht angeschlossen."), "Fehler")
            return
        cdir = obsrec.clips_dir(folder)
        try:
            os.makedirs(cdir, exist_ok=True)
        except OSError as e:
            self._log(_("Kann {path} nicht öffnen: {error}", path=cdir, error=e), "Fehler")
            return
        self._open(cdir)

    def _clip_saved(self, r, out, win):
        """The editor saved a clip or a still of recording ``r``: into the clips index with its round."""
        self._rec_dirty = True
        still = os.path.splitext(out)[1].lower() in obsrec.STILL_EXTS
        self.recorder.add_clip(file=os.path.basename(out), kind="still" if still else "clip", source=r.t,
                               map_id=r.map_id, label=r.label, role=r.role, killer=r.killer, farming=r.farming,
                               seconds=0.0 if still else float(win.saved_seconds.get(out, 0.0)))
        if not still:                                                              # 1.10: by itself, when wanted
            self._yt_auto_clip(out, r.label, r.role, r.killer, time.time(), float(win.saved_seconds.get(out, 0.0)))

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
        for b in (self.rec_play_btn, self.rec_show_btn, self.rec_keep_btn, self.rec_delete_btn, self.rec_clip_btn):
            b.configure(state=state)
        self.rec_keep_btn.configure(text=_("Nicht mehr behalten") if r is not None and r.keep else _("Behalten"))
        self.rec_yt_btn.configure(state="normal" if r is not None and self._rec_uploadable(r) else "disabled")
        self._rec_preview_follow(r)
        if r is None:
            self.rec_marks_var.set("")
        elif r.marks:
            self.rec_marks_var.set(_("Marken: {list}", list=" · ".join(fmt_duration(m) for m in r.marks)))
        else:
            self.rec_marks_var.set(_("Keine Marken – F8 während der Runde setzt eine."))

    def _rec_menu_items(self):
        """1.8.10: right click on a recording – the buttons above the table, without looking for them."""
        r = self._rec_selected()
        if r is None:
            return []
        items = [("play", _("Abspielen"), True), ("clip", _("Clip bearbeiten …"), True),
                 ("explorer", _("Im Explorer zeigen"), True), ("copy", _("Datei kopieren (zum Einfügen)"), True), None,
                 ("keep", _("Behalten"), True, bool(r.keep)), ("farming", _("Farming-Runde"), True, bool(r.farming)),
                 None]
        if r.yt:                                                                   # 1.10
            items += [("yt_link", _("YouTube-Link kopieren"), True), ("yt_open", _("Auf YouTube öffnen"), True), None]
        else:
            items += [("youtube", _("Auf YouTube hochladen"), self._rec_uploadable(r)), None]
        return items + [("delete", _("Aufnahme löschen"), True)]

    def _rec_menu_act(self, ident):
        r = self._rec_selected()
        act = {"play": self._rec_play, "clip": self._rec_clip, "explorer": self._rec_explorer,
               "copy": self._rec_copy, "keep": self._rec_keep, "farming": self._rec_farming,
               "delete": self._rec_delete, "youtube": self._rec_youtube,
               "yt_link": lambda: self._yt_copy_link(r.yt) if r is not None and r.yt else None,
               "yt_open": lambda: self._yt_open_link(r.yt) if r is not None and r.yt else None}.get(ident)
        if act is not None:
            act()

    def _rec_uploadable(self, r) -> bool:
        return self._yt_ready() and not r.yt and r.file not in self._yt_queued

    def _rec_youtube(self):
        """1.10: the marked recording into the upload queue (rounds only on request, never by themselves)."""
        r = self._rec_selected()
        if r is not None and self._rec_uploadable(r):
            self._yt_enqueue("round", r.file, r.label, r.role, r.killer, r.t, r.end - r.t if r.end > r.t else 0.0)
            self._rec_buttons()

    def _rec_path(self, r):
        folder = self.recorder.folder()
        return obsrec.rel_path(folder, r.file) if folder else None

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

    def _rec_copy(self):
        r = self._rec_selected()
        if r is not None:
            self._copy_file(self._rec_path(r), r.file)

    def _rec_farming(self):
        """1.8.60: the round of the recording as a farming round (or not) – the same as in Statistik → Letzte
        Runden: the statistics and the recording's folder follow."""
        r = self._rec_selected()
        if r is not None:
            self._stats_toggle_farming([r.t])
            self._rec_dirty = True

    def _rec_delete(self):
        r = self._rec_selected()
        if r is None:
            return
        if not self._ask(_("Aufnahme löschen"), _("{file} von der Platte löschen?", file=r.file), self._rec_delete):
            return
        self.recorder.delete(r.t)

    def _rec_clip(self, at=None):
        """1.5.1: the clip editor for the marked recording (its own top-level window; several may be open).
        ``at`` (1.8.8) = (start, end, position) taken over from the compact preview."""
        r = self._rec_selected()
        path = self._rec_editable(r)
        if path is None:
            return
        win = self._clip_window(r, path)
        if at is not None and win.info.ok:
            start, end, pos = at
            win.timeline.set_range(start, end)
            win._show_range()
            win.goto(pos)
        self._clip_windows = [w for w in self._clip_windows if w.isVisible()] + [win]
        win.show()
        win.raise_()
        win.activateWindow()

    def _rec_editable(self, r, quiet=False):
        """The path of recording ``r`` if a clip can be made of it, else None (logged unless ``quiet``)."""
        path = self._rec_path(r) if r is not None else None
        if path is None:
            return None
        if not os.path.exists(path):
            if not quiet:
                self._log(_("Aufnahme fehlt: {file}", file=r.file), "Fehler")
            return None
        if obsrec.ffmpeg_exe() is None:
            if not quiet:
                self._log(_("ffmpeg fehlt (Paket imageio-ffmpeg) – start.bat installiert es beim nächsten Start; "
                            "bis dahin bleibt der Vorlauf eine eigene Datei."), "Fehler")
            return None
        return path

    def _clip_window(self, r, path, **extra):
        from .clipedit import CLIPS_DIR
        from .qt_clip import ClipWindow
        win = ClipWindow(path, r.marks, os.path.join(self.recorder.folder(), CLIPS_DIR),   # one "Clips" for all
                         mode=str(self.settings.get("clip_mode", "copy")), sound=bool(self.settings.get("clip_sound", True)),
                         on_setting=self.settings.set, log=self._log,
                         dark=bool(self.settings.get("dark_mode", True)),
                         qss=getattr(self.qt, "_qss", "") if self.qt is not None else "",
                         target_mb=int(self.settings.get("clip_target_mb", 10) or 10),
                         censor_on=bool(self.settings.get("clip_censor_on", False)),          # 1.7.2
                         censor_style=str(self.settings.get("clip_censor_style", "pixel")),
                         censor_boxes=self.settings.get("clip_censor_boxes") or [],
                         mix_on=self.settings.get("clip_mix_on") or {},                           # 1.8.6
                         mix_vol=self.settings.get("clip_mix_vol") or {},
                         sources=(r.extra or {}).get("sources"), **extra)                   # 1.8.23
        win.on_saved = lambda out: self._clip_saved(r, out, win)              # 1.8.13: into the clips list
        return win

    def _rec_preview_follow(self, r):
        """1.8.8: the compact editor beside the table follows the marked recording – a new one for another
        recording, hidden without one (or when the file is missing / ffmpeg is not there)."""
        if self.qt is None:
            return
        host = self.qt.host(str(self.rec_host))
        if host is None:
            return
        t = r.t if r is not None else None
        if t == self._rec_preview_t and (t is None or host.content is not None):
            return
        self._rec_preview_t = t
        job = getattr(self, "_rec_preview_job", None)
        if job is not None:
            self.root.after_cancel(job)
            self._rec_preview_job = None
        path = self._rec_editable(r, quiet=True) if r is not None else None
        if path is None:
            host.set_content(None)
            self.rec_host.pack_forget()
            return
        # 1.8.11: built a moment later – marking row after row (arrow keys, quick clicks) started ffmpeg for each
        # one in the window's thread and the marking lagged; now only the row that stays marked is loaded
        self._rec_preview_job = self.root.after(PREVIEW_DELAY_MS, lambda: self._rec_preview_build(host, r, path))

    def _rec_preview_build(self, host, r, path):
        self._rec_preview_job = None
        if self._rec_preview_t != r.t:
            return
        win = self._clip_window(r, path, compact=True, parent=host,
                                on_expand=lambda s, e, p: self._rec_clip(at=(s, e, p)))
        host.set_content(win)
        self.rec_host.pack(side="left", fill="both")

    def _rec_preview_stop(self):
        """1.8.8: the recordings tab was left – the preview stops playing."""
        host = self.qt.host(str(self.rec_host)) if self.qt is not None and hasattr(self, "rec_host") else None
        if host is not None and host.content is not None:
            host.content.stop()

    def _rec_changed(self, d):
        """Recorder → "changed" (keep / delete from this tab): re-read on the next tick, log the deletion."""
        self._rec_dirty = True
        if d.get("what") == "clip_delete":
            self._log(_("Clip gelöscht: {file}", file=d.get("file", "")), "System")
        if d.get("what") == "keep":
            self._log(_("Aufnahme wird behalten: {file}", file=d.get("file", "")) if d.get("on")
                      else _("Aufnahme wird nicht mehr behalten: {file}", file=d.get("file", "")), "System")


def clip_round(c, recs) -> SimpleNamespace:
    """1.8.60: what the clip editor needs of a round, for clip ``c``: the round it came from (``c.source``), its
    map/role/killer, the sources OBS had on their own tracks then (from the recording, if still in ``recs``).
    No marks – they count from the start of the recording, not of the clip."""
    rec = next((r for r in recs if c.source and r.t == c.source), None)
    return SimpleNamespace(t=c.source, marks=[], extra={"sources": (rec.extra or {}).get("sources")} if rec else {},
                           map_id=c.map_id, label=c.label, role=c.role, killer=c.killer, farming=c.farming)
