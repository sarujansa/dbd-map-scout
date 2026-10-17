"""Round recordings with OBS (1.4): the obs-websocket client against a fake server on 127.0.0.1, the recorder's
start/stop, file naming, the index and the room limit. No real OBS, nothing leaves the PC."""
import base64
import hashlib
import json
import os
import queue
import socket
import struct
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dbdmapscout import obsrec  # noqa: E402


# ------------------------------------------------------------------ a fake obs-websocket 5 server
class FakeObs(threading.Thread):
    """Enough of obs-websocket 5 for the client: handshake, Hello/Identify (with or without a password),
    requests GetVersion / GetRecordStatus / StartRecord / StopRecord / replay buffer. Records what it was asked."""

    def __init__(self, password="", record_dir=None, replay=False):
        super().__init__(daemon=True)
        self.password, self.record_dir, self.replay = password, record_dir, replay
        self.srv = socket.socket()
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(3)
        self.port = self.srv.getsockname()[1]
        self.requests = []
        self.recording = None
        self.files = 0
        self.stop_flag = False

    def run(self):
        self.srv.settimeout(0.2)
        while not self.stop_flag:
            try:
                conn, _a = self.srv.accept()
            except socket.timeout:
                continue
            except OSError:                       # stop() closed the listening socket (Windows: WinError 10038)
                break
            try:
                self.serve(conn)
            except (OSError, ValueError):
                pass
            finally:
                conn.close()

    # ---- framing (server frames are unmasked, client frames masked)
    @staticmethod
    def _recv(conn, n):
        buf = b""
        while len(buf) < n:
            c = conn.recv(n - len(buf))
            if not c:
                raise OSError("closed")
            buf += c
        return buf

    def _read(self, conn):
        b0, b1 = self._recv(conn, 2)
        n = b1 & 0x7F
        if n == 126:
            n = struct.unpack("!H", self._recv(conn, 2))[0]
        elif n == 127:
            n = struct.unpack("!Q", self._recv(conn, 8))[0]
        assert b1 & 0x80, "client frames must be masked"
        mask = self._recv(conn, 4)
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(self._recv(conn, n)))
        if b0 & 0x0F == 8:
            raise OSError("closed")
        return json.loads(data.decode())

    @staticmethod
    def _send(conn, obj):
        payload = json.dumps(obj).encode()
        head = b"\x81" + (bytes([len(payload)]) if len(payload) < 126 else b"\x7e" + struct.pack("!H", len(payload)))
        conn.sendall(head + payload)

    def serve(self, conn):
        head = b""
        while b"\r\n\r\n" not in head:
            head += conn.recv(4096)
        key = next(ln.split(":", 1)[1].strip() for ln in head.decode().split("\r\n")
                   if ln.lower().startswith("sec-websocket-key"))
        accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest())
        conn.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                     b"Sec-WebSocket-Accept: " + accept + b"\r\nSec-WebSocket-Protocol: obswebsocket.json\r\n\r\n")
        hello = {"obsWebSocketVersion": "5.5.0", "rpcVersion": 1}
        if self.password:
            hello["authentication"] = {"challenge": "c" * 44, "salt": "s" * 44}
        self._send(conn, {"op": 0, "d": hello})
        ident = self._read(conn)
        assert ident["op"] == 1
        if self.password:
            if ident["d"].get("authentication") != obsrec.auth_string(self.password, "s" * 44, "c" * 44):
                conn.close()                        # OBS closes the socket on a wrong password
                return
        self._send(conn, {"op": 2, "d": {"negotiatedRpcVersion": 1}})
        while True:
            msg = self._read(conn)
            d = msg["d"]
            kind, rid, data = d["requestType"], d["requestId"], d.get("requestData") or {}
            self.requests.append((kind, data))
            ok, out = True, {}
            if kind == "GetVersion":
                out = {"obsVersion": "31.0.0"}
            elif kind == "GetRecordStatus":
                out = {"outputActive": self.recording is not None}
            elif kind == "SetRecordDirectory":
                self.record_dir = data["recordDirectory"]
            elif kind == "StartRecord":
                self.files += 1
                self.recording = os.path.join(self.record_dir, f"obs {self.files}.mkv")
                with open(self.recording, "wb") as f:
                    f.write(ROUND_BYTES)
            elif kind == "StopRecord":
                out, self.recording = {"outputPath": self.recording}, None
            elif kind == "GetReplayBufferStatus":
                out = {"outputActive": self.replay}
            elif kind == "StartReplayBuffer":
                self.replay = True
            elif kind == "StopReplayBuffer":
                self.replay = False
            elif kind == "SaveReplayBuffer":
                self.last_replay = os.path.join(self.record_dir, "Replay.mkv")
                with open(self.last_replay, "wb") as f:
                    f.write(PRE_BYTES)
            elif kind == "GetLastReplayBufferReplay":
                out = {"savedReplayPath": self.last_replay}
            else:
                ok = False
            self._send(conn, {"op": 7, "d": {"requestType": kind, "requestId": rid,
                                             "requestStatus": {"result": ok, "code": 100 if ok else 204},
                                             "responseData": out}})

    def stop(self):
        self.stop_flag = True
        self.srv.close()


