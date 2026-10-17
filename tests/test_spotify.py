"""Spotify "Als nächstes" (dbdmapscout/spotify.py, 1.8): PKCE and the queue (pure), the token store, the login
listener, the thread against a fake Spotify on 127.0.0.1 (token endpoint + queue), the list on the music card."""
import json
import os
import socket
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dbdmapscout import spotify  # noqa: E402

QUEUE = {"currently_playing": {"type": "track", "name": "Blinding Lights", "artists": [{"name": "The Weeknd"}]},
         "queue": [{"type": "track", "name": "Save Your Tears", "artists": [{"name": "The Weeknd"}, {"name": "Ariana Grande"}]},
                   {"type": "episode", "name": "Folge 12", "show": {"name": "Ein Podcast"}},
                   {"type": "track", "name": "   ", "artists": []},
                   {"type": "track", "name": "Levitating", "artists": [{"name": "Dua Lipa"}]}]}


class FakeSpotify(threading.Thread):
    """accounts.spotify.com + api.spotify.com on one local port: /api/token (code / refresh grants with PKCE) and
    /v1/me/player/queue (Bearer). ``mode`` switches the queue answer: ok | 401 | 429 | 403 | 204."""

    def __init__(self):
        super().__init__(daemon=True)
        outer = self
        self.tokens = []                  # access tokens handed out
        self.refreshes = []               # refresh tokens handed out
        self.grants = []                  # (grant_type, form)
        self.queue_calls = 0
        self.mode = "ok"
        self.verifier_for = {}            # code -> expected code_verifier (set by the "browser")
        self.dead_refresh = set()

        class H(BaseHTTPRequestHandler):
            def log_message(self, *_a):
                pass

            def _json(self, status, d, headers=()):
                body = json.dumps(d).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                for k, v in headers:
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                form = {k: v[0] for k, v in urllib.parse.parse_qs(self.rfile.read(n).decode()).items()}
                outer.grants.append((form.get("grant_type"), form))
                if self.path != "/api/token":
                    return self._json(404, {"error": "nope"})
                if form.get("grant_type") == "authorization_code":
                    want = outer.verifier_for.get(form.get("code"))
                    if want is None or want != form.get("code_verifier") or form.get("redirect_uri") != spotify.REDIRECT_URI:
                        return self._json(400, {"error": "invalid_grant", "error_description": "Invalid authorization code"})
                elif form.get("grant_type") == "refresh_token":
                    if form.get("refresh_token") in outer.dead_refresh or not form.get("refresh_token"):
                        return self._json(400, {"error": "invalid_grant", "error_description": "Refresh token revoked"})
                else:
                    return self._json(400, {"error": "unsupported_grant_type"})
                access = f"acc{len(outer.tokens) + 1}"
                refresh = f"ref{len(outer.refreshes) + 1}"
                outer.tokens.append(access)
                outer.refreshes.append(refresh)
                return self._json(200, {"access_token": access, "token_type": "Bearer", "expires_in": 3600,
                                        "refresh_token": refresh, "scope": spotify.SCOPES})

            def do_GET(self):
                if not self.path.startswith("/v1/me/player/queue"):
                    return self._json(404, {"error": {"status": 404, "message": "nope"}})
                outer.queue_calls += 1
                auth = self.headers.get("Authorization", "")
                if outer.mode == "401" or auth != "Bearer " + (outer.tokens[-1] if outer.tokens else "?"):
                    return self._json(401, {"error": {"status": 401, "message": "The access token expired"}})
                if outer.mode == "429":
                    return self._json(429, {"error": {"status": 429, "message": "rate"}}, [("Retry-After", "2")])
                if outer.mode == "403":
                    return self._json(403, {"error": {"status": 403, "message": "User not registered in the Developer Dashboard"}})
                if outer.mode == "204":
                    self.send_response(204)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return None
                return self._json(200, QUEUE)

        self.srv = HTTPServer(("127.0.0.1", 0), H)
        self.srv.timeout = 0.2
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"
        self.stop_flag = False

    def run(self):
        while not self.stop_flag:
            self.srv.handle_request()

    def stop(self):
        self.stop_flag = True
        self.srv.server_close()


