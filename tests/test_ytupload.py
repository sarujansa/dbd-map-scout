"""1.10 (user: "ich zahle für YouTube … Clips immer hochladen, bestimmte Videos per Rechtsklick"): the YouTube upload –
OAuth with PKCE and client secret, the quota day, the queue, the resumable protocol and the thread, all against a
fake Google on 127.0.0.1 (the real one needs the user's own client)."""
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fogscout import spotify, ytupload as yt  # noqa: E402

CID = "123456789012-abcdefghijklmnop.apps.googleusercontent.com"
SECRET = "GOCSPX-secret"


class FakeGoogle(threading.Thread):
    """oauth2.googleapis.com + www.googleapis.com on one local port: /token (code / refresh grants with PKCE and the
    client secret), the resumable videos.insert and its session PUTs. ``mode``: ok | quota | 401-once | gone."""

    def __init__(self):
        super().__init__(daemon=True)
        outer = self
        self.tokens, self.grants, self.sessions = [], [], {}
        self.inserts = 0
        self.mode = "ok"
        self.scope = yt.SCOPE             # what the token answers say the login grants (1.11)
        self.playlists = [("PL1", "Clips"), ("PL2", "Runden")]
        self.playlist_items = []          # (playlist id, video id) added
        self.pl_fail_once = False         # the next playlistItems.insert answers 500
        self.verifier_for = {}            # code -> expected code_verifier
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

            def _api_error(self, status, reason, message="nope"):
                return self._json(status, {"error": {"code": status, "message": message,
                                                     "errors": [{"reason": reason, "message": message}]}})

            def _authed(self):
                return self.headers.get("Authorization", "") == "Bearer " + (outer.tokens[-1] if outer.tokens else "?")

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(n)
                if self.path == "/token":
                    form = {k: v[0] for k, v in urllib.parse.parse_qs(raw.decode()).items()}
                    outer.grants.append((form.get("grant_type"), form))
                    if form.get("client_id") != CID or form.get("client_secret") != SECRET:
                        return self._json(401, {"error": "invalid_client", "error_description": "Unauthorized"})
                    if form.get("grant_type") == "authorization_code":
                        want = outer.verifier_for.get(form.get("code"))
                        if want is None or want != form.get("code_verifier") or not str(form.get("redirect_uri", "")).startswith("http://127.0.0.1:"):
                            return self._json(400, {"error": "invalid_grant", "error_description": "Bad Request"})
                        refresh = f"ref{len(outer.grants)}"
                    elif form.get("grant_type") == "refresh_token":
                        if form.get("refresh_token") in outer.dead_refresh or not form.get("refresh_token"):
                            return self._json(400, {"error": "invalid_grant", "error_description": "Token has been expired or revoked."})
                        refresh = None                           # Google hands out none here
                    else:
                        return self._json(400, {"error": "unsupported_grant_type"})
                    access = f"acc{len(outer.tokens) + 1}"
                    outer.tokens.append(access)
                    d = {"access_token": access, "token_type": "Bearer", "expires_in": 3599, "scope": outer.scope}
                    if refresh:
                        d["refresh_token"] = refresh
                    return self._json(200, d)
                if self.path.startswith("/upload/youtube/v3/videos"):
                    if not self._authed():
                        return self._api_error(401, "authError", "Invalid Credentials")
                    outer.inserts += 1
                    if outer.mode == "quota":
                        return self._api_error(403, "quotaExceeded", "The request cannot be completed because you have exceeded your quota.")
                    sid = f"s{outer.inserts}"
                    outer.sessions[sid] = {"meta": json.loads(raw.decode()), "size": int(self.headers.get("X-Upload-Content-Length", 0)),
                                           "data": bytearray(), "done": ""}
                    self.send_response(200)
                    self.send_header("Location", f"{outer.base}/upload/session/{sid}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return None
                if self.path.startswith("/youtube/v3/playlistItems"):
                    if not self._authed():
                        return self._api_error(401, "authError", "Invalid Credentials")
                    if yt.SCOPE_MANAGE not in outer.scope:
                        return self._api_error(403, "insufficientPermissions", "Insufficient Permission")
                    if outer.pl_fail_once:
                        outer.pl_fail_once = False
                        return self._api_error(500, "backendError", "Backend Error")
                    snippet = json.loads(raw.decode())["snippet"]
                    if snippet["playlistId"] not in {pid for pid, _t in outer.playlists}:
                        return self._api_error(404, "playlistNotFound", "Playlist not found.")
                    outer.playlist_items.append((snippet["playlistId"], snippet["resourceId"]["videoId"]))
                    return self._json(200, {"id": f"pli{len(outer.playlist_items)}", "kind": "youtube#playlistItem"})
                return self._api_error(404, "notFound")

            def do_GET(self):
                if self.path.startswith("/youtube/v3/playlists"):
                    if not self._authed():
                        return self._api_error(401, "authError", "Invalid Credentials")
                    if yt.SCOPE_MANAGE not in outer.scope:
                        return self._api_error(403, "insufficientPermissions", "Insufficient Permission")
                    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.path).query))
                    assert q.get("mine") == "true" and q.get("part") == "snippet"
                    return self._json(200, {"items": [{"id": pid, "snippet": {"title": t}} for pid, t in outer.playlists]})
                return self._api_error(404, "notFound")

            def do_PUT(self):
                n = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(n)
                m = re.match(r"^/upload/session/(\w+)$", self.path)
                sess = outer.sessions.get(m.group(1)) if m else None
                if outer.mode == "401-once":
                    outer.mode = "ok"
                    return self._api_error(401, "authError", "Invalid Credentials")
                if sess is None or outer.mode == "gone":
                    return self._api_error(404, "notFound", "Not Found")
                rng = self.headers.get("Content-Range", "")
                total = sess["size"]
                if rng.startswith("bytes */"):
                    pass                                         # a query: answer the state below
                else:
                    a, b = re.match(r"^bytes (\d+)-(\d+)/\d+$", rng).groups()
                    if int(a) == len(sess["data"]):
                        sess["data"] += raw
                if len(sess["data"]) >= total and total:
                    sess["done"] = sess["done"] or f"vid{m.group(1)}"
                    return self._json(200, {"id": sess["done"], "kind": "youtube#video"})
                headers = [("Range", f"bytes=0-{len(sess['data']) - 1}")] if sess["data"] else []
                self.send_response(308)
                for k, v in headers:
                    self.send_header(k, v)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return None

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
    f = FakeGoogle()
    f.start()
    monkeypatch.setitem(yt.ENDPOINTS, "auth", f.base + "/auth")
    monkeypatch.setitem(yt.ENDPOINTS, "token", f.base + "/token")
    monkeypatch.setitem(yt.ENDPOINTS, "upload", f.base + "/upload/youtube/v3/videos")
    monkeypatch.setitem(yt.ENDPOINTS, "playlists", f.base + "/youtube/v3/playlists")
    monkeypatch.setitem(yt.ENDPOINTS, "items", f.base + "/youtube/v3/playlistItems")
    monkeypatch.setattr(yt, "OPENER", urllib.request.build_opener(urllib.request.ProxyHandler({})))
    monkeypatch.setattr(yt, "CHUNK", 256 * 1024)
    monkeypatch.setattr(yt, "RETRY_S", 0.3)
    yield f
    f.stop()