ROUND_BYTES = b"\x1a\x45\xdf\xa3" + b"\0" * obsrec.MIN_FILE_BYTES      # an MKV header, big enough
PRE_BYTES = b"\x1a\x45\xdf\xa3" + b"\0" * 300


@pytest.fixture
def obs(tmp_path):
    srv = FakeObs(record_dir=str(tmp_path))
    srv.start()
    yield srv
    srv.stop()


def test_the_auth_string_is_sha256_twice_base64():
    secret = base64.b64encode(hashlib.sha256(b"pwsalt").digest()).decode()
    want = base64.b64encode(hashlib.sha256((secret + "chal").encode()).digest()).decode()
    assert obsrec.auth_string("pw", "salt", "chal") == want


def test_the_client_talks_to_obs_only_on_this_pc(obs):
    assert obsrec.HOST == "127.0.0.1"
    c = obsrec.ObsClient(obs.port).connect()
    assert c.request("GetVersion")["obsVersion"] == "31.0.0"
    c.close()
    with pytest.raises(obsrec.ObsError):
        obsrec.ObsClient(1).connect()                       # nothing listening


def test_a_wrong_or_missing_password_is_a_clear_error(tmp_path):
    srv = FakeObs(password="geheim", record_dir=str(tmp_path))
    srv.start()
    try:
        with pytest.raises(obsrec.ObsError, match="Passwort"):
            obsrec.ObsClient(srv.port, "").connect()
        with pytest.raises(obsrec.ObsError, match="Passwort"):
            obsrec.ObsClient(srv.port, "falsch").connect()
        c = obsrec.ObsClient(srv.port, "geheim").connect()
        assert c.request("GetRecordStatus") == {"outputActive": False}
        c.close()
    finally:
        srv.stop()


def _recorder(obs, folder, **kw):
    posted = queue.Queue()
    r = obsrec.Recorder(lambda kind, **d: posted.put((kind, d)))
    r.cfg = obsrec.Config(on=True, port=obs.port, folder=folder, **kw)
    return r, posted


