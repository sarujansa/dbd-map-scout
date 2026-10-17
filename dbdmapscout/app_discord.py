"""Mixin of App (1.7): Discord Rich Presence – the settings card under "Mehr", the game state for the
``discordrpc.Presence`` thread (from the 250-ms tick) and its status line."""
from __future__ import annotations

import webbrowser

from . import discordrpc
from . import uimodel as ui
from .i18n import _
from .lobby import killer_label

PORTAL = "https://discord.com/developers/applications"


class DiscordPresence:
    def _discord_init(self):
        self.presence = discordrpc.Presence(lambda text, ok: self.events.put(("discord", text, ok)))
        self.presence.start()
        self._discord_setting(save=False)

    # ---------------------------------------------------------- settings card (Einstellungen → Mehr)
    def _discord_card(self, more):
        dc = self._reg("st.more.discord", ui.LabelFrame(more, text=_("Discord"), padding=8))
        dc.pack(fill="x", pady=(8, 0))
        self.dc_on_var = ui.BooleanVar(value=bool(self.settings.get("discord_on", False)))
        self._reg("st.more.dc_on", ui.Checkbutton(dc, text=_("Spielstatus in Discord anzeigen (Rich Presence)"),
                                                   variable=self.dc_on_var, command=self._discord_setting)).pack(anchor="w")
        row = ui.Frame(dc)
        row.pack(fill="x", pady=(4, 0))
        self._reg("st.more.dc_id.label", ui.Label(row, text=_("Application-ID"))).pack(side="left")
        self.dc_id_var = ui.StringVar(value=str(self.settings.get("discord_client_id", "")))
        self.dc_id_var.trace_add("write", lambda *a: self._discord_setting())
        self._reg("st.more.dc_id", ui.Entry(row, textvariable=self.dc_id_var, width=22)).pack(side="left", padx=6)
        self._reg("st.more.dc_test", ui.Button(row, text=_("Discord testen"), command=self._discord_test)).pack(side="left")
        self._reg("st.more.dc_portal", ui.Button(row, text=_("Developer-Portal öffnen"),
                                                  command=lambda: webbrowser.open(PORTAL))).pack(side="left", padx=(6, 0))
        self.dc_killer_var = ui.BooleanVar(value=bool(self.settings.get("discord_killer", True)))
        self._reg("st.more.dc_killer", ui.Checkbutton(dc, text=_("Killer in Discord anzeigen"),
                                                       variable=self.dc_killer_var, command=self._discord_setting)).pack(anchor="w", pady=(4, 0))
        self.dc_lobby_var = ui.BooleanVar(value=bool(self.settings.get("discord_lobby", True)))
        self._reg("st.more.dc_lobby", ui.Checkbutton(dc, text=_("Auch Lobby, Suche und Menü anzeigen"),
                                                      variable=self.dc_lobby_var, command=self._discord_setting)).pack(anchor="w")
        self.dc_status_var = ui.StringVar(value="")
        self._reg("st.more.dc_status", ui.Label(dc, textvariable=self.dc_status_var, wraplength=420,
                                                 style="Dim.TLabel")).pack(anchor="w", pady=(4, 0))
        self._reg("st.more.dc_text", ui.Label(dc, text=_(
            "Zeigt in deinem Discord-Status, was gerade läuft: „Nurse auf Coal Tower“ mit Rundenzeit, in der Lobby "
            "„Sucht ein Match“. Discord braucht dafür eine Application-ID: im Developer-Portal „New Application“ "
            "anlegen (als Name z. B. „Dead by Daylight“ – so steht es im Status), die Application-ID kopieren und "
            "hier eintragen. Das Programm spricht nur mit dem Discord-Client auf diesem PC (lokale Pipe), ohne ID "
            "wird nichts gesendet; Discord erfährt nur Map, Rolle, Killer und die Startzeit."),
            style="Dim.TLabel", wraplength=420)).pack(anchor="w", pady=(4, 0))

    def _discord_setting(self, save=True):
        on, cid = bool(self.dc_on_var.get()), self.dc_id_var.get().strip()
        show_killer, show_lobby = bool(self.dc_killer_var.get()), bool(self.dc_lobby_var.get())
        if save:
            self.settings.set("discord_on", on)
            self.settings.set("discord_client_id", cid)
            self.settings.set("discord_killer", show_killer)
            self.settings.set("discord_lobby", show_lobby)
            self._save_soon()
        self.presence.configure(on, cid, show_killer, show_lobby)

    def _discord_test(self):
        self.dc_status_var.set(_("Verbinde mit Discord …"))
        self._discord_setting()
        self.presence.test()

    def _discord_status(self, text, ok):
        """Event from the presence thread: the status line, and errors once in the log."""
        self.dc_status_var.set(text)
        if not ok and self.settings.get("discord_on"):
            self._log(text, "Fehler")

    # ---------------------------------------------------------- the game state (every 250 ms, coalesced)
    def _discord_state(self) -> discordrpc.GameState:
        running = self.game is not None and not self.simulate
        h, q = self._hist, self._queue
        if h is not None:
            m = self.catalog.maps.get(h.get("map_id"))
            return discordrpc.GameState(running, "match", h.get("map", ""), self._realm_name(m) if m else "",
                                        h.get("role") or "", self._killer_name(h.get("killer")), h.get("t"))
        if self.current and self.round.running:          # a map shown by hand (hotkey, Maps page)
            m = self.catalog.maps.get(self.current)
            return discordrpc.GameState(running, "match", m.label(1) if m else str(self.current),
                                        self._realm_name(m) if m else "", q.get("role") or "",
                                        self._killer_name(q.get("killer")), self.round.start_t)
        state = q.get("state")
        if state in ("search", "lobby", "custom"):
            f = q.get("found")
            since = q.get("since") if state == "search" else (f.t if f is not None else None)
            return discordrpc.GameState(running, state, role=q.get("role") or "",
                                        killer=self._killer_name(q.get("killer")), since=since)
        return discordrpc.GameState(running, "menu")

    def _killer_name(self, name) -> str:
        return killer_label(self._killer_of(name)) if name else ""

    def _discord_tick(self):
        self.presence.update(self._discord_state())
