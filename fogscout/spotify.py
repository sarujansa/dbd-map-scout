"""Spotify "Als nächstes" (1.8, user's explicit decision after the limits were explained): the coming tracks of the
Spotify queue in the music card.

The Windows media controls (media.py) know only the *current* song – no player exposes its queue there. The queue
comes from the **Spotify Web API** (``GET /me/player/queue``), which needs an internet connection and a login:

- The user registers an app of their own in Spotify's developer dashboard (like the Discord Application-ID) and
  enters its **Client-ID**; the redirect URI to register is ``REDIRECT_URI`` (loopback, fixed port).
- "Mit Spotify verbinden" opens the Spotify login in the browser (OAuth 2 **PKCE**, no client secret). For the
  few minutes of the login the program listens once on ``127.0.0.1:REDIRECT_PORT`` for the browser's redirect
  (``LoginServer``: one request, the ``state`` must match, then it closes) – the only time it opens a port.
- The **refresh token** is the only thing kept: in settings.json, protected with the Windows DPAPI (readable only
  by this Windows account; ``protect``/``unprotect``), PC-specific (config.LOCAL_KEYS), cleared by "Abmelden".
- Reads only: the queue, every POLL_S while the music card is active (and at once when the song changes) –
  never play/pause/skip, nothing else of the account. Titles never go to the log or the diagnosis.
- Only the standard library (urllib, http.server, hashlib, secrets). Everything but the thread is pure/testable;
  ``ENDPOINTS`` and ``OPENER`` let the tests point it at a fake Spotify on 127.0.0.1.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import queue
import re
import secrets
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer

from .i18n import _

log = logging.getLogger(__name__)

IS_WIN = sys.platform == "win32"
ENDPOINTS = {"auth": "https://accounts.spotify.com/authorize",
             "token": "https://accounts.spotify.com/api/token",
             "queue": "https://api.spotify.com/v1/me/player/queue"}
DASHBOARD = "https://developer.spotify.com/dashboard"
SCOPES = "user-read-playback-state user-read-currently-playing"
REDIRECT_PORT = 27831                 # fixed: Spotify matches the registered redirect URI including the port
REDIRECT_PATH = "/callback"
REDIRECT_URI = f"http://127.0.0.1:{REDIRECT_PORT}{REDIRECT_PATH}"
LOGIN_WAIT_S = 180.0                  # the browser has this long to come back
POLL_S = 30.0                         # the queue is read this often while the music card is active (1.8.36:
                                      # 10 → 30 s – a song change reads it at once anyway; Development Mode
                                      # quotas count per developer account since July 2026)
REREAD_S = 5.0                        # 1.8.37: after a song change the queue is read at once and once more
                                      # after this long – right after a skip Spotify still answers the old queue
RATE_WAIT_S = (5.0, 300.0)            # 429 without Retry-After: wait from … doubling up to …
QUOTA_WAIT_S = 900.0                  # 429 "QUOTA_EXCEEDED": at least this long before asking again
RETRY_S = 30.0                        # after a network error
HTTP_TIMEOUT = 8.0
MAX_ITEMS = 10                        # coming tracks kept (the card shows 1–5)
REFRESH_AHEAD_S = 60.0                # a token this close to expiry is refreshed first
OPENER = None                         # urllib opener; the tests set one without a proxy


class SpotifyError(Exception):
    """``kind``: auth (login needed / refused), expired (401 on the API: refresh first), rate (429), forbidden
    (403: account not allowed in the app), net (everything else)."""

    def __init__(self, msg: str, kind: str = "net", retry_after: float = 0.0, reason: str = ""):
        super().__init__(msg)
        self.kind = kind
        self.retry_after = retry_after    # 0 = the answer named no wait
        self.reason = reason              # 1.8.36: the API's "reason" (QUOTA_EXCEEDED, …)


# ------------------------------------------------------------------ HTTP (standard library only)
def _opener():
    global OPENER
    if OPENER is None:
        OPENER = urllib.request.build_opener()        # honours the system proxy like every urllib call
    return OPENER


def _request(url: str, data: bytes | None = None, headers: dict | None = None) -> tuple:
    """(status, json dict); raises SpotifyError with the kind the status implies."""
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data is not None else "GET")
    try:
        with _opener().open(req, timeout=HTTP_TIMEOUT) as r:
            body = r.read()
            return r.status, (json.loads(body) if body.strip() else {})
    except urllib.error.HTTPError as e:
        try:
            body = e.read()
            d = json.loads(body) if body.strip() else {}
        except ValueError:
            d = {}
        err = d.get("error") if isinstance(d, dict) else None
        msg = d.get("error_description") if isinstance(d, dict) else None
        msg = msg or (err.get("message") if isinstance(err, dict) else err) or f"HTTP {e.code}"
        reason = str((err.get("reason") if isinstance(err, dict) else None) or
                     (d.get("reason") if isinstance(d, dict) else None) or "")
        if e.code == 429:
            try:
                wait = max(1.0, float(e.headers.get("Retry-After") or 0))
            except ValueError:
                wait = 0.0
            raise SpotifyError(str(msg), "rate", wait if e.headers.get("Retry-After") else 0.0, reason) from None
        if e.code == 401:
            raise SpotifyError(str(msg), "expired") from None
        if e.code == 400:
            raise SpotifyError(str(msg), "auth") from None
        if e.code == 403:
            raise SpotifyError(str(msg), "forbidden") from None
        raise SpotifyError(str(msg), "net") from None
    except (urllib.error.URLError, OSError, ValueError) as e:
        reason = getattr(e, "reason", None)
        raise SpotifyError(str(reason or e), "net") from None


# ------------------------------------------------------------------ OAuth 2 with PKCE (pure)
def pkce_pair() -> tuple:
    """(code_verifier, code_challenge): the verifier is random, the challenge its SHA-256, base64url without =."""
    verifier = secrets.token_urlsafe(64)[:96]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def auth_url(client_id: str, state: str, challenge: str, redirect: str = REDIRECT_URI) -> str:
    q = {"client_id": client_id, "response_type": "code", "redirect_uri": redirect, "scope": SCOPES,
         "code_challenge_method": "S256", "code_challenge": challenge, "state": state}
    return ENDPOINTS["auth"] + "?" + urllib.parse.urlencode(q)


@dataclass(frozen=True)
class Token:
    access: str = ""
    refresh: str = ""
    expires_at: float = 0.0


def _token_request(form: dict) -> Token:
    data = urllib.parse.urlencode(form).encode("ascii")
    _status, d = _request(ENDPOINTS["token"], data, {"Content-Type": "application/x-www-form-urlencoded"})
    access = str(d.get("access_token") or "")
    if not access:
        raise SpotifyError(_("keine Antwort mit Token"), "auth")
    try:
        ttl = float(d.get("expires_in", 3600))
    except (TypeError, ValueError):
        ttl = 3600.0
    return Token(access, str(d.get("refresh_token") or form.get("refresh_token") or ""), time.time() + ttl)


def exchange_code(client_id: str, code: str, verifier: str, redirect: str = REDIRECT_URI) -> Token:
    return _token_request({"grant_type": "authorization_code", "code": code, "redirect_uri": redirect,
                           "client_id": client_id, "code_verifier": verifier})


def refresh(client_id: str, refresh_token: str) -> Token:
    """A new access token (and, with PKCE, usually a new refresh token) from the refresh token."""
    return _token_request({"grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": client_id})


# ------------------------------------------------------------------ the queue (pure apart from fetch_queue)
@dataclass(frozen=True)
class UpNext:
    title: str = ""           # what Spotify says it plays now (to check against the Windows media controls)
    artist: str = ""
    items: tuple = ()         # ((title, artist), …) – the coming tracks, in order
    t: float = 0.0            # time.time() of the reading


def _track(d):
    if not isinstance(d, dict):
        return None
    name = " ".join(str(d.get("name") or "").split())
    if not name:
        return None
    if d.get("type") == "episode":
        show = d.get("show") if isinstance(d.get("show"), dict) else {}
        who = str(show.get("name") or show.get("publisher") or "")
    else:
        who = ", ".join(str(a.get("name")) for a in (d.get("artists") or ()) if isinstance(a, dict) and a.get("name"))
    return name, " ".join(who.split())


def parse_queue(data, wall: float | None = None) -> UpNext:
    """The API's answer -> UpNext (pure): tracks and episodes with a name, at most MAX_ITEMS."""
    data = data if isinstance(data, dict) else {}
    cur = _track(data.get("currently_playing")) or ("", "")
    items = tuple(t for t in (_track(x) for x in (data.get("queue") or ())) if t)[:MAX_ITEMS]
    return UpNext(cur[0], cur[1], items, time.time() if wall is None else wall)