def test_a_round_is_recorded_named_and_indexed(obs, tmp_path):
    folder = str(tmp_path)
    r, posted = _recorder(obs, folder, pre=False)
    t = time.mktime((2026, 10, 17, 21, 40, 0, 0, 0, -1))
    r._begin({"t": t, "map_id": "coal", "label": "Coal Tower", "role": "killer", "killer": "Nurse"})
    assert obs.recording and ("SetRecordDirectory", {"recordDirectory": folder}) in obs.requests
    assert posted.get(timeout=1)[0] == "status" and posted.get(timeout=1)[0] == "started"
    r._finish({})
    names = sorted(os.listdir(folder))
    assert names == ["2026-10-17 21-40 Coal Tower – Nurse.mkv", obsrec.INDEX]
    recs = obsrec.load_index(folder)
    assert len(recs) == 1 and recs[0].t == t and recs[0].killer == "Nurse" and recs[0].size == len(ROUND_BYTES)
    assert not recs[0].extra
    kinds = [posted.get(timeout=1)[0] for _i in range(2)]
    assert kinds == ["status", "saved"]
    # survivor round, no killer: the role names the file; a second file of the same minute gets "(2)"
    r._begin({"t": t, "map_id": "coal", "label": "Coal Tower", "role": "survivor"})
    r._finish({})
    assert "2026-10-17 21-40 Coal Tower – Survivor.mkv" in os.listdir(folder)


def test_the_replay_buffer_becomes_the_pre_roll(tmp_path):
    obs = FakeObs(record_dir=str(tmp_path), replay=True)
    obs.start()
    try:
        r, posted = _recorder(obs, str(tmp_path), pre=True, merge=False)
        r._begin({"t": 1.0, "label": "Gas Heaven", "role": "killer", "killer": "Hag"})
        assert ("SaveReplayBuffer", {}) in obs.requests
        r._finish({})
        rec = obsrec.load_index(str(tmp_path))[0]
        assert rec.pre.endswith("(Vorlauf).mkv") and os.path.exists(os.path.join(str(tmp_path), rec.pre))
        assert rec.size == len(ROUND_BYTES) + len(PRE_BYTES)      # round + pre-roll
    finally:
        obs.stop()


def test_a_new_banner_while_recording_closes_the_old_round_first(obs, tmp_path):
    r, posted = _recorder(obs, str(tmp_path), pre=False)
    r._begin({"t": 1.0, "label": "A"})
    r._begin({"t": 2.0, "label": "B"})
    assert [k for k, _d in obs.requests].count("StopRecord") == 1
    r._finish({})
    assert len(obsrec.load_index(str(tmp_path))) == 2


def test_nothing_is_recorded_without_the_drive_or_when_obs_records_by_hand(obs, tmp_path):
    r, posted = _recorder(obs, os.path.join(str(tmp_path), "missing"), pre=False)
    r._begin({"t": 1.0, "label": "A"})
    assert r.active is None and "nicht angeschlossen" in posted.get(timeout=1)[1]["text"]
    assert not obs.requests                                  # OBS was not even asked
    r.cfg.folder = str(tmp_path)
    obs.recording = "/somewhere/manual.mkv"
    r._begin({"t": 1.0, "label": "A"})
    assert r.active is None and "schon auf" in posted.get(timeout=1)[1]["text"]
    r.cfg.on = False
    obs.recording = None
    r._begin({"t": 1.0, "label": "A"})
    assert r.active is None


def test_prune_deletes_the_oldest_unkept_recordings_only_from_the_index(tmp_path):
    folder = str(tmp_path)
    recs = []
    for i in range(5):
        name = f"r{i}.mkv"
        with open(os.path.join(folder, name), "wb") as f:
            f.write(b"\0" * 100)
        recs.append(obsrec.Recording(t=float(i), file=name, keep=(i == 1)))
    with open(os.path.join(folder, "someone-elses.mkv"), "wb") as f:
        f.write(b"\0" * 100)
    recs.append(obsrec.Recording(t=9.0, file="gone.mkv"))          # file missing: drops out silently
    left, deleted = obsrec.prune(folder, recs, limit=350, reserve=0, free=10 ** 9)
    assert deleted == ["r0.mkv", "r2.mkv"] and [r.file for r in left] == ["r1.mkv", "r3.mkv", "r4.mkv"]
    assert os.path.exists(os.path.join(folder, "someone-elses.mkv"))
    # whole drive (limit 0): only the free-space reserve counts (r1 is kept: never deleted)
    left, deleted = obsrec.prune(folder, left, limit=0, reserve=1000, free=920)
    assert deleted == ["r3.mkv"] and [r.file for r in left] == ["r1.mkv", "r4.mkv"]
    left, deleted = obsrec.prune(folder, left, limit=0, reserve=1000, free=5000)
    assert deleted == []


