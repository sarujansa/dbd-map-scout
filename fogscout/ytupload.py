"""YouTube upload (1.10, user's explicit decision: "ich zahle für YouTube … Clips immer hochladen, bestimmte Videos
per Rechtsklick oder Knopf"). This lifts the project's "no upload" rule for exactly this feature.

What leaves the PC and where to: only to Google (``ENDPOINTS``) – the OAuth login and token refresh
(``accounts.google.com`` / ``oauth2.googleapis.com``) and the video bytes plus a title/description of our own
making (``www.googleapis.com/upload/youtube/v3/videos``). Nothing is read from the account but the answers to
these requests. Only files from the recordings folder (``Job.rel``) are uploaded; the local file always stays.

- The user registers an OAuth client of type "Desktop app" in the Google Cloud console (YouTube Data API v3
  enabled) and enters its **Client-ID and Client-Secret** (both DPAPI-protected like the Spotify token; Google
  treats a desktop client's secret as not confidential and still requires it in the token requests).
- Login: OAuth 2 with PKCE in the browser; the redirect comes back to ``spotify.LoginServer`` on a free loopback
  port (Google's desktop clients accept any ``http://127.0.0.1:<port>``). The refresh token is kept, protected.
- Uploads are **resumable** (one POST that opens a session, then PUTs of ``CHUNK`` bytes with ``Content-Range``;
  Google answers 308 with how far it got, the last PUT answers the video). A pause (a round is running: the
  upload would eat the game's bandwidth), a network error or a restart continue where Google says
  (``resume_point``) – the session URI is kept in the queue, the queue in the settings.
- **Quota**: the YouTube Data API grants 10 000 units per project and day, a ``videos.insert`` costs 1 600 –
  six uploads a day, whatever the user pays YouTube. ``Quota`` counts them (the day turns at Pacific midnight,
  taken as 08:00 UTC: during daylight time the real reset is an hour earlier, so we wait that hour); a
  ``quotaExceeded`` answer marks the day used up. The queue waits for the next day, nothing is dropped.
- Only the standard library (urllib, json, secrets). Everything but the thread is pure; ``ENDPOINTS`` and
  ``OPENER`` let the tests point it at a fake Google on 127.0.0.1.
"""
from __future__ import annotations

import calendar
import json
import logging
import os
import queue
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import asdict, dataclass

from . import spotify
from .i18n import N_, _
from .textnorm import fmt_duration

log = logging.getLogger(__name__)

ENDPOINTS = {"auth": "https://accounts.google.com/o/oauth2/v2/auth",
             "token": "https://oauth2.googleapis.com/token",
             "upload": "https://www.googleapis.com/upload/youtube/v3/videos",
             "playlists": "https://www.googleapis.com/youtube/v3/playlists",          # 1.11: playlists.list (mine)
             "items": "https://www.googleapis.com/youtube/v3/playlistItems"}          # 1.11: playlistItems.insert
CONSOLE = "https://console.cloud.google.com/apis/credentials"
SCOPE = "https://www.googleapis.com/auth/youtube.upload"
SCOPE_MANAGE = "https://www.googleapis.com/auth/youtube"   # 1.11: playlists (list + add); asked for only with the box ticked
PLAYLIST_COST = 50                # playlistItems.insert (units)
LIST_COST = 1                     # playlists.list, per page of 50
PLAYLIST_PAGES = 4                # at most 200 playlists are listed
REDIRECT_PATH = spotify.REDIRECT_PATH
LOGIN_WAIT_S = 180.0
QUOTA_DAY = 10000                 # units per project and day (Google's default)
UPLOAD_COST = 1600                # videos.insert
QUOTA_RESET_UTC_H = 8             # Pacific midnight in standard time (PST); see the module docstring
QUOTA_RESET_DST_UTC_H = 7         # 1.11.2: … and in daylight time (PDT, second Sunday of March to first of November)
CHUNK = 8 << 20                   # bytes per PUT – a multiple of 256 KiB (Google's rule)
HTTP_TIMEOUT = 60.0               # a chunk of 8 MB needs a while on a slow line
RETRY_S = 60.0                    # after a network error
REFRESH_AHEAD_S = 60.0            # a token this close to expiry is refreshed first
TICK_BUDGET_S = 2.0               # chunks are sent for at most this long per tick (commands stay responsive)
MAX_ATTEMPTS = 6                  # network errors per job before it is given up
PRIVACY = (("private", N_("Privat")), ("unlisted", N_("Nicht gelistet")), ("public", N_("Öffentlich")))
CATEGORY_GAMING = "20"
VIDEO_URL = "https://youtu.be/{id}"
VIDEO_EXTS = (".mkv", ".mp4", ".mov", ".webm", ".avi", ".ts", ".m4v")
OPENER = None                     # urllib opener; the tests set one without a proxy