def fetch_queue(access: str) -> UpNext:
    status, d = _request(ENDPOINTS["queue"], headers={"Authorization": "Bearer " + access})
    return parse_queue(d if status != 204 else {})


def _norm(s) -> str:
    return " ".join(str(s or "").casefold().split())


_BRACKETS = re.compile(r"\s*[(\[][^)\]]*[)\]]")
_FEAT = re.compile(r"\s+(?:feat\.?|ft\.|featuring)\s.*$")


def _loose(s) -> str:
    """The title without what players write differently (1.8.37): bracketed parts ("(feat. X)", "[Live]"),
    a " - …" suffix ("- 2011 Remaster", "- Radio Edit") and a trailing "feat. X"."""
    t = _BRACKETS.sub("", _norm(s))
    t = re.split(r" [-–—] ", t)[0]
    return _FEAT.sub("", t).strip()


def matches(up: UpNext, title: str, artist: str = "") -> bool:
    """Spotify's current track is the one the Windows media controls show (pure) – else the music comes from
    another player and the list would be wrong. Same title; the artist, when both know one, must overlap."""
    if not up.title or not same_title(up.title, title):
        return False
    a, b = _norm(artist), _norm(up.artist)
    if not a or not b:
        return True
    first_a, first_b = a.split(",")[0].strip(), b.split(",")[0].strip()
    return first_a in b or first_b in a