def test_the_index_round_trips_and_skips_bad_lines(tmp_path):
    folder = str(tmp_path)
    recs = [obsrec.Recording(t=1.0, file="a.mkv", label="Coal Tower", killer="Nurse", keep=True),
            obsrec.Recording(t=0.5, file="b.mkv")]
    obsrec.save_index(folder, recs)
    with open(os.path.join(folder, obsrec.INDEX), "a", encoding="utf-8") as f:
        f.write("not json\n")
    back = obsrec.load_index(folder)
    assert [r.file for r in back] == ["b.mkv", "a.mkv"] and back[1].keep and back[1].killer == "Nurse"


def test_file_names_carry_no_forbidden_characters():
    name = obsrec.file_name(0.0, 'The "Game" <II>', "Oni: Bear", ".mkv")
    assert not any(ch in name for ch in '<>:"/\\|?*') and name.endswith(".mkv") and "Oni Bear" in name
    assert obsrec.file_name(0.0, "", "", ".mkv").endswith(" Map.mkv")


def test_the_folder_is_found_by_its_volume_or_the_last_path(tmp_path):
    assert obsrec.find_folder("", "", str(tmp_path)) == str(tmp_path)
    assert obsrec.find_folder("", "", str(tmp_path / "nope")) is None
    if sys.platform != "win32":
        assert obsrec.volume_of(str(tmp_path)) == ("", str(tmp_path))


def test_the_recorder_thread_survives_errors(obs, tmp_path):
    r, posted = _recorder(obs, str(tmp_path), pre=False)
    r.start()
    r.cfg.port = 1                                            # nothing listening: an ObsError per command
    r.test()
    kind, d = posted.get(timeout=3)
    assert kind == "status" and not d["ok"] and "nicht erreichbar" in d["text"]
    r.cfg.port = obs.port
    r.test()
    kind, d = posted.get(timeout=3)
    assert kind == "status" and d["ok"] and "OBS 31.0.0" in d["text"] and "bereit" in d["text"]
    r.quit()
    r.join(timeout=3)
    assert not r.is_alive()


def test_the_replay_buffer_follows_the_game_and_obs_is_checked_once(tmp_path):
    """1.4.1: DBD starts -> OBS checked, replay buffer started; DBD closes -> a running round ends, the buffer we
    started stops. OBS not running -> one warning for the user."""
    obs = FakeObs(record_dir=str(tmp_path))
    obs.start()
    try:
        r, posted = _recorder(obs, str(tmp_path), pre=True, buffer_auto=True)
        r._game_changed(True)
        assert obs.replay and r._buffer_ours
        assert posted.get(timeout=1)[1]["ok"]
        r._begin({"t": 1.0, "label": "A"})
        r._game_changed(False)                               # DBD closed mid-round
        assert r.active is None and not obs.replay and not r._buffer_ours
        assert len(obsrec.load_index(str(tmp_path))) == 1
        while not posted.empty():                            # the round's own messages
            posted.get_nowait()
        r.cfg.port = 1
        r._game = None
        r._game_changed(True)
        kinds = [posted.get(timeout=1) for _i in range(2)]
        warn = next(d for k, d in kinds if k == "warn")
        assert "OBS läuft nicht" in warn["text"]
    finally:
        obs.stop()


