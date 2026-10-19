"""Tab „Einstellungen“: language, tray/autostart, updates, backup of the settings.

Mixin of App (app.py) – the methods use App's attributes; split out of app.py unchanged."""
from __future__ import annotations

import logging
import os
import threading
import time
from . import __version__, i18n, obsrec, qt_theme, regions, status
from . import uimodel as ui
from .capture import IS_WIN, foreground_root, is_game_window
from . import autostart
from .connwatch import is_admin
from .i18n import N_, _
from .app_hotkeys import HOTKEY_LABELS
from .textnorm import fmt_duration

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
        self.swatches = self._reg("st.swatches", ui.Swatches(look, command=self._swatch_picked,
                                                             values=[(c, c) for c in qt_theme.SWATCHES]))
        self.swatches.pack(anchor="w", pady=(4, 0))
        self.swatches.dark = bool(self.settings.get("dark_mode", True))
        self._swatch_mark()
        self.oled_var = ui.BooleanVar(value=bool(self.settings.get("oled_black", False)))
        self._reg("st.oled", ui.Checkbutton(look, text=_("OLED-Schwarz (echtes Schwarz statt Grau im Dark Mode)"),
                                            variable=self.oled_var, command=self._theme_changed)
                  ).pack(anchor="w", pady=(4, 0))
        zr = ui.Frame(look)
        zr.pack(fill="x", pady=(6, 0))
        self._reg("st.zoom.label", ui.Label(zr, text=_("Schriftgrösse"))).pack(side="left")
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
        self._reg("st.more.structure", ui.Button(om, text=_("Aufbau der Match-Daten speichern"),       # 1.8.46
                                                  command=self._official_structure)).pack(anchor="w", pady=(6, 0))
        self._reg("st.more.resave", ui.Button(om, text=_("Alle Matches neu speichern"),                # 1.8.52
                                               command=self._official_resave)).pack(anchor="w", pady=(6, 0))
        self._reg("st.more.off_text", ui.Label(om, text=_("Einmal einrichten: Tampermonkey im Browser installieren, „Userscript kopieren“ und dort "
                             "als neues Skript einfügen und speichern, auf stats.deadbydaylight.com anmelden. Chrome/"
                             "Edge: in den Details der Erweiterung „Allow User Scripts“ einschalten, sonst läuft "
                             "kein Skript. Beim Öffnen der Seite speichert das Skript neue Matches (die letzten 30) im "
                             "Download-Ordner; das Programm liest die Datei und löscht sie. Es geht dafür selbst nicht "
                             "ins Internet."),
                  style="Dim.TLabel", wraplength=420)).pack(anchor="w", pady=(4, 0))

        fm = self._reg("st.more.farming", ui.LabelFrame(more, text=_("Farming-Runden"), padding=8))   # 1.2.20
        fm.pack(fill="x", pady=(8, 0))
        self.farm_cross_var = ui.BooleanVar(value=self.settings.get("farming_crossplay", True))
        self._reg("st.more.farm_cross", ui.Checkbutton(fm, text=_("Runden ohne Crossplay als Farming zählen"),
                                                        variable=self.farm_cross_var,
                                                        command=self._farming_setting)).pack(anchor="w")
        fr = ui.Frame(fm)
        fr.pack(fill="x", pady=(4, 0))
        self._reg("st.more.farm_region.label", ui.Label(fr, text=_("Alle Runden auf"), width=14)).pack(side="left")
        self._farm_regions = [("", _("(keine)"))] + [(c, _(n)) for c, n, _cont in regions.REGIONS]
        names = dict(self._farm_regions)
        self.farm_region_var = ui.StringVar(value=names.get(self.settings.get("farming_region", ""), names[""]))
        cb = self._reg("st.more.farm_region", ui.Combobox(fr, textvariable=self.farm_region_var, state="readonly",
                                                           width=22, values=[lbl for _c, lbl in self._farm_regions]))
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self._farming_setting())
        self._reg("st.more.farm_text", ui.Label(fm, text=_(
            "Farming-Runden zählen nicht zu den normalen Runden (Rollen-Filter, Wartezeiten, Bilanz, Ergebnisse) – "
            "die Statistik hat dafür den Filter „Farming“. Crossplay aus erkennt das Programm an der Weltkugel mit "
            "rotem Kreuz neben dem Lobby-Knopf; Runden auf der gewählten Region zählen immer als Farming, auch "
            "ältere. Einzelne Runden: „Farming an/aus“ unter „Letzte Runden“."),
            style="Dim.TLabel", wraplength=420)).pack(anchor="w", pady=(4, 0))

        # 1.4: round recordings with OBS (obs-websocket on this PC) on the user's external drive
        rc = self._reg("st.more.rec", ui.LabelFrame(more, text=_("Aufnahmen mit OBS"), padding=8))
        rc.pack(fill="x", pady=(8, 0))
        self.rec_on_var = ui.BooleanVar(value=bool(self.settings.get("rec_on", False)))
        self._reg("st.more.rec_on", ui.Checkbutton(rc, text=_("Jede Runde mit OBS aufnehmen"),
                                                    variable=self.rec_on_var, command=self._rec_setting)).pack(anchor="w")
        rr = ui.Frame(rc)
        rr.pack(fill="x", pady=(4, 0))
        self._reg("st.more.rec_port.label", ui.Label(rr, text=_("Port"))).pack(side="left")
        self.rec_port_var = ui.StringVar(value=str(self.settings.get("rec_port", obsrec.DEFAULT_PORT)))
        self.rec_port_var.trace_add("write", lambda *a: self._rec_setting())
        self._reg("st.more.rec_port", ui.Entry(rr, textvariable=self.rec_port_var, width=7)).pack(side="left", padx=6)
        self._reg("st.more.rec_pw.label", ui.Label(rr, text=_("Passwort"))).pack(side="left")
        self.rec_pw_var = ui.StringVar(value=str(self.settings.get("rec_password", "")))
        self.rec_pw_var.trace_add("write", lambda *a: self._rec_setting())
        pw = self._reg("st.more.rec_pw", ui.Entry(rr, textvariable=self.rec_pw_var, width=18))
        pw._dbdms_secret = True
        pw.pack(side="left", padx=6)
        self._reg("st.more.rec_test", ui.Button(rr, text=_("Verbindung testen"), command=self._rec_test)).pack(side="left")
        rd = ui.Frame(rc)
        rd.pack(fill="x", pady=(4, 0))
        self._reg("st.more.rec_dir", ui.Button(rd, text=_("Aufnahmeordner wählen …"), command=self._rec_pick_folder)).pack(side="left")
        self.rec_folder_var = ui.StringVar(value="")
        self._reg("st.more.rec_folder", ui.Label(rd, textvariable=self.rec_folder_var, style="Dim.TLabel")).pack(side="left", padx=8)
        rl = ui.Frame(rc)
        rl.pack(fill="x", pady=(4, 0))
        self._reg("st.more.rec_limit.label", ui.Label(rl, text=_("Platz für Aufnahmen"))).pack(side="left")
        self._rec_limits = [(0, _("Ganze Platte (Älteste weg, wenn sie voll wird)"))] + \
            [(gb, f"{gb} GB") for gb in obsrec.LIMITS_GB if gb]
        names = dict(self._rec_limits)
        self.rec_limit_var = ui.StringVar(value=names.get(int(self.settings.get("rec_limit_gb", 0) or 0), names[0]))
        cb = self._reg("st.more.rec_limit", ui.Combobox(rl, textvariable=self.rec_limit_var, state="readonly",
                                                         width=36, values=[lbl for _g, lbl in self._rec_limits]))
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self._rec_setting())
        self.rec_pre_var = ui.BooleanVar(value=bool(self.settings.get("rec_pre", True)))
        self._reg("st.more.rec_pre", ui.Checkbutton(rc, text=_("Vorlauf: Wiederholungspuffer von OBS beim Map-Banner sichern (Sekunden davor)"),
                                                     variable=self.rec_pre_var, command=self._rec_setting)).pack(anchor="w", pady=(4, 0))
        self.rec_buffer_var = ui.BooleanVar(value=bool(self.settings.get("rec_buffer_auto", True)))   # 1.4.1
        self._reg("st.more.rec_buffer", ui.Checkbutton(rc, text=_("Wiederholungspuffer mit DBD starten und stoppen"),
                                                        variable=self.rec_buffer_var, command=self._rec_setting)).pack(anchor="w")
        self.rec_obs_start_var = ui.BooleanVar(value=bool(self.settings.get("rec_obs_start", False)))   # 1.8.47
        self._reg("st.more.rec_obs_start", ui.Checkbutton(rc, text=_("OBS mit DBD starten, falls es noch nicht läuft"),
                                                           variable=self.rec_obs_start_var,
                                                           command=self._rec_setting)).pack(anchor="w")
        self.rec_window_var = ui.BooleanVar(value=bool(self.settings.get("rec_window", False)))   # 1.8.41
        self._reg("st.more.rec_window", ui.Checkbutton(rc, text=_("Nur das DBD-Fenster aufnehmen (Fensteraufnahme in OBS selbst einrichten)"),
                                                        variable=self.rec_window_var, command=self._rec_setting)).pack(anchor="w")
        self.rec_merge_var = ui.BooleanVar(value=bool(self.settings.get("rec_merge", True)))       # 1.4.2
        self._reg("st.more.rec_merge", ui.Checkbutton(rc, text=_("Vorlauf und Runde zu einer Datei zusammenfügen"),
                                                       variable=self.rec_merge_var, command=self._rec_setting)).pack(anchor="w")
        self.rec_early_var = ui.BooleanVar(value=bool(self.settings.get("rec_early", True)))      # 1.6
        self._reg("st.more.rec_early", ui.Checkbutton(rc, text=_("Aufnahme schon am Ende des Ladebildschirms starten (mit Spawn)"),
                                                       variable=self.rec_early_var, command=self._rec_setting)).pack(anchor="w")
        self.rec_instant_var = ui.BooleanVar(value=bool(self.settings.get("rec_instant", True)))  # 1.6
        ri = ui.Frame(rc)
        ri.pack(fill="x")
        self._reg("st.more.rec_instant", ui.Checkbutton(ri, text=_("F8 speichert die letzten Sekunden als Sofort-Clip"),
                                                         variable=self.rec_instant_var, command=self._rec_setting)).pack(side="left")
        self._rec_clips = [(s, _("{n} s", n=s)) for s in obsrec.CLIP_SECONDS]
        clips = dict(self._rec_clips)
        self.rec_clip_var = ui.StringVar(value=clips.get(int(self.settings.get("rec_clip_s", obsrec.DEFAULT_CLIP_S) or 0),
                                                         clips[obsrec.DEFAULT_CLIP_S]))
        cc = self._reg("st.more.rec_clip", ui.Combobox(ri, textvariable=self.rec_clip_var, state="readonly", width=8,
                                                        values=[lbl for _s, lbl in self._rec_clips]))
        cc.pack(side="left", padx=6)
        cc.bind("<<ComboboxSelected>>", lambda e: self._rec_setting())
        self.rec_clip_notify_var = ui.BooleanVar(value=bool(self.settings.get("rec_clip_notify", True)))   # 1.8.13
        self._reg("st.more.rec_clip_notify", ui.Checkbutton(ri, text=_("mit kurzer Meldung"),
                                                             variable=self.rec_clip_notify_var,
                                                             command=self._rec_setting)).pack(side="left", padx=(6, 0))
        self.rec_audio_var = ui.BooleanVar(value=bool(self.settings.get("rec_audio", True)))      # 1.6
        self._reg("st.more.rec_audio", ui.Checkbutton(rc, text=_("Ton in OBS einstellen, sobald DBD startet:"),
                                                       variable=self.rec_audio_var, command=self._rec_setting)).pack(anchor="w", pady=(4, 0))
        ra = ui.Frame(rc)
        ra.pack(fill="x")
        self.rec_audio_vars = {key: ui.BooleanVar(value=bool(self.settings.get("rec_audio_" + key,
                                                                               key in ("dbd", "discord"))))
                               for key in ("dbd", "discord", "desktop", "mic")}

        def sound_box(key, text):
            return ui.Checkbutton(ra, text=text, variable=self.rec_audio_vars[key], command=self._rec_audio_changed)
        self._reg("st.more.rec_audio_dbd", sound_box("dbd", _("DBD"))).pack(side="left", padx=(0, 10))
        self._reg("st.more.rec_audio_discord", sound_box("discord", _("Discord"))).pack(side="left", padx=(0, 10))
        self._reg("st.more.rec_audio_desktop", sound_box("desktop", _("Übriger Desktop-Ton"))).pack(side="left", padx=(0, 10))
        self._reg("st.more.rec_audio_mic", sound_box("mic", _("Mikrofon"))).pack(side="left")
        self.rec_tracks_var = ui.BooleanVar(value=bool(self.settings.get("rec_tracks", True)))      # 1.8.5
        self._reg("st.more.rec_tracks", ui.Checkbutton(rc, text=_("Jede Tonquelle auf eine eigene OBS-Tonspur legen (1 alles, 2 nur DBD, 3 Discord, 4 Mikrofon, 5 Hintergrund) – zum Mischen im Clip-Editor"),
                                                        variable=self.rec_tracks_var, command=self._rec_audio_changed)).pack(anchor="w", pady=(4, 0))
        self._reg("st.more.rec_tracks_hint", ui.Label(rc, text=_(
            "Dafür in OBS: Einstellungen → Ausgabe → Ausgabemodus „Erweitert“ → Reiter Aufnahme → Audiospur 1 bis 5 anhaken. "
            "Das Programm prüft das beim DBD-Start und meldet es im Status unten; es ändert nichts am OBS-Profil."),
            wraplength=420, style="Dim.TLabel")).pack(anchor="w")
        rs = ui.Frame(rc)                                                                           # 1.8.6
        rs.pack(fill="x")
        self._reg("st.more.rec_clip_src.label", ui.Label(rs, text=_("Sofort-Clip (F8) mit Ton von:"))).pack(side="left", padx=(0, 10))
        chosen = set(self.settings.get("rec_clip_sources") or ())
        self.rec_clip_src_vars = {key: ui.BooleanVar(value=key in chosen) for key in obsrec.SOURCES}
        def clip_box(key, text):
            return ui.Checkbutton(rs, text=text, variable=self.rec_clip_src_vars[key], command=self._rec_setting)
        self._reg("st.more.rec_clip_dbd", clip_box("dbd", _("Spiel"))).pack(side="left", padx=(0, 10))
        self._reg("st.more.rec_clip_discord", clip_box("discord", _("Discord"))).pack(side="left", padx=(0, 10))
        self._reg("st.more.rec_clip_mic", clip_box("mic", _("Mikrofon"))).pack(side="left", padx=(0, 10))
        self._reg("st.more.rec_clip_other", clip_box("other", _("Hintergrund"))).pack(side="left")      # 1.8.19
        self.rec_farming_var = ui.BooleanVar(value=bool(self.settings.get("rec_farming_dir", True)))   # 1.5.3
        self._reg("st.more.rec_farming", ui.Checkbutton(rc, text=_("Farming-Runden im Unterordner „Farming“ ablegen"),
                                                         variable=self.rec_farming_var, command=self._rec_setting)).pack(anchor="w")
        rf = ui.Frame(rc)                                                                           # 1.8.23
        rf.pack(fill="x", pady=(2, 0))
        self._reg("st.more.rec_farming_days.label", ui.Label(rf, text=_("Farming-Aufnahmen löschen nach"))).pack(side="left")
        self._rec_farming_days = [(0, _("nie")), *[(d, _("{n} Tagen", n=d)) for d in obsrec.FARMING_DAYS if d]]
        days = int(self.settings.get("rec_farming_days", obsrec.DEFAULT_FARMING_DAYS) or 0)
        self.rec_farming_days_var = ui.StringVar(value=dict(self._rec_farming_days).get(days, _("nie")))
        cb = self._reg("st.more.rec_farming_days", ui.Combobox(rf, textvariable=self.rec_farming_days_var, state="readonly",
                                                                width=12, values=[lbl for _d, lbl in self._rec_farming_days]))
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self._rec_setting())
        self.rec_ffmpeg_var = ui.StringVar(value="")
        self._reg("st.more.rec_ffmpeg", ui.Label(rc, textvariable=self.rec_ffmpeg_var, wraplength=420,
                                                  style="Dim.TLabel")).pack(anchor="w")
        rt = ui.Frame(rc)
        rt.pack(fill="x", pady=(4, 0))
        self._reg("st.more.rec_tail.label", ui.Label(rt, text=_("Nachlauf nach dem Rundenende"))).pack(side="left")
        self._rec_tails = [(s, _("{n} s", n=s) if s else _("keiner")) for s in obsrec.TAILS_S]
        tails = dict(self._rec_tails)
        self.rec_tail_var = ui.StringVar(value=tails.get(int(self.settings.get("rec_tail_s", obsrec.DEFAULT_TAIL_S) or 0),
                                                         tails[obsrec.DEFAULT_TAIL_S]))
        ct = self._reg("st.more.rec_tail", ui.Combobox(rt, textvariable=self.rec_tail_var, state="readonly", width=10,
                                                        values=[lbl for _s, lbl in self._rec_tails]))
        ct.pack(side="left", padx=6)
        ct.bind("<<ComboboxSelected>>", lambda e: self._rec_setting())
        self.rec_status_var = ui.StringVar(value="")
        self._reg("st.more.rec_status", ui.Label(rc, textvariable=self.rec_status_var, wraplength=420,
                                                  style="Dim.TLabel")).pack(anchor="w", pady=(4, 0))
        self._reg("st.more.rec_text", ui.Label(rc, text=_(
            "OBS nimmt auf, das Programm sagt nur wann: Start beim Map-Banner, Stopp beim erkannten Rundenende, "
            "Datei nach Datum, Map und Killer benannt. Dafür in OBS unter Werkzeuge → WebSocket-Servereinstellungen "
            "den Server einschalten und das Passwort hier eintragen; Verbindung nur auf diesem PC (127.0.0.1). "
            "Empfohlen: Aufnahmeformat MKV oder Hybrid-MP4 (bleibt bei Abbruch lesbar), Fenster- oder "
            "Bildschirmaufnahme statt Spielaufnahme. Der Ordner wird über sein Laufwerk gemerkt – ist die Platte "
            "nicht angeschlossen, wird nicht aufgenommen."),
            style="Dim.TLabel", wraplength=420)).pack(anchor="w", pady=(4, 0))
        self._rec_setting(save=False)
        self._discord_card(more)                      # 1.7: Rich Presence
        self._discord_init()
        self._spotify_card(more)                      # 1.8: "Als nächstes" from Spotify
        self._spotify_init()

        # 1.2.15: the same controls once more for the setup assistant's step "Match-Daten" – the originals sit
        # under "Mehr" and count as hidden while it is folded (the settings page itself draws only SPECS keys)
        sx = ui.Frame(f)
        sx.pack(fill="x")
        self._reg("setup.script", ui.Button(sx, text=_("Userscript kopieren"),
                                             command=self._official_copy_script)).pack(side="left")
        self._reg("setup.open_site", ui.Button(sx, text=_("Stats-Seite öffnen"),
                                                command=lambda: self._official_open(False))).pack(side="left")
        self._reg("setup.off_notify", ui.Checkbutton(
            sx, text=_("Meldung, wenn Match-Daten eingelesen und gelöscht wurden"), variable=self.off_notify_var,
            command=self._official_setting)).pack(anchor="w")
        self._reg("setup.off_open", ui.Checkbutton(sx, text=_("Stats-Seite öffnen, wenn DBD beendet wird"),
                                                    variable=self.off_open_var,
                                                    command=self._official_setting)).pack(anchor="w")
        self._reg("setup.off_text", ui.Label(sx, text=_("Einmal einrichten: Tampermonkey im Browser installieren, „Userscript kopieren“ und dort "
                             "als neues Skript einfügen und speichern, auf stats.deadbydaylight.com anmelden. Chrome/"
                             "Edge: in den Details der Erweiterung „Allow User Scripts“ einschalten, sonst läuft "
                             "kein Skript. Beim Öffnen der Seite speichert das Skript neue Matches (die letzten 30) im "
                             "Download-Ordner; das Programm liest die Datei und löscht sie. Es geht dafür selbst nicht "
                             "ins Internet."),
                  style="Dim.TLabel", wraplength=420)).pack(anchor="w")

        bk = self._reg("st.more.backup", ui.LabelFrame(more, text=_("Sicherung"), padding=8))
        bk.pack(fill="x", pady=(8, 0))
        self._reg("st.more.export", ui.Button(bk, text=_("Einstellungen exportieren …"),
                                               command=self._export_settings)).pack(side="left")
        self._reg("st.more.import", ui.Button(bk, text=_("Einstellungen importieren …"),
                                               command=self._import_settings)).pack(side="left", padx=6)
        self._reg("st.more.clear_hist", ui.Button(bk, text=_("Verlauf löschen"),      # 1.2.16: moved from the
                                                   command=self._stats_clear)).pack(side="right")   # statistics
        self._reg("st.more.reset_all", ui.Button(bk, text=_("Alle Einstellungen zurücksetzen"),   # 1.2.19
                                                  command=self._reset_all_settings)).pack(side="right", padx=(0, 6))

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
        self.more_btn.configure(text=arrow + _("Mehr (Match-Daten, Farming, OBS-Aufnahmen, Discord, Spotify, Sicherung, Ordner)"))
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

    def _reset_all_settings(self):
        """1.2.19: back to the defaults (PC-specific values stay), then a restart like after an import."""
        if not self._ask(_("Alle Einstellungen zurücksetzen"),
                         _("Alle Einstellungen auf die Auslieferung zurücksetzen? Runden, Match-Daten und eigene "
                           "Bilder bleiben. Das Programm startet danach neu."), self._reset_all_settings):
            return
        from .config import reset_data
        self.settings.data = reset_data(self.settings.data)
        self.settings.save()
        self.settings.frozen = True
        self._log(_("Alle Einstellungen zurückgesetzt."), "System")
        from . import restart
        try:
            ok = restart.spawn_helper(self.root_dir)
        except OSError:
            ok = False
        if ok:
            self.quit()
        else:
            self._inform(_("Alle Einstellungen zurücksetzen"), _("Bitte das Programm jetzt neu starten."))

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
        self._swatch_mark()
        self._apply_theme()

    def _swatch_picked(self, colour):
        """A square of the palette or "Eigene Farbe …": this colour as own accent (theme "custom", 1.63)."""
        colour = qt_theme.norm_hex(colour)
        if colour is None:
            return
        self.settings.set("accent_custom", colour)
        self.theme_var.set(dict(self._themes)["custom"])
        self._theme_changed()

    def _swatch_mark(self):
        """The ring on the palette: the own colour while the theme is "custom", else none."""
        on = self.settings.get("color_theme", "gold") == "custom"
        self.swatches.current = qt_theme.norm_hex(self.settings.get("accent_custom")) if on else None

    def _card_order_reset(self):
        """The cards of all pages, the tab rows and the navigation back in their built-in order."""
        self.settings.set("card_order", {})
        self.settings.set("tab_order", {})                 # 1.7.6
        self.settings.set("nav_order", [])
        self._save_soon()
        if self.qt is not None:
            self.qt.set_card_order({})
            self.qt.set_tab_order({})
            self.qt.set_nav_order([])

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

    # ---------------------------------------------------------- recordings (1.4)
    def _rec_cfg(self) -> obsrec.Config:
        try:
            port = int(self.rec_port_var.get().strip() or obsrec.DEFAULT_PORT)
        except ValueError:
            port = obsrec.DEFAULT_PORT
        limit = next((gb for gb, lbl in self._rec_limits if lbl == self.rec_limit_var.get()), 0)
        tail = next((s for s, lbl in self._rec_tails if lbl == self.rec_tail_var.get()), obsrec.DEFAULT_TAIL_S)
        return obsrec.Config(on=bool(self.rec_on_var.get()), port=port, password=self.rec_pw_var.get(),
                             volume=str(self.settings.get("rec_volume", "")), rel=str(self.settings.get("rec_rel", "")),
                             folder=str(self.settings.get("rec_folder", "")), limit_gb=limit,
                             pre=bool(self.rec_pre_var.get()), tail_s=tail, buffer_auto=bool(self.rec_buffer_var.get()),
                             window=bool(self.rec_window_var.get()), obs_start=bool(self.rec_obs_start_var.get()),
                             merge=bool(self.rec_merge_var.get()), farming_sub=bool(self.rec_farming_var.get()),
                             early=bool(self.rec_early_var.get()), instant=bool(self.rec_instant_var.get()),
                             clip_s=next((s for s, lbl in self._rec_clips if lbl == self.rec_clip_var.get()),
                                         obsrec.DEFAULT_CLIP_S),
                             audio=bool(self.rec_audio_var.get()),
                             audio_dbd=bool(self.rec_audio_vars["dbd"].get()),
                             audio_discord=bool(self.rec_audio_vars["discord"].get()),
                             audio_desktop=bool(self.rec_audio_vars["desktop"].get()),
                             audio_mic=bool(self.rec_audio_vars["mic"].get()),
                             tracks=bool(self.rec_tracks_var.get()),                       # 1.8.6
                             clip_sources=tuple(k for k in obsrec.SOURCES if self.rec_clip_src_vars[k].get()),
                             farming_days=next((d for d, lbl in self._rec_farming_days
                                                if lbl == self.rec_farming_days_var.get()), 0))

    def _rec_setting(self, save=True):
        cfg = self._rec_cfg()
        if save:
            self.settings.set("rec_on", cfg.on)
            self.settings.set("rec_port", cfg.port)
            self.settings.set("rec_password", cfg.password)
            self.settings.set("rec_limit_gb", cfg.limit_gb)
            self.settings.set("rec_pre", cfg.pre)
            self.settings.set("rec_tail_s", int(cfg.tail_s))
            self.settings.set("rec_buffer_auto", cfg.buffer_auto)
            self.settings.set("rec_window", cfg.window)
            self.settings.set("rec_obs_start", cfg.obs_start)
            self.settings.set("rec_merge", cfg.merge)
            self.settings.set("rec_farming_dir", cfg.farming_sub)
            self.settings.set("rec_farming_days", int(cfg.farming_days))
            self.settings.set("rec_early", cfg.early)
            self.settings.set("rec_instant", cfg.instant)
            self.settings.set("rec_clip_s", int(cfg.clip_s))
            self.settings.set("rec_clip_notify", bool(self.rec_clip_notify_var.get()))
            self.settings.set("rec_audio", cfg.audio)
            for key in ("dbd", "discord", "desktop", "mic"):
                self.settings.set("rec_audio_" + key, bool(getattr(cfg, "audio_" + key)))
            self.settings.set("rec_tracks", cfg.tracks)
            self.settings.set("rec_clip_sources", list(cfg.clip_sources))
            self._save_soon()
        self.recorder.configure(cfg)
        folder = cfg.folder
        self.rec_folder_var.set(folder if folder else _("(kein Ordner gewählt)"))
        self.rec_ffmpeg_var.set(_("ffmpeg fehlt (Paket imageio-ffmpeg) – start.bat installiert es beim nächsten Start; "
                                  "bis dahin bleibt der Vorlauf eine eigene Datei.")
                                if cfg.merge and cfg.pre and obsrec.ffmpeg_exe() is None else "")

    def _rec_audio_changed(self):
        """1.6: a sound switch – saved, and OBS is set at once while DBD runs (anytime, also mid-round)."""
        self._rec_setting()
        self.recorder.apply_audio()

    def _match_started(self, d):
        """1.6: worker – the loading screen after a found lobby is over: OBS records from the spawn on."""
        q = self._queue
        f = q.get("found")
        farming = bool(f is not None and f.crossplay_off and not f.custom
                       and self.settings.get("farming_crossplay", True))
        self._log(_("Ladebildschirm vorbei – das Match beginnt."), "Erkennung")
        if self.settings.get("rec_on") and self.settings.get("rec_early", True):
            self.recorder.start_early(t=d.get("t") or time.time(), role=(f.role if f else "") or q.get("role") or "",
                                      killer=(f.killer if f else "") or "", farming=farming)

    def _rec_pick_folder(self):
        self._qt_file("dir", _("Ordner für die Aufnahmen (z. B. auf der externen Platte)"),
                      str(self.settings.get("rec_folder", "")), self._rec_folder_chosen)

    def _rec_folder_chosen(self, path):
        if not path or not os.path.isdir(path):
            return
        volume, rel = obsrec.volume_of(path)
        self.settings.set("rec_volume", volume)
        self.settings.set("rec_rel", rel)
        self.settings.set("rec_folder", os.path.abspath(path))
        self._rec_setting()
        self._log(_("Aufnahmeordner: {path}", path=os.path.abspath(path)), "System")

    def _rec_test(self):
        self.rec_status_var.set(_("Verbinde mit OBS …"))
        self.recorder.configure(self._rec_cfg())
        self.recorder.test()

    def _rec_event(self, kind, d):
        """Recorder thread -> UI: status (text, ok) | started | saved | deleted."""
        if kind == "status":
            self.rec_status_var.set(d.get("text", ""))
            if not d.get("ok", True):
                self._log(_("Aufnahme: {text}", text=d.get("text", "")), "Fehler")
        elif kind == "warn":                    # 1.4.1: OBS/drive missing when DBD starts, a broken file
            self._log(_("Aufnahme: {text}", text=d.get("text", "")), "Fehler")
            if not (self.game is not None and not self.simulate and is_game_window(foreground_root())):
                self.toast.show(_("Aufnahme"), d.get("text", ""))
        elif kind == "saved":
            self._log(_("Aufnahme gespeichert: {file}", file=d.get("file", "")), "System")
            self._rec_dirty = True
        elif kind == "deleted":
            if d.get("manual"):                 # 1.5: from the tab
                self._log(_("Aufnahme gelöscht: {file}", file=(d.get("files") or [""])[0]), "System")
            elif d.get("farming"):              # 1.8.23: farming recordings past their days
                self._log(_("Alte Farming-Aufnahmen gelöscht (älter als {days} Tage): {n}", days=d.get("days", 0),
                            n=len(d.get("files") or [])), "System")
            else:
                self._log(_("Aufnahmen gelöscht (Platz): {n}", n=len(d.get("files") or [])), "System")
            self._rec_dirty = True
        elif kind == "clip":                    # 1.6: F8 instant clip
            if d.get("ok"):
                self._log(_("Sofort-Clip gespeichert ({n} s): {file}", n=d.get("seconds", 0), file=d.get("file", "")),
                          "System")
                self._rec_dirty = True
                self._clip_toast(_("Clip gespeichert ✓"), _("{n} s · im Tab Aufnahmen → Clips", n=d.get("seconds", 0)))
            else:
                self._log(_("Kein Sofort-Clip: {why}", why=d.get("why", "")), "Fehler")
                self._clip_toast(_("Kein Clip"), d.get("why", ""), 5)
        elif kind == "changed":                 # 1.5: keep / delete done by the recorder thread
            self._rec_changed(d)
        elif kind == "marked":                  # 1.4.2: F8
            if d.get("pos") is None:
                self._log(_("Keine Aufnahme läuft – keine Clip-Marke gesetzt."), "System")
            else:
                self._log(_("Clip-Marke {n} bei {pos} gesetzt.", n=d.get("n", 1), pos=fmt_duration(d["pos"])), "System")
                self.root.bell()

    def mark_clip(self):
        """1.4.2: hotkey (F8) – note this moment in the running OBS recording; the clip editor jumps to it.
        1.6: and (setting rec_instant) save the last seconds of OBS's replay buffer as a clip right away."""
        instant = bool(self.settings.get("rec_on") and self.settings.get("rec_instant", True))
        if self.recorder.recording:
            self.recorder.mark()
        elif not instant:
            self._log(_("Keine Aufnahme läuft – keine Clip-Marke gesetzt."), "System")
            return
        if instant:
            self._clip_toast(_("Clip wird gespeichert …"),
                             _("Die letzten {n} s aus dem Puffer von OBS", n=int(self.settings.get("rec_clip_s", 30))),
                             6)
            hist = self._hist or {}
            self.recorder.instant_clip(label=hist.get("map", ""), role=hist.get("role", ""),
                                       killer=hist.get("killer", ""), map_id=hist.get("map_id", ""),   # 1.8.13
                                       farming=bool(hist.get("farming")), source=float(hist.get("t") or 0.0))

    def _clip_toast(self, title, text, seconds=3):
        """1.8.13 (user: "eine kleine Benachrichtigung, wenn ich mit F8 einen Clip mache"): the own notification
        window bottom right – also while DBD is in front (that is when F8 is pressed); no sound."""
        if self.settings.get("rec_clip_notify", True):
            self.toast.show(title, text, seconds)

    def _reveal_rec(self):
        """Overview tile "Aufnahmen" → Settings, "Mehr" open, the card "Aufnahmen mit OBS" lit up."""
        self.qt.show_page("settings")
        if not self._more_open:
            self._toggle_more()
        self._qt_refresh(force=True)
        self.qt.reveal("settings", "st.more.rec")

    # ---------------------------------------------------------- tray and autostart
    def _tray_start(self):
        if not self.tray.active and not self.tray.start():
            self._log(_("Symbol im Infobereich nicht verfügbar ({error}) – Minimieren wie gewohnt.",
                        error=self.tray.error), "Fehler")

    def _tray_tick(self):
        """1.3.6: the tray icon shows the state by a coloured dot (like the overview's status dot)."""
        if not self.tray.active:
            return
        st = status.user_state(self._worker_status, auto_detect=bool(self.settings.get("auto_detect", True)),
                               game_found=self.game is not None, simulate=bool(self.simulate),
                               has_map=self.overlay.has_map(), visible_wanted=self.user_visible,
                               hidden_after_match=self.hidden_after_match, menu_paused=self.menu_paused)
        u = self._unsure
        self.tray.set_status(status.tray_dot(st, bool(u and u.get("shown")),
                                             self.game is not None or bool(self.simulate)),
                             rec=self.recorder.recording)

    def _rec_tick(self):
        """1.4.1: the recorder learns whether DBD runs (replay buffer, checks); the overlay shows a REC dot."""
        self.recorder.set_game(self.game is not None and not self.simulate)
        self._rec_tab_tick()
        # 1.8.31 (user: "das Rekord-Zeichen finde ich nicht mehr"): it shows only while OBS records a round – with
        # recordings switched on, "Overlay testen" shows it too, so one sees where it sits
        sample = bool(getattr(self, "_forced", False)) and bool(self.settings.get("rec_on", False))
        self.overlay.set_rec(self.recorder.recording or sample)

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