class YouTubeError(Exception):
    """``kind``: auth (login needed / refused), expired (401: refresh first), quota (the day's units are used up),
    limit (the channel's upload limit), forbidden (403 otherwise), gone (the upload session is no more), rate
    (429), net (everything else)."""

    def __init__(self, msg: str, kind: str = "net", reason: str = ""):
        super().__init__(msg)
        self.kind = kind
        self.reason = reason


# ------------------------------------------------------------------ HTTP (standard library only)
def _opener():
    global OPENER
    if OPENER is None:
        OPENER = urllib.request.build_opener()        # honours the system proxy like every urllib call
    return OPENER


def _parse(body: bytes):
    try:
        d = json.loads(body) if body.strip() else {}
    except ValueError:
        return {}
    return d if isinstance(d, dict) else {}


def _error(code: int, body: bytes) -> YouTubeError:
    d = _parse(body)
    err = d.get("error")
    reason, msg = "", ""
    if isinstance(err, dict):                           # the API: {"error": {"code", "message", "errors": [...]}}
        msg = str(err.get("message") or "")
        errors = err.get("errors")
        if isinstance(errors, list) and errors and isinstance(errors[0], dict):
            reason = str(errors[0].get("reason") or "")
    elif isinstance(err, str):                          # OAuth: {"error": "invalid_grant", "error_description": …}
        reason = err
        msg = str(d.get("error_description") or err)
    msg = msg or f"HTTP {code}"
    if reason in ("invalid_grant", "invalid_client", "unauthorized_client", "invalid_request"):
        kind = "auth"                                   # the token endpoint: 400 or 401 – the login is no good
    elif code == 401:
        kind = "expired"
    elif code == 403 and reason in ("quotaExceeded", "dailyLimitExceeded"):
        kind = "quota"
    elif reason == "uploadLimitExceeded":
        kind = "limit"
    elif code == 403:
        kind = "forbidden"
    elif code in (404, 410):
        kind = "gone"
    elif code == 429:
        kind = "rate"
    else:
        kind = "net"
    return YouTubeError(msg, kind, reason)


def _call(url: str, data: bytes | None = None, headers: dict | None = None, method: str | None = None) -> tuple:
    """(status, headers dict, body bytes). 308 (Resume Incomplete) comes back as a normal answer; every other
    error raises YouTubeError."""
    method = method or ("POST" if data is not None else "GET")
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with _opener().open(req, timeout=HTTP_TIMEOUT) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as e:
        body = e.read()
        if e.code == 308:
            return 308, {k.lower(): v for k, v in e.headers.items()}, body
        raise _error(e.code, body) from None
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise YouTubeError(str(getattr(e, "reason", None) or e), "net") from None


# ------------------------------------------------------------------ OAuth 2 (pure apart from the requests)
def valid_client_id(client_id) -> bool:
    s = str(client_id or "").strip()
    return s.endswith(".apps.googleusercontent.com") and len(s) > len(".apps.googleusercontent.com") + 8


CLIENT_FILE_MAX = 64 << 10        # Google's client file has a few hundred bytes


def read_client_file(path: str) -> tuple:
    """1.10.1: the ``client_secret_….json`` Google offers for download right after the OAuth client was created
    (``{"installed": {"client_id": …, "client_secret": …}}`` for a desktop client). Returns (client_id, secret);
    ``ValueError`` says what is wrong – also for a "web" client, which cannot log in from a desktop program.
    The file is only read and stays where it is."""
    try:
        too_big = os.path.getsize(path) > CLIENT_FILE_MAX
        with open(path, "r", encoding="utf-8-sig") as fh:
            text = "" if too_big else fh.read()
    except OSError as e:
        raise ValueError(_("nicht lesbar: {error}", error=e)) from None
    if too_big:
        raise ValueError(_("Datei zu gross"))
    try:
        data = json.loads(text)
    except ValueError as e:
        raise ValueError(_("kein JSON: {error}", error=e)) from None
    if not isinstance(data, dict):
        raise ValueError(_("kein JSON-Objekt"))
    inner = data.get("installed")
    if not isinstance(inner, dict):
        if isinstance(data.get("web"), dict):
            raise ValueError(_("OAuth-Client vom Typ „Webanwendung“ – in der Cloud Console einen vom Typ „Desktop-App“ anlegen"))
        raise ValueError(_("kein Abschnitt „installed“"))
    cid = str(inner.get("client_id") or "").strip()
    secret = str(inner.get("client_secret") or "").strip()
    if not valid_client_id(cid):
        raise ValueError(_("Client-ID fehlt oder endet nicht auf .apps.googleusercontent.com"))
    if not secret:
        raise ValueError(_("Client-Secret fehlt"))
    return cid, secret