def is_spotify(app_id) -> bool:
    """The Windows media session belongs to Spotify (desktop app "Spotify.exe" or the Store app
    "SpotifyAB.SpotifyMusic_…!Spotify") – then the queue is Spotify's even when the titles are not written alike."""
    return "spotify" in str(app_id or "").casefold()


def lines(up: UpNext, n: int) -> tuple:
    """The first ``n`` coming tracks as ((title, artist), …)."""
    return tuple(up.items[:max(0, int(n))])


def same_title(a: str, b: str) -> bool:
    """Same title, also when written differently (1.8.37: "Song - 2011 Remaster" vs "Song", "Song (feat. X)")."""
    if not a or not b:
        return False
    if _norm(a) == _norm(b):
        return True
    la, lb = _loose(a), _loose(b)
    return bool(la) and la == lb


def advance(up: UpNext, title: str, artist: str = "") -> UpNext:
    """The list moved on with the song (1.8.1, pure): when the Windows media controls now show the first coming
    track, it becomes the current one and the rest moves up – at once, before Spotify's next answer confirms it.
    Unchanged when the song is still the current one or not in the list."""
    if not up.items or not title or matches(up, title, artist):
        return up
    nt, na = (tuple(up.items[0]) + ("", ""))[:2]
    if not same_title(nt, title):
        return up
    return UpNext(nt, na, tuple(up.items[1:]), up.t)