def test_the_tail_keeps_recording_after_the_end(obs, tmp_path):
    r, posted = _recorder(obs, str(tmp_path), pre=False, tail_s=0.3)
    r._begin({"t": 1.0, "label": "A"})
    r._stop_later({"role": "killer"})
    assert r.active is not None and r._pending is not None and obs.recording      # still recording
    r._due()
    assert obs.recording                                       # not yet due
    time.sleep(0.35)
    r._due()
    assert r.active is None and r._pending is None and not obs.recording
    # the next banner during a tail ends the old round at once
    r._begin({"t": 2.0, "label": "B"})
    r._stop_later({})
    r._begin({"t": 3.0, "label": "C"})
    assert r._pending is None and len(obsrec.load_index(str(tmp_path))) == 2
    r._finish({})
    assert r.recording is False


def test_broken_recordings_are_reported(tmp_path):
    f = tmp_path / "a.mkv"
    f.write_bytes(b"")
    assert obsrec.check_file(str(f)) == "leer"
    f.write_bytes(b"\x1a\x45\xdf\xa3" + b"\0" * 10)
    assert obsrec.check_file(str(f)) == "zu klein"
    f.write_bytes(b"\0" * (obsrec.MIN_FILE_BYTES + 8))
    assert obsrec.check_file(str(f)) == "kein Video"
    f.write_bytes(b"\0\0\0\x1cftypisom" + b"\0" * obsrec.MIN_FILE_BYTES)
    assert obsrec.check_file(str(f)) is None
    assert obsrec.check_file(str(tmp_path / "missing.mkv")) == "fehlt"


def test_a_broken_file_from_obs_gives_a_warning(tmp_path):
    obs = FakeObs(record_dir=str(tmp_path))
    obs.start()
    try:
        r, posted = _recorder(obs, str(tmp_path), pre=False)
        r._begin({"t": 1.0, "label": "A"})
        with open(obs.recording, "wb") as f:                  # OBS wrote nothing usable
            f.write(b"\0" * 10)
        r._finish({})
        kinds = [posted.get(timeout=1) for _i in range(4)]
        assert any(k == "warn" and "beschädigt" in d["text"] for k, d in kinds)
        assert obsrec.load_index(str(tmp_path))[0].extra == {"bad": "zu klein"}
    finally:
        obs.stop()


def test_the_rec_dot_is_drawn_on_the_overlay_and_the_tray_icon():
    from PIL import Image
    from dbdmapscout import icon, overlay_win32
    pic = Image.new("RGBA", (400, 600), (0, 0, 0, 255))
    out = overlay_win32.rec_badge(pic, 480)
    assert out is not pic and out.size == pic.size
    reds = [out.getpixel((x, y)) for x in range(380, 400) for y in range(0, 20)]
    assert any(p[0] > 200 and p[1] < 120 for p in reds) and pic.getpixel((390, 10)) == (0, 0, 0, 255)
    plain, rec = icon.draw_status(64, None), icon.draw_status(64, None, rec=True)
    assert plain.tobytes() != rec.tobytes()
    r, g, b, a = rec.getpixel((52, 12))
    assert r > 180 and g < 120 and plain.getpixel((10, 50)) == rec.getpixel((10, 50))


# ------------------------------------------------------------------ 1.4.2: one file, marks, room, prune order
def _fake_ffmpeg(ok=True, duration=b"00:00:20.50"):
    """Stands in for the ffmpeg binary: ``-i file`` answers with a duration, the concat call glues the files."""
    calls = []

    def run(args, timeout=None):
        calls.append(args)
        if "concat" not in args:
            return 0, b"Input #0, matroska\n  Duration: " + duration + b", start: 0.000000, bitrate: 1 kb/s\n"
        if not ok:
            return 1, b"Invalid data found when processing input"
        lst, out = args[args.index("-i") + 1], args[-1]
        with open(out, "wb") as o:
            for line in open(lst, encoding="utf-8"):
                path = line.strip()[6:-1].replace("'\\''", "'")
                o.write(open(path, "rb").read())
        return 0, b""
    return run, calls


