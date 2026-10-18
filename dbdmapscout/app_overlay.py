"""The overlay page of the control window (1.2.14, analysis point 3 – moved out of app.py unchanged): its UI
model (``_tab_overlay``, the widgets the Qt page draws by key) and the handlers of its controls – position, size,
opacity, map style, the tick boxes of the map and the cards. Mixin of App; never imports app.py."""
from __future__ import annotations

from . import layout
from . import uimodel as ui
from .i18n import N_, _
from .skin import STYLE_LABELS
from .app_spotify import MEDIA_NEXT_N, MEDIA_NEXT_SPOTS
from .app_sysinfo import (BAR_ALIGNS, HUD_ROW_LABELS, HUD_SIDES, MAP_SCALE, MEDIA_SCALE, MEDIA_SPOTS, MEDIA_STYLES,
                          OPACITY_KEYS, PRESET_LABELS, SELECTABLE, TODAY_SPOTS)

ANCHORS = [("auto", N_("automatisch")), ("top-left", N_("oben links")), ("top-right", N_("oben rechts")),
           ("bottom-left", N_("unten links")), ("bottom-right", N_("unten rechts")), ("custom", N_("eigene Position"))]


# 1.8.24: where the map's lines (timer, record, server) go – an element of their own, or drawn with the map as before
INFO_SPOTS = [("below", N_("Eigenes Element unter der Karte")), ("above", N_("Eigenes Element über der Karte")),
              ("custom", N_("Eigenes Element, eigene Position")), ("inside", N_("Mit der Karte verbunden (wie früher)"))]
# 1.8.24 (user: "zwischen runden und eckigen Bildern"): the shape of the music card's cover
COVER_SHAPES = [("style", N_("Wie der Stil")), ("round", N_("Rund")), ("square", N_("Eckig"))]
STYLE_DEFER_MS = 30                     # 1.3.4: the window repaints before the slow part of a map style change
MAP_STYLES = [("classic", N_("Original")), ("dark", N_("Dunkel")),            # 1.66, mapstyle.py
              ("grey", N_("Grau")), ("grey_edge", N_("Grau mit Rand")),         # 1.8.16: with a floor
              ("lilac", N_("Lila dunkel")), ("lilac_glass", N_("Lila transparent"))]


def anchor_label(key: str) -> str:
    return _(dict(ANCHORS).get(key, "automatisch"))