def _wait(cond, timeout=6.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return cond()


def _video(folder, rel, size):
    path = os.path.join(folder, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = bytes(range(256)) * (size // 256) + b"x" * (size % 256)
    with open(path, "wb") as fh:
        fh.write(data)
    return path, data


# ------------------------------------------------------------------ pure parts
def test_the_client_file_google_offers_is_read(tmp_path):
    """1.10.1: client_secret_….json from the Cloud console – id and secret out of "installed"; a web client, junk and
    missing fields are refused with a reason; the file is left in place."""
    good = tmp_path / "client_secret_1234567890-abc.apps.googleusercontent.com.json"
    good.write_text(json.dumps({"installed": {"client_id": "1234567890-abc.apps.googleusercontent.com",
                                              "project_id": "x", "client_secret": "GOCSPX-s3cret",
                                              "redirect_uris": ["http://localhost"]}}), encoding="utf-8")
    assert yt.read_client_file(str(good)) == ("1234567890-abc.apps.googleusercontent.com", "GOCSPX-s3cret")
    assert good.exists()
    bom = tmp_path / "bom.json"                                     # Notepad saves JSON with a BOM
    bom.write_bytes(b"\xef\xbb\xbf" + good.read_bytes())
    assert yt.read_client_file(str(bom))[1] == "GOCSPX-s3cret"
    bad = {"web.json": json.dumps({"web": {"client_id": "1234567890-abc.apps.googleusercontent.com", "client_secret": "s"}}),
           "junk.json": "{not json", "list.json": "[1, 2]", "other.json": json.dumps({"foo": 1}),
           "noid.json": json.dumps({"installed": {"client_id": "abc", "client_secret": "s"}}),
           "nosecret.json": json.dumps({"installed": {"client_id": "1234567890-abc.apps.googleusercontent.com"}})}
    reasons = {}
    for name, text in bad.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
        with pytest.raises(ValueError) as err:
            yt.read_client_file(str(tmp_path / name))
        reasons[name] = str(err.value)
    assert "Desktop-App" in reasons["web.json"] and "JSON" in reasons["junk.json"] and "installed" in reasons["other.json"]
    assert "Client-ID" in reasons["noid.json"] and "Client-Secret" in reasons["nosecret.json"]
    assert "JSON-Objekt" in reasons["list.json"]
    big = tmp_path / "big.json"
    big.write_bytes(b" " * (yt.CLIENT_FILE_MAX + 1))
    with pytest.raises(ValueError, match="gross"):
        yt.read_client_file(str(big))
    with pytest.raises(ValueError, match="nicht lesbar"):
        yt.read_client_file(str(tmp_path / "missing.json"))


def test_auth_url_tokens_and_the_secret(fake):
    url = yt.auth_url(CID, "st", "chal", "http://127.0.0.1:5/callback")
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
    assert q["response_type"] == "code" and q["code_challenge_method"] == "S256" and q["scope"] == yt.SCOPE
    assert q["access_type"] == "offline" and q["prompt"] == "consent" and q["redirect_uri"] == "http://127.0.0.1:5/callback"
    wide = yt.auth_url(CID, "st", "chal", "http://127.0.0.1:5/callback", manage=True)          # 1.11: playlists
    assert dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(wide).query))["scope"] == f"{yt.SCOPE} {yt.SCOPE_MANAGE}"
    assert yt.valid_client_id(CID) and not yt.valid_client_id("abc") and not yt.valid_client_id("")
    fake.verifier_for["code-1"] = "verifier-1"
    tok = yt.exchange_code(CID, SECRET, "code-1", "verifier-1", "http://127.0.0.1:5/callback")
    assert tok.access == "acc1" and tok.refresh == "ref1" and tok.expires_at > time.time() + 3000
    assert tok.scopes == (yt.SCOPE,)                                            # what Google granted
    tok2 = yt.refresh(CID, SECRET, "ref1")
    assert tok2.access == "acc2" and tok2.refresh == "ref1"                     # Google gives no new refresh token
    with pytest.raises(yt.YouTubeError) as e:
        yt.refresh(CID, "wrong", "ref1")
    assert e.value.kind == "auth"                                              # a wrong secret: no "expired"
    fake.dead_refresh.add("ref-dead")
    with pytest.raises(yt.YouTubeError) as e:
        yt.refresh(CID, SECRET, "ref-dead")
    assert e.value.kind == "auth" and "revoked" in str(e.value)


def test_the_quota_day_turns_at_pacific_midnight_and_counts_uploads():
    t = time.mktime(time.strptime("2026-10-23 07:59:00 UTC", "%Y-%m-%d %H:%M:%S %Z")) if False else None
    base = 1792000800.0                                                        # 2026-10-23 ~ 08:00 UTC? computed below
    import calendar
    before = calendar.timegm((2026, 10, 23, 7, 59, 0, 0, 0, 0))
    after = calendar.timegm((2026, 10, 23, 8, 1, 0, 0, 0, 0))
    assert yt.quota_day(before) == "2026-10-22" and yt.quota_day(after) == "2026-10-23"
    assert yt.next_reset(before) == calendar.timegm((2026, 10, 23, 8, 0, 0, 0, 0, 0))
    assert yt.next_reset(after) == calendar.timegm((2026, 10, 24, 8, 0, 0, 0, 0, 0))
    q = yt.Quota()
    assert q.allows(after) and q.left(after) == 6
    for _i in range(6):
        q.spend(after)
    assert not q.allows(after) and q.left(after) == 0 and q.used == 9600
    assert q.allows(after + 86400) and q.day == "2026-10-24" and q.used == 0   # the next day: fresh
    q.exhaust(after + 86400)
    assert q.left(after + 86400) == 0
    assert yt.Quota.from_dict({"day": "2026-10-24", "used": "3200"}).used == 3200
    assert yt.Quota.from_dict("junk") == yt.Quota() and yt.Quota.from_dict({"used": -5}).used == 0
    assert base and t is None


def test_jobs_titles_and_metadata():
    j = yt.Job.from_dict({"rel": "Clips/a.mp4", "kind": "clip", "title": "T", "unknown": 1})
    assert j.rel == "Clips/a.mp4" and j.kind == "clip" and j.title == "T" and j.session == ""
    assert yt.Job.from_dict({"kind": "clip"}) is None and yt.Job.from_dict("x") is None
    t = time.mktime((2026, 10, 17, 21, 40, 0, 0, 0, -1))
    title, text = yt.describe("clip", "Coal Tower", "Nurse", t, 30)
    assert title == "Clip: Coal Tower – Nurse · 17.10.2026 21:40"
    assert "Dead by Daylight – Coal Tower" in text and "Nurse" in text and "00:30" in text and "Fog Scout" in text
    title, _text = yt.describe("round", "", "", t)
    assert title == "Dead by Daylight · 17.10.2026 21:40"
    assert len(yt.describe("round", "x" * 200, "", t)[0]) <= 100
    meta = yt.metadata(yt.Job(rel="Clips/a.mp4", title="T", description="D"), "unlisted")
    assert meta["snippet"]["title"] == "T" and meta["snippet"]["categoryId"] == "20"
    assert meta["status"] == {"privacyStatus": "unlisted", "selfDeclaredMadeForKids": False}
    assert yt.metadata(yt.Job(rel="x.mkv"), "nonsense")["status"]["privacyStatus"] == "private"
    assert yt.metadata(yt.Job(rel="x.mkv"), "private")["snippet"]["title"] == "x.mkv"
    assert yt.video_url("abc") == "https://youtu.be/abc"


def test_the_resumable_protocol_in_chunks_and_the_resume_point(fake, tmp_path):
    path, data = _video(str(tmp_path), "Clips/a.mp4", 600 * 1024)
    tok = yt.refresh(CID, SECRET, "ref-x")
    session = yt.start_upload(tok.access, len(data), yt.metadata(yt.Job(rel="Clips/a.mp4", title="T"), "private"))
    assert session.startswith(fake.base + "/upload/session/") and fake.inserts == 1
    how, at = yt.send_chunk(tok.access, session, path, 0, len(data))
    assert (how, at) == ("more", 256 * 1024)
    assert yt.resume_point(tok.access, session, len(data)) == ("more", 256 * 1024)
    how, at = yt.send_chunk(tok.access, session, path, at, len(data))
    assert (how, at) == ("more", 512 * 1024)
    how, vid = yt.send_chunk(tok.access, session, path, at, len(data))
    assert how == "done" and vid == "vids1"
    assert bytes(fake.sessions["s1"]["data"]) == data
    assert yt.resume_point(tok.access, session, len(data)) == ("done", "vids1")
    assert yt.resume_point(tok.access, fake.base + "/upload/session/nope", 10) == ("gone", 0)
    fake.mode = "quota"
    with pytest.raises(yt.YouTubeError) as e:
        yt.start_upload(tok.access, 10, {})
    assert e.value.kind == "quota" and e.value.reason == "quotaExceeded"


# ------------------------------------------------------------------ the thread
def _uploader(events, opener=None):
    up = yt.Uploader(lambda kind, data: events.append((kind, data)), opener=opener or (lambda url: False))
    up.start()
    return up


def test_the_thread_uploads_a_queued_clip_and_tells_the_app(fake, tmp_path):
    folder = str(tmp_path)
    path, data = _video(folder, "Clips/a.mp4", 300 * 1024)
    events = []
    up = _uploader(events)
    try:
        up.configure(True, CID, SECRET, "unlisted", spotify.protect("ref-stored"), [], {})
        up.set_folder(folder)
        assert _wait(lambda: up.state == "linked")
        up.add(yt.Job(rel="Clips/a.mp4", kind="clip", title="Clip: Coal Tower", description="D"))
        assert _wait(lambda: any(k == "done" for k, _d in events))
        done = next(d for k, d in events if k == "done")
        assert done == {"rel": "Clips/a.mp4", "kind": "clip", "id": "vids1", "url": "https://youtu.be/vids1"}
        meta = fake.sessions["s1"]["meta"]
        assert meta["snippet"]["title"] == "Clip: Coal Tower" and meta["status"]["privacyStatus"] == "unlisted"
        assert bytes(fake.sessions["s1"]["data"]) == data and os.path.exists(path)      # the local file stays
        quotas = [d for k, d in events if k == "quota"]
        assert quotas and quotas[-1]["used"] == yt.UPLOAD_COST
        queues = [d for k, d in events if k == "queue"]
        assert queues[0][0]["rel"] == "Clips/a.mp4" and queues[-1] == []                 # kept while pending, then gone
        assert any(k == "progress" for k, _d in events) and up.uploaded == 1
        assert fake.grants[0][0] == "refresh_token" and fake.grants[0][1]["refresh_token"] == "ref-stored"
        assert "hochgeladen" in up.status and "Warteschlange=0" in up.diag_line()
    finally:
        up.quit()
        up.join(timeout=3)


def test_a_round_pauses_the_upload_and_a_restart_resumes_the_session(fake, tmp_path, monkeypatch):
    monkeypatch.setattr(yt, "CHUNK", 64 * 1024)
    monkeypatch.setattr(yt, "TICK_BUDGET_S", 0.0)                 # one chunk per tick: the pause lands between chunks
    folder = str(tmp_path)
    _path, data = _video(folder, "r.mkv", 640 * 1024)
    events = []
    up = _uploader(events)
    try:
        up.set_paused(True)
        up.configure(False, CID, SECRET, "private", spotify.protect("ref-stored"), [], {})
        up.set_folder(folder)
        up.add(yt.Job(rel="r.mkv", kind="round", title="R"))
        assert _wait(lambda: "Runde" in up.status)                 # queued, but a round runs: nothing is sent
        time.sleep(0.6)
        assert fake.inserts == 0
        up.set_paused(False)
        assert _wait(lambda: any(k == "progress" for k, _d in events))
        up.set_paused(True)
        time.sleep(0.8)
        sent = len(fake.sessions["s1"]["data"])
        assert 0 < sent < len(data)
        time.sleep(0.8)
        assert len(fake.sessions["s1"]["data"]) == sent             # paused: no more bytes
        queued = [d for k, d in events if k == "queue"][-1]
        assert queued[0]["session"].startswith(fake.base) and queued[0]["size"] == len(data)
    finally:
        up.quit()
        up.join(timeout=3)
    # the program is restarted with the queue from the settings: the session is asked where it got, not opened anew
    events2 = []
    up2 = _uploader(events2)
    try:
        up2.configure(False, CID, SECRET, "private", spotify.protect("ref-stored"), queued, {"day": "x", "used": 1600})
        up2.set_folder(folder)
        assert _wait(lambda: any(k == "done" for k, _d in events2))
        assert fake.inserts == 1 and bytes(fake.sessions["s1"]["data"]) == data
        assert not any(k == "quota" for k, _d in events2)           # nothing counted twice
    finally:
        up2.quit()
        up2.join(timeout=3)


def test_an_exhausted_quota_waits_for_the_next_day_and_a_dead_session_starts_over(fake, tmp_path):
    folder = str(tmp_path)
    _video(folder, "Clips/a.mp4", 100 * 1024)
    events = []
    up = _uploader(events)
    try:
        fake.mode = "quota"
        up.configure(True, CID, SECRET, "private", spotify.protect("ref-stored"), [], {})
        up.set_folder(folder)
        up.add(yt.Job(rel="Clips/a.mp4", title="T"))
        assert _wait(lambda: "Tageskontingent" in up.status)
        assert up.quota.used == yt.QUOTA_DAY and up.jobs and fake.inserts == 1
        assert [d for k, d in events if k == "quota"][-1]["used"] == yt.QUOTA_DAY
        fake.mode = "ok"
        time.sleep(0.5)
        assert fake.inserts == 1                                    # still waiting for the day to turn
        up.quota = yt.Quota()                                       # the day turned
        assert _wait(lambda: any(k == "done" for k, _d in events))
        # a session Google forgot: a new one is opened
        _video(folder, "Clips/b.mp4", 100 * 1024)
        up.add(yt.Job(rel="Clips/b.mp4", title="B", session=fake.base + "/upload/session/old", size=100 * 1024))
        assert _wait(lambda: sum(1 for k, d in events if k == "done") == 2)
        assert fake.inserts == 3
    finally:
        up.quit()
        up.join(timeout=3)


def test_a_dead_refresh_token_and_a_missing_file_are_reported(fake, tmp_path):
    folder = str(tmp_path)
    path, _data = _video(folder, "Clips/a.mp4", 1024)
    events = []
    up = _uploader(events)
    try:
        fake.dead_refresh.add("ref-dead")
        up.configure(True, CID, SECRET, "private", spotify.protect("ref-dead"), [], {})
        up.set_folder(folder)
        up.add(yt.Job(rel="Clips/a.mp4", title="T"))
        assert _wait(lambda: up.state == "login_needed" and ("token", "") in events)
        assert "abgelaufen" in up.status and not up.linked and up.jobs      # the job waits for the new login
        # the login is back; the file is gone meanwhile: given up for good
        os.remove(path)
        up.configure(True, CID, SECRET, "private", spotify.protect("ref-ok"), [], {})
        assert _wait(lambda: any(k == "failed" for k, _d in events))
        failed = next(d for k, d in events if k == "failed")
        assert failed["rel"] == "Clips/a.mp4" and "nicht gefunden" in failed["why"] and not up.jobs
        # without a client id nothing runs
        up.configure(True, "", "", "private", "", [], {})
        assert _wait(lambda: up.state == "no_id")
    finally:
        up.quit()
        up.join(timeout=3)


def test_playlists_take_the_uploaded_videos_only_with_the_wider_scope(fake, tmp_path):
    """1.11: with the box, the login grants SCOPE_MANAGE: the channel's playlists are listed, each upload lands in the
    playlist of its kind (a failed insert is tried again without a second upload), the quota counts both. An old
    login without the scope still uploads, says what is missing and asks to reconnect."""
    folder = str(tmp_path)
    _video(folder, "Clips/a.mp4", 300 * 1024)
    _video(folder, "r.mkv", 300 * 1024)
    fake.scope = f"{yt.SCOPE} {yt.SCOPE_MANAGE}"
    events = []
    up = _uploader(events)
    try:
        up.configure(True, CID, SECRET, "private", spotify.protect("ref-stored"), [], {}, manage=True,
                     playlists={"clip": "PL1", "round": "PL2"})
        up.set_folder(folder)
        up.list_playlists()
        assert _wait(lambda: any(k == "playlists" for k, _d in events))
        listed = next(d for k, d in events if k == "playlists")
        assert listed["ok"] and listed["items"] == [["PL1", "Clips"], ["PL2", "Runden"]]
        fake.pl_fail_once = True                                   # the first insert fails: no second upload
        up.add(yt.Job(rel="Clips/a.mp4", kind="clip", title="C", description="D"))
        up.add(yt.Job(rel="r.mkv", kind="round", title="R", description="D"))
        assert _wait(lambda: sum(1 for k, d in events if k == "playlist" and d["ok"]) == 2, 12)
        assert fake.playlist_items == [("PL1", "vids1"), ("PL2", "vids2")] and fake.inserts == 2
        assert [d["rel"] for k, d in events if k == "done"] == ["Clips/a.mp4", "r.mkv"]
        assert _wait(lambda: up.jobs == [])
        quotas = [d for k, d in events if k == "quota"]
        assert quotas[-1]["used"] == yt.LIST_COST + 2 * (yt.UPLOAD_COST + yt.PLAYLIST_COST)
        assert "Playlists=True" in up.diag_line()
        assert _wait(lambda: up.status == "YouTube: verbunden")                    # no reconnect hint
    finally:
        up.quit()
        up.join(timeout=3)
    # the old login (upload only): the status asks to reconnect, uploads go on, the playlist step says why not
    fake.scope = yt.SCOPE
    _video(folder, "Clips/b.mp4", 100 * 1024)
    events, urls = [], []
    up = _uploader(events, opener=urls.append)
    try:
        up.configure(True, CID, SECRET, "private", spotify.protect("ref-stored"), [], {}, manage=True,
                     playlists={"clip": "PL1"})
        up.set_folder(folder)
        assert _wait(lambda: up.state == "linked" and "neu" in up.status)
        up.add(yt.Job(rel="Clips/b.mp4", kind="clip", title="C", description="D"))
        assert _wait(lambda: any(k == "playlist" for k, _d in events))
        note = next(d for k, d in events if k == "playlist")
        assert not note["ok"] and "verbinden" in note["why"] and any(k == "done" for k, _d in events)
        assert len(fake.playlist_items) == 2 and _wait(lambda: up.jobs == [])
        up.list_playlists()
        assert _wait(lambda: any(k == "playlists" for k, _d in events))
        assert not next(d for k, d in events if k == "playlists")["ok"]
        up.login()                                                 # the new login asks for both scopes
        assert _wait(lambda: bool(urls))
        assert yt.SCOPE_MANAGE in dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(urls[0]).query))["scope"]
    finally:
        up.quit()
        up.join(timeout=3)