def test_the_pre_roll_is_joined_into_the_round_file_and_marks_move_with_it(tmp_path, monkeypatch):
    run, calls = _fake_ffmpeg()
    monkeypatch.setattr(obsrec, "ffmpeg_exe", lambda: "ffmpeg")
    monkeypatch.setattr(obsrec, "_run", run)
    obs = FakeObs(record_dir=str(tmp_path), replay=True)
    obs.start()
    try:
        r, posted = _recorder(obs, str(tmp_path), pre=True, merge=True)
        r._begin({"t": 1.0, "label": "Gas Heaven", "role": "killer", "killer": "Hag", "farming": True})
        r.active["since"] -= 100                              # 100 s into the round …
        r._mark()                                             # … F8
        assert posted.get(timeout=1)[0] == "status" and posted.get(timeout=1)[0] == "started"
        kind, d = posted.get(timeout=1)
        assert kind == "marked" and d["n"] == 1 and 99 <= d["pos"] <= 101
        r._finish({})
        names = sorted(n for n in os.listdir(str(tmp_path)) if n != obsrec.INDEX)
        assert len(names) == 1 and "Gas Heaven – Hag" in names[0] and "Vorlauf" not in names[0]   # one file
        rec = obsrec.load_index(str(tmp_path))[0]
        assert rec.pre == "" and rec.pre_s == 20.5 and rec.farming and not rec.extra
        assert rec.size == len(ROUND_BYTES) + len(PRE_BYTES)
        assert len(rec.marks) == 1 and 119 <= rec.marks[0] <= 121      # shifted by the pre-roll
        with open(os.path.join(str(tmp_path), rec.file), "rb") as f:
            assert f.read(len(PRE_BYTES)) == PRE_BYTES              # the pre-roll comes first
        concat = next(a for a in calls if "concat" in a)
        assert concat[-3:] == ["-c", "copy", os.path.join(str(tmp_path), rec.file[:-4] + " (zusammen).mkv")]
        assert "-y" in concat and not os.path.exists(concat[concat.index("-i") + 1])          # the list file is gone
        saved = next(d for k, d in _drain(posted) if k == "saved")
        assert saved["marks"] == 1
    finally:
        obs.stop()


def _drain(q):
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


def test_a_failed_join_keeps_both_files(tmp_path, monkeypatch):
    run, _calls = _fake_ffmpeg(ok=False)
    monkeypatch.setattr(obsrec, "ffmpeg_exe", lambda: "ffmpeg")
    monkeypatch.setattr(obsrec, "_run", run)
    obs = FakeObs(record_dir=str(tmp_path), replay=True)
    obs.start()
    try:
        r, posted = _recorder(obs, str(tmp_path), pre=True, merge=True)
        r._begin({"t": 1.0, "label": "A"})
        r._finish({})
        rec = obsrec.load_index(str(tmp_path))[0]
        assert rec.pre.endswith("(Vorlauf).mkv") and rec.extra == {"merge_failed": True} and rec.pre_s == 0
        assert os.path.exists(os.path.join(str(tmp_path), rec.pre)) and os.path.exists(os.path.join(str(tmp_path), rec.file))
        assert not [n for n in os.listdir(str(tmp_path)) if "zusammen" in n]
        texts = [d.get("text", "") for k, d in _drain(posted) if k == "status"]
        assert any("nicht angefügt" in t for t in texts)
    finally:
        obs.stop()


def test_without_ffmpeg_or_a_recording_nothing_is_joined_or_marked(tmp_path, monkeypatch):
    monkeypatch.setattr(obsrec, "ffmpeg_exe", lambda: None)
    assert obsrec.merge_files(["a", "b"], str(tmp_path / "x.mkv")) is False
    assert obsrec.media_duration("a") is None
    r = obsrec.Recorder(lambda kind, **d: None)
    posted = []
    r._post = lambda kind, **d: posted.append((kind, d))
    r._mark()
    assert posted == [("marked", {"pos": None})]