@pytest.fixture
def fake(monkeypatch):
    f = FakeSpotify()
    f.start()
    monkeypatch.setitem(spotify.ENDPOINTS, "auth", f.base + "/authorize")
    monkeypatch.setitem(spotify.ENDPOINTS, "token", f.base + "/api/token")
    monkeypatch.setitem(spotify.ENDPOINTS, "queue", f.base + "/v1/me/player/queue")
    monkeypatch.setattr(spotify, "OPENER", urllib.request.build_opener(urllib.request.ProxyHandler({})))
    monkeypatch.setattr(spotify, "POLL_S", 0.2)
    monkeypatch.setattr(spotify, "RETRY_S", 0.3)
    yield f
    f.stop()


@pytest.fixture
def app_root(tmp_path):
    """The whole program offscreen (like tests/test_uimodel.py)."""
    if sys.platform == "win32":
        pytest.skip("Linux: the Windows job tests the native parts; the app would touch the system there")
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name in ("maps", "models", "maps.json"):
        os.symlink(os.path.join(root, name), tmp_path / name)
    (tmp_path / "sim").mkdir()
    return tmp_path


def _wait(cond, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return cond()


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _browser(fake, port):
    """What the user's browser does: open the auth URL (here: remember the challenge), then come back to the
    redirect URI with a code and the state."""
    def opener(url):
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
        assert q["response_type"] == "code" and q["code_challenge_method"] == "S256"
        assert q["redirect_uri"] == spotify.REDIRECT_URI and q["scope"] == spotify.SCOPES
        opener.challenge = q["code_challenge"]
        opener.state = q["state"]
        opener.client_id = q["client_id"]
        return True
    opener.challenge = opener.state = opener.client_id = None
    return opener


# ------------------------------------------------------------------ pure
def test_pkce_and_the_auth_url():
    verifier, challenge = spotify.pkce_pair()
    assert 43 <= len(verifier) <= 128 and "=" not in challenge and "+" not in challenge and "/" not in challenge
    import base64, hashlib
    assert challenge == base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert spotify.pkce_pair()[0] != verifier
    url = spotify.auth_url("cid", "st", challenge)
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
    assert url.startswith("https://accounts.spotify.com/authorize?")
    assert q == {"client_id": "cid", "response_type": "code", "redirect_uri": spotify.REDIRECT_URI,
                 "scope": spotify.SCOPES, "code_challenge_method": "S256", "code_challenge": challenge, "state": "st"}
    assert spotify.REDIRECT_URI == "http://127.0.0.1:27831/callback"


def test_the_queue_is_parsed_matched_against_the_media_controls_and_cut():
    up = spotify.parse_queue(QUEUE, wall=5.0)
    assert (up.title, up.artist, up.t) == ("Blinding Lights", "The Weeknd", 5.0)
    assert up.items == (("Save Your Tears", "The Weeknd, Ariana Grande"), ("Folge 12", "Ein Podcast"),
                        ("Levitating", "Dua Lipa"))                               # the nameless track is skipped
    assert spotify.lines(up, 2) == up.items[:2] and spotify.lines(up, 0) == () and spotify.lines(up, 9) == up.items
    assert spotify.matches(up, "blinding  lights", "The Weeknd")
    assert spotify.matches(up, "Blinding Lights", "")                           # Windows knows no artist: title decides
    assert spotify.matches(up, "Blinding Lights", "The Weeknd, Someone")
    assert not spotify.matches(up, "Blinding Lights", "Dua Lipa")               # same title, another artist
    assert not spotify.matches(up, "Another Song", "The Weeknd")
    assert not spotify.matches(spotify.UpNext(), "Blinding Lights", "The Weeknd")
    assert spotify.parse_queue(None).items == () and spotify.parse_queue({"queue": "x"}).items == ()
    many = {"queue": [{"type": "track", "name": f"T{i}", "artists": [{"name": "A"}]} for i in range(30)]}
    assert len(spotify.parse_queue(many).items) == spotify.MAX_ITEMS


def test_the_refresh_token_is_stored_protected_and_garbage_reads_as_nothing():
    stored = spotify.protect("ref-secret")
    assert stored.startswith("dpapi:" if sys.platform == "win32" else "plain:") and "ref-secret" not in stored
    assert spotify.unprotect(stored) == "ref-secret"
    assert spotify.protect("") == "" and spotify.unprotect("") == "" and spotify.unprotect(None) == ""
    assert spotify.unprotect("plain:!!!") == "" and spotify.unprotect("ref-secret") == ""


# ------------------------------------------------------------------ the login listener
def test_the_login_listener_takes_only_its_callback_with_the_right_state(monkeypatch):
    port = _free_port()
    srv = spotify.LoginServer("good-state", port)
    srv.start()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        def get(path):
            try:
                with opener.open(f"http://127.0.0.1:{port}{path}", timeout=3) as r:
                    return r.status, r.read().decode()
            except urllib.error.HTTPError as e:
                return e.code, e.read().decode()
        assert get("/other")[0] == 404
        assert get("/callback?code=abc&state=wrong")[0] == 400 and srv.code is None
        assert get("/callback?state=good-state")[0] == 400
        status, page = get("/callback?code=abc&state=good-state")
        assert status == 200 and "DbD Map Scout" in page and "schliessen" in page
        assert srv.code == "abc" and srv.done()
    finally:
        srv.stop()
    assert _wait(lambda: not srv._thread.is_alive())
    # the port is free again; a refused login reports the error
    srv2 = spotify.LoginServer("s2", port)
    srv2.start()
    try:
        with opener.open(f"http://127.0.0.1:{port}/callback?error=access_denied&state=s2", timeout=3) as r:
            assert r.status == 200 and "abgelehnt" in r.read().decode()
        assert srv2.error == "access_denied" and srv2.code is None
    finally:
        srv2.stop()


# ------------------------------------------------------------------ the thread against the fake Spotify
def test_the_thread_logs_in_reads_the_queue_refreshes_and_forgets_a_dead_token(fake, monkeypatch):
    port = _free_port()
    monkeypatch.setattr(spotify, "REDIRECT_PORT", port)
    monkeypatch.setattr(spotify, "REDIRECT_URI", f"http://127.0.0.1:{port}/callback")
    events = []
    browser = _browser(fake, port)
    link = spotify.SpotifyLink(lambda kind, data: events.append((kind, data)), opener=browser)
    link.start()
    try:
        link.configure(True, "cid-1", "")
        assert _wait(lambda: link.state == "login_needed")
        link.login()
        assert _wait(lambda: browser.state is not None and link.state == "linking")
        assert browser.client_id == "cid-1"
        # the browser comes back with a code that belongs to the challenge the thread sent
        import base64, hashlib
        fake.verifier_for["code-1"] = link._verifier
        assert base64.urlsafe_b64encode(hashlib.sha256(link._verifier.encode()).digest()).rstrip(b"=").decode() \
            == browser.challenge
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"http://127.0.0.1:{port}/callback?code=code-1&state={browser.state}", timeout=3) as r:
            assert r.status == 200
        assert _wait(lambda: link.state == "linked")
        assert ("token", spotify.protect("ref1")) in events and link.linked
        assert fake.grants[0][0] == "authorization_code" and fake.grants[0][1]["code_verifier"] == fake.verifier_for["code-1"]
        # not active: nothing is read
        time.sleep(0.5)
        assert fake.queue_calls == 0 and link.upnext.items == ()
        link.active = True
        assert _wait(lambda: link.upnext.items != ())
        assert link.upnext.title == "Blinding Lights" and link.upnext.items[0] == ("Save Your Tears", "The Weeknd, Ariana Grande")
        assert ("status", ("Spotify: verbunden", True)) in events
        calls = fake.queue_calls
        link.kick()
        assert _wait(lambda: fake.queue_calls > calls)
        # the access token dies: one refresh, the list stays
        fake.mode = "401"
        n_tok = len(fake.tokens)
        fake.mode = "ok"
        fake.tokens.append("expired-now")          # the fake expects the newest token: ours is now wrong -> 401
        assert _wait(lambda: len(fake.tokens) > n_tok + 1 and link.state == "linked")
        assert fake.grants[-1][0] == "refresh_token"
        assert events[-1] != ("token", "") and any(k == "token" and d == spotify.protect(fake.refreshes[-1]) for k, d in events)
        # too many requests: it waits and comes back
        fake.mode = "429"
        link.kick()
        assert _wait(lambda: link._retry_at > time.time())
        fake.mode = "ok"
        # the refresh token is revoked: back to the login, the stored token is forgotten
        fake.dead_refresh.add(fake.refreshes[-1])
        fake.tokens.append("expired-again")
        assert _wait(lambda: link.state == "login_needed", timeout=8)
        assert events[-1] == ("token", "") or ("token", "") in events[-3:]
        assert not link.linked and link.upnext.items == ()
        assert "abgelaufen" in link.status
        link.configure(False, "cid-1", "")
        assert _wait(lambda: link.state == "off")
    finally:
        link.quit()
        link.join(timeout=3)
    assert not link.is_alive()