def test_the_browser_login_hands_a_refresh_token_to_the_app(fake):
    seen = {}

    def browser(url):
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
        seen.update(q)
        return True
    events = []
    up = _uploader(events, opener=browser)
    try:
        up.configure(True, CID, SECRET, "private", "", [], {})
        assert _wait(lambda: up.state == "login_needed")
        up.login()
        assert _wait(lambda: "state" in seen and up.state == "linking")
        redirect = seen["redirect_uri"]
        assert redirect.startswith("http://127.0.0.1:") and redirect.endswith("/callback")
        import base64, hashlib
        assert base64.urlsafe_b64encode(hashlib.sha256(up._verifier.encode()).digest()).rstrip(b"=").decode() \
            == seen["code_challenge"]
        fake.verifier_for["code-7"] = up._verifier
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"{redirect}?code=code-7&state={seen['state']}", timeout=3) as r:
            assert r.status == 200 and "YouTube" in r.read().decode()
        assert _wait(lambda: up.state == "linked" and up.linked)
        saved = [spotify.unprotect(d) for k, d in events if k == "token" and d]
        assert saved == ["ref1"]
        assert fake.grants[0][1]["client_secret"] == SECRET and fake.grants[0][1]["redirect_uri"] == redirect
        up.logout()
        assert _wait(lambda: not up.linked and ("token", "") in events)
    finally:
        up.quit()
        up.join(timeout=3)