def auth_url(client_id: str, state: str, challenge: str, redirect: str, manage: bool = False) -> str:
    """``manage``: also ask for SCOPE_MANAGE (playlists) – only when the user ticked the playlist box."""
    q = {"client_id": client_id, "redirect_uri": redirect, "response_type": "code",
         "scope": SCOPE + (" " + SCOPE_MANAGE if manage else ""),
         "code_challenge": challenge, "code_challenge_method": "S256", "state": state,
         "access_type": "offline", "prompt": "consent"}            # offline + consent: a refresh token every time
    return ENDPOINTS["auth"] + "?" + urllib.parse.urlencode(q)


@dataclass(frozen=True)
class GToken(spotify.Token):
    scopes: tuple = ()               # what Google granted (the token answer's "scope"; empty = not told)


def _token_request(form: dict) -> GToken:
    data = urllib.parse.urlencode(form).encode("ascii")
    _status, _h, body = _call(ENDPOINTS["token"], data, {"Content-Type": "application/x-www-form-urlencoded"})
    d = _parse(body)
    access = str(d.get("access_token") or "")
    if not access:
        raise YouTubeError(_("keine Antwort mit Token"), "auth")
    try:
        ttl = float(d.get("expires_in", 3600))
    except (TypeError, ValueError):
        ttl = 3600.0
    return GToken(access, str(d.get("refresh_token") or form.get("refresh_token") or ""), time.time() + ttl,
                  tuple(str(d.get("scope") or "").split()))


def exchange_code(client_id: str, secret: str, code: str, verifier: str, redirect: str) -> GToken:
    return _token_request({"grant_type": "authorization_code", "code": code, "redirect_uri": redirect,
                           "client_id": client_id, "client_secret": secret, "code_verifier": verifier})


def refresh(client_id: str, secret: str, refresh_token: str) -> GToken:
    """A new access token; Google hands out no new refresh token here, the old one stays."""
    return _token_request({"grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": client_id,
                           "client_secret": secret})


# ------------------------------------------------------------------ quota (pure)
def _nth_sunday(year: int, month: int, n: int) -> int:
    """Day of the month of the n-th Sunday."""
    first = next(d for d in range(1, 8) if calendar.weekday(year, month, d) == 6)
    return first + 7 * (n - 1)


def reset_hour_utc(now: float) -> int:
    """1.11.2: the UTC hour Pacific midnight falls on at ``now`` – 7 in US daylight time (from the second Sunday of
    March 02:00 PST = 10:00 UTC to the first Sunday of November 02:00 PDT = 09:00 UTC), else 8. Pure arithmetic:
    Windows has no tz database and the program carries no tzdata; the US rule has been fixed since 2007."""
    year = time.gmtime(now).tm_year
    start = calendar.timegm((year, 3, _nth_sunday(year, 3, 2), 10, 0, 0, 0, 0, 0))
    end = calendar.timegm((year, 11, _nth_sunday(year, 11, 1), 9, 0, 0, 0, 0, 0))
    return QUOTA_RESET_DST_UTC_H if start <= now < end else QUOTA_RESET_UTC_H


def quota_day(now: float) -> str:
    """The quota day ``now`` falls into: Google counts per Pacific day (reset_hour_utc to reset_hour_utc)."""
    return time.strftime("%Y-%m-%d", time.gmtime(now - reset_hour_utc(now) * 3600))


def next_reset(now: float) -> float:
    """When the next quota day begins (UTC timestamp)."""
    shifted = now - reset_hour_utc(now) * 3600
    day_start = shifted - (shifted % 86400)
    nxt = day_start + 86400
    return nxt + reset_hour_utc(nxt + QUOTA_RESET_UTC_H * 3600) * 3600