def test_a_stored_token_logs_in_without_the_browser_and_logout_forgets_it(fake):
    events = []
    link = spotify.SpotifyLink(lambda kind, data: events.append((kind, data)), opener=lambda url: False)
    link.start()
    try:
        link.active = True
        link.configure(True, "cid", spotify.protect("ref-stored"))
        assert _wait(lambda: link.upnext.items != ())
        assert fake.grants[0] == ("refresh_token", fake.grants[0][1]) and fake.grants[0][1]["refresh_token"] == "ref-stored"
        assert ("token", spotify.protect("ref1")) in events          # Spotify handed out a new refresh token
        link.logout()
        assert _wait(lambda: link.state == "login_needed" and not link.linked)
        assert ("token", "") in events[-3:] and link.upnext.items == ()
        # a different client id drops the tokens too
        link.configure(True, "cid", spotify.protect("ref-stored"))
        assert _wait(lambda: link.linked)
        link.configure(True, "other", spotify.protect("ref-stored"))
        assert _wait(lambda: fake.grants[-1][1]["client_id"] == "other")   # stored token taken for the new id
        assert link.linked
    finally:
        link.quit()
        link.join(timeout=3)


def test_no_id_a_busy_port_and_a_forbidden_account_are_reported(fake, monkeypatch):
    said = []
    link = spotify.SpotifyLink(lambda kind, data: said.append((kind, data)), opener=lambda url: False)
    link.start()
    try:
        link.configure(True, "", "")
        assert _wait(lambda: link.state == "no_id")
        assert "Client-ID fehlt" in link.status
        # the port is taken by someone else
        port = _free_port()
        blocker = socket.socket()
        blocker.bind(("127.0.0.1", port))
        blocker.listen(1)
        monkeypatch.setattr(spotify, "REDIRECT_PORT", port)
        link.configure(True, "cid", "")
        link.login()
        assert _wait(lambda: "belegt" in link.status)
        blocker.close()
        # a 403: the account is not allowed in the developer app
        fake.mode = "403"
        link.active = True
        link.configure(True, "cid", spotify.protect("ref-x"))
        assert _wait(lambda: "User Management" in link.status, timeout=5)
        assert link.linked and link.state == "error"
        line = link.diag_line()
        assert "Zustand=error" in line and "Blinding" not in line
    finally:
        link.quit()
        link.join(timeout=3)