CLIENT_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def valid_client_id(client_id) -> bool:
    """A Spotify Client-ID is 32 hex characters (the user pasted a user id once, 1.8.1)."""
    return bool(CLIENT_ID_RE.match(str(client_id or "").strip().lower()))


def BAD_ID_TEXT() -> str:
    return _("Spotify: Client-ID sieht falsch aus – erwartet werden 32 Zeichen aus 0–9 und a–f (Dashboard → "
             "deine App → Settings → Basic Information → Client ID).")


# ------------------------------------------------------------------ keeping the refresh token
def _dpapi(data: bytes, encrypt: bool) -> bytes:
    """Windows DPAPI: encrypt/decrypt for the current Windows account (no prompt)."""
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.c_void_p)]

    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.LocalFree.argtypes = [ctypes.c_void_p]
    buf = ctypes.create_string_buffer(data, len(data))
    inp = BLOB(len(data), ctypes.cast(buf, ctypes.c_void_p))
    out = BLOB()
    fn = crypt.CryptProtectData if encrypt else crypt.CryptUnprotectData
    fn.restype = wintypes.BOOL
    if not fn(ctypes.byref(inp), None, None, None, None, 1, ctypes.byref(out)):     # 1 = CRYPTPROTECT_UI_FORBIDDEN
        raise OSError(ctypes.get_last_error())
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        k32.LocalFree(out.pbData)


def protect(secret: str) -> str:
    """The refresh token for settings.json: DPAPI-encrypted on Windows ("dpapi:…"), elsewhere only encoded
    ("plain:…", tests/Linux). "" stays ""."""
    if not secret:
        return ""
    raw = secret.encode("utf-8")
    if IS_WIN:
        try:
            return "dpapi:" + base64.b64encode(_dpapi(raw, True)).decode("ascii")
        except OSError as e:
            log.warning("Spotify: DPAPI nicht verfügbar (%s)", e)
    return "plain:" + base64.b64encode(raw).decode("ascii")


def unprotect(stored) -> str:
    """The refresh token back from its stored form; "" when it is missing or not readable here."""
    s = str(stored or "")
    try:
        if s.startswith("dpapi:"):
            return _dpapi(base64.b64decode(s[6:]), False).decode("utf-8") if IS_WIN else ""
        if s.startswith("plain:"):
            return base64.b64decode(s[6:]).decode("utf-8")
    except (ValueError, OSError):
        pass
    return ""


# ------------------------------------------------------------------ the browser's redirect during the login
class _NoReuse(HTTPServer):
    allow_reuse_address = not IS_WIN      # Windows: SO_REUSEADDR would let another socket take the port


