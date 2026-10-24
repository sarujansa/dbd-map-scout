"""1.8.91 (user: "Mach für Export so ein Fenster, wo ich alles auswählen kann, Killer, Zeit etc."): the export dialog.

Statistik → "Exportieren …" opens a window of the UI model (like "Kartenbild hinzufügen"): time range with presets
or a typed from/to, the filters (role, killer, map, region, custom games and farming rounds in or out), the columns
and the format – CSV for Excel or a plain text list – with a live count and preview; the result goes to the
clipboard or into a file. The maths is in roundexport.py. Mixin of App (never imports app.py).
"""
from __future__ import annotations

import logging
import time

from . import history, roundexport, tooltip
from . import uimodel as ui
from .i18n import _
from .lobby import killer_label

log = logging.getLogger("fogscout.export")


class ExportDialog:
    """Mixin: the statistics' export window (self.settings, self._joined, self._stats_* filters, self.catalog)."""

    def _export_open(self):
        dlg = getattr(self, "_export_dlg", None)
        if dlg is not None and dlg.winfo_exists():
            return                                   # already open
        j = self._joined()
        all_rounds = list(j.rounds)
        ctx = getattr(self, "_stats_ctx", None)
        d = self._export_dlg = ui.Toplevel(self.ui_root)
        d.title(_("Runden exportieren"))
        body = ui.Frame(d, padding=12)
        body.pack(fill="both", expand=True)

        # ---- time range: a preset fills "Von"/"Bis"; typing there makes it "Eigener Zeitraum"
        tf = ui.LabelFrame(body, text=_("Zeitraum"), padding=8)
        tf.pack(fill="x")
        self._export_presets = [(k, _(lbl)) for k, lbl in roundexport.PRESETS]
        preset = ctx.period if ctx is not None and ctx.period in dict(roundexport.PRESETS) else "day"
        self.export_preset_var = ui.StringVar(value=dict(self._export_presets)[preset])
        row = ui.Frame(tf)
        row.pack(fill="x")
        cb = ui.Combobox(row, textvariable=self.export_preset_var, values=[lbl for _k, lbl in self._export_presets],
                         state="readonly", width=20)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: self._export_preset_changed())
        row2 = ui.Frame(tf)
        row2.pack(fill="x", pady=(6, 0))
        ui.Label(row2, text=_("Von")).pack(side="left")
        self.export_from_var = ui.StringVar(value="")
        ui.Entry(row2, textvariable=self.export_from_var, width=18).pack(side="left", padx=(6, 14))
        ui.Label(row2, text=_("Bis")).pack(side="left")
        self.export_to_var = ui.StringVar(value="")
        ui.Entry(row2, textvariable=self.export_to_var, width=18).pack(side="left", padx=(6, 0))
        ui.Label(tf, text=_("TT.MM.JJJJ HH:MM – auch nur ein Datum (ganzer Tag) oder nur eine Uhrzeit (heute); "
                            "leer = offen."), style="Dim.TLabel", wraplength=560).pack(anchor="w", pady=(4, 0))
        self._export_filling = False
        self._export_fill_range(preset)
        self.export_from_var.trace_add("write", lambda *a: self._export_typed())
        self.export_to_var.trace_add("write", lambda *a: self._export_typed())

        # ---- filters, prefilled with the statistics' current ones
        ff = ui.LabelFrame(body, text=_("Filter"), padding=8)
        ff.pack(fill="x", pady=(8, 0))
        fr = ui.Frame(ff)
        fr.pack(fill="x")
        self._export_roles = [("all", _("Alle Rollen")), ("killer", _("Killer")), ("survivor", _("Survivor"))]
        role = ctx.role if ctx is not None and ctx.role in ("killer", "survivor") else "all"
        self.export_role_var = ui.StringVar(value=dict(self._export_roles)[role])
        self._export_killers = [(None, _("Alle Killer"))] + [(k, killer_label(k)) for k in history.killers_used(all_rounds)]
        killer = self._stats_pick(getattr(self, "_stats_killers", ()), getattr(self, "stats_killer_var", None))
        self.export_killer_var = ui.StringVar(value=dict(self._export_killers).get(killer, self._export_killers[0][1]))
        self._export_maps = [(None, _("Alle Maps"))] + [(m, m) for m in sorted({r.map for r in all_rounds}, key=str.lower)]
        wmap = self._stats_pick(getattr(self, "_stats_maps_f", ()), getattr(self, "stats_map_var", None))
        self.export_map_var = ui.StringVar(value=dict(self._export_maps).get(wmap, self._export_maps[0][1]))
        self._export_regions = [(None, _("Alle Regionen"))] + \
            [(c, self._stats_region_name(c)) for c in history.regions_used(all_rounds)] + \
            ([(history.NO_REGION, _("ohne Region"))] if any(not r.region for r in all_rounds) else [])
        region = self._stats_pick(getattr(self, "_stats_regions", ()), getattr(self, "stats_region_var", None))
        self.export_region_var = ui.StringVar(value=dict(self._export_regions).get(region, self._export_regions[0][1]))
        for label, var, values, width in ((_("Rolle"), self.export_role_var, self._export_roles, 12),
                                          (_("Killer"), self.export_killer_var, self._export_killers, 16),
                                          (_("Map"), self.export_map_var, self._export_maps, 22),
                                          (_("Region"), self.export_region_var, self._export_regions, 16)):
            ui.Label(fr, text=label).pack(side="left", padx=(0, 4))
            c = ui.Combobox(fr, textvariable=var, values=[lbl for _k, lbl in values], state="readonly", width=width)
            c.pack(side="left", padx=(0, 12))
            c.bind("<<ComboboxSelected>>", lambda e: self._export_refresh())
        fr2 = ui.Frame(ff)
        fr2.pack(fill="x", pady=(6, 0))
        self.export_custom_var = ui.BooleanVar(value=True)
        ui.Checkbutton(fr2, text=_("Custom Games einschliessen"), variable=self.export_custom_var,
                       command=self._export_refresh).pack(side="left")
        self.export_farming_var = ui.BooleanVar(value=True)
        ui.Checkbutton(fr2, text=_("Farming-Runden einschliessen"), variable=self.export_farming_var,
                       command=self._export_refresh).pack(side="left", padx=(14, 0))

        # ---- columns (remembered)
        cf = ui.LabelFrame(body, text=_("Spalten"), padding=8)
        cf.pack(fill="x", pady=(8, 0))
        chosen = set(self.settings.get("export_columns") or roundexport.DEFAULT_COLUMNS)
        grid = ui.Frame(cf)
        grid.pack(fill="x")
        self.export_col_vars, self._export_col_checks = {}, []
        for i, (key, label) in enumerate(roundexport.COLUMNS):
            var = ui.BooleanVar(value=key in chosen)
            self.export_col_vars[key] = var
            c = ui.Checkbutton(grid, text=_(label), variable=var, command=self._export_refresh)
            c.grid(row=i // 5, column=i % 5, sticky="w", padx=(0, 12))
            self._export_col_checks.append(c)

        # ---- format, preview, buttons
        of = ui.LabelFrame(body, text=_("Format"), padding=8)
        of.pack(fill="x", pady=(8, 0))
        fmt = self.settings.get("export_format") or "csv"
        self.export_format_var = ui.StringVar(value=fmt if fmt in dict(roundexport.FORMATS) else "csv")
        for key, label in roundexport.FORMATS:
            ui.Radiobutton(of, text=_(label), variable=self.export_format_var, value=key,
                           command=self._export_refresh).pack(anchor="w")
        self.export_count_var = ui.StringVar(value="")
        ui.Label(body, textvariable=self.export_count_var).pack(anchor="w", pady=(10, 0))
        self.export_preview_var = ui.StringVar(value="")
        ui.Label(body, textvariable=self.export_preview_var, style="Dim.TLabel", wraplength=580).pack(anchor="w")
        self.export_msg_var = ui.StringVar(value="")
        ui.Label(body, textvariable=self.export_msg_var, style="Dim.TLabel", wraplength=580).pack(anchor="w", pady=(4, 0))
        br = ui.Frame(body)
        br.pack(fill="x", pady=(10, 0))
        ui.Button(br, text=_("In Zwischenablage kopieren"), command=self._export_copy).pack(side="left")
        ui.Button(br, text=_("Als Datei speichern …"), command=self._export_save).pack(side="left", padx=6)
        ui.Button(br, text=_("Schliessen"), command=d.destroy).pack(side="right")
        d.bind("<Escape>", lambda e: d.destroy())
        self._export_refresh()
        tooltip.attach_all(d, self._tip_lookup)
        self._dialog(d)

    @staticmethod
    def _stats_pick(pairs, var):
        """The key the statistics' filter box shows now (None = all / not there)."""
        if var is None:
            return None
        return next((k for k, lbl in pairs if lbl == var.get()), None)

    def _export_fill_range(self, preset: str):
        since, until = roundexport.preset_range(preset, time.time())
        self._export_filling = True
        try:
            if preset != "custom":
                self.export_from_var.set(roundexport.fmt_when(since) if since is not None else "")
                self.export_to_var.set(roundexport.fmt_when(until) if until is not None else "")
        finally:
            self._export_filling = False

    def _export_preset_changed(self):
        key = next((k for k, lbl in self._export_presets if lbl == self.export_preset_var.get()), "custom")
        self._export_fill_range(key)
        self._export_refresh()

    def _export_typed(self):
        """Typing into Von/Bis: the preset box says "Eigener Zeitraum"."""
        if getattr(self, "_export_filling", False):
            return
        self.export_preset_var.set(dict(self._export_presets)["custom"])
        self._export_refresh()

    def _export_filter(self):
        """The Filter the widgets describe, or None (with a message) when a time cannot be read."""
        try:
            since = roundexport.parse_when(self.export_from_var.get())
            until = roundexport.parse_when(self.export_to_var.get(), end=True)
        except ValueError as e:
            self.export_msg_var.set(_("Zeitangabe nicht lesbar: „{text}“ – Format TT.MM.JJJJ HH:MM.", text=e))
            return None
        pick = lambda pairs, var: next((k for k, lbl in pairs if lbl == var.get()), None)   # noqa: E731
        return roundexport.Filter(since=since, until=until, role=pick(self._export_roles, self.export_role_var) or "all",
                                  killer=pick(self._export_killers, self.export_killer_var),
                                  map_label=pick(self._export_maps, self.export_map_var),
                                  region=pick(self._export_regions, self.export_region_var),
                                  custom=bool(self.export_custom_var.get()), farming=bool(self.export_farming_var.get()))

    def _export_names(self) -> roundexport.Names:
        def realm(map_id):
            m = self.catalog.maps.get(map_id)
            return self.catalog.realm_display(m) if m is not None else ""
        return roundexport.Names(role=self._role_name, region=self._stats_region_name, realm=realm)

    def _export_refresh(self):
        """Every change: the rows anew, the count and the first lines; columns and format are remembered."""
        dlg = getattr(self, "_export_dlg", None)
        if dlg is None or not dlg.winfo_exists():
            return
        keys = [k for k, _lbl in roundexport.COLUMNS if self.export_col_vars[k].get()]
        fmt = self.export_format_var.get()
        if list(keys) != list(self.settings.get("export_columns") or ()) or fmt != self.settings.get("export_format"):
            self.settings.set("export_columns", keys)
            self.settings.set("export_format", fmt)
            self._save_soon()
        self.export_msg_var.set("")
        flt = self._export_filter()
        if flt is None:
            self._export_rows, self._export_head = [], []
            self.export_count_var.set("")
            self.export_preview_var.set("")
            return
        j = self._joined()
        rounds = roundexport.select(j.rounds, flt)
        self._export_head = roundexport.header(keys)
        self._export_rows = roundexport.table(rounds, j.off, keys, self._export_names())
        self.export_count_var.set(_("{n} Runden, {m} Spalten", n=len(rounds), m=len(keys)))
        self.export_preview_var.set(roundexport.preview(fmt, self._export_head, self._export_rows) if keys else "")

    def _export_text(self) -> str:
        if self.export_format_var.get() == "csv":
            return roundexport.csv_text(self._export_head, self._export_rows)
        return "\n".join(roundexport.text_lines(self._export_rows))

    def _export_copy(self):
        self._export_refresh()
        rows = getattr(self, "_export_rows", [])
        if not rows or not self._export_head:
            self.export_msg_var.set(_("Nichts zu kopieren – keine Runde passt, oder keine Spalte gewählt."))
            return
        self.root.clipboard_set(self._export_text())
        self.export_msg_var.set(_("{n} Runden in die Zwischenablage kopiert.", n=len(rows)))

    def _export_save(self, path=None):
        if path is None:
            self._export_refresh()
            if not getattr(self, "_export_rows", None) or not self._export_head:
                self.export_msg_var.set(_("Nichts zu speichern – keine Runde passt, oder keine Spalte gewählt."))
                return
            csv_fmt = self.export_format_var.get() == "csv"
            self._qt_file("save", _("Runden exportieren"), "fogscout-runden.csv" if csv_fmt else "fogscout-runden.txt",
                          self._export_save, pattern="CSV (*.csv)" if csv_fmt else "Text (*.txt)")
            return
        try:
            n = roundexport.write(path, self.export_format_var.get(), self._export_head, self._export_rows)
        except OSError as e:
            self._log(_("Export fehlgeschlagen: {error}", error=e), "Fehler")
            self.export_msg_var.set(_("Export fehlgeschlagen: {error}", error=e))
            return
        self._log(_("{n} Runden exportiert: {path}", n=n, path=path), "System")
        self.export_msg_var.set(_("{n} Runden exportiert: {path}", n=n, path=path))