@dataclass
class Quota:
    day: str = ""
    used: int = 0

    def roll(self, now: float):
        day = quota_day(now)
        if self.day != day:
            self.day, self.used = day, 0

    def allows(self, now: float, cost: int = UPLOAD_COST) -> bool:
        self.roll(now)
        return self.used + cost <= QUOTA_DAY

    def spend(self, now: float, cost: int = UPLOAD_COST):
        self.roll(now)
        self.used += cost

    def exhaust(self, now: float):
        self.roll(now)
        self.used = QUOTA_DAY

    def left(self, now: float, cost: int = UPLOAD_COST) -> int:
        """Uploads still possible today (``cost`` per upload – 1.11.2: with a playlist step 1 650, not 1 600)."""
        self.roll(now)
        return max(0, (QUOTA_DAY - self.used) // max(1, cost))

    @classmethod
    def from_dict(cls, d) -> "Quota":
        d = d if isinstance(d, dict) else {}
        try:
            return cls(str(d.get("day") or ""), max(0, int(d.get("used") or 0)))
        except (TypeError, ValueError):
            return cls()


# ------------------------------------------------------------------ the queue (pure)
@dataclass
class Job:
    rel: str                         # file relative to the recordings folder ("Clips/x.mp4", "Farming/y.mkv", "z.mkv")
    kind: str = "clip"               # clip | round
    title: str = ""
    description: str = ""
    added: float = 0.0
    session: str = ""                # Google's resumable session URI once the upload was opened
    size: int = 0
    attempts: int = 0
    video: str = ""                  # 1.11: the uploaded video's id while the playlist step is still due

    @classmethod
    def from_dict(cls, d) -> "Job | None":
        if not isinstance(d, dict) or not str(d.get("rel") or ""):
            return None
        fields = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        try:
            return cls(**fields)
        except TypeError:
            return None


def describe(kind: str, label: str, who: str, t: float, seconds: float = 0.0) -> tuple:
    """(title, description) of a video from what the program knows – map, role/killer, time; no player names."""
    when = time.strftime("%d.%m.%Y %H:%M", time.localtime(t)) if t else ""
    head = " – ".join(p for p in (label, who) if p) or "Dead by Daylight"
    title = (_("Clip: {what}", what=head) if kind == "clip" else head)
    if when:
        title += f" · {when}"
    lines = ["Dead by Daylight" + (f" – {label}" if label else "")]
    if who:
        lines.append(who)
    if when:
        lines.append(when)
    if seconds:
        lines.append(_("Dauer {d}", d=fmt_duration(seconds)))
    lines.append(_("Aufgenommen mit Fog Scout"))
    return title[:100], "\n".join(lines)[:5000]


def metadata(job: Job, privacy: str) -> dict:
    privacy = privacy if privacy in dict(PRIVACY) else "private"
    return {"snippet": {"title": job.title or os.path.basename(job.rel), "description": job.description,
                        "categoryId": CATEGORY_GAMING, "tags": ["Dead by Daylight", "DbD", "Fog Scout"]},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}}


# ------------------------------------------------------------------ resumable upload (requests only)
def start_upload(access: str, size: int, meta: dict) -> str:
    """Open a resumable session: the session URI the chunks go to. This is the videos.insert the quota counts."""
    body = json.dumps(meta).encode("utf-8")
    headers = {"Authorization": f"Bearer {access}", "Content-Type": "application/json; charset=UTF-8",
               "X-Upload-Content-Type": "video/*", "X-Upload-Content-Length": str(int(size))}
    _status, h, _body = _call(ENDPOINTS["upload"] + "?uploadType=resumable&part=snippet,status", body, headers)
    uri = h.get("location", "")
    if not uri:
        raise YouTubeError(_("keine Upload-Sitzung erhalten"), "net")
    return uri


def _range_end(h: dict) -> int:
    """Bytes Google confirmed from a 308 answer's Range header ("bytes=0-1234567"): the next byte to send."""
    r = str(h.get("range") or "")
    if "-" in r:
        try:
            return int(r.rsplit("-", 1)[1]) + 1
        except ValueError:
            pass
    return 0


def send_chunk(access: str, session: str, path: str, start: int, size: int, chunk: int | None = None) -> tuple:
    """PUT the bytes from ``start`` (``chunk`` of them, CHUNK by default): ("more", next_start) or ("done", video id)."""
    with open(path, "rb") as fh:
        fh.seek(start)
        data = fh.read(min(chunk or CHUNK, size - start))
    end = start + len(data)
    headers = {"Authorization": f"Bearer {access}", "Content-Type": "video/*",
               "Content-Range": f"bytes {start}-{end - 1}/{size}"}
    status, h, body = _call(session, data, headers, "PUT")
    if status == 308:
        return "more", _range_end(h)
    vid = str(_parse(body).get("id") or "")
    if not vid:
        raise YouTubeError(_("Antwort ohne Video-ID"), "net")
    return "done", vid


def resume_point(access: str, session: str, size: int) -> tuple:
    """Ask Google how far a session got: ("more", next_start), ("done", video id) or ("gone", 0) when the session
    is no more (then a new one is opened – and counted again)."""
    headers = {"Authorization": f"Bearer {access}", "Content-Range": f"bytes */{size}"}
    try:
        status, h, body = _call(session, b"", headers, "PUT")
    except YouTubeError as e:
        if e.kind == "gone":
            return "gone", 0
        raise
    if status == 308:
        return "more", _range_end(h)
    vid = str(_parse(body).get("id") or "")
    return ("done", vid) if vid else ("gone", 0)


def video_url(video_id: str) -> str:
    return VIDEO_URL.format(id=video_id)


# ------------------------------------------------------------------ playlists (1.11, SCOPE_MANAGE)
def list_playlists(access: str) -> tuple:
    """The user's own playlists: ([(id, title), …], pages read). playlists.list mine=true, LIST_COST per page."""
    out, token, pages = [], "", 0
    while pages < PLAYLIST_PAGES:
        q = {"part": "snippet", "mine": "true", "maxResults": "50"}
        if token:
            q["pageToken"] = token
        _s, _h, body = _call(ENDPOINTS["playlists"] + "?" + urllib.parse.urlencode(q), None,
                             {"Authorization": f"Bearer {access}"})
        pages += 1
        d = _parse(body)
        for it in d.get("items") or []:
            if isinstance(it, dict) and it.get("id"):
                snippet = it.get("snippet") if isinstance(it.get("snippet"), dict) else {}
                out.append((str(it["id"]), str(snippet.get("title") or it["id"])))
        token = str(d.get("nextPageToken") or "")
        if not token:
            break
    return out, pages