class LoginServer:
    """Listens once on 127.0.0.1:``port`` for the redirect of the Spotify login: only ``REDIRECT_PATH`` with the
    matching ``state`` is accepted (``code`` or ``error``); everything else gets 404/400. Closed by ``stop()``."""

    def __init__(self, state: str, port: int = REDIRECT_PORT, texts=None):
        self.state = state
        self.port = port                      # 1.10: 0 = any free port (read it back after start – YouTube's login)
        self.texts = texts                    # 1.10: (page when ok, page when refused); None = the Spotify texts
        self.code = None
        self.error = ""
        self._srv = None
        self._thread = None

    def start(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            timeout = 5                           # 1.8.38: a client that connects and sends nothing blocks no login
            def log_message(self, *_a):           # nothing on stderr
                pass

            def do_GET(self):
                u = urllib.parse.urlsplit(self.path)
                if u.path != REDIRECT_PATH:
                    return self._reply(404, "Not found")
                q = urllib.parse.parse_qs(u.query)
                if q.get("state", [""])[0] != outer.state:
                    return self._reply(400, "Bad state")
                if q.get("error", [""])[0]:
                    outer.error = q["error"][0]
                    return self._reply(200, outer.page(False))
                code = q.get("code", [""])[0]
                if not code:
                    return self._reply(400, "No code")
                outer.code = code
                return self._reply(200, outer.page(True))

            def do_POST(self):
                self._reply(405, "Method not allowed")

            def _reply(self, status: int, text: str):
                body = text.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)

        srv = _NoReuse(("127.0.0.1", self.port), Handler)
        srv.timeout = 0.5
        self.port = srv.server_address[1]
        self._srv = srv
        self._thread = threading.Thread(target=self._serve, daemon=True, name="spotify-login")
        self._thread.start()

    def page(self, ok: bool) -> str:
        if self.texts:
            text = self.texts[0] if ok else self.texts[1]
        else:
            text = _("Mit Spotify verbunden – du kannst dieses Fenster schliessen.") if ok else \
                _("Spotify hat die Anmeldung abgelehnt – du kannst dieses Fenster schliessen.")
        return ("<!doctype html><html><head><meta charset='utf-8'><title>Fog Scout</title></head>"
                "<body style='font-family:sans-serif;background:#1b1c21;color:#eee;padding:40px'>"
                f"<h2>Fog Scout</h2><p>{text}</p></body></html>")

    def _serve(self):
        while self._srv is not None and not self.done():
            try:
                self._srv.handle_request()
            except OSError:
                break

    def done(self) -> bool:
        return self.code is not None or bool(self.error)

    def stop(self):
        srv, self._srv = self._srv, None
        if srv is not None:
            try:
                srv.server_close()
            except OSError:
                pass