@pytest.mark.skipif(obsrec.ffmpeg_exe() is None, reason="imageio-ffmpeg not installed")
def test_merge_files_joins_real_videos_without_re_encoding(tmp_path):
    """The real ffmpeg from imageio-ffmpeg on two tiny generated clips: one file, twice as long."""
    ff = obsrec.ffmpeg_exe()
    parts = []
    for i in range(2):
        p = str(tmp_path / f"part {i}'s.mkv")                        # an apostrophe: the concat list must escape it
        rc, err = obsrec._run([ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                               "-i", "testsrc=duration=1:size=64x64:rate=10", "-c:v", "mpeg4", p], timeout=60)
        assert rc == 0, err
        parts.append(p)
    d1 = obsrec.media_duration(parts[0], ff)
    assert d1 is not None and 0.8 <= d1 <= 1.3
    out = str(tmp_path / "both.mkv")
    assert obsrec.merge_files(parts, out, ff)
    d = obsrec.media_duration(out, ff)
    assert d is not None and 1.8 <= d <= 2.3 and not os.path.exists(out + ".txt")


def test_prune_goes_for_farming_and_short_rounds_first_and_marked_last(tmp_path):
    folder = str(tmp_path)
    recs = []
    spec = [("old.mkv", 0.0, {}), ("farm.mkv", 100.0, {"farming": True}),
            ("short.mkv", 200.0, {"end": 200.0 + 120}), ("marked.mkv", 50.0, {"marks": [12.5]}),
            ("long.mkv", 300.0, {"end": 300.0 + 900})]
    for name, t, kw in spec:
        with open(os.path.join(folder, name), "wb") as f:
            f.write(b"\0" * 100)
        recs.append(obsrec.Recording(t=t, file=name, **kw))
    assert [obsrec.prune_rank(r) for r in recs] == [1, 0, 0, 2, 1]
    left, deleted = obsrec.prune(folder, recs, limit=150, reserve=0, free=10 ** 9)
    assert deleted == ["farm.mkv", "short.mkv", "old.mkv", "long.mkv"] and [r.file for r in left] == ["marked.mkv"]


def test_space_counts_the_index_and_the_drive(tmp_path):
    folder = str(tmp_path)
    for name in ("a.mkv", "b.mkv"):
        with open(os.path.join(folder, name), "wb") as f:
            f.write(b"\0" * 100)
    recs = [obsrec.Recording(t=5.0, file="a.mkv", size=100), obsrec.Recording(t=3.0, file="b.mkv", size=100, marks=[1.0])]
    obsrec.save_index(folder, recs)
    sp = obsrec.space(folder)
    assert sp.count == 2 and sp.used == 200 and sp.oldest == 3.0 and sp.marked == 1 and sp.folder == folder
    assert sp.free > 0 and sp.total >= sp.free and sp.t > 0
    assert obsrec.space(None).folder == "" and obsrec.space(None).count == 0


def test_the_f8_hotkey_and_the_overview_tile_exist():
    import inspect
    from types import SimpleNamespace
    from dbdmapscout import config, hotkeys, overview, qt_window
    from dbdmapscout.app_hotkeys import HOTKEY_LABELS
    assert config.DEFAULTS["hotkeys"]["mark_clip"] == "f8" and hotkeys.game_only("f8")
    assert "mark_clip" in dict(HOTKEY_LABELS) and '"mark_clip"' in inspect.getsource(qt_window)
    app = SimpleNamespace(settings={"rec_on": False}, recorder=SimpleNamespace(space=obsrec.Space()))
    assert overview.recordings(app) is None
    app.settings = {"rec_on": True, "rec_folder": "D:\\DBD"}
    assert "gemessen" in overview.recordings(app).sub           # not measured yet
    app.recorder.space = obsrec.Space(t=1.0)
    f = overview.recordings(app)
    assert f.action == "rec_setup" and "nicht angeschlossen" in f.sub
    gb = 1024 ** 3
    app.recorder.space = obsrec.Space(free=900 * gb, total=1000 * gb, used=60 * gb, count=2, oldest=1.0,
                                      marked=1, folder="D:\\DBD", t=1.0)
    f = overview.recordings(app)
    assert f.value == "900 GB frei" and "2 Runden" in f.sub and "60 GB" in f.sub and "1 mit Marke" in f.sub
    assert f.action == "" and abs(f.frac - 0.1) < 1e-9 and f.colour is None
    app.recorder.space.free = 6 * gb
    assert overview.recordings(app).colour is not None