# ------------------------------------------------------------------ the list on the music card
def test_the_music_card_grows_by_the_list_below_or_to_the_right_in_every_style():
    from dbdmapscout import skin, sysinfo
    from dbdmapscout.overlay_win32 import render_music
    from dbdmapscout.preview import sample_cover
    rows = [[("Blinding Lights", sysinfo.WHITE)], [("The Weeknd", sysinfo.DIM)]]
    up = ("ALS NÄCHSTES", (("Save Your Tears", "The Weeknd"), ("Levitating", "Dua Lipa")))
    cover = sample_cover()
    for layout in ("big", "compact"):
        plain = render_music(rows, cover, 1440, layout, (70, 176), ("accent", "backdrop"))
        below = render_music(rows, cover, 1440, layout, (70, 176), ("accent", "backdrop"), up, "below")
        right = render_music(rows, cover, 1440, layout, (70, 176), ("accent", "backdrop"), up, "right")
        assert below.height > plain.height + 40 and abs(below.width - plain.width) < 120
        assert right.width > plain.width + 100 and right.height == plain.height
        assert render_music(rows, cover, 1440, layout, (70, 176), (), ("x", ()), "below").size == \
            render_music(rows, cover, 1440, layout, (70, 176), ()).size            # an empty list changes nothing
        for style in ("glass", "chips", "line"):
            plain = skin.music(rows, cover, 1440, style, (70, 176), ("accent",), "#3987e5", layout)
            below = skin.music(rows, cover, 1440, style, (70, 176), ("accent",), "#3987e5", layout, up, "below")
            right = skin.music(rows, cover, 1440, style, (70, 176), ("accent",), "#3987e5", layout, up, "right")
            assert below.height > plain.height + 40, (style, layout)
            assert right.width > plain.width + 100 and right.height >= plain.height, (style, layout)
    long = ("ALS NÄCHSTES", (("A very very long title that goes on and on and on forever", "Some Artist With A Long Name"),))
    wide = skin.music(rows, cover, 1440, "glass", None, (), None, "compact", long, "below")
    assert wide.width <= int(skin.WRAP_SHARE * 1440) + 60                      # fitted, never wider than the bar


