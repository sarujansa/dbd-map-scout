"""Lobby: search, waiting time and role from the worker, notifications (sound + own window).

Mixin of App (app.py) – the methods use App's attributes; split out of app.py unchanged."""
from __future__ import annotations

import logging

from .capture import IS_WIN, foreground_root, is_game_window
from .i18n import _
from .lobby import killer_label
from .textnorm import fmt_duration

log = logging.getLogger("dbdmapscout")


class LobbyInfo:
    def _notify_flags_changed(self):
        for key, v in self.notify_vars.items():
            self.settings.set(key, bool(v.get()))
        self._save_soon()

    def _notify(self, title, text, force=False):
        """Sound + own notification window (lobby found, countdown) – only local, nothing goes to the game."""
        if (not force and self.settings.get("notify_background_only", True) and not self.simulate
                and self.game is not None):
            fg = foreground_root()
            if is_game_window(fg):
                return                                   # DBD is in front: the player sees it anyway
        try:
            if IS_WIN:
                import winsound
                winsound.PlaySound("SystemNotification", winsound.SND_ALIAS | winsound.SND_ASYNC)
            else:
                self.root.bell()
        except Exception:
            log.debug("notify sound", exc_info=True)
        # own window instead of a Windows notification: those are swallowed by "Do not disturb",
        # which Windows turns on by itself while a game runs
        self.toast.show(title, text)

    # ---------------------------------------------------------- lobby: search, waiting time, role
    def _role_name(self, role):
        return {"killer": _("Killer"), "survivor": _("Survivor")}.get(role, "")

    def _queue_text(self, now):
        q = self._queue
        role = self._role_name(q.get("role"))
        if q.get("role") == "killer" and q.get("killer"):
            role = killer_label(q["killer"])                 # "Nurse" says more than "Killer"
        if q["state"] == "search" and q.get("since"):
            text = _("Suche läuft: {time}", time=fmt_duration(max(0.0, now - q["since"])))
            return text + (f" · {role}" if role else "")
        f = q.get("found") or q.get("used")          # lobby found / the round it led to
        if q["state"] == "custom" or (f is not None and f.custom):
            return _("Custom Game")
        if f is not None:
            parts = ([_("Rolle: {role}", role=role)] if role else []) + \
                ([_("Wartezeit {time}", time=fmt_duration(f.wait))] if f.wait is not None else [])
            return " · ".join(parts)
        return ""

    def _queue_event(self, d):
        prev, what = self._queue, d.get("what")
        if what == "search":
            self._queue = {"state": "search", "since": d.get("since"), "role": d.get("role") or prev.get("role"),
                           "killer": d.get("killer") or prev.get("killer", "")}
            if prev.get("state") != "search":
                self._log(_("Suche nach einem Match gestartet."), "Erkennung")
        elif what == "cancel":
            self._queue = {"state": "idle"}
            self._log(_("Suche abgebrochen."), "Erkennung")
        elif what == "found" and d.get("found") is not None:
            f = d["found"]
            self._queue = {"state": "custom" if f.custom else "lobby", "role": f.role, "killer": f.killer, "found": f}
            if not f.custom and self.settings.get("lobby_notify", True):
                self._notify(_("Lobby gefunden"), (_("nach {time}", time=fmt_duration(f.wait)) + " – "
                                                   if f.wait is not None else "") + _("READY drücken."))
            if f.custom:
                self._log(_("Custom Game – keine Wartezeit."), "Erkennung")
            else:
                who = f" ({self._role_name(f.role)}{', ' + f.killer if f.killer else ''})" if f.role else ""
                if f.wait is not None:
                    self._log(_("Lobby gefunden nach {time}{role}.", time=fmt_duration(f.wait), role=who), "Erkennung")
                else:
                    self._log(_("Lobby gefunden{role}.", role=who), "Erkennung")
        elif what == "remind":
            if self.settings.get("lobby_remind", True):
                self._notify(_("Lobby startet gleich"), _("Noch {n} s – READY ist noch nicht gedrückt.",
                                                           n=int(d.get("seconds") or 0)))
                self._log(_("Lobby-Countdown läuft ab, READY ist noch nicht gedrückt."), "Erkennung")
        else:
            self._queue = dict(prev, role=d.get("role") or prev.get("role"),
                               killer=d.get("killer") or prev.get("killer", ""))
