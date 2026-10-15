"""Tab „Einstellungen“: language, tray/autostart, updates, backup of the settings.

Mixin of App (app.py) – the methods use App's attributes; split out of app.py unchanged."""
from __future__ import annotations

import logging
import os
import threading
from . import __version__, i18n, qt_theme
from . import uimodel as ui
from .capture import IS_WIN
from . import autostart
from .connwatch import is_admin
from .i18n import N_, _
from .app_hotkeys import HOTKEY_LABELS

log = logging.getLogger("dbdmapscout")


class SettingsTab:
    # --------------------------------------------------------- tab: settings
    def _tab_settings(self):
        outer, f = self._scroll_tab()
        hk = self._reg("st.hotkeys", ui.LabelFrame(f, text=_("Hotkeys"), padding=8))
        hk.pack(fill="x")
        self.hk_buttons = {}
        self._hk_rec, self._hk_mods = None, set()
        grid = ui.Frame(hk)
        grid.pack(fill="x")
        for i, (key, label) in enumerate(HOTKEY_LABELS):
            self._reg(f"st.hk.{key}.label", ui.Label(grid, text=_(label))).grid(row=i, column=0, sticky="w", pady=1)
            b = self._reg(f"st.hk.{key}", ui.Button(grid, width=22, command=lambda k=key: self._hk_begin(k)))
            b._dbdms_recording = lambda k=key: self._hk_rec == k        # for the Qt window
            b.grid(row=i, column=1, sticky="w", padx=(10, 0), pady=1)
            self.hk_buttons[key] = b
        self._hk_show_all()
        r = ui.Frame(hk)
        r.pack(fill="x", pady=(6, 0))
        self._reg("st.hk_defaults", ui.Button(r, text=_("Standard"), command=self._hk_defaults)).pack(side="left")
        self.hk_status = ui.StringVar(value=_("Zum Ändern anklicken und die neue Tastenkombination drücken."))
        self._reg("st.hk_status", ui.Label(r, textvariable=self.hk_status, style="Dim.TLabel",
                                            wraplength=300)).pack(side="left", padx=8)

        nt = self._reg("st.notify", ui.LabelFrame(f, text=_("Benachrichtigungen"), padding=8))
        nt.pack(fill="x", pady=(8, 0))
        self.notify_vars = {}
        for key, label in (("lobby_notify", N_("Ton und Meldung, wenn eine Lobby gefunden wurde")),
                           ("lobby_remind", N_("Erinnern, wenn der Lobby-Countdown abläuft und READY noch nicht "
                                               "gedrückt ist")),
                           ("notify_background_only", N_("Nur wenn DBD nicht das aktive Fenster ist"))):
            v = self.notify_vars[key] = ui.BooleanVar(value=bool(self.settings.get(key, True)))
            self._reg(f"st.{key}", ui.Checkbutton(nt, text=_(label), variable=v,
                                                   command=self._notify_flags_changed)).pack(anchor="w")
        self._reg("st.notify_text", ui.Label(nt, text=_("Die Meldung erscheint unten rechts über allen Fenstern – auch bei „Nicht stören“ – und "
                             "nimmt dem aktiven Fenster nicht den Fokus. Klick darauf schliesst sie."),
                  style="Dim.TLabel", wraplength=400)).pack(anchor="w", padx=(22, 0))
        self._reg("st.notify_test", ui.Button(
            nt, text=_("Meldung testen"), command=lambda: self._notify(
                _("Lobby gefunden"), _("nach {time}", time="04:12") + " – " + _("READY drücken."), force=True))).pack(
            anchor="w", pady=(6, 0))

        st = self._reg("st.start", ui.LabelFrame(f, text=_("Start und Infobereich"), padding=8))
        st.pack(fill="x", pady=(8, 0))
        self.tray_var = ui.BooleanVar(value=self.settings.get("tray", True))
        self._reg("st.tray", ui.Checkbutton(st, text=_("Beim Minimieren in den Infobereich (neben der Uhr)"),
                                             variable=self.tray_var, command=self._tray_flag_changed)).pack(anchor="w")
        self.autostart_var = ui.BooleanVar(value=False)
        self.autostart_cb = self._reg("st.autostart", ui.Checkbutton(
            st, text=_("Mit Windows starten (im Infobereich, ohne Windows-Abfrage)"), variable=self.autostart_var,
            command=self._autostart_changed))
        self.autostart_cb.pack(anchor="w", pady=(2, 0))
        self.autostart_cb.state(["disabled"])
        self.autostart_info = ui.StringVar(value="")
        self._reg("st.autostart_info", ui.Label(st, textvariable=self.autostart_info, style="Dim.TLabel",
                                                 wraplength=400)).pack(anchor="w", padx=(22, 0))
        self._reg("st.setup_again", ui.Button(st, text=_("Einrichtung starten"),
                                               command=lambda: self.qt is not None and self.qt.show_setup(True))
                  ).pack(anchor="w", pady=(6, 0))

        look = self._reg("st.look", ui.LabelFrame(f, text=_("Sprache und Darstellung"), padding=8))
        look.pack(fill="x", pady=(8, 0))
        lr = ui.Frame(look)
        lr.pack(fill="x")
        self._reg("st.lang.label", ui.Label(lr, text="Sprache / Language")).pack(side="left")
        cur = self.settings.get("ui_language", "auto")
        self._ui_langs = [(code, _(label) if code == "auto" else label) for code, label in i18n.LANGUAGES]
        self.ui_lang_var = ui.StringVar(value=dict(self._ui_langs).get(cur, self._ui_langs[0][1]))
        lcb = self._reg("st.lang", ui.Combobox(lr, textvariable=self.ui_lang_var,
                                                values=[lbl for _c, lbl in self._ui_langs], state="readonly", width=30))
        lcb.pack(side="left", padx=8)
        lcb.bind("<<ComboboxSelected>>", lambda e: self._ui_lang_changed())
        self.ui_lang_note = ui.StringVar(value="")
        self._reg("st.lang_note", ui.Label(look, textvariable=self.ui_lang_note, style="Dim.TLabel",
                                            wraplength=400)).pack(anchor="w")
        self.dark_var = ui.BooleanVar(value=self.settings.get("dark_mode", True))
        self._reg("st.dark", ui.Checkbutton(look, text=_("Dark Mode"), variable=self.dark_var,
                                             command=self._dark_changed)).pack(anchor="w", pady=(4, 0))
        tr = ui.Frame(look)
        tr.pack(fill="x", pady=(6, 0))
        self._reg("st.theme.label", ui.Label(tr, text=_("Farbthema"))).pack(side="left")
        self._themes = [(k, _(label)) for k, (label, _c) in qt_theme.THEMES.items()]
        self.theme_var = ui.StringVar(value=dict(self._themes).get(self.settings.get("color_theme", "gold"),
                                                                   self._themes[0][1]))
        tcb = self._reg("st.theme", ui.Combobox(tr, textvariable=self.theme_var, state="readonly", width=18,
                                                 values=[lbl for _k, lbl in self._themes]))
        tcb.pack(side="left", padx=8)
        tcb.bind("<<ComboboxSelected>>", lambda e: self._theme_changed())
        self.oled_var = ui.BooleanVar(value=bool(self.settings.get("oled_black", False)))
        self._reg("st.oled", ui.Checkbutton(look, text=_("OLED-Schwarz (echtes Schwarz statt Grau im Dark Mode)"),
                                            variable=self.oled_var, command=self._theme_changed)
                  ).pack(anchor="w", pady=(4, 0))
        zr = ui.Frame(look)
        zr.pack(fill="x", pady=(6, 0))
        self._reg("st.zoom.label", ui.Label(zr, text=_("Schriftgröße"))).pack(side="left")
        self._zooms = [(z, f"{z:.0%}") for z in qt_theme.ZOOMS]
        zoom = float(self.settings.get("ui_zoom", 1.0))
        self.zoom_var = ui.StringVar(value=dict(self._zooms).get(zoom, "100%"))
        zcb = self._reg("st.zoom", ui.Combobox(zr, textvariable=self.zoom_var, values=[lbl for _z, lbl in self._zooms],
                                                state="readonly", width=8))
        zcb.pack(side="left", padx=8)
        zcb.bind("<<ComboboxSelected>>", lambda e: self._zoom_changed())
        ar = ui.Frame(look)
        ar.pack(fill="x", pady=(6, 0))
        self._reg("st.card_reset", ui.Button(ar, text=_("Anordnung zurücksetzen"),
                                              command=self._card_order_reset)).pack(side="left")
        self._reg("st.card_hint", ui.Label(ar, text=_("Die Kästen der Seiten lassen sich am Griff rechts im Titel "
                                                       "verschieben."), style="Dim.TLabel")).pack(side="left", padx=8)

        upd = self._reg("st.updates", ui.LabelFrame(f, text=_("Updates"), padding=8))
        upd.pack(fill="x", pady=(8, 0))
        self.update_var = ui.BooleanVar(value=self.settings.get("auto_update", True))
        self._reg("st.update", ui.Checkbutton(upd, text=_("Beim Start nach Updates suchen und installieren (GitHub)"),
                                               variable=self.update_var, command=self._update_flag_changed)).pack(
            anchor="w")
        self._reg("st.update_note", ui.Label(upd, text=_("nur über start.bat bzw. die Desktop-Verknüpfung; eigene "
                                                          "Änderungen werden nie überschrieben"), style="Dim.TLabel",
                                              wraplength=400)).pack(anchor="w", padx=(22, 0))
        ur = ui.Frame(upd)
        ur.pack(fill="x", pady=(6, 0))
        self.upd_btn = self._reg("st.upd_btn", ui.Button(ur, text=_("Jetzt nach Updates suchen"),
                                                          command=self.check_update))
        self.upd_btn.pack(side="left")
        self.upd_apply_btn = self._reg("st.upd_apply", ui.Button(ur, text=_("Aktualisieren und neu starten"),
                                                                  command=self.apply_update))
        self.upd_status = ui.StringVar(value="")
        self._reg("st.upd_status", ui.Label(upd, textvariable=self.upd_status, wraplength=420,
                                             justify="left")).pack(anchor="w", pady=(4, 0))

        # rarely needed: folded away (like "Erweitert" in the detection tab)
        self.more_btn = self._reg("st.more_btn", ui.Button(f, command=self._toggle_more))
        self.more_btn.pack(anchor="w", pady=(10, 0))
        more = self.more_frame = ui.Frame(f)
        own = self._reg("st.more.own", ui.LabelFrame(more, text=_("Eigene Map-Zuordnungen"), padding=8))
        own.pack(fill="x")
        self.alias_var = ui.StringVar(value="")
        self._reg("st.more.aliases", ui.Label(own, textvariable=self.alias_var, style="Dim.TLabel",
                                               wraplength=300)).pack(side="left", fill="x")
        self._reg("st.more.aliases_clear", ui.Button(own, text=_("Alle löschen"),
                                                      command=self._clear_aliases)).pack(side="right")
        self._show_aliases()

        om = self._reg("st.more.official", ui.LabelFrame(more, text=_("Offizielle Match-Daten"), padding=8))
        om.pack(fill="x", pady=(8, 0))
        self.off_open_var = ui.BooleanVar(value=self.settings.get("official_open_after_dbd", False))
        self._reg("st.more.off_open", ui.Checkbutton(om, text=_("Stats-Seite öffnen, wenn DBD beendet wird"),
                                                      variable=self.off_open_var,
                                                      command=self._official_setting)).pack(anchor="w")
        self.off_notify_var = ui.BooleanVar(value=self.settings.get("official_notify", True))
        self._reg("st.more.off_notify", ui.Checkbutton(
            om, text=_("Meldung, wenn Match-Daten eingelesen und gelöscht wurden"), variable=self.off_notify_var,
            command=self._official_setting)).pack(anchor="w")
        self._reg("st.more.script", ui.Button(om, text=_("Userscript kopieren"),
                                               command=self._official_copy_script)).pack(anchor="w", pady=(6, 0))
        self._reg("st.more.off_text", ui.Label(om, text=_("Einmal einrichten: Tampermonkey im Browser installieren, „Userscript kopieren“ und dort "
                             "als neues Skript einfügen, auf stats.deadbydaylight.com anmelden. Beim Öffnen der Seite "
                             "speichert das Skript die letzten 30 Matches im Download-Ordner; das Programm liest die "
                             "Datei und löscht sie. Es geht dafür selbst nicht ins Internet."),
                  style="Dim.TLabel", wraplength=420)).pack(anchor="w", pady=(4, 0))

        bk = self._reg("st.more.backup", ui.LabelFrame(more, text=_("Sicherung"), padding=8))
        bk.pack(fill="x", pady=(8, 0))
        self._reg("st.more.export", ui.Button(bk, text=_("Einstellungen exportieren …"),
                                               command=self._export_settings)).pack(side="left")
        self._reg("st.more.import", ui.Button(bk, text=_("Einstellungen importieren …"),
                                               command=self._import_settings)).pack(side="left", padx=6)

        folders = self._reg("st.more.folders", ui.LabelFrame(more, text=_("Ordner"), padding=8))
        folders.pack(fill="x", pady=(8, 0))
        self._reg("st.more.dir", ui.Button(folders, text=_("Programmordner öffnen"),
                                            command=lambda: self._open(self.root_dir))).pack(side="left")
        self._reg("st.more.maps_dir", ui.Button(folders, text=_("Karten-Ordner öffnen"),
                                                 command=lambda: self._open(os.path.join(self.root_dir, "maps")))).pack(
            side="left", padx=6)
        self.version_label = self._reg("st.version", ui.Label(f, text=f"DbD Map Scout {__version__} · " + _("liest nur Bildschirmpixel, sendet keine Eingaben ans Spiel."),
                  style="Dim.TLabel", wraplength=430))
        self.version_label.pack(anchor="w", pady=(10, 0))
        self._more_open = False
        self._show_more()
        return outer

    def _toggle_more(self):
        self._more_open = not self._more_open
        self._show_more()

    def _show_more(self):
        arrow = "▾ " if self._more_open else "▸ "
        self.more_btn.configure(text=arrow + _("Mehr (Map-Zuordnungen, Match-Daten, Sicherung, Ordner)"))
        if self._more_open:
            self.more_frame.pack(fill="x", pady=(4, 0), before=self.version_label)
        else:
            self.more_frame.pack_forget()

    def _export_settings(self, path=None):
        if path is None:                            # the window asks for the file and calls again
            self._qt_file("save", _("Einstellungen exportieren"), "dbdmapscout-einstellungen.json",
                          self._export_settings)
            return
        from .config import export_settings
        try:
            export_settings(self.settings.data, path)
        except OSError as e:
            self._log(_("Export fehlgeschlagen: {error}", error=e), "Fehler")
            return
        self._log(_("Einstellungen gesichert: {path}", path=path), "System")

    def _import_settings(self, path=None):
        if path is None:
            self._qt_file("open", _("Einstellungen importieren"), "", self._import_settings)
            return
        from .config import read_backup
        try:
            data = read_backup(path, self.settings.data)
        except ValueError as e:
            self._inform(_("Einstellungen importieren"),
                         _("Das ist keine Einstellungsdatei von DbD Map Scout ({error}).", error=e))
            return
        if not self._ask(_("Einstellungen importieren"),
                         _("Alle Einstellungen durch die aus der Datei ersetzen? Das Programm startet danach neu."),
                         lambda: self._import_settings(path)):
            return
        self.settings.data = data
        self.settings.save()
        self.settings.frozen = True                 # the running program must not write its old values back
        self._log(_("Einstellungen importiert aus {path}.", path=path), "System")
        from . import restart
        try:
            ok = restart.spawn_helper(self.root_dir)
        except OSError:
            ok = False
        if ok:
            self.quit()
        else:
            self._inform(_("Einstellungen importieren"), _("Bitte das Programm jetzt neu starten."))

    def _theme_changed(self):
        key = next((k for k, lbl in self._themes if lbl == self.theme_var.get()), "gold")
        self.settings.set("color_theme", key)
        self.settings.set("oled_black", bool(self.oled_var.get()))
        self._save_soon()
        self._apply_theme()

    def _card_order_reset(self):
        """The cards of all pages back in their built-in order."""
        self.settings.set("card_order", {})
        self._save_soon()
        if self.qt is not None:
            self.qt.set_card_order({})

    def _zoom_changed(self):
        zoom = next((z for z, lbl in self._zooms if lbl == self.zoom_var.get()), 1.0)
        self.settings.set("ui_zoom", zoom)
        self._save_soon()
        self._qt_theme()

    def _ui_lang_changed(self):
        code = next((c for c, lbl in self._ui_langs if lbl == self.ui_lang_var.get()), "auto")
        self.settings.set("ui_language", code)
        self._save_soon()
        changed = i18n.resolve(code) != i18n.current()
        self.ui_lang_note.set(_("Wirkt nach dem nächsten Start des Programms.") if changed else "")
        if changed:
            self._log(_("Sprache geändert – wirkt nach dem nächsten Start des Programms."), "System")

    # ---------------------------------------------------------- tray and autostart
    def _tray_start(self):
        if not self.tray.active and not self.tray.start():
            self._log(_("Symbol im Infobereich nicht verfügbar ({error}) – Minimieren wie gewohnt.",
                        error=self.tray.error), "Fehler")

    def _tray_flag_changed(self):
        on = bool(self.tray_var.get())
        self.settings.set("tray", on)
        self._save_soon()
        if on and IS_WIN:
            self._tray_start()
        elif not on:
            self.tray.stop()

    def _setup_then_read_autostart(self):
        """Thread: create/renew task, icon and shortcuts if needed, and the logon task unless autostart was
        switched off (only as administrator, no prompt), then read the autostart state for the settings tab."""
        if IS_WIN and is_admin():
            try:
                res = autostart.ensure(self.root_dir, self.settings.get("setup_version"),
                                       self.settings.get("setup_root"))
            except Exception as e:
                res = (False, f"{type(e).__name__}: {e}")
            if res is not None:
                self.events.put(("setup_done", res[0], res[1]))
            try:
                auto = autostart.ensure_autostart(self.root_dir, self.settings.get("autostart", True))
            except Exception as e:
                auto = (False, f"{type(e).__name__}: {e}")
            if auto is not None:
                self.events.put(("status_log", _(
                    "Startet ab jetzt mit Windows im Infobereich (abschaltbar unter Einstellungen → Start und "
                    "Infobereich).") if auto[0] else _("Autostart mit Windows fehlgeschlagen: {error}", error=auto[1])))
        elif IS_WIN and not autostart.task_exists(autostart.TASK):
            self.events.put(("setup_done", None, _(
                "Tipp: Einmal als Administrator starten (Rechtsklick auf start.bat → „Als Administrator ausführen“) "
                "– dann richtet das Programm die Desktop-Verknüpfung ein, die künftig ohne Windows-Abfrage startet.")))
        self._read_autostart()

    def _setup_done(self, ok, msg):
        if ok:
            self.settings.set("setup_version", autostart.SETUP_VERSION)
            self.settings.set("setup_root", os.path.abspath(self.root_dir))
            self._save_soon()
            self._log(_("Desktop-Verknüpfung eingerichtet/aktualisiert: startet ab jetzt ohne Windows-Abfrage."),
                      "System")
        elif ok is None:
            self._log(msg, "System")
        else:
            self._log(_("Einrichtung der Verknüpfung fehlgeschlagen: {error}", error=msg), "Fehler")

    def _read_autostart(self):
        """Runs in a thread: does the logon task exist, may we change it (administrator)?"""
        if not IS_WIN:
            self.events.put(("autostart", None, False, _("Nur unter Windows.")))
            return
        exists = autostart.task_exists(autostart.TASK_AUTO)
        admin = is_admin()
        info = ("" if admin else _("Änderbar, wenn das Programm über die Desktop-Verknüpfung gestartet wurde "
                                   "(verknuepfung_erstellen.bat einmal ausführen)."))
        self.events.put(("autostart", exists, admin, info))

    def _autostart_state(self, exists, can_change, info):
        self.autostart_var.set(bool(exists))
        self.autostart_cb.state(["!disabled"] if can_change else ["disabled"])
        self.autostart_info.set(info)

    def _autostart_changed(self):
        on = bool(self.autostart_var.get())
        self.settings.set("autostart", on)         # switched off stays off (else it is set up again at start)
        self._save_soon()
        self.autostart_cb.state(["disabled"])
        self.autostart_info.set(_("Wird eingerichtet …"))
        root_dir = self.root_dir

        def work():
            ok, out = autostart.set_autostart(root_dir, on)
            if ok:
                msg = (_("Startet ab jetzt mit Windows im Infobereich.") if on
                       else _("Startet nicht mehr mit Windows."))
            else:
                msg = _("Fehlgeschlagen: {error}", error=out)
            self.events.put(("autostart", on if ok else not on, True, msg))
            self.events.put(("status_log", msg))
        threading.Thread(target=work, daemon=True, name="autostart").start()

    # ---------------------------------------------------------- updates (done by start.bat)
    def check_update(self):
        """Button: ask GitHub (git fetch) whether there is something new – only on this click."""
        from . import update
        self.upd_btn.state(["disabled"])
        self.upd_apply_btn.pack_forget()
        self.upd_status.set(_("Suche nach Updates …"))

        def work():
            try:
                res = update.check(self.root_dir)
            except Exception as e:
                res = ("error", f"{type(e).__name__}: {e}", False)
            self.events.put(("upd_check",) + tuple(res))
        threading.Thread(target=work, daemon=True, name="update-check").start()

    def _update_checked(self, state, msg, can_apply):
        self.upd_btn.state(["!disabled"])
        self.upd_status.set(msg)
        self._log(msg.splitlines()[0] if msg else "", "System")
        if state == "available" and can_apply:
            self.upd_apply_btn.pack(side="left", padx=6)

    def apply_update(self):
        from . import restart
        try:
            ok = restart.spawn_helper(self.root_dir)
        except OSError as e:
            self.upd_status.set(_("Neustart nicht möglich: {error}", error=e))
            return
        if not ok:
            self.upd_status.set(_("Nur unter Windows: bitte das Programm über start.bat neu starten."))
            return
        self._log(_("Programm startet neu und installiert das Update …"), "System")
        self.quit()

    def _update_flag_changed(self):
        self.settings.set("auto_update", bool(self.update_var.get()))
        self.settings.save()                      # start.bat reads it at the next start

    def _show_update_status(self):
        """What start.bat / update.py did before this start (update installed, skipped, packages)."""
        path = os.path.join(self.root_dir, ".venv", "update_status.txt")
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read().strip()
            os.remove(path)
        except OSError:
            return
        for line in text.splitlines():
            if line.strip():
                self._log(line.rstrip(), "System")
