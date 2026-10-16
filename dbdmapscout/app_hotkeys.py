"""Global hotkeys and recording a new combination by pressing it.

Mixin of App (app.py) – the methods use App's attributes; split out of app.py unchanged."""
from __future__ import annotations

from types import SimpleNamespace

from .capture import IS_WIN, foreground_root, is_game_window
from .i18n import N_, _
from .hotkeys import HotkeyThread, combo_from_keys, game_only, modifier_name, pretty

HOTKEY_LABELS = [("toggle_overlay", N_("Overlay ein/aus")), ("next_variant", N_("Layout-Variante")),
                 ("scan_now", N_("Bildschirm scannen")), ("prev_map", N_("Vorherige Map")),
                 ("next_map", N_("Nächste Map")), ("bigger", N_("Grösser")), ("smaller", N_("Kleiner")),
                 ("edit_position", N_("Mit Maus verschieben")), ("rotate_map", N_("Karte drehen")),
                 ("next_floor", N_("Etage wechseln")), ("reject_map", N_("Falsch erkannt"))]


class Hotkeys:
    # ============================================================ hotkeys
    def _start_hotkeys(self):
        t = HotkeyThread(self.settings["hotkeys"], lambda name: self.events.put(("hotkey", name)))
        t.on_failed = lambda name, combo, why: self.events.put(("hotkey_failed", name, combo, why))
        t.start()
        self.root.after(300, lambda: self._report_hotkeys(t))
        return t

    def _hotkeys_tick(self):
        """Single keys (F5, Numpad …) are hotkeys only while DBD is the active window – every other program
        keeps them."""
        fg = self.game is not None and not self.simulate and is_game_window(foreground_root())
        self.hotkeys.set_game_active(fg)

    def _hotkey_failed(self, name, combo, why):
        self._log(_("Hotkey {keys} ({action}) nicht verfügbar: {why}.", keys=pretty(combo),
                    action=_(dict(HOTKEY_LABELS).get(name, name)), why=why), "Fehler")

    def _report_hotkeys(self, t):
        if not t.ready.is_set():
            self.root.after(300, lambda: self._report_hotkeys(t))
            return
        labels = dict(HOTKEY_LABELS)
        for name, combo, why in t.failed:
            self._log(_("Hotkey {keys} ({action}) nicht verfügbar: {why}.", keys=pretty(combo),
                        action=_(labels.get(name, name)), why=why), "Fehler")
        if t.failed and hasattr(self, "hk_status"):
            self.hk_status.set(_("{n} Hotkey(s) nicht verfügbar – siehe Log.", n=len(t.failed)))

    # ---------------------------------------------------------- hotkeys: record by pressing
    def _hk_show_all(self):
        for key, b in self.hk_buttons.items():
            combo = self.settings["hotkeys"].get(key, "")
            b.configure(text=pretty(combo) if combo else _("– aus –"))

    def _hk_begin(self, key):
        """Start recording ``key`` (the window's HotkeyButton sends the keys pressed, _hk_qt_key)."""
        if self._hk_rec:
            self._hk_stop(save=False)
        self._hk_rec, self._hk_mods = key, set()
        self.hk_buttons[key].configure(text=_("Tasten drücken …"))
        # registered global hotkeys never reach this window: release them while recording
        self.hotkeys.stop()
        self.hotkeys.join(timeout=1.5)
        self.hk_status.set(_("Neue Kombination drücken – Esc bricht ab, Entf schaltet den Hotkey aus."))

    def _hk_qt_key(self, key, mods, keysym, keycode):
        """A key pressed in the window while ``key`` records."""
        if self._hk_rec != key:
            return
        self._hk_mods = set(mods)
        self._hk_key(SimpleNamespace(keysym=keysym or "", keycode=keycode))

    def _hk_key(self, e):
        key = self._hk_rec
        if key is None:
            return None
        if e.keysym == "Escape":
            self._hk_stop(save=False)
            return "break"
        if e.keysym in ("Delete", "BackSpace") and not self._hk_mods:
            self._hk_stop(save=True, combo="")
            return "break"
        m = modifier_name(e.keysym)
        if m:
            self._hk_mods.add(m)
            held = [m for m in ("ctrl", "alt", "shift") if m in self._hk_mods]
            self.hk_buttons[key].configure(text=pretty("+".join(held)) + "+ …")
            return "break"
        combo, why = combo_from_keys(self._hk_mods, e.keysym, e.keycode if IS_WIN else None)
        if combo is None:
            if why:
                self.hk_status.set(why)
            return "break"
        labels = dict(HOTKEY_LABELS)
        taken = [k for k, c in self.settings["hotkeys"].items() if c == combo and k != key]
        if taken:
            self.hk_status.set(_("{keys} ist schon „{action}“ – andere wählen.", keys=pretty(combo),
                                  action=_(labels.get(taken[0], taken[0]))))
            return "break"
        self._hk_stop(save=True, combo=combo)
        return "break"

    def _hk_stop(self, save: bool, combo: str = ""):
        key, self._hk_rec = self._hk_rec, None
        if key is None:
            return
        if save:
            self.settings["hotkeys"][key] = combo
            self._save_soon()
            label = _(dict(HOTKEY_LABELS)[key])
            keys = pretty(combo) if combo else _("aus")
            self.hk_status.set(f"{label}: {keys}" + ("  " + _("Gilt nur, solange DBD im Vordergrund ist – DBD selbst "
                                                               "bekommt {keys} dann nicht mehr (in DBD nicht belegt?).",
                                                               keys=keys) if game_only(combo) else ""))
            self._log(_("Hotkey {action}: {keys}.", action=label, keys=keys), "System")
        else:
            self.hk_status.set(_("Zum Ändern anklicken und die neue Tastenkombination drücken."))
        self._hk_show_all()
        self.hotkeys = self._start_hotkeys()

    def _hk_set(self, key, what):
        """1.2.19: one hotkey to its default ("default") or off ("off") – from the button's right-click menu."""
        from .config import DEFAULTS
        if key not in DEFAULTS["hotkeys"]:
            return
        if self._hk_rec:
            self._hk_stop(save=False)
        combo = DEFAULTS["hotkeys"][key] if what == "default" else ""
        taken = [k for k, c in self.settings["hotkeys"].items() if combo and c == combo and k != key]
        if taken:
            self.hk_status.set(_("{keys} ist schon „{action}“ – andere wählen.", keys=pretty(combo),
                                  action=_(dict(HOTKEY_LABELS).get(taken[0], taken[0]))))
            return
        self._hk_rec = key
        self._hk_stop(save=True, combo=combo)        # saves, logs, shows all, restarts the hotkey thread

    def _hk_defaults(self):
        from .config import DEFAULTS
        if self._hk_rec:
            self._hk_stop(save=False)
        self.settings["hotkeys"].update(DEFAULTS["hotkeys"])
        self._save_soon()
        self._hk_show_all()
        self.hotkeys.stop()
        self.hotkeys.join(timeout=1.5)
        self.hotkeys = self._start_hotkeys()
        self.hk_status.set(_("Standard-Hotkeys wiederhergestellt."))
