"""Mixin of App (1.10): YouTube upload – the settings card under Einstellungen → Verbindungen (client id and
secret, login, privacy, status), the events of the ``ytupload.Uploader`` thread, the queue the settings keep,
and what the recordings tab needs (enqueue a clip or a round, links of uploaded videos)."""
from __future__ import annotations

import os
import time
import webbrowser

from . import obsrec, spotify, ytupload
from . import uimodel as ui
from .capture import foreground_root, is_game_window
from .i18n import _
from .lobby import killer_label

FOLDER_EVERY_S = 5.0      # recorder.folder() asks every drive letter on Windows – not four times a second


class YouTubeUpload:
    def _youtube_init(self):
        self.youtube = ytupload.Uploader(lambda kind, data: self.events.put(("youtube", kind, data)))
        self.youtube.start()
        self._yt_sent = None                 # (paused, folder) last given to the thread
        self._yt_folder, self._yt_folder_at = "", 0.0
        self._yt_queued = set()              # rels waiting (mirror of the thread's queue, for the tables)
        self._youtube_setting(save=False)

    # ---------------------------------------------------------- settings card (Einstellungen → Verbindungen)
    def _youtube_card(self, more):
        yc = self._reg("st.more.youtube", ui.LabelFrame(more, text=_("YouTube"), padding=8))
        yc.pack(fill="x", pady=(8, 0))
        self.yt_on_var = ui.BooleanVar(value=bool(self.settings.get("youtube_on", False)))
        self._reg("st.more.yt_on", ui.Checkbutton(yc, text=_("Clips automatisch auf YouTube hochladen"),
                                                   variable=self.yt_on_var, command=self._youtube_setting)).pack(anchor="w")
        row = ui.Frame(yc)
        row.pack(fill="x", pady=(4, 0))
        self._reg("st.more.yt_id.label", ui.Label(row, text=_("Client-ID"))).pack(side="left")
        self.yt_id_var = ui.StringVar(value=str(self.settings.get("youtube_client_id", "")))
        self.yt_id_var.trace_add("write", lambda *a: self._youtube_setting())
        self._reg("st.more.yt_id", ui.Entry(row, textvariable=self.yt_id_var, width=34)).pack(side="left", padx=6)
        self._reg("st.more.yt_secret.label", ui.Label(row, text=_("Client-Secret"))).pack(side="left")
        self.yt_secret_var = ui.StringVar(value=spotify.unprotect(self.settings.get("youtube_client_secret", "")))
        self.yt_secret_var.trace_add("write", lambda *a: self._youtube_setting())
        secret = self._reg("st.more.yt_secret", ui.Entry(row, textvariable=self.yt_secret_var, width=22))
        secret._dbdms_secret = True
        secret.pack(side="left", padx=6)
        self._reg("st.more.yt_file", ui.Button(row, text=_("Client-Datei laden …"),
                                                command=self._youtube_file)).pack(side="left")       # 1.10.1
        self._reg("st.more.yt_console", ui.Button(row, text=_("Google Cloud Console öffnen"),
                                                   command=lambda: webbrowser.open(ytupload.CONSOLE))).pack(side="left", padx=(6, 0))
        row2 = ui.Frame(yc)
        row2.pack(fill="x", pady=(4, 0))
        self._reg("st.more.yt_privacy.label", ui.Label(row2, text=_("Sichtbarkeit"))).pack(side="left")
        self._yt_privacies = [(k, _(label)) for k, label in ytupload.PRIVACY]
        current = str(self.settings.get("youtube_privacy", "private"))
        self.yt_privacy_var = ui.StringVar(value=dict(self._yt_privacies).get(current, self._yt_privacies[0][1]))
        cb = self._reg("st.more.yt_privacy", ui.Combobox(row2, textvariable=self.yt_privacy_var, state="readonly",
                                                          width=14, values=[lbl for _k, lbl in self._yt_privacies]))
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self._youtube_setting())
        self._reg("st.more.yt_login", ui.Button(row2, text=_("Mit YouTube verbinden"),
                                                 command=self._youtube_login)).pack(side="left", padx=(6, 0))
        self._reg("st.more.yt_logout", ui.Button(row2, text=_("YouTube-Verbindung trennen"),
                                                  command=self._youtube_logout)).pack(side="left", padx=(6, 0))
        # 1.11: playlists – the login asks for the wider scope "youtube" only with this box ticked
        row3 = ui.Frame(yc)
        row3.pack(fill="x", pady=(4, 0))
        self.yt_pl_var = ui.BooleanVar(value=bool(self.settings.get("youtube_playlists", False)))
        self._reg("st.more.yt_pl_on", ui.Checkbutton(row3, text=_("Uploads in Playlists einsortieren"),
                                                      variable=self.yt_pl_var,
                                                      command=self._youtube_playlists_toggle)).pack(side="left")
        self._reg("st.more.yt_pl_load", ui.Button(row3, text=_("Playlists laden"),
                                                   command=self._youtube_playlists_load)).pack(side="left", padx=(6, 0))
        row4 = ui.Frame(yc)
        row4.pack(fill="x", pady=(4, 0))
        self.yt_pl_vars = {"clip": ui.StringVar(), "round": ui.StringVar()}
        self._yt_pl_items = []
        self._reg("st.more.yt_pl_clip.label", ui.Label(row4, text=_("Clips in"))).pack(side="left")
        self.yt_pl_cbs = {"clip": self._reg("st.more.yt_pl_clip", ui.Combobox(
            row4, textvariable=self.yt_pl_vars["clip"], state="readonly", width=22, values=[]))}
        self.yt_pl_cbs["clip"].pack(side="left", padx=6)
        self._reg("st.more.yt_pl_round.label", ui.Label(row4, text=_("Runden in"))).pack(side="left", padx=(10, 0))
        self.yt_pl_cbs["round"] = self._reg("st.more.yt_pl_round", ui.Combobox(
            row4, textvariable=self.yt_pl_vars["round"], state="readonly", width=22, values=[]))
        self.yt_pl_cbs["round"].pack(side="left", padx=6)
        for cb in self.yt_pl_cbs.values():
            cb.bind("<<ComboboxSelected>>", lambda e: self._youtube_setting())
        self._yt_playlists_fill()
        self.yt_status_var = ui.StringVar(value="")
        self._reg("st.more.yt_status", ui.Label(yc, textvariable=self.yt_status_var, wraplength=420,
                                                 style="Dim.TLabel")).pack(anchor="w", pady=(4, 0))
        self._reg("st.more.yt_text", ui.Label(yc, text=_(
            "Lädt Clips (F8 und Editor) von selbst auf deinen YouTube-Kanal, Runden nur auf Wunsch: Rechtsklick oder "
            "„Auf YouTube hochladen“ unter Aufnahmen. Dafür einmal in der Google Cloud Console ein Projekt anlegen, "
            "„YouTube Data API v3“ aktivieren, unter „Anmeldedaten“ einen OAuth-Client vom Typ „Desktop-App“ erstellen "
            "und den Zustimmungsbildschirm veröffentlichen (sonst läuft die Anmeldung nach 7 Tagen ab); Client-ID und "
            "Client-Secret hier einfügen oder die heruntergeladene JSON-Datei laden, dann „Mit YouTube verbinden“ – der Browser fragt einmal nach der Freigabe. "
            "Google erlaubt mit dem Standardkontingent etwa sechs Uploads am Tag; was nicht mehr passt, wartet in der "
            "Warteschlange bis zum nächsten Tag. Hochgeladen wird nur, wenn du weder in einer Lobby noch in einer Runde bist; die Datei bleibt immer "
            "auch auf der Platte. Gesendet werden nur die Videodatei, Titel (Map, Killer, Datum) und Beschreibung – "
            "nie Spielernamen; die Freigabe liegt verschlüsselt auf diesem PC. Mit „Uploads in Playlists einsortieren“ kommt jedes Video "
            "zusätzlich in eine Playlist deiner Wahl – dafür fragt die Anmeldung die breitere Berechtigung „YouTube-Konto "
            "verwalten“ an (einmal neu verbinden)."),
            style="Dim.TLabel", wraplength=420)).pack(anchor="w", pady=(4, 0))

    def _youtube_setting(self, save=True):
        on, cid = bool(self.yt_on_var.get()), self.yt_id_var.get().strip()
        secret = self.yt_secret_var.get().strip()
        privacy = next((k for k, lbl in self._yt_privacies if lbl == self.yt_privacy_var.get()), "private")
        manage = bool(self.yt_pl_var.get())
        playlists = {key: self._yt_pl_id(var.get()) for key, var in self.yt_pl_vars.items()}
        if save:
            self.settings.set("youtube_on", on)
            self.settings.set("youtube_client_id", cid)
            self.settings.set("youtube_client_secret", spotify.protect(secret))
            self.settings.set("youtube_privacy", privacy)
            self.settings.set("youtube_playlists", manage)
            for key, pid in playlists.items():
                self.settings.set(f"youtube_playlist_{key}", pid)
            self._save_soon()
        self.youtube.configure(on, cid, secret, privacy, self.settings.get("youtube_token", ""),
                               self.settings.get("youtube_queue") or [], self.settings.get("youtube_quota") or {},
                               manage=manage, playlists=playlists)
        self._yt_queued = {str(d.get("rel")) for d in (self.settings.get("youtube_queue") or [])
                           if isinstance(d, dict) and d.get("rel")}

    def _youtube_login(self):
        self._youtube_setting()
        if not ytupload.valid_client_id(self.yt_id_var.get()) or not self.yt_secret_var.get().strip():
            self.yt_status_var.set(_("YouTube: Client-ID (…apps.googleusercontent.com) und Client-Secret eintragen."))
            return
        self.yt_status_var.set(_("YouTube: öffne die Anmeldung im Browser …"))
        self.youtube.login()

    def _youtube_logout(self):
        self.youtube.logout()

    # ---------------------------------------------------------- playlists (1.11)
    def _yt_pl_names(self) -> dict:
        names = self.settings.get("youtube_playlist_names") or {}
        return {str(k): str(v) for k, v in names.items() if k} if isinstance(names, dict) else {}

    def _yt_playlists_fill(self):
        """The two choices: "(keine)" + the playlists Google listed; a chosen id Google no longer lists stays
        selectable under its id. Labels are made unique (two playlists may share a title)."""
        names = self._yt_pl_names()
        chosen = {key: str(self.settings.get(f"youtube_playlist_{key}") or "") for key in self.yt_pl_vars}
        for pid in chosen.values():
            if pid:
                names.setdefault(pid, pid)
        items, seen = [("", _("(keine)"))], {_("(keine)")}
        for pid, title in sorted(names.items(), key=lambda kv: (kv[1].lower(), kv[0])):
            label = title
            if label in seen:
                label = f"{title} ({pid[-4:]})"
            seen.add(label)
            items.append((pid, label))
        self._yt_pl_items = items
        labels = [lbl for _pid, lbl in items]
        for key, cb in self.yt_pl_cbs.items():
            cb.configure(values=labels)
            self.yt_pl_vars[key].set(next((lbl for pid, lbl in items if pid == chosen[key]), labels[0]))

    def _yt_pl_id(self, label: str) -> str:
        return next((pid for pid, lbl in self._yt_pl_items if lbl == label), "")

    def _youtube_playlists_toggle(self):
        self._youtube_setting()
        if self.yt_pl_var.get() and self._yt_ready() and not self._yt_pl_names():
            self.yt_status_var.set(_("YouTube: lade Playlists …"))
            self.youtube.list_playlists()

    def _youtube_playlists_load(self):
        self._youtube_setting()
        if not self.yt_pl_var.get():
            self.yt_status_var.set(_("YouTube: zuerst „Uploads in Playlists einsortieren“ anhaken."))
            return
        if not self._yt_ready():
            self.yt_status_var.set(_("YouTube: nicht verbunden – „Mit YouTube verbinden“ klicken."))
            return
        self.yt_status_var.set(_("YouTube: lade Playlists …"))
        self.youtube.list_playlists()

    def _youtube_file(self, path=None):
        """1.10.1: the client_secret_….json Google offers after the OAuth client was created – no copying of id
        and secret by hand (Google shows the secret only once). The file is read once and stays where it is."""
        if path is None:
            from .official import downloads_dir
            start = downloads_dir()
            self._qt_file("open", _("Client-Datei von Google laden"), start if os.path.isdir(start) else "",
                          self._youtube_file)
            return
        try:
            cid, secret = ytupload.read_client_file(path)
        except ValueError as e:
            self._inform(_("Client-Datei laden"), _("Das ist keine Client-Datei von Google ({error}).", error=e))
            return
        self.yt_id_var.set(cid)
        self.yt_secret_var.set(secret)
        self._youtube_setting()
        self.yt_status_var.set(_("YouTube: Client-ID und Client-Secret aus {file} übernommen – jetzt „Mit YouTube verbinden“ klicken.",
                               file=os.path.basename(path)))
        self._log(_("YouTube: Client-Daten aus {file} übernommen.", file=os.path.basename(path)), "System")

    def _youtube_tick(self):
        """Every tick: the thread learns whether uploads must pause and where the recordings are. 1.11.2: paused
        not only during a round (map detected / OBS recording) but from the lobby on – searching, lobby found,
        custom game, loading screen – while the game window is there: the upload saturates the upstream, and the
        connection to the server is made before the banner (before, the first ~40 s of a match were unprotected)."""
        yt = getattr(self, "youtube", None)
        if yt is None:
            return
        now = time.time()
        if now - self._yt_folder_at >= FOLDER_EVERY_S:
            self._yt_folder, self._yt_folder_at = self.recorder.folder() or "", now
        state = (self._yt_pause_wanted(), self._yt_folder)
        if state != self._yt_sent:
            self._yt_sent = state
            yt.set_paused(state[0])
            yt.set_folder(state[1])

    def _yt_pause_wanted(self) -> bool:
        """A round runs, or DBD is open and the lobby state is not idle (search / lobby / custom)."""
        if self._round_running():
            return True
        in_game = getattr(self, "game", None) is not None
        return in_game and str((getattr(self, "_queue", None) or {}).get("state", "idle")) != "idle"

    # ---------------------------------------------------------- events from the thread
    def _youtube_event(self, kind, data):
        if kind == "status":
            text, ok = data
            self.yt_status_var.set(text)
            if not ok:
                self._log(text, "Fehler")
        elif kind == "token":
            self.settings.set("youtube_token", str(data or ""))
            self._save_soon()
        elif kind == "queue":
            self.settings.set("youtube_queue", list(data or []))
            self._yt_queued = {str(d.get("rel")) for d in data if isinstance(d, dict) and d.get("rel")}
            self._rec_dirty = True
            self._save_soon()
        elif kind == "quota":
            self.settings.set("youtube_quota", dict(data or {}))
            self._save_soon()
        elif kind == "done":
            self.recorder.set_link(data.get("kind", "clip"), data.get("rel", ""), data.get("id", ""))
            self._log(_("YouTube: hochgeladen – {file} → {url}", file=os.path.basename(data.get("rel", "")),
                        url=data.get("url", "")), "System")
            if not (self.game is not None and not self.simulate and is_game_window(foreground_root())):
                self.toast.show(_("YouTube"), _("Hochgeladen: {file}", file=os.path.basename(data.get("rel", ""))))
        elif kind == "failed":
            self._log(_("YouTube: nicht hochgeladen – {file}: {why}", file=os.path.basename(data.get("rel", "")),
                        why=data.get("why", "")), "Fehler")
        elif kind == "playlists":                             # 1.11
            if data.get("ok"):
                names = {str(pid): str(title) for pid, title in (data.get("items") or []) if pid}
                self.settings.set("youtube_playlist_names", names)
                self._save_soon()
                self._yt_playlists_fill()
                self.yt_status_var.set(_("YouTube: {n} Playlists geladen – im Kasten auswählen", n=len(names)) if names
                                       else _("YouTube: keine Playlists auf dem Kanal – zuerst auf YouTube eine anlegen"))
            else:
                self._log(_("YouTube: Playlists nicht geladen – {why}", why=data.get("why", "")), "Fehler")
        elif kind == "playlist":
            file, pid = os.path.basename(data.get("rel", "")), str(data.get("playlist") or "")
            if data.get("ok"):
                self._log(_("YouTube: {file} in Playlist „{name}“ einsortiert", file=file,
                            name=self._yt_pl_names().get(pid, pid)), "System")
            else:
                self._log(_("YouTube: {file} hochgeladen, aber nicht in die Playlist – {why}", file=file,
                            why=data.get("why", "")), "Fehler")

    # ---------------------------------------------------------- what the recordings tab asks for
    def _yt_who(self, role, killer) -> str:
        return killer_label(self._killer_of(killer)) if role == "killer" and killer else (self._role_name(role) or "")

    def _yt_enqueue(self, kind: str, rel: str, label: str, role: str, killer: str, t: float, seconds: float = 0.0):
        """A file of the recordings folder into the upload queue (nothing twice)."""
        yt = getattr(self, "youtube", None)
        if yt is None or not rel or rel in self._yt_queued:
            return False
        if os.path.splitext(rel)[1].lower() not in ytupload.VIDEO_EXTS:
            return False
        title, text = ytupload.describe(kind, label or "", self._yt_who(role, killer), t, seconds)
        yt.add(ytupload.Job(rel=rel.replace(os.sep, "/"), kind=kind, title=title, description=text))
        self._yt_queued.add(rel)
        self._rec_dirty = True
        self._log(_("YouTube: in die Warteschlange – {file}", file=os.path.basename(rel)), "System")
        return True

    def _yt_auto_clip(self, name: str, label: str, role: str, killer: str, t: float, seconds: float = 0.0):
        """1.10: a new clip (F8 / editor) – uploaded by itself when the box is ticked and the login is there."""
        if not self.settings.get("youtube_on", False) or not getattr(self, "youtube", None) or not self.youtube.linked:
            return
        self._yt_enqueue("clip", f"{obsrec.CLIPS_DIR}/{os.path.basename(name)}", label, role, killer, t, seconds)

    def _yt_ready(self) -> bool:
        yt = getattr(self, "youtube", None)
        return yt is not None and yt.linked

    def _yt_mark(self, rel: str, video_id: str) -> str:
        """What the tables show in their YouTube column."""
        if video_id:
            return "✓"
        return "…" if rel in self._yt_queued else ""

    def _yt_copy_link(self, video_id: str):
        self.root.clipboard_set(ytupload.video_url(video_id))
        self._log(_("YouTube-Link kopiert: {url}", url=ytupload.video_url(video_id)), "System")

    def _yt_open_link(self, video_id: str):
        webbrowser.open(ytupload.video_url(video_id))