class OverlayTab:
    """Tab "Overlay": preview, the element picked, one tab per element (qt_window.SPECS) – and what its controls do."""

    def _tab_overlay(self):
        outer, f = self._scroll_tab()
        o = self.settings["overlay"]
        pos = self._reg("ov.pos", ui.LabelFrame(f, text=_("Position"), padding=8))
        pos.pack(fill="x")
        # 1.61: the screen with the map on it – where and how big, live; a click or drag places it there
        self._reg("ov.preview", ui.Preview(pos, source=self._preview_data, command=self._preview_pick)).pack(fill="x")
        # 1.64.9: the element picked in the preview (or here) – one slider sizes it
        rs = ui.Frame(pos)
        rs.pack(fill="x", pady=(4, 0))
        self._reg("ov.sel.label", ui.Label(rs, text=_("Element"), width=12)).pack(side="left")
        self._sel = "map"
        self.sel_var = ui.StringVar(value=_(dict(SELECTABLE)["map"]))
        scb = self._reg("ov.sel", ui.Combobox(rs, textvariable=self.sel_var, state="readonly", width=24,
                                               values=[_(t) for _k, t in SELECTABLE]))
        scb.pack(side="left", padx=6)
        scb.bind("<<ComboboxSelected>>", lambda e: self._sel_picked())
        self.sel_size_var = ui.DoubleVar(value=o["height"] * 100)
        self.sel_size_label = self._slider(pos, _("Grösse"), self.sel_size_var, *MAP_SCALE, self._sel_size_changed,
                                           key="ov.sel_size")
        self.sel_scale = self._qt_reg["ov.sel_size"]
        self.opacity_var = ui.DoubleVar(value=o["opacity"] * 100)        # 1.2.7: of the element picked
        self.opacity_label = self._slider(pos, _("Deckkraft"), self.opacity_var, 25, 100, self._opacity_changed,
                                          key="ov.opacity")
        sr = ui.Frame(pos)                              # 1.3: the overlay style (skin.py)
        sr.pack(fill="x", pady=(0, 4))
        self._reg("ov.style.label", ui.Label(sr, text=_("Stil"), width=12)).pack(side="left")
        styles = dict(STYLE_LABELS)
        self.style_var = ui.StringVar(value=_(styles.get(o.get("style", "classic"), styles["classic"])))
        scb = self._reg("ov.style", ui.Combobox(sr, textvariable=self.style_var, state="readonly", width=24,
                                                 values=[_(t) for _k, t in STYLE_LABELS]))
        scb.pack(side="left", padx=6)
        scb.bind("<<ComboboxSelected>>", lambda e: self._style_changed())
        # 1.2.8: one gap for stacked cards, and where everything sits in the bar
        self.gap_var = ui.DoubleVar(value=float(o.get("stack_gap", 8)))
        self._slider(pos, _("Abstand"), self.gap_var, 0, 40, self._gap_changed, fmt="{:.0f} px", key="ov.gap")
        ar = ui.Frame(pos)
        ar.pack(fill="x", pady=(4, 0))
        self._reg("ov.bar_align.label", ui.Label(ar, text=_("Im Balken"), width=12)).pack(side="left")
        aligns = dict(BAR_ALIGNS)
        self.bar_align_var = ui.StringVar(value=_(aligns.get(o.get("bar_align", "centre"), aligns["centre"])))
        acb = self._reg("ov.bar_align", ui.Combobox(ar, textvariable=self.bar_align_var, state="readonly", width=24,
                                                     values=[_(t) for _k, t in BAR_ALIGNS]))
        acb.pack(side="left", padx=6)
        acb.bind("<<ComboboxSelected>>", lambda e: self._bar_align_changed())
        # 1.8.14 (user: "Limiter … oben und unten, wo die GUI-Elemente nicht überschreiten dürfen"): lines in the bars
        self.limits_var = ui.BooleanVar(value=bool(o.get("bar_limits_on", False)))
        self._reg("ov.limits", ui.Checkbutton(pos, text=_("Grenzen oben und unten in den schwarzen Balken"),
                                              variable=self.limits_var, command=self._limits_changed)
                  ).pack(anchor="w", pady=(4, 0))
        lr = ui.Frame(pos)
        lr.pack(fill="x")
        self.limits_same_var = ui.BooleanVar(value=bool(o.get("bar_limits_same", False)))
        self._reg("ov.limits_same", ui.Checkbutton(lr, text=_("Links und rechts gleich"),
                                                   variable=self.limits_same_var, command=self._limits_changed)
                  ).pack(side="left")
        self._reg("ov.limits_reset", ui.Button(lr, text=_("Grenzen zurücksetzen"), command=self._limits_reset)
                  ).pack(side="left", padx=(6, 0))
        self._reg("ov.limits_hint", ui.Label(pos, text=_("Die Linien in der Vorschau mit „Mit der Maus verschieben“ "
                                                         "ziehen – Karte, Systemwerte, Heute und Musik bleiben im "
                                                         "Balken dazwischen."),
                                             style="Dim.TLabel", wraplength=520)).pack(anchor="w")
        # 1.8.25 (user's screenshots with Discord's overlay open): keep its widgets free
        self.keep_out_var = ui.BooleanVar(value=bool(o.get("keep_out_on", True)))
        self._reg("ov.keep_out", ui.Checkbutton(pos, text=_("Discord-Overlay freihalten (Sprach-Widget unten links, "
                                                            "Benachrichtigungen oben rechts, Text-Chat rechts)"),
                                                variable=self.keep_out_var, command=self._keep_out_changed)
                  ).pack(anchor="w", pady=(4, 0))
        # 1.8.29 (user: "rechts sind die Felder nicht untereinander … zusammenführen"): one column per bar
        cw = ui.Frame(pos)
        cw.pack(fill="x", pady=(4, 0))
        self.same_width_var = ui.BooleanVar(value=bool(o.get("cards_same_width", True)))
        self._reg("ov.same_width", ui.Checkbutton(cw, text=_("Karten im selben Balken gleich breit (Systemwerte, "
                                                              "Heute, Musik)"),
                                                  variable=self.same_width_var, command=self._same_width_changed)
                  ).pack(side="left")
        self._reg("ov.merge_column", ui.Button(cw, text=_("Zu einer Spalte zusammenführen"),
                                               command=self._merge_column)).pack(side="left", padx=(8, 0))
        pr = ui.Frame(pos)                              # 1.2.9: ready-made arrangements
        pr.pack(fill="x", pady=(4, 0))
        self._reg("ov.preset.label", ui.Label(pr, text=_("Vorlage"), width=12)).pack(side="left")
        self.preset_var = ui.StringVar(value=_(PRESET_LABELS[0][1]))
        pcb = self._reg("ov.preset", ui.Combobox(pr, textvariable=self.preset_var, state="readonly", width=30,
                                                  values=[_(t) for _k, t in PRESET_LABELS]))
        pcb.pack(side="left", padx=6)
        self._reg("ov.preset_apply", ui.Button(pr, text=_("Vorlage anwenden"), command=self._preset_apply)
                  ).pack(side="left")
        self.size_scope_var = ui.StringVar(value="")     # 1.65.5: this map only / all maps
        # 1.2.17: packed – unpacked, the Qt page counted both hints as hidden (never shown since the Qt window)
        self._reg("ov.size_scope", ui.Label(pos, textvariable=self.size_scope_var, style="Dim.TLabel")).pack(anchor="w")
        self.size_cap_var = ui.StringVar(value="")       # 1.65.2: the bar is what limits the map's size
        self._reg("ov.size_cap", ui.Label(pos, textvariable=self.size_cap_var, style="Dim.TLabel")).pack(anchor="w")
        r = ui.Frame(pos)
        r.pack(fill="x", pady=(0, 4))
        self._reg("ov.anchor.label", ui.Label(r, text=_("Vorgabe"), width=12)).pack(side="left")
        self.anchor_var = ui.StringVar(value=anchor_label(o["anchor"]))
        cb = self._reg("ov.anchor", ui.Combobox(r, textvariable=self.anchor_var, values=[_(a[1]) for a in ANCHORS],
                                                 state="readonly", width=16))
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self._anchor_changed())
        self._reg("ov.reset", ui.Button(r, text=_("Zurücksetzen"), command=self._reset_position)).pack(side="right")
        self.posx_var = ui.DoubleVar(value=o.get("pos_x", 0.0) * 100)
        self.posy_var = ui.DoubleVar(value=o.get("pos_y", 0.0) * 100)
        self.posx_label = self._slider(pos, _("Horizontal"), self.posx_var, 0, 100, self._pos_changed, key="ov.posx")
        self.posy_label = self._slider(pos, _("Vertikal"), self.posy_var, 0, 100, self._pos_changed, key="ov.posy")
        r2 = ui.Frame(pos)
        r2.pack(fill="x", pady=(4, 0))
        self._pos_rows = (self.posx_label.master, self.posy_label.master, r2)   # 1.66.3: only for "eigene Position"
        self.edit_btn = self._reg("ov.edit", ui.Button(r2, text=_("Mit der Maus verschieben"), command=self.toggle_edit))
        self.edit_btn.pack(side="left")
        self.test_btn = self._reg("ov.test", ui.Button(r2, text=_("Overlay testen"), command=self.test_overlay))
        self.test_btn.pack(side="left", padx=(6, 0))
        self.undo_btn = self._reg("ov.undo", ui.Button(r2, text=_("Rückgängig"), command=self.undo_layout))
        self.undo_btn.pack(side="left", padx=(6, 0))
        self.undo_btn.state(["disabled"])
        self.master_var = ui.BooleanVar(value=bool(self.settings.get("overlay_on", True)))     # 1.8.18
        self._reg("ov.master", ui.Checkbutton(pos, text=_("Overlay anzeigen (aus: nichts im Spiel, Erkennung läuft weiter)"),
                                              variable=self.master_var,
                                              command=lambda: self.set_overlay_on(self.master_var.get())))
        self.per_size_var = ui.BooleanVar(value=self.settings.get("layout_per_size", True))
        self._reg("ov.per_size", ui.Checkbutton(pos, text=_("Position und Grösse je DBD-Fenstergrösse merken"),
                                                variable=self.per_size_var, command=self._per_size_changed)
                  ).pack(anchor="w", pady=(4, 0))
        self.per_size_text = ui.StringVar(value="")
        self._reg("ov.per_size_hint", ui.Label(pos, textvariable=self.per_size_text, style="Dim.TLabel"))
        self.pos_hint_var = ui.StringVar(value="")
        self._reg("ov.pos_hint", ui.Label(pos, textvariable=self.pos_hint_var, style="Dim.TLabel",
                                           wraplength=520)).pack(anchor="w", pady=(4, 0))
        self._pos_hint()

        look = self._reg("ov.look", ui.LabelFrame(f, text=_("Darstellung"), padding=8))
        look.pack(fill="x", pady=(8, 0))
        self.size_var = ui.DoubleVar(value=o["height"] * 100)
        self.size_label = self._slider(look, _("Grösse"), self.size_var, *MAP_SCALE, self._size_changed, key="ov.size")
        self.map_size_row = ui.Frame(look)
        self.map_size_var = ui.StringVar(value="")
        self._reg("ov.map_size", ui.Label(self.map_size_row, textvariable=self.map_size_var, style="Dim.TLabel",
                                           wraplength=330)).pack(side="left")
        self._reg("ov.map_size_reset", ui.Button(self.map_size_row, text=_("Für diese Map zurücksetzen"),
                                                  command=self._reset_map_size)).pack(side="right")
        self._size_row_after = self.size_label.master
        sr = ui.Frame(look)
        sr.pack(fill="x", pady=(4, 0))
        self._reg("ov.map_style.label", ui.Label(sr, text=_("Kartenstil"), width=12)).pack(side="left")
        styles = dict(MAP_STYLES)
        self.map_style_var = ui.StringVar(value=_(styles.get(o.get("map_style", "classic"), styles["classic"])))
        mscb = self._reg("ov.map_style", ui.Combobox(sr, textvariable=self.map_style_var, state="readonly", width=38,
                                                      values=[_(t) for _k, t in MAP_STYLES]))
        mscb.pack(side="left", padx=6)
        mscb.bind("<<ComboboxSelected>>", lambda e: self._map_style_changed())
        ir = ui.Frame(look)
        ir.pack(fill="x", pady=(4, 0))
        self._reg("ov.info_pos.label", ui.Label(ir, text=_("Infos"), width=12)).pack(side="left")
        spots = dict(INFO_SPOTS)
        self.info_pos_var = ui.StringVar(value=_(spots.get(o.get("info_pos", "below"), spots["below"])))
        icb = self._reg("ov.info_pos", ui.Combobox(ir, textvariable=self.info_pos_var, state="readonly", width=38,
                                                    values=[_(t) for _k, t in INFO_SPOTS]))
        icb.pack(side="left", padx=6)
        icb.bind("<<ComboboxSelected>>", lambda e: self._info_spot_changed())
        self.focus_var = ui.BooleanVar(value=o["only_when_game_focused"])
        self.caption_var = ui.BooleanVar(value=o["show_caption"])
        self.transp_var = ui.BooleanVar(value=o.get("transparent", True))
        self.timer_show_var = ui.BooleanVar(value=o.get("show_timer", True))
        self.server_show_var = ui.BooleanVar(value=o.get("show_server", True))
        self.keep_bar_var = ui.BooleanVar(value=o.get("keep_in_bar", True))
        self.show_map_var = ui.BooleanVar(value=o.get("show_map", True))
        self.waiting_var = ui.BooleanVar(value=o.get("show_waiting", True))
        self.floor_auto_var = ui.BooleanVar(value=o.get("floor_auto", True))
        self.record_var = ui.BooleanVar(value=o.get("show_record", True))
        self._reg("ov.keep_bar", ui.Checkbutton(
            pos, text=_("Karte im schwarzen Rand halten (Ultrawide: nie ins Spielbild ragen)"),
            variable=self.keep_bar_var, command=self._overlay_flags_changed)).pack(anchor="w", pady=(4, 0))
        self.grow_var = ui.BooleanVar(value=o.get("grow_past_bar", False))
        self._reg("ov.grow", ui.Checkbutton(
            pos, text=_("Karte darf grösser als der Balken werden (ragt dann ins Spielbild)"),
            variable=self.grow_var, command=self._overlay_flags_changed)).pack(anchor="w", pady=(2, 0))
        for key, text, var in (("show_map", N_("Karte anzeigen (aus: nur Timer, Ort und Ping)"), self.show_map_var),
                               ("focus", N_("Nur zeigen, wenn DBD das aktive Fenster ist"), self.focus_var),
                               ("caption", N_("Map-Namen über der Karte anzeigen"), self.caption_var),
                               ("timer", N_("Rundentimer unter der Karte anzeigen"), self.timer_show_var),
                               ("server", N_("Verbundenen Server unter der Karte anzeigen (Tab Server)"),
                                self.server_show_var),
                               ("waiting", N_("Ohne Karte: „Warte auf Map“ und Lobby-Status anzeigen"), self.waiting_var),
                               ("floors", N_("Etagen (Midwich) untereinander zeigen (aus: nur die untere)"),
                                self.floor_auto_var),
                               ("record", N_("Eigene Bilanz auf der Map unter dem Timer (Stats-Seite)"), self.record_var),
                               ("transparent", N_("Transparenter Rand um die Karte"), self.transp_var)):
            self._reg(f"ov.{key}", ui.Checkbutton(look, text=_(text), variable=var,
                                                   command=self._overlay_flags_changed)).pack(anchor="w", pady=1)
        self.fade_var = ui.BooleanVar(value=o.get("fade", True))
        self._reg("ov.fade", ui.Checkbutton(look, text=_("Weich ein- und ausblenden (Karte, Systemwerte, Heute)"),
                                            variable=self.fade_var, command=self._look_flags_changed)
                  ).pack(anchor="w", pady=1)
        self.map_backdrop_var = ui.BooleanVar(value=o.get("map_backdrop", False))
        self._reg("ov.map_backdrop", ui.Checkbutton(look, text=_("Dunkle Fläche hinter Karte und Infos"),
                                                    variable=self.map_backdrop_var,
                                                    command=self._look_flags_changed)).pack(anchor="w", pady=1)
        sysf = self._reg("ov.sys", ui.LabelFrame(f, text=_("Systemwerte (CPU/GPU-Temperatur, Auslastung, VRAM, RAM)"),
                                                  padding=8))
        sysf.pack(fill="x", pady=(8, 0))
        r = ui.Frame(sysf)
        r.pack(fill="x")
        self._reg("ov.sysinfo.label", ui.Label(r, text=_("Position"), width=12)).pack(side="left")
        labels = dict(HUD_SIDES)
        self.sysinfo_var = ui.StringVar(value=_(labels.get(self.settings.get("sysinfo", "off"), labels["off"])))
        cb = self._reg("ov.sysinfo", ui.Combobox(r, textvariable=self.sysinfo_var, values=[_(t) for _k, t in HUD_SIDES],
                                                  state="readonly", width=38))
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self._sysinfo_changed())
        self._reg("ov.sys_text", ui.Label(sysf, text=_("Im schwarzen Rand, solange die Karte im Match zu sehen ist. GPU-Werte von NVIDIA "
                               "(Treiber), CPU-Temperatur nur mit HWiNFO („Shared Memory Support“ an) – kein "
                               "eigener Treiber."),
                  style="Dim.TLabel", wraplength=520)).pack(anchor="w", pady=(4, 0))
        self.sysinfo_hint_var = ui.StringVar(value="")
        self._reg("ov.sys_hint", ui.Label(sysf, textvariable=self.sysinfo_hint_var, style="Dim.TLabel",
                                           wraplength=520)).pack(anchor="w")
        self.hud_backdrop_var = ui.BooleanVar(value=o.get("hud_backdrop", False))
        self._reg("ov.hud_backdrop", ui.Checkbutton(sysf, text=_("Dunkle Fläche hinter den Systemwerten"),
                                                    variable=self.hud_backdrop_var, command=self._look_flags_changed)
                  ).pack(anchor="w", pady=(2, 0))
        shown = o.get("hud_rows") or {}
        self.hud_row_vars = {}

        def row_check(key, text):                      # 1.2.8: rows of the system values, each its own tick box
            var = self.hud_row_vars[key] = ui.BooleanVar(value=bool(shown.get(key, True)))
            return ui.Checkbutton(sysf, text=text, variable=var, command=self._hud_rows_changed)
        labels = dict(HUD_ROW_LABELS)
        self._reg("ov.hud_row_cpu", row_check("cpu", _(labels["cpu"]))).pack(anchor="w", pady=(2, 0))
        self._reg("ov.hud_row_gpu", row_check("gpu", _(labels["gpu"]))).pack(anchor="w", pady=(2, 0))
        self._reg("ov.hud_row_spot", row_check("spot", _(labels["spot"]))).pack(anchor="w", pady=(2, 0))
        self._reg("ov.hud_row_vram", row_check("vram", _(labels["vram"]))).pack(anchor="w", pady=(2, 0))
        self._reg("ov.hud_row_ram", row_check("ram", _(labels["ram"]))).pack(anchor="w", pady=(2, 0))
        # 1.2.12: "Heute" and the music each have their own frame (= tab of the Qt page)
        tf = self._reg("ov.today_f", ui.LabelFrame(f, text=_("Heute"), padding=8))
        tf.pack(fill="x", pady=(8, 0))
        self.today_var = ui.BooleanVar(value=o.get("show_today", True))
        self._reg("ov.today", ui.Checkbutton(tf, text=_("„Heute“: Runden, Spielzeit, Ø Kills/Entkommen, Uhrzeit"),
                                             variable=self.today_var, command=self._look_flags_changed)
                  ).pack(anchor="w", pady=(6, 0))
        tr = ui.Frame(tf)
        tr.pack(fill="x", pady=(4, 0))
        self._reg("ov.today_pos.label", ui.Label(tr, text=_("Position"), width=12)).pack(side="left")
        spots = dict(TODAY_SPOTS)
        self.today_pos_var = ui.StringVar(value=_(spots.get(o.get("today_pos", "below"), spots["below"])))
        tcb = self._reg("ov.today_pos", ui.Combobox(tr, textvariable=self.today_pos_var, state="readonly", width=38,
                                                     values=[_(t) for _k, t in TODAY_SPOTS]))
        tcb.pack(side="left", padx=6)
        tcb.bind("<<ComboboxSelected>>", lambda e: self._today_spot_changed())
        self.today_backdrop_var = ui.BooleanVar(value=o.get("today_backdrop", False))
        self._reg("ov.today_backdrop", ui.Checkbutton(tf, text=_("Dunkle Fläche hinter „Heute“"),
                                                      variable=self.today_backdrop_var,
                                                      command=self._look_flags_changed)).pack(anchor="w", pady=(2, 0))
        mf = self._reg("ov.music_f", ui.LabelFrame(f, text=_("Musik"), padding=8))
        mf.pack(fill="x", pady=(8, 0))
        self.media_var = ui.BooleanVar(value=o.get("show_media", True))
        self._reg("ov.media", ui.Checkbutton(mf, text=_("„Läuft gerade“: Titel, Interpret und Cover der Musik "
                                                           "(Spotify, Browser … – nur während sie spielt)"),
                                             variable=self.media_var, command=self._look_flags_changed)
                  ).pack(anchor="w", pady=(2, 0))
        mr = ui.Frame(mf)
        mr.pack(fill="x", pady=(4, 0))
        self._reg("ov.media_pos.label", ui.Label(mr, text=_("Position"), width=12)).pack(side="left")
        spots = dict(MEDIA_SPOTS)
        self.media_pos_var = ui.StringVar(value=_(spots.get(o.get("media_pos", "below"), spots["below"])))
        mcb = self._reg("ov.media_pos", ui.Combobox(mr, textvariable=self.media_pos_var, state="readonly", width=38,
                                                     values=[_(t) for _k, t in MEDIA_SPOTS]))
        mcb.pack(side="left", padx=6)
        mcb.bind("<<ComboboxSelected>>", lambda e: self._media_spot_changed())
        sr = ui.Frame(mf)
        sr.pack(fill="x", pady=(4, 0))
        self._reg("ov.media_style.label", ui.Label(sr, text=_("Stil"), width=12)).pack(side="left")
        styles = dict(MEDIA_STYLES)
        self.media_style_var = ui.StringVar(value=_(styles.get(o.get("media_style", "big"), styles["big"])))
        scb = self._reg("ov.media_style", ui.Combobox(sr, textvariable=self.media_style_var, state="readonly",
                                                       width=38, values=[_(t) for _k, t in MEDIA_STYLES]))
        scb.pack(side="left", padx=6)
        scb.bind("<<ComboboxSelected>>", lambda e: self._media_style_changed())
        self.media_size_var = ui.DoubleVar(value=round(float(o.get("media_scale", 1.0)) * 100))
        self._slider(mf, _("Grösse Musik"), self.media_size_var, *MEDIA_SCALE, self._media_size_changed,
                     key="ov.media_size")
        cr = ui.Frame(mf)                                    # 1.8.24: round or square cover
        cr.pack(fill="x", pady=(4, 0))
        self._reg("ov.media_shape.label", ui.Label(cr, text=_("Cover"), width=12)).pack(side="left")
        shapes = dict(COVER_SHAPES)
        self.media_shape_var = ui.StringVar(value=_(shapes.get(o.get("media_cover_shape", "style"), shapes["style"])))
        ccb = self._reg("ov.media_shape", ui.Combobox(cr, textvariable=self.media_shape_var, state="readonly",
                                                       width=38, values=[_(t) for _k, t in COVER_SHAPES]))
        ccb.pack(side="left", padx=6)
        ccb.bind("<<ComboboxSelected>>", lambda e: self._media_shape_changed())
        self.media_cover_var = ui.BooleanVar(value=o.get("media_cover", True))
        self._reg("ov.media_cover", ui.Checkbutton(mf, text=_("Albumcover zeigen"), variable=self.media_cover_var,
                                                   command=self._look_flags_changed)).pack(anchor="w", pady=(2, 0))
        self.media_progress_var = ui.BooleanVar(value=o.get("media_progress", True))
        self._reg("ov.media_progress", ui.Checkbutton(mf, text=_("Fortschritt des Lieds zeigen (Zeit und Balken)"),
                                                      variable=self.media_progress_var,
                                                      command=self._look_flags_changed)).pack(anchor="w", pady=(2, 0))
        self.media_look_vars = {}

        def look_check(key, text):                     # 1.2.4: the music card's look
            var = self.media_look_vars[key] = ui.BooleanVar(value=o.get(key, True))
            return ui.Checkbutton(mf, text=text, variable=var, command=self._look_flags_changed)
        self._reg("ov.media_accent", look_check("media_accent", _("Balken in der Farbe des Covers"))
                  ).pack(anchor="w", pady=(2, 0))
        self._reg("ov.media_remaining", look_check("media_remaining", _("Restzeit statt Länge (−1:46)"))
                  ).pack(anchor="w", pady=(2, 0))
        self._reg("ov.media_backdrop", look_check("media_backdrop", _("Dunkle Fläche hinter der Musikkarte"))
                  ).pack(anchor="w", pady=(2, 0))
        self._reg("ov.media_fade", look_check("media_fade", _("Weich ein- und ausblenden (auch beim nächsten Lied)"))
                  ).pack(anchor="w", pady=(2, 0))
        self._reg("ov.media_videos", look_check("media_videos", _("Auch Videos zeigen (YouTube, Twitch …) – aus: nur Musik"))
                  ).pack(anchor="w", pady=(2, 0))                   # 1.8.4
        nr = ui.Frame(mf)                                   # 1.8: the Spotify queue on the card
        nr.pack(fill="x", pady=(6, 0))
        self._reg("ov.media_next.label", ui.Label(nr, text=_("Als nächstes"), width=12)).pack(side="left")
        nspots = dict(MEDIA_NEXT_SPOTS)
        self.media_next_var = ui.StringVar(value=_(nspots.get(o.get("media_next_pos", "below"), nspots["below"])))
        ncb = self._reg("ov.media_next", ui.Combobox(nr, textvariable=self.media_next_var, state="readonly",
                                                      width=38, values=[_(t) for _k, t in MEDIA_NEXT_SPOTS]))
        ncb.pack(side="left", padx=6)
        ncb.bind("<<ComboboxSelected>>", lambda e: self._media_next_changed())
        self.media_next_n_var = ui.DoubleVar(value=int(o.get("media_next_n", 3)))
        self._slider(mf, _("Anzahl Titel"), self.media_next_n_var, *MEDIA_NEXT_N, self._media_next_changed,
                     fmt="{:.0f}", key="ov.media_next_n")
        self._reg("ov.media_next_hint", ui.Label(mf, text=_("Die Liste kommt aus Spotify – einrichten unter "
                                                             "Einstellungen → Mehr → Spotify."),
                                                 style="Dim.TLabel", wraplength=420)).pack(anchor="w")
        return outer

    def _look_flags_changed(self):
        self.settings["overlay"]["show_today"] = bool(self.today_var.get())
        self.settings["overlay"]["show_media"] = bool(self.media_var.get())
        self.settings["overlay"]["media_cover"] = bool(self.media_cover_var.get())
        self.settings["overlay"]["media_progress"] = bool(self.media_progress_var.get())
        for key, var in self.media_look_vars.items():
            self.settings["overlay"][key] = bool(var.get())
        self.settings["overlay"]["hud_backdrop"] = bool(self.hud_backdrop_var.get())
        self.settings["overlay"]["today_backdrop"] = bool(self.today_backdrop_var.get())
        self.settings["overlay"]["fade"] = bool(self.fade_var.get())
        self.settings["overlay"]["map_backdrop"] = bool(self.map_backdrop_var.get())
        self.overlay.set_backdrop(self.settings["overlay"]["map_backdrop"])
        self._save_soon()
        self._tick_overlay(reschedule=False)

    @staticmethod
    def _realm_name(m) -> str:
        """The realm as the styled map card shows it in its header (English like the map names)."""
        names = getattr(m, "realm_names", None) or {}
        return names.get("en") or next(iter(names.values()), "") or getattr(m, "realm", "") or ""

    def _style_changed(self):
        """1.3: the look of the cards (system values, today, music) – classic or one of the modern styles."""
        key = dict((_(label), k) for k, label in STYLE_LABELS).get(self.style_var.get(), "classic")
        o = self.settings["overlay"]
        if o.get("style", "classic") == key:
            return
        o["style"] = key
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _set_map_style(self, key: str):
        """1.3.3: the map style from the maps page – the same as the list in Overlay → Karte."""
        if key not in dict(MAP_STYLES):
            return
        self.map_style_var.set(_(dict(MAP_STYLES)[key]))
        self._map_style_changed()
        self._qt_maps_rev = getattr(self, "_qt_maps_rev", 0) + 1     # the tiles take the other pictures

    def _map_style_changed(self):
        key = dict((_(label), k) for k, label in MAP_STYLES).get(self.map_style_var.get(), "classic")
        o = self.settings["overlay"]
        if o.get("map_style", "classic") == key:
            return
        o["map_style"] = key
        self._save_soon()
        self._preview_pic = None                 # the preview's sample and the maps page picture anew
        self._qt_preview_cache = None
        self._style_warm()
        self._log(_("Kartenstil: {style}.", style=_(dict(MAP_STYLES)[key])), "Overlay")
        # 1.3.4: the window shows the click first, the picture is loaded right after (60–175 ms)
        self.root.after(STYLE_DEFER_MS, self._map_style_apply)

    def _map_style_apply(self):
        if self.current and self._map_on():
            self._reload_picture()
        else:
            self._tick_overlay(reschedule=False)

    def _show_map_size(self):
        """Hint below the size slider when the map on display has a size or rotation of its own."""
        o = self.settings["overlay"]
        own = (o.get("map_heights") or {}).get(self.current[0]) if self.current else None
        deg = self._map_rotation()
        if own or deg:
            m = self.catalog.maps.get(self.current[0])
            parts = ([_("eigene Grösse {n} % (Hotkeys/Strg+Mausrad)", n=f"{own * 100:.0f}")] if own else []) + \
                ([_("gedreht um {deg}°", deg=deg)] if deg else [])
            self.map_size_var.set((m.name if m else "") + ": " + " · ".join(parts))
            if not self.map_size_row.winfo_manager():
                self.map_size_row.pack(fill="x", pady=(0, 3), after=self._size_row_after)
        elif self.map_size_row.winfo_manager():
            self.map_size_row.pack_forget()
        self._sel_sync()                          # the size slider shows the size of the map on display

    def _reset_map_size(self, map_id=None):
        """The map's own size and rotation go (button under the slider; 1.2.18 also the tiles' right click)."""
        map_id = map_id or (self.current[0] if self.current else None)
        if not map_id:
            return
        o = self.settings["overlay"]
        m = self.catalog.maps.get(map_id)
        name = m.name if m else map_id
        if (o.get("map_heights") or {}).pop(map_id, None):
            self._log(_("Eigene Grösse für {map} entfernt – es gilt wieder der Schieberegler.", map=name), "Overlay")
        if (o.get("map_rotations") or {}).pop(map_id, None):
            self._log(_("Drehung für {map} entfernt.", map=name), "Overlay")
            if self.current and self.current[0] == map_id:
                self._reload_picture()
        self._show_map_size()
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _apply_overlay_settings(self):
        o = self.settings["overlay"]
        self.overlay.opacity = o["opacity"]
        self.overlay.show_caption = o["show_caption"]
        self.overlay.set_transparent(o.get("transparent", True))
        self.overlay.set_backdrop(o.get("map_backdrop", False))
        self.overlay.set_show_map(o.get("show_map", True))

    def _pos_hint(self):
        """1.66.3 (user: the sliders at 1 % with "automatisch" looked dead): the sliders only for "eigene Position";
        with a preset the hint says how to get one."""
        anchor = self.settings["overlay"].get("anchor", "auto")
        rows = getattr(self, "_pos_rows", None)
        if rows:
            x, y, after = rows
            for row in (x, y):
                if anchor == "custom" and not row.winfo_manager():
                    row.pack(fill="x", pady=3, before=after)
                elif anchor != "custom" and row.winfo_manager():
                    row.pack_forget()
        if anchor == "custom":                   # 1.2.17: one short line each; the long version is the tooltip
            text = _("0 % = links/oben, 100 % = rechts/unten")
        elif anchor == "auto":
            text = _("Automatisch: im schwarzen Rand neben dem Spielbild bzw. neben dem DBD-Fenster. Frei "
                     "platzieren: „Mit der Maus verschieben“.")
        else:
            text = _("Frei platzieren: „Mit der Maus verschieben“ oder Vorgabe „eigene Position“.")
        self.pos_hint_var.set(text)

    def _anchor_text(self, key):
        return anchor_label(key)

    def _anchor_changed(self):
        self._layout_mark()
        rev = {_(v): k for k, v in ANCHORS}
        self.settings["overlay"]["anchor"] = rev.get(self.anchor_var.get(), "auto")
        self._pos_hint()
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _reset_position(self):
        self.anchor_var.set(anchor_label("auto"))
        self._anchor_changed()
        self._log(_("Position zurückgesetzt (automatisch)."), "Overlay")

    def _set_pos_sliders(self, fx, fy):
        fx, fy = min(1.0, max(0.0, fx)), min(1.0, max(0.0, fy))
        if abs(self.posx_var.get() - fx * 100) < 0.5 and abs(self.posy_var.get() - fy * 100) < 0.5:
            return
        self._syncing = True
        try:
            self.posx_var.set(round(fx * 100, 1))
            self.posy_var.set(round(fy * 100, 1))
            self.posx_label.configure(text=f"{fx * 100:.0f} %")
            self.posy_label.configure(text=f"{fy * 100:.0f} %")
        finally:
            self._syncing = False

    def _pos_changed(self):
        if self._syncing:
            return
        self._layout_mark()
        o = self.settings["overlay"]
        if o["anchor"] != "custom":
            o["anchor"] = "custom"
            self.anchor_var.set(anchor_label("custom"))
            self._pos_hint()
        o["pos_x"] = round(self.posx_var.get() / 100, 4)
        o["pos_y"] = round(self.posy_var.get() / 100, 4)
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _size_changed(self):
        self._layout_mark()
        self.settings["overlay"]["height"] = round(self.size_var.get() / 100, 3)
        self._sel_sync()
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _opacity_changed(self):
        """The opacity slider: the element picked (1.2.7; "text" is part of the map's window)."""
        key = OPACITY_KEYS.get(getattr(self, "_sel", "map"), "opacity")
        self.settings["overlay"][key] = round(self.opacity_var.get() / 100, 2)
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _overlay_flags_changed(self):
        o = self.settings["overlay"]
        o["only_when_game_focused"] = bool(self.focus_var.get())
        o["show_caption"] = bool(self.caption_var.get())
        o["show_timer"] = bool(self.timer_show_var.get())
        o["show_server"] = bool(self.server_show_var.get())
        o["keep_in_bar"] = bool(self.keep_bar_var.get())
        o["grow_past_bar"] = bool(self.grow_var.get())
        o["show_waiting"] = bool(self.waiting_var.get())
        if bool(self.record_var.get()) != o.get("show_record", True):
            o["show_record"] = bool(self.record_var.get())
            self._update_record()
        if bool(self.floor_auto_var.get()) != o.get("floor_auto", True):
            o["floor_auto"] = bool(self.floor_auto_var.get())
            self._floor = None if o["floor_auto"] else 0          # the map on display follows right away
        if bool(self.show_map_var.get()) != o.get("show_map", True):
            o["show_map"] = bool(self.show_map_var.get())
            self.overlay.set_show_map(o["show_map"])
            self._log(_("Karte im Overlay eingeblendet.") if o["show_map"] else
                      _("Karte im Overlay aus – es werden nur Timer, Ort und Ping angezeigt."), "Overlay")
        if bool(self.transp_var.get()) != o.get("transparent", True):
            o["transparent"] = bool(self.transp_var.get())
            self.overlay.set_transparent(o["transparent"])
        if self.current:
            self.overlay.show_caption = o["show_caption"]
            self._reload_picture()
        self._save_soon()
        self._tick_overlay(reschedule=False)

    # ---- 1.8.24: the map's lines as an element of their own (user: "Zeit etc. nicht mehr mit der Map verbunden")
    def _info_spot_changed(self):
        self._layout_mark()
        key = dict((_(label), k) for k, label in INFO_SPOTS).get(self.info_pos_var.get(), "below")
        self.settings["overlay"]["info_pos"] = key
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _info_card(self, gh, margin, bar):
        """Render the lines' card for this tick (their own size, ``text_scale`` – never the map's) into
        ``info_win``; returns (w, h), or None when there is nothing to show. In a black bar never wider than it."""
        from .overlay_win32 import add_border
        win, o = self.info_win, self.settings["overlay"]
        editing = bool(self.overlay.editing)
        win.set_editing(editing)
        self._info_size = None
        if self.overlay.waiting() or not self.overlay.has_map():
            return None
        text_h = self._text_height(gh)
        avail = layout.max_width(bar, margin) if bar >= layout.MIN_BAR else None     # also at an own place
        placeholder = "0:00" if editing else ""             # something to drag while moving
        pic = self.overlay.info_picture(text_h, placeholder)
        for _try in range(3):                               # wider than the bar: smaller text, the map stays
            if pic is None or avail is None or pic.width <= avail or text_h <= 40:
                break
            text_h = max(40, int(text_h * avail / pic.width) - 1)
            pic = self.overlay.info_picture(text_h, placeholder)
        if pic is None:
            return None
        key = (self.overlay._info_key, editing, win.edit_label)
        if editing:
            pic = add_border(pic.copy(), win.edit_label)
        win.opacity = float(o.get("info_opacity", o["opacity"]))
        self._info_size = win.set_picture(pic, key)
        return self._info_size

    def _info_place(self, rect, gx, gy, gw, gh, margin, fade):
        """Show the lines right below / above the map ``rect`` (or at their own place); returns their box."""
        o = self.settings["overlay"]
        if not self._info_size or not self.overlay.shown:
            self._info_hide(fade)
            return None
        x, y = layout.info_xy(o.get("info_pos", "below"), rect, self._info_size, (gx, gy, gw, gh),
                              layout.stack_gap(o, gh), margin, o.get("info_xy"), o.get("bar_align", "centre"),
                              self._bands(gx, gy, gw, gh))
        self._fade_show("info", fade)
        self.worker.info_rect = self._el_show("text", self.info_win, x, y, self._info_size)
        return self.worker.info_rect

    def _info_hide(self, fade):
        if getattr(self, "info_win", None) is not None:
            self._fade_hide("info", fade)
        self.worker.info_rect = None
        self._info_size = None

    def _info_dragged(self, x, y):
        """The lines dropped somewhere (moving mode): from now on their own place there."""
        self._layout_mark()
        gx, gy, gw, gh = self._game_rect()
        self._info_own_place(*layout.media_own(gw, gh, self.info_win.size, x - gx, y - gy))

    def _info_own_place(self, fx, fy):
        """The lines dragged in the preview or the game: their own place (their centre) from now on."""
        o = self.settings["overlay"]
        o["info_xy"], o["info_pos"] = [fx, fy], "custom"
        if hasattr(self, "info_pos_var"):
            self.info_pos_var.set(_(dict(INFO_SPOTS)["custom"]))
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _media_shape_changed(self):
        """The music card's cover round / square / like its style (1.8.24)."""
        key = dict((_(label), k) for k, label in COVER_SHAPES).get(self.media_shape_var.get(), "style")
        self.settings["overlay"]["media_cover_shape"] = key
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _same_width_changed(self):
        """1.8.29: the cards in one bar drawn at the widest one's width – on/off."""
        self._layout_mark()
        self.settings["overlay"]["cards_same_width"] = bool(self.same_width_var.get())
        self._save_soon()
        self._tick_overlay(reschedule=False)

    def _merge_column(self):
        """1.8.29 (user: "rechts sind die Felder nicht untereinander, evtl. zusammenführen"): one column in the
        bar of the system values – "today" right below them, the music below "today", all at one width (an
        undo step like a preset)."""
        from . import layoutmem
        self._layout_mark()
        snap = layoutmem.snapshot(self.settings.data)
        snap["overlay"].update(today_pos="below", media_pos="under_today", cards_same_width=True)
        self._layout_apply(snap)

    def _keep_out_changed(self):
        """1.8.25: Discord's overlay widgets kept free (hatched in the preview) – on/off."""
        self._layout_mark()
        self.settings["overlay"]["keep_out_on"] = bool(self.keep_out_var.get())
        self._save_soon()
        self._tick_overlay(reschedule=False)