def test_the_preview_and_the_app_pass_the_list_to_the_music_card(tmp_path):
    from dbdmapscout import preview, sysinfo
    from dbdmapscout.config import DEFAULTS
    import copy
    o = copy.deepcopy(DEFAULTS["overlay"])
    o["media_pos"] = "bottom_right"
    rows = [[("Blinding Lights", sysinfo.WHITE)], [("The Weeknd", sysinfo.DIM)]]
    music = (rows, preview.sample_cover(), (70, 176))
    without, _r = preview.layers(3440, 1440, o, "", [], None, None, "", {}, 0.4, music, None)
    up = ("ALS NÄCHSTES", (("Save Your Tears", "The Weeknd"),))
    with_list, _r = preview.layers(3440, 1440, o, "", [], None, None, "", {}, 0.4, music, None, upnext=up)
    a = next(p for n, p, _x, _y in without if n == "music")
    b = next(p for n, p, _x, _y in with_list if n == "music")
    assert b.height > a.height


def test_the_app_shows_the_list_only_when_spotify_plays_the_same_song(app_root):
    import json as _json
    from dbdmapscout.app import App
    from dbdmapscout import media
    (app_root / "settings.json").write_text(_json.dumps({"welcome_seen": True}), encoding="utf-8")
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        now = media.NowPlaying("Blinding Lights", "The Weeknd", True, time.time())
        assert app._upnext(now) is None and app._upnext(now, sample=True) is None       # off by default
        app.sp_on_var.set(True)
        app.sp_id_var.set("cid")
        app._spotify_setting()
        assert app.settings.get("spotify_on") is True and app.settings.get("spotify_client_id") == "cid"
        assert app._upnext(now) is None                                                # nothing read yet
        assert app._upnext(now, sample=True)[1][0] == ("Save Your Tears", "The Weeknd")   # the sample list
        app.spotify.upnext = spotify.parse_queue(QUEUE)
        label, items = app._upnext(now)
        assert label == "ALS NÄCHSTES" and len(items) == 3 and items[0][0] == "Save Your Tears"
        app.settings["overlay"]["media_next_n"] = 1
        assert len(app._upnext(now)[1]) == 1
        assert app._upnext(media.NowPlaying("Other Song", "Someone", True, time.time())) is None
        app._spotify_event("token", "plain:eC1yZWY=")
        assert app.settings.get("spotify_token") == "plain:eC1yZWY="
        app._spotify_event("status", ("Spotify: verbunden", True))
        assert app.sp_status_var.get() == "Spotify: verbunden"
        app.media_next_var.set("Rechts neben dem Lied")
        app.media_next_n_var.set(4)
        app._media_next_changed()
        assert app.settings["overlay"]["media_next_pos"] == "right" and app.settings["overlay"]["media_next_n"] == 4
        from dbdmapscout import diagnose
        text = diagnose.collect(app)
        assert "Spotify:" in text and "Blinding" not in text and "Save Your" not in text
    finally:
        app.quit()
