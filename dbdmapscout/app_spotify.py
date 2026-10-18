"""Mixin of App (1.8): Spotify "Als nächstes" – the settings card under "Mehr" (client id, login, logout, status),
the events of the ``spotify.SpotifyLink`` thread and the list the music card shows (app_sysinfo._media_card)."""
from __future__ import annotations

import webbrowser

from . import spotify
from . import uimodel as ui
from .i18n import N_, _

MEDIA_NEXT_SPOTS = [("below", N_("Unter dem Lied")), ("right", N_("Rechts neben dem Lied"))]
MEDIA_NEXT_N = (1, 5)                      # tracks shown
SAMPLE_UPNEXT = (("Save Your Tears", "The Weeknd"), ("Levitating", "Dua Lipa"), ("As It Was", "Harry Styles"),
                 ("Bad Habits", "Ed Sheeran"), ("Flowers", "Miley Cyrus"))     # "Overlay testen" / preview


class SpotifyUpNext:
    def _spotify_init(self):
        self.spotify = spotify.SpotifyLink(lambda kind, data: self.events.put(("spotify", kind, data)))
        self.spotify.start()
        self._spotify_setting(save=False)

    # ---------------------------------------------------------- settings card (Einstellungen → Mehr)
    def _spotify_card(self, more):
        sc = self._reg("st.more.spotify", ui.LabelFrame(more, text=_("Spotify"), padding=8))
        sc.pack(fill="x", pady=(8, 0))
        self.sp_on_var = ui.BooleanVar(value=bool(self.settings.get("spotify_on", False)))
        self._reg("st.more.sp_on", ui.Checkbutton(sc, text=_("„Als nächstes“ aus Spotify in der Musikkarte zeigen"),
                                                   variable=self.sp_on_var, command=self._spotify_setting)).pack(anchor="w")
        row = ui.Frame(sc)
        row.pack(fill="x", pady=(4, 0))
        self._reg("st.more.sp_id.label", ui.Label(row, text=_("Client-ID"))).pack(side="left")
        self.sp_id_var = ui.StringVar(value=str(self.settings.get("spotify_client_id", "")))
        self.sp_id_var.trace_add("write", lambda *a: self._spotify_setting())
        self._reg("st.more.sp_id", ui.Entry(row, textvariable=self.sp_id_var, width=34)).pack(side="left", padx=6)
        self._reg("st.more.sp_dash", ui.Button(row, text=_("Developer-Dashboard öffnen"),
                                                command=lambda: webbrowser.open(spotify.DASHBOARD))).pack(side="left")
        row2 = ui.Frame(sc)
        row2.pack(fill="x", pady=(4, 0))
        self._reg("st.more.sp_login", ui.Button(row2, text=_("Mit Spotify verbinden"),
                                                 command=self._spotify_login)).pack(side="left")
        self._reg("st.more.sp_logout", ui.Button(row2, text=_("Spotify-Verbindung trennen"),
                                                  command=self._spotify_logout)).pack(side="left", padx=(6, 0))
        self.sp_status_var = ui.StringVar(value="")
        self._reg("st.more.sp_status", ui.Label(sc, textvariable=self.sp_status_var, wraplength=420,
                                                 style="Dim.TLabel")).pack(anchor="w", pady=(4, 0))
        self._reg("st.more.sp_text", ui.Label(sc, text=_(
            "Zeigt in der Musikkarte, was in Spotify als Nächstes kommt (Position und Anzahl unter Overlay → Musik). "
            "Die Windows-Mediensteuerung kennt nur den laufenden Titel, die Liste holt das Programm deshalb von "
            "Spotify selbst: Dafür im Developer-Dashboard „Create app“ anlegen (Name frei, API „Web API“), als "
            "Redirect URI genau {uri} eintragen, die Client-ID kopieren und hier einfügen, dann „Mit Spotify "
            "verbinden“ – der Browser fragt einmal nach der Freigabe. Gelesen wird nur die Warteschlange, nichts "
            "gesteuert; die Freigabe liegt verschlüsselt auf diesem PC und lässt sich hier trennen. Titel kommen nie "
            "ins Log.", uri=spotify.REDIRECT_URI), style="Dim.TLabel", wraplength=420)).pack(anchor="w", pady=(4, 0))

    def _spotify_setting(self, save=True):
        on, cid = bool(self.sp_on_var.get()), self.sp_id_var.get().strip()
        if save:
            self.settings.set("spotify_on", on)
            self.settings.set("spotify_client_id", cid)
            self._save_soon()
        self.spotify.configure(on, cid, self.settings.get("spotify_token", ""))

    def _spotify_login(self):
        self._spotify_setting()
        if not spotify.valid_client_id(self.sp_id_var.get()):        # 1.8.1: the user pasted a user id once
            self.sp_status_var.set(spotify.BAD_ID_TEXT())
            return
        self.sp_status_var.set(_("Spotify: öffne die Anmeldung im Browser …"))
        self.spotify.login()

    def _spotify_logout(self):
        self.spotify.logout()

    def _spotify_event(self, kind, data):
        """Event from the thread: the status line (errors once in the log) or the token to keep."""
        if kind == "status":
            text, ok = data
            self.sp_status_var.set(text)
            if not ok and self.settings.get("spotify_on"):
                self._log(text, "Fehler")
        elif kind == "token":
            self.settings.set("spotify_token", str(data or ""))
            self._save_soon()

    # ---------------------------------------------------------- what the music card shows
    def _upnext(self, now, sample: bool = False):
        """(label, ((title, artist), …)) for the music card, or None: only with the setting on and when Spotify's
        current track is the one Windows shows (else the list belongs to another player). ``sample``: a sample
        list for "Overlay testen" and the preview when there is no real one."""
        if not self.settings.get("spotify_on", False):
            return None
        o = self.settings["overlay"]
        n = max(MEDIA_NEXT_N[0], min(MEDIA_NEXT_N[1], int(o.get("media_next_n", 3))))
        up = spotify.advance(self.spotify.upnext, now.title, now.artist)   # 1.8.1: moved up at once on a new song
        if spotify.matches(up, now.title, now.artist):
            items = spotify.lines(up, n)
        elif sample:
            items = SAMPLE_UPNEXT[:n]
        else:
            return None
        return (_("ALS NÄCHSTES"), items) if items else None

    def _media_next_changed(self):
        o = self.settings["overlay"]
        o["media_next_pos"] = dict((_(label), k) for k, label in MEDIA_NEXT_SPOTS).get(self.media_next_var.get(), "below")
        o["media_next_n"] = int(round(float(self.media_next_n_var.get())))
        self._save_soon()