# ------------------------------------------------------------------ the thread
class SpotifyLink(threading.Thread):
    """Keeps the login and reads the queue while ``active`` (set by the app: music card shown, DBD running).
    ``upnext`` is replaced as a whole – safe to read from the UI thread. ``post(kind, data)``: "status" ->
    (text, ok) for the settings card, "token" -> the protected refresh token to save ("" = forget it)."""

    def __init__(self, post, opener=None):
        super().__init__(name="spotify", daemon=True)
        self._post = post
        self._open = opener or webbrowser.open
        self.cmds = queue.Queue()
        self.on, self.client_id = False, ""
        self.active = False
        self.state = "off"                # off | no_id | login_needed | linking | linked | error
        self.status = _("Spotify: aus")
        self.upnext = UpNext()
        self._token = Token()
        self._refresh = ""
        self._login = None                # LoginServer while the browser is open
        self._login_at = 0.0
        self._verifier = ""
        self._next_fetch = 0.0
        self._retry_at = 0.0
        self._rate_wait = 0.0             # the last wait after a 429 without Retry-After (doubles)
        self._kicked = False
        self._song_kick = False           # 1.8.37: the kick came from a song change – read once more after REREAD_S
        self._refreshed_once = False

    # ---- UI thread
    def configure(self, on: bool, client_id: str, stored_token=""):
        self.cmds.put(("config", (bool(on), str(client_id or "").strip(), str(stored_token or ""))))

    def login(self):
        self.cmds.put(("login", None))

    def logout(self):
        self.cmds.put(("logout", None))

    def kick(self, title: str = "", artist: str = ""):
        """Read the queue now (the song changed); with the new song the list moves up at once (advance)."""
        self.cmds.put(("kick", (str(title or ""), str(artist or ""))))

    def quit(self):
        self.cmds.put(("quit", None))

    @property
    def linked(self) -> bool:
        return bool(self._refresh)

    def diag_line(self) -> str:
        """For the diagnosis: state only – never a title."""
        return (f"Spotify: an={self.on}, Zustand={self.state}, aktiv={self.active}, Titel in Liste="
                f"{len(self.upnext.items)}, Alter={time.time() - self.upnext.t:.0f}s, Status={self.status}"
                if self.upnext.t else
                f"Spotify: an={self.on}, Zustand={self.state}, aktiv={self.active}, keine Liste, Status={self.status}")

    # ---- thread
    def run(self):
        while True:
            try:
                cmd, arg = self.cmds.get(timeout=0.5)
            except queue.Empty:
                cmd, arg = None, None
            if cmd == "quit":
                self._stop_login()
                return
            if cmd == "config":
                on, cid, stored = arg
                if cid != self.client_id:                 # tokens belong to the app: a new id starts over
                    self._drop_tokens(tell=bool(self.client_id and self._refresh))
                self.on, self.client_id = on, cid
                if not self._refresh:
                    self._refresh = unprotect(stored)
                self._retry_at = 0.0
            elif cmd == "login":
                self._start_login()
            elif cmd == "logout":
                self._stop_login()
                self._drop_tokens(tell=True)
                self.upnext = UpNext()
            elif cmd == "kick":
                if arg and arg[0]:
                    self.upnext = advance(self.upnext, arg[0], arg[1])
                    self._song_kick = True
                self._kicked = True
            try:
                self._tick()
            except Exception as e:                        # never die
                self.state = "error"
                self._say(_("Spotify: Fehler – {error}", error=f"{type(e).__name__}: {e}"), False)
                self._retry_at = time.time() + RETRY_S

    def _say(self, text: str, ok: bool):
        if text != self.status:
            self.status = text
            try:
                self._post("status", (text, ok))
            except Exception:
                pass

    def _drop_tokens(self, tell: bool):
        self._token, self._refresh = Token(), ""
        if tell:
            try:
                self._post("token", "")
            except Exception:
                pass

    def _keep_tokens(self, tok: Token):
        changed = tok.refresh and tok.refresh != self._refresh
        self._token = tok
        if tok.refresh:
            self._refresh = tok.refresh
        if changed:
            try:
                self._post("token", protect(tok.refresh))
            except Exception:
                pass

    def _tick(self):
        now = time.time()
        if not self.on or not valid_client_id(self.client_id):
            self._stop_login()
            self.upnext = UpNext()
            if not self.on:
                self.state = "off"
                self._say(_("Spotify: aus"), True)
            elif not self.client_id:
                self.state = "no_id"
                self._say(_("Spotify: Client-ID fehlt – im Developer-Dashboard anlegen und hier eintragen."), False)
            else:                                         # 1.8.1: a user id or the like – nothing is tried with it
                self.state = "no_id"
                self._say(BAD_ID_TEXT(), False)
            return
        if self._login is not None:
            self._poll_login(now)
            return
        if not self._refresh:
            self.upnext = UpNext()
            if self.state not in ("login_needed", "error"):
                self.state = "login_needed"
                self._say(_("Spotify: nicht verbunden – „Mit Spotify verbinden“ klicken."), False)
            return
        if not self.active:
            self.upnext = UpNext()
            self._next_fetch = 0.0
            return
        if now < self._retry_at or not (self._kicked or now >= self._next_fetch):
            return
        self._kicked = False
        self._next_fetch = now + POLL_S
        try:
            self._ensure_access(now)
            self.upnext = fetch_queue(self._token.access)
            if self._song_kick:                           # 1.8.37: once more shortly after a song change
                self._song_kick = False
                self._next_fetch = now + REREAD_S
            self._refreshed_once = False
            self._rate_wait = 0.0
            self.state = "linked"
            self._say(_("Spotify: verbunden"), True)
        except SpotifyError as e:
            self._failed(e, now)

    def _failed(self, e: SpotifyError, now: float):
        if e.kind == "rate":
            # 1.8.36 (user: "auf Spotify wird mir die Warteschlange nicht mehr angezeigt"): since July 2026 the
            # quota of Development Mode apps counts per developer account and an exhausted one answers 429
            # QUOTA_EXCEEDED – before, that was silent and, without Retry-After, asked again every 5 s
            if e.reason.upper() == "QUOTA_EXCEEDED":
                wait = max(e.retry_after, QUOTA_WAIT_S)
                self.state = "error"
                self._say(_("Spotify: Kontingent der Developer-App aufgebraucht – „Als nächstes“ pausiert bis "
                            "{time}.", time=time.strftime("%H:%M", time.localtime(now + wait))), False)
            elif e.retry_after:
                wait = e.retry_after
            else:
                wait = self._rate_wait = min(RATE_WAIT_S[1], max(RATE_WAIT_S[0], 2 * self._rate_wait))
            if wait >= 60:
                self.upnext = UpNext()                   # a list that long out of date would be wrong
            self._retry_at = now + wait
        elif e.kind == "expired" and not self._refreshed_once:     # 401 on the API: refresh first, once
            self._refreshed_once = True
            self._token = Token()
            self._kicked = True
        elif e.kind in ("auth", "expired"):                       # the refresh token is dead: log in again
            self._drop_tokens(tell=True)
            self.upnext = UpNext()
            self.state = "login_needed"
            self._say(_("Spotify: Anmeldung abgelaufen – bitte neu verbinden."), False)
        elif e.kind == "forbidden":
            self._retry_at = now + RETRY_S
            self.state = "error"
            self._say(_("Spotify: kein Zugriff ({error}) – ist dein Spotify-Konto in der Developer-App unter "
                        "„User Management“ eingetragen?", error=str(e)), False)
        else:
            self._retry_at = now + RETRY_S
            self.state = "error"
            self._say(_("Spotify: Fehler – {error}", error=str(e)), False)

    def _ensure_access(self, now: float):
        if self._token.access and self._token.expires_at - now > REFRESH_AHEAD_S:
            return
        self._keep_tokens(refresh(self.client_id, self._refresh))

    # ---- login
    def _start_login(self):
        self.status = ""                                  # the login's messages always reach the card again
        if not self.client_id:
            self.state = "no_id"
            self._say(_("Spotify: Client-ID fehlt – im Developer-Dashboard anlegen und hier eintragen."), False)
            return
        if not valid_client_id(self.client_id):
            self.state = "no_id"
            self._say(BAD_ID_TEXT(), False)
            return
        self._stop_login()
        self._verifier, challenge = pkce_pair()
        state = secrets.token_urlsafe(24)
        srv = LoginServer(state, REDIRECT_PORT)
        try:
            srv.start()
        except OSError:
            self.state = "error"
            self._say(_("Spotify: Port {port} ist belegt – Anmeldung nicht möglich.", port=REDIRECT_PORT), False)
            return
        self._login, self._login_at = srv, time.time()
        self.state = "linking"
        self._say(_("Spotify: Anmeldung im Browser offen – dort bei Spotify anmelden und zustimmen …"), True)
        try:
            self._open(auth_url(self.client_id, state, challenge, REDIRECT_URI))
        except Exception as e:
            self._stop_login()
            self.state = "error"
            self._say(_("Spotify: Browser konnte nicht geöffnet werden ({error})", error=e), False)

    def _poll_login(self, now: float):
        srv = self._login
        if srv.code is not None:
            verifier = self._verifier
            self._stop_login()
            try:
                tok = exchange_code(self.client_id, srv.code, verifier, REDIRECT_URI)
            except SpotifyError as e:
                self.state = "login_needed"
                self._say(_("Spotify: Anmeldung fehlgeschlagen ({error})", error=str(e)), False)
                return
            self._keep_tokens(tok)
            self.state = "linked"
            self._say(_("Spotify: verbunden"), True)
            self._kicked = True
        elif srv.error:
            self._stop_login()
            self.state = "login_needed"
            self._say(_("Spotify: Anmeldung abgelehnt ({error})", error=srv.error), False)
        elif now - self._login_at > LOGIN_WAIT_S:
            self._stop_login()
            self.state = "login_needed"
            self._say(_("Spotify: keine Antwort vom Browser – Anmeldung abgebrochen."), False)

    def _stop_login(self):
        srv, self._login = self._login, None
        if srv is not None:
            srv.stop()
        self._verifier = ""