# ------------------------------------------------------------------ 1.5: tab "Aufnahmen"
def test_select_recordings_filters_the_index():
    R = obsrec.Recording
    recs = [R(t=10.0, file="a.mkv", label="Coal Tower", role="killer"),
            R(t=20.0, file="b.mkv", label="Gas Heaven", role="survivor", marks=[3.0]),
            R(t=30.0, file="c.mkv", label="Coal Tower", role="killer", farming=True, keep=True),
            R(t=40.0, file="d.mkv", label="Coal Tower", role="killer", extra={"bad": "leer"})]
    files = lambda out: [r.file for r in out]  # noqa: E731
    assert files(obsrec.select_recordings(recs)) == ["d.mkv", "c.mkv", "b.mkv", "a.mkv"]       # newest first
    assert files(obsrec.select_recordings(recs, since=25.0)) == ["d.mkv", "c.mkv"]
    assert files(obsrec.select_recordings(recs, map_label="Gas Heaven")) == ["b.mkv"]
    assert files(obsrec.select_recordings(recs, role="killer")) == ["d.mkv", "a.mkv"]          # farming not a killer round
    assert files(obsrec.select_recordings(recs, role="farming")) == ["c.mkv"]
    assert files(obsrec.select_recordings(recs, only="marked")) == ["b.mkv"]
    assert files(obsrec.select_recordings(recs, only="kept")) == ["c.mkv"]
    assert files(obsrec.select_recordings(recs, only="bad")) == ["d.mkv"]


def test_keep_and_delete_from_the_tab_go_through_the_recorder(tmp_path):
    """1.5: the tab never writes the index itself – the recorder thread does (one writer); deleting removes only
    the files the entry names."""
    folder = str(tmp_path)
    for name in ("a.mkv", "a (Vorlauf).mkv", "b.mkv", "someone-elses.mkv"):
        with open(os.path.join(folder, name), "wb") as f:
            f.write(b"\0" * 10)
    obsrec.save_index(folder, [obsrec.Recording(t=1.0, file="a.mkv", pre="a (Vorlauf).mkv"),
                               obsrec.Recording(t=2.0, file="b.mkv")])
    posted = []
    r = obsrec.Recorder(lambda kind, **d: posted.append((kind, d)))
    r.cfg = obsrec.Config(on=True, folder=folder)
    r._set_keep(2.0, True)
    assert [x.keep for x in obsrec.load_index(folder)] == [False, True]
    assert posted[-1] == ("changed", {"what": "keep", "t": 2.0, "on": True, "file": "b.mkv"})
    r._set_keep(99.0, True)                                   # unknown: nothing happens
    r._delete_one(1.0)
    assert sorted(os.listdir(folder)) == ["b.mkv", obsrec.INDEX, "someone-elses.mkv"]
    assert [x.file for x in obsrec.load_index(folder)] == ["b.mkv"]
    kinds = [k for k, _d in posted]
    assert kinds[-2:] == ["changed", "deleted"] and posted[-1][1] == {"files": ["a.mkv", "a (Vorlauf).mkv"], "manual": True}
    r.cfg.folder = os.path.join(folder, "gone")                # drive missing: a warning, nothing written
    r._delete_one(2.0)
    assert posted[-1][0] == "warn" and os.path.exists(os.path.join(folder, "b.mkv"))
    # the thread takes the same commands
    r.cfg.folder = folder
    r.start()
    r.set_keep(2.0, False)
    r.delete(2.0)
    r.quit()
    r.join(timeout=5)
    assert not os.path.exists(os.path.join(folder, "b.mkv")) and obsrec.load_index(folder) == []