def add_to_playlist(access: str, playlist_id: str, video_id: str):
    """playlistItems.insert (PLAYLIST_COST): the video at the end of the playlist. Errors raise YouTubeError."""
    body = json.dumps({"snippet": {"playlistId": playlist_id,
                                   "resourceId": {"kind": "youtube#video", "videoId": video_id}}}).encode("utf-8")
    _call(ENDPOINTS["items"] + "?part=snippet", body,
          {"Authorization": f"Bearer {access}", "Content-Type": "application/json; charset=UTF-8"})


# ------------------------------------------------------------------ the thread
class Uploader(threading.Thread):
    """Keeps the login and works the queue: one job at a time, chunk by chunk, only while not ``paused`` (a round
    runs) and while the day's quota allows. ``post(kind, data)``: "status" -> (text, ok); "token" -> the protected
    refresh token to keep ("" = forget); "queue" -> [job dicts] to keep whenever it changes; "quota" -> dict;
    "progress" -> (rel, sent, size); "done" -> {rel, kind, id, url}; "failed" -> {rel, kind, why};
    1.11: "playlists" -> {ok, why, items: [[id, title], …]}; "playlist" -> {rel, kind, ok, playlist, why}."""

    def __init__(self, post, opener=None):
        super().__init__(name="youtube", daemon=True)
        self._post = post
        self._open = opener or webbrowser.open
        self.cmds = queue.Queue()
        self.on = False                   # clips go up by themselves (the queue is worked either way)
        self.client_id, self.secret = "", ""
        self.privacy = "private"
        self.manage = False               # 1.11: playlists wanted (the login then asks for SCOPE_MANAGE)
        self.playlists = {}               # kind -> playlist id ("" = none)
        self._scopes = ()                 # what the current login grants (known after a token answer)
        self._probed = False              # a token answer was fetched just to learn the scopes
        self.folder = ""
        self.paused = False
        self.jobs: list = []
        self.quota = Quota()
        self.state = "off"                # off | no_id | login_needed | linking | linked | error
        self.status = _("YouTube: aus")
        self._token = spotify.Token()
        self._refresh = ""
        self._login = None
        self._login_at = 0.0
        self._verifier = ""
        self._redirect = ""
        self._retry_at = 0.0
        self._sent = {}                   # rel -> bytes Google confirmed (this session of the program)
        self._active = False              # 1.11.2: a chunk loop stopped only because its tick budget was up
        self.uploaded = 0                 # videos done since start (diagnosis)

    # ---- UI thread
    def configure(self, on: bool, client_id: str, secret: str, privacy: str, stored_token="", jobs=None, quota=None,
                  manage: bool = False, playlists=None):
        self.cmds.put(("config", (bool(on), str(client_id or "").strip(), str(secret or "").strip(),
                                  str(privacy or "private"), str(stored_token or ""), list(jobs or []), quota,
                                  bool(manage), {str(k): str(v or "") for k, v in dict(playlists or {}).items()})))

    def set_folder(self, folder):
        self.cmds.put(("folder", str(folder or "")))

    def set_paused(self, paused: bool):
        self.cmds.put(("pause", bool(paused)))

    def login(self):
        self.cmds.put(("login", None))

    def logout(self):
        self.cmds.put(("logout", None))

    def list_playlists(self):
        """1.11: fetch the channel's playlists once (LIST_COST) -> event "playlists"."""
        self.cmds.put(("playlists", None))

    def add(self, job: Job):
        self.cmds.put(("add", job))

    def remove(self, rel: str):
        self.cmds.put(("remove", str(rel)))

    def quit(self):
        self.cmds.put(("quit", None))

    @property
    def linked(self) -> bool:
        return bool(self._refresh)

    def diag_line(self) -> str:
        return (f"YouTube: an={self.on}, Zustand={self.state}, Pause={self.paused}, Warteschlange={len(self.jobs)}, "
                f"Playlists={self.manage}, Rechte={len(self._scopes)}, "
                f"Kontingent={self.quota.used}/{QUOTA_DAY} ({self.quota.day}), hochgeladen={self.uploaded}, "
                f"Status={self.status}")

    # ---- thread
    def run(self):
        while True:
            try:
                # 1.11.2: mid-upload the next tick follows at once – waiting the 0.5 s here after every
                # TICK_BUDGET_S of sending idled a fifth of the time (measured in the tests with a fake Google)
                cmd, arg = self.cmds.get(timeout=0.0 if self._active else 0.5)
            except queue.Empty:
                cmd, arg = None, None
            if cmd == "quit":
                self._stop_login()
                return
            try:
                self._command(cmd, arg)
                self._tick()
            except Exception as e:                        # never die
                self.state = "error"
                self._say(_("YouTube: Fehler – {error}", error=f"{type(e).__name__}: {e}"), False)
                self._retry_at = time.time() + RETRY_S

    def _command(self, cmd, arg):
        if cmd == "config":
            on, cid, secret, privacy, stored, jobs, quota, manage, playlists = arg
            if (cid, secret) != (self.client_id, self.secret):     # tokens belong to the client: a new one starts over
                self._drop_tokens(tell=bool(self.client_id and self._refresh))
            self.on, self.client_id, self.secret, self.privacy = on, cid, secret, privacy
            self.manage, self.playlists = manage, playlists
            if not self._refresh:
                self._refresh = spotify.unprotect(stored)
            if not self.jobs:
                self.jobs = [j for j in (Job.from_dict(d) for d in jobs) if j is not None]
            if quota is not None:
                self.quota = Quota.from_dict(quota)
            self._retry_at = 0.0
        elif cmd == "folder":
            self.folder = arg
        elif cmd == "pause":
            self.paused = arg
        elif cmd == "login":
            self._start_login()
        elif cmd == "playlists":
            self._list_playlists()
        elif cmd == "logout":
            self._stop_login()
            self._drop_tokens(tell=True)
            self.state = "login_needed"
            self._say(_("YouTube: nicht verbunden – „Mit YouTube verbinden“ klicken."), True)
        elif cmd == "add":
            job = arg
            if job.rel and all(j.rel != job.rel for j in self.jobs):
                job.added = job.added or time.time()
                self.jobs = self.jobs + [job]
                self._queue_changed()
        elif cmd == "remove":
            if any(j.rel == arg for j in self.jobs):
                self.jobs = [j for j in self.jobs if j.rel != arg]
                self._queue_changed()

    def _say(self, text: str, ok: bool):
        if text != self.status:
            self.status = text
            self._tell("status", (text, ok))

    def _tell(self, kind, data):
        try:
            self._post(kind, data)
        except Exception:
            pass

    def _queue_changed(self):
        self._tell("queue", [asdict(j) for j in self.jobs])

    def _drop_tokens(self, tell: bool):
        self._token, self._refresh, self._scopes, self._probed = spotify.Token(), "", (), False
        if tell:
            self._tell("token", "")

    # ---- login
    def _start_login(self):
        if not (valid_client_id(self.client_id) and self.secret):
            self.state = "no_id"
            self._say(_("YouTube: Client-ID (…apps.googleusercontent.com) und Client-Secret eintragen."), False)
            return
        self._stop_login()
        state = secrets.token_urlsafe(24)
        self._verifier, challenge = spotify.pkce_pair()
        srv = spotify.LoginServer(state, 0, texts=(_("Mit YouTube verbunden – du kannst dieses Fenster schliessen."),
                                                   _("Google hat die Anmeldung abgelehnt – du kannst dieses Fenster "
                                                     "schliessen.")))
        try:
            srv.start()
        except OSError as e:
            self.state = "error"
            self._say(_("YouTube: Anmeldung nicht möglich – {error}", error=e), False)
            return
        self._redirect = f"http://127.0.0.1:{srv.port}{REDIRECT_PATH}"
        self._login, self._login_at = srv, time.time()
        self.state = "linking"
        self._say(_("YouTube: öffne die Anmeldung im Browser …"), True)
        try:
            self._open(auth_url(self.client_id, state, challenge, self._redirect, manage=self.manage))
        except Exception as e:
            self._stop_login()
            self.state = "error"
            self._say(_("YouTube: Browser nicht geöffnet – {error}", error=e), False)

    def _stop_login(self):
        srv, self._login = self._login, None
        if srv is not None:
            srv.stop()

    def _finish_login(self):
        srv = self._login
        if srv is None:
            return
        if srv.done():
            self._stop_login()
            if srv.error:
                self.state = "login_needed"
                self._say(_("YouTube: Anmeldung abgelehnt ({error})", error=srv.error), False)
                return
            tok = exchange_code(self.client_id, self.secret, srv.code, self._verifier, self._redirect)
            self._token, self._refresh, self._scopes = tok, tok.refresh, tok.scopes
            if not tok.refresh:
                self.state = "login_needed"
                self._say(_("YouTube: Google gab kein dauerhaftes Token – in der Cloud Console den OAuth-Client als "
                            "„Desktop“ anlegen und den Zustimmungsbildschirm veröffentlichen."), False)
                return
            self._tell("token", spotify.protect(tok.refresh))
            self.state = "linked"
            self._say(self._linked_status(), True)
            if self.manage and self._has_manage():
                self._list_playlists()                    # the new login can: fill the choices right away
        elif time.time() - self._login_at > LOGIN_WAIT_S:
            self._stop_login()
            self.state = "login_needed"
            self._say(_("YouTube: Anmeldung abgelaufen – noch einmal „Mit YouTube verbinden“ klicken."), False)

    def _access(self) -> str:
        """A valid access token (refreshed when due). Raises YouTubeError("auth") when the login is gone."""
        if self._token.access and time.time() < self._token.expires_at - REFRESH_AHEAD_S:
            return self._token.access
        if not self._refresh:
            raise YouTubeError(_("nicht angemeldet"), "auth")
        try:
            tok = refresh(self.client_id, self.secret, self._refresh)
        except YouTubeError as e:
            if e.kind == "auth":                              # revoked / expired refresh token: log in again
                self._drop_tokens(tell=True)
            raise
        self._token = tok
        if tok.scopes:
            self._scopes = tok.scopes
        if tok.refresh and tok.refresh != self._refresh:
            self._refresh = tok.refresh
            self._tell("token", spotify.protect(tok.refresh))
        return tok.access

    # ---- playlists (1.11)
    def _has_manage(self) -> bool:
        """The login grants SCOPE_MANAGE – or has not said yet (empty: the first token answer tells)."""
        return not self._scopes or SCOPE_MANAGE in self._scopes

    def _linked_status(self) -> str:
        if self.manage and not self._has_manage():
            return _("YouTube: verbunden – für Playlists einmal neu „Mit YouTube verbinden“ klicken.")
        return _("YouTube: verbunden")

    def _playlist_for(self, job: Job) -> str:
        return str(self.playlists.get(job.kind) or "") if self.manage else ""

    def _cost(self, job: Job) -> int:
        """Units the job still needs: the insert (unless the video is up already) and the playlist step."""
        return (0 if job.video else UPLOAD_COST) + (PLAYLIST_COST if self._playlist_for(job) else 0)

    def _access_failed(self, e: YouTubeError):
        if e.kind == "auth":
            self.state = "login_needed"
            self._say(_("YouTube: Anmeldung abgelaufen – noch einmal „Mit YouTube verbinden“ klicken."), False)
        else:
            self._retry_at = time.time() + RETRY_S
            self._say(_("YouTube: {error} – neuer Versuch in {s} s", error=e, s=int(RETRY_S)), False)

    def _list_playlists(self):
        now = time.time()
        try:
            access = self._access()
            if not self._has_manage():
                raise YouTubeError(_("Berechtigung fehlt – noch einmal „Mit YouTube verbinden“ klicken"), "forbidden",
                                   "insufficientPermissions")
            items, pages = list_playlists(access)
        except YouTubeError as e:
            if e.kind == "auth":
                self._access_failed(e)
            self._tell("playlists", {"ok": False, "why": str(e), "items": []})
            return
        self.quota.spend(now, LIST_COST * max(1, pages))
        self._tell("quota", asdict(self.quota))
        self._tell("playlists", {"ok": True, "why": "", "items": [[pid, title] for pid, title in items]})

    def _playlist_step(self, job: Job, access: str, now: float):
        """After the upload: the video into its playlist (when one is chosen and the login allows), then the job
        is done. Quota, expired token and network errors raise – the step is tried again, never the upload."""
        pid = self._playlist_for(job)
        note = {"rel": job.rel, "kind": job.kind, "ok": False, "playlist": pid, "why": ""}
        if pid and not self._has_manage():
            note["why"] = _("Berechtigung fehlt – noch einmal „Mit YouTube verbinden“ klicken")
            self._tell("playlist", note)
        elif pid:
            try:
                add_to_playlist(access, pid, job.video)
            except YouTubeError as e:
                if e.kind not in ("forbidden", "limit", "gone"):
                    raise                                 # quota / expired / rate / net: again next time
                note["why"] = str(e)                      # no right, or the playlist is no more: the video stays up
                self._tell("playlist", note)
            else:
                self.quota.spend(now, PLAYLIST_COST)
                self._tell("quota", asdict(self.quota))
                note["ok"] = True
                self._tell("playlist", note)
        self._done(job)

    def _done(self, job: Job):
        self.jobs = [j for j in self.jobs if j.rel != job.rel]
        self._sent.pop(job.rel, None)
        self._queue_changed()

    # ---- the work
    def _tick(self):
        now = time.time()
        self._active = False
        if self._login is not None:
            self._finish_login()
            return
        if not (self.on or self.jobs) and self.state == "off":
            return
        if not (valid_client_id(self.client_id) and self.secret):
            self.state = "no_id"
            self._say(_("YouTube: Client-ID (…apps.googleusercontent.com) und Client-Secret eintragen."), False)
            return
        if not self._refresh:
            if self.state != "login_needed":
                self.state = "login_needed"
                self._say(_("YouTube: nicht verbunden – „Mit YouTube verbinden“ klicken."), True)
            return
        if not self.jobs:
            if self.manage and not self._scopes and not self._probed and now >= self._retry_at:
                try:
                    self._access()                        # one token answer tells what the login grants
                    self._probed = True                   # once: an answer without "scope" must not loop
                except YouTubeError as e:
                    self._access_failed(e)
                    return
            text = self._linked_status()
            if self.state != "linked" or text != self.status:
                self.state = "linked"
                self._say(text, True)
            return
        if self.paused:
            self._say(_("YouTube: {n} in der Warteschlange – wartet, bis Lobby und Runde vorbei sind", n=len(self.jobs)), True)
            return
        if now < self._retry_at:
            return
        job = self.jobs[0]
        if not self.quota.allows(now, self._cost(job)):
            self._say(_("YouTube: {n} in der Warteschlange – Tageskontingent aufgebraucht, weiter ab {when}",
                        n=len(self.jobs), when=time.strftime("%H:%M", time.localtime(next_reset(now)))), True)
            return
        path = os.path.join(self.folder, job.rel.replace("/", os.sep)) if self.folder else ""
        if not job.video and (not path or not os.path.isfile(path)):
            self._give_up(job, _("Datei nicht gefunden") if self.folder else _("Aufnahmeordner nicht da"),
                          final=bool(self.folder))
            return
        try:
            self._work(job, path, now)
        except YouTubeError as e:
            self._failed(job, e)

    def _work(self, job: Job, path: str, now: float):
        access = self._access()
        if job.video:                                     # uploaded already, only the playlist step is left
            self._playlist_step(job, access, now)
            return
        size = os.path.getsize(path)
        if not job.session or job.size != size:
            job.size = size
            job.session = start_upload(access, size, metadata(job, self.privacy))
            self.quota.spend(now)
            self._tell("quota", asdict(self.quota))
            self._sent[job.rel] = 0
            self._queue_changed()
        if job.rel not in self._sent:                     # a session from before a restart: ask Google where it got
            how, at = resume_point(access, job.session, size)
            if how == "gone":
                job.session = ""
                self._queue_changed()
                return                                    # the next tick opens a new session (counted again)
            if how == "done":
                self._uploaded(job, at, access, now)
                return
            self._sent[job.rel] = at
        deadline = time.time() + TICK_BUDGET_S
        while not self.paused and self.cmds.empty():
            start = self._sent[job.rel]
            how, at = send_chunk(access, job.session, path, start, size)
            if how == "done":
                self._uploaded(job, at, access, now)
                return
            self._sent[job.rel] = at
            self._tell("progress", (job.rel, at, size))
            self._say(_("YouTube: lädt {file} hoch ({pct} %)", file=os.path.basename(job.rel),
                        pct=int(100 * at / max(1, size))), True)
            if time.time() > deadline:
                self._active = True                       # more to send: the next tick must not wait
                return

    def _uploaded(self, job: Job, video_id: str, access: str, now: float):
        """The video is up: the app learns the id at once; the playlist step follows (and finishes the job)."""
        job.video = video_id
        self._sent.pop(job.rel, None)
        self.uploaded += 1
        self._queue_changed()
        self._tell("done", {"rel": job.rel, "kind": job.kind, "id": video_id, "url": video_url(video_id)})
        self._say(_("YouTube: hochgeladen – {file}", file=os.path.basename(job.rel)), True)
        self._playlist_step(job, access, now)

    def _failed(self, job: Job, e: YouTubeError):
        if e.kind == "quota":
            self.quota.exhaust(time.time())
            self._tell("quota", asdict(self.quota))
            return                                        # the job waits for the next day
        if e.kind == "expired":
            self._token = spotify.Token()                 # refreshed on the next tick
            return
        if e.kind == "gone":
            job.session = ""
            self._sent.pop(job.rel, None)
            self._queue_changed()
            return
        if e.kind == "auth":
            self.state = "login_needed"
            self._say(_("YouTube: Anmeldung abgelaufen – noch einmal „Mit YouTube verbinden“ klicken."), False)
            return
        if e.kind in ("limit", "forbidden"):
            self._give_up(job, str(e), final=True)
            return
        job.attempts += 1                                 # rate / net: wait, try again, give up eventually
        self._retry_at = time.time() + RETRY_S
        if job.attempts >= MAX_ATTEMPTS:
            self._give_up(job, str(e), final=True)
        else:
            self._say(_("YouTube: {error} – neuer Versuch in {s} s", error=e, s=int(RETRY_S)), False)

    def _give_up(self, job: Job, why: str, final: bool):
        if final:
            self.jobs = [j for j in self.jobs if j.rel != job.rel]
            self._sent.pop(job.rel, None)
            self._queue_changed()
            self._tell("failed", {"rel": job.rel, "kind": job.kind, "why": why})
            self._say(_("YouTube: nicht hochgeladen – {file}: {why}", file=os.path.basename(job.rel), why=why), False)
        else:
            self._retry_at = time.time() + RETRY_S
            self._say(_("YouTube: {n} in der Warteschlange – {why}", n=len(self.jobs), why=why), True)
