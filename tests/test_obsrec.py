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

    def __init__(self, password="", record_dir=None, replay=False, replay_delay=0):
        super().__init__(daemon=True)
        self.password, self.record_dir, self.replay = password, record_dir, replay
        self.replay_delay = replay_delay            # 1.5.4: GetLastReplayBufferReplay answers the old path this often
        self.last_replay = os.path.join(record_dir or ".", "Replay_old.mkv") if record_dir else ""
        self._pending = None
        self.saves = 0
        self.srv = socket.socket()
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(3)
        self.port = self.srv.getsockname()[1]
        self.requests = []
        self.recording = None
        self.files = 0
        self.stop_flag = False
        self.inputs = {"Desktop-Audio": {"muted": False}, "Mic/Aux": {"muted": False}}
        self.profile = {("Output", "Mode"): "Advanced", ("AdvOut", "RecTracks"): "15"}  # 1.8.6: tracks 1–4 ticked
        self.scenes = {}                            # 1.8.18: {scene: [scene items]}

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
                self.saves += 1
                new = os.path.join(self.record_dir, f"Replay_{self.saves}.mkv")
                self._pending = [new, self.replay_delay]      # written (and reported) only after the delay
                if not self.replay_delay:
                    self._write_replay()
            elif kind == "GetInputList":              # 1.6: audio sources
                out = {"inputs": [{"inputName": n} for n in self.inputs]}
            elif kind == "GetCurrentProgramScene":
                out = {"currentProgramSceneName": "Szene", "sceneName": "Szene"}
            elif kind == "CreateInput":
                self.inputs[data["inputName"]] = dict(data, muted=False)
                self._item(data["sceneName"], data["inputName"], data.get("sceneItemEnabled", True))
            elif kind == "GetSceneItemList":           # 1.8.18
                out = {"sceneItems": [dict(i) for i in self.scenes.get(data["sceneName"], [])]}
            elif kind == "CreateSceneItem":
                ok = data["sourceName"] in self.inputs
                if ok:
                    self._item(data["sceneName"], data["sourceName"], data.get("sceneItemEnabled", True))
            elif kind == "SetSceneItemEnabled":
                hits = [i for i in self.scenes.get(data["sceneName"], []) if i["sceneItemId"] == data["sceneItemId"]]
                ok = bool(hits)
                for i in hits:
                    i["sceneItemEnabled"] = data["sceneItemEnabled"]
            elif kind == "SetInputMute":
                ok = data["inputName"] in self.inputs
                if ok:
                    self.inputs[data["inputName"]]["muted"] = data["inputMuted"]
            elif kind == "GetSpecialInputs":
                out = {"desktop1": "Desktop-Audio", "desktop2": None, "mic1": "Mic/Aux"}
            elif kind == "SetInputAudioTracks":        # 1.8.5
                ok = data["inputName"] in self.inputs
                if ok:
                    self.inputs[data["inputName"]]["tracks"] = dict(data["inputAudioTracks"])
            elif kind == "GetProfileParameter":
                value = self.profile.get((data["parameterCategory"], data["parameterName"]))
                out = {"parameterValue": value, "defaultParameterValue": None}
            elif kind == "GetLastReplayBufferReplay":
                if self._pending and self._pending[1] > 0:
                    self._pending[1] -= 1
                    if self._pending[1] == 0:
                        self._write_replay()
                out = {"savedReplayPath": self.last_replay}
            else:
                ok = False
            self._send(conn, {"op": 7, "d": {"requestType": kind, "requestId": rid,
                                             "requestStatus": {"result": ok, "code": 100 if ok else 204},
                                             "responseData": out}})

    def _item(self, scene, source, enabled=True):
        items = self.scenes.setdefault(scene, [])
        items.append({"sourceName": source, "sceneItemId": len(items) + 1, "sceneItemEnabled": enabled})

    def _write_replay(self):
        path, self._pending = self._pending[0], None
        with open(path, "wb") as f:
            f.write(PRE_BYTES)
        self.last_replay = path

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


def _reds(img, x0=0):
    px = img.convert("RGBA").load()
    return [(x, y) for x in range(x0, img.width) for y in range(img.height)
            if px[x, y][3] > 200 and px[x, y][0] > 200 and px[x, y][1] < 120 and px[x, y][2] < 120]


def test_the_rec_dot_blinks_right_of_the_timer_in_every_style_and_on_the_tray_icon():
    """1.5.2 (user: "rechts von der Rundenzeit blinkend"): the red dot sits right of the round timer – classic
    info block and the three modern cards – on during even seconds, off during odd ones, never while not
    recording; the card keeps its size between the phases (nothing jumps)."""
    from PIL import Image
    from dbdmapscout import icon, overlay_win32, skin
    assert overlay_win32.rec_phase(10.2) and not overlay_win32.rec_phase(11.7)
    pic = Image.new("RGBA", (400, 300), (0, 0, 0, 0))
    on = overlay_win32.add_info(pic.copy(), "03:12", "", 480, rec=True)
    off = overlay_win32.add_info(pic.copy(), "03:12", "", 480, rec=False)
    none = overlay_win32.add_info(pic.copy(), "03:12", "", 480)
    assert on.size == off.size == none.size
    reds = _reds(on)
    assert reds and min(x for x, _y in reds) > on.width // 2 + 40      # right of the centred digits
    assert min(y for _x, y in reds) > 300 and not _reds(off) and not _reds(none)   # below the map, on only
    body = Image.new("RGBA", (300, 200), (40, 40, 60, 255))
    for style in ("glass", "chips", "line"):
        cards = {rec: skin.map_card(body, "Coal Tower", "MacMillan", "03:12", "", "", "", None, (), 480, style,
                                    "#c9a227", rec=rec) for rec in (True, False, None)}
        assert cards[True].size == cards[False].size, style
        reds = _reds(cards[True])
        assert reds and min(x for x, _y in reds) > cards[True].width // 2, style
        assert not _reds(cards[False]) and not _reds(cards[None]), style
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
        assert sorted(os.listdir(str(tmp_path))) == ["Farming", obsrec.INDEX]       # 1.5.3: a farming round
        names = os.listdir(os.path.join(str(tmp_path), "Farming"))
        assert len(names) == 1 and "Gas Heaven – Hag" in names[0] and "Vorlauf" not in names[0]   # one file
        rec = obsrec.load_index(str(tmp_path))[0]
        assert rec.file == "Farming/" + names[0] and rec.pre == "" and rec.pre_s == 20.5 and rec.farming
        assert not rec.extra and rec.size == len(ROUND_BYTES) + len(PRE_BYTES)
        assert len(rec.marks) == 1 and 119 <= rec.marks[0] <= 121      # shifted by the pre-roll
        with open(obsrec.rel_path(str(tmp_path), rec.file), "rb") as f:
            assert f.read(len(PRE_BYTES)) == PRE_BYTES              # the pre-roll comes first
        concat = next(a for a in calls if "concat" in a)
        assert concat[-3:] == ["-c", "copy", os.path.join(str(tmp_path), "Farming", names[0][:-4] + " (zusammen).mkv")]
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


# ------------------------------------------------------------------ 1.5.3: farming subfolder, paths stay inside
def test_index_paths_stay_inside_the_folder():
    f = os.path.join("D", "DBD") if os.name == "nt" else "/d/DBD"
    assert obsrec.rel_path(f, "a.mkv") == os.path.join(f, "a.mkv")
    assert obsrec.rel_path(f, "Farming/a.mkv") == os.path.join(f, "Farming", "a.mkv")
    assert obsrec.rel_path(f, "Farming\\a.mkv") == os.path.join(f, "Farming", "a.mkv")
    for bad in ("", "../a.mkv", "Farming/../a.mkv", "/etc/passwd", "C:\\x.mkv", "a/b/c.mkv", "./a.mkv"):
        assert obsrec.rel_path(f, bad) is None, bad


def test_farming_rounds_go_into_their_own_subfolder_and_are_pruned_and_deleted_there(obs, tmp_path):
    folder = str(tmp_path)
    r, posted = _recorder(obs, folder, pre=False)
    r._begin({"t": 1.0, "label": "Coal Tower", "role": "killer", "killer": "Nurse"})
    r._finish({"farming": True})                                     # known at the end (region) counts too
    r._begin({"t": 2.0, "label": "Gas Heaven", "role": "survivor"})
    r._finish({})
    recs = obsrec.load_index(folder)
    assert [x.file.split("/")[0] for x in recs] == ["Farming", "1970-01-01 01-00 Gas Heaven – Survivor.mkv"] \
        or [x.file.startswith("Farming/") for x in recs] == [True, False]
    farm = next(x for x in recs if x.farming)
    assert os.path.exists(os.path.join(folder, "Farming", farm.file.split("/", 1)[1]))
    # room needed: the farming round goes first – from inside the subfolder
    left, deleted = obsrec.prune(folder, recs, limit=len(ROUND_BYTES) + 10, reserve=0, free=10 ** 12)
    assert deleted == [farm.file] and not os.path.exists(obsrec.rel_path(folder, farm.file)) and len(left) == 1
    # the switch off: farming rounds stay among the others
    r.cfg.farming_sub = False
    r._begin({"t": 3.0, "label": "The Game", "role": "killer", "farming": True})
    r._finish({})
    assert all("/" not in x.file for x in obsrec.load_index(folder) if x.t == 3.0)
    # delete from the tab reaches into the subfolder
    r.cfg.farming_sub = True
    r._begin({"t": 4.0, "label": "Ormond", "role": "killer", "farming": True})
    r._finish({})
    hit = next(x for x in obsrec.load_index(folder) if x.t == 4.0)
    assert hit.file.startswith("Farming/")
    r._delete_one(4.0)
    assert not os.path.exists(obsrec.rel_path(folder, hit.file)) and all(x.t != 4.0 for x in obsrec.load_index(folder))


# ------------------------------------------------------------------ 1.5.4: the replay is picked up when OBS is done
def test_the_pre_roll_is_waited_for_when_obs_saves_it_slowly(tmp_path):
    """1.5.4 (user: files named "Replay_…" stayed behind): OBS writes the replay buffer asynchronously – the
    recorder polls until the path changes and the file exists instead of taking whatever OBS names 0.3 s later."""
    obs = FakeObs(record_dir=str(tmp_path), replay=True, replay_delay=3)
    obs.start()
    try:
        r, posted = _recorder(obs, str(tmp_path), pre=True, merge=False)
        r._begin({"t": 1.0, "label": "A", "role": "killer", "killer": "Hag"})
        assert r.active["pre"].endswith("Replay_1.mkv")              # this save's file, not the old one
        assert [k for k, _d in obs.requests].count("GetLastReplayBufferReplay") >= 4
        r._finish({})
        rec = obsrec.load_index(str(tmp_path))[0]
        assert rec.pre.endswith("(Vorlauf).mkv") and not os.path.exists(os.path.join(str(tmp_path), "Replay_1.mkv"))
    finally:
        obs.stop()


def test_the_timer_field_and_the_dot_keep_their_place_while_the_seconds_run():
    """1.5.4 (user: "die Zeit und der Punkt werden immer grösser und kleiner"): digits are proportional – the
    field is measured with the widest ("0"), so the block and the dot never move between 11:11 and 00:00."""
    from PIL import Image
    from dbdmapscout import overlay_win32, skin
    pic = Image.new("RGBA", (400, 300), (0, 0, 0, 0))
    a = overlay_win32.add_info(pic.copy(), "11:11", "", 480, rec=True)
    b = overlay_win32.add_info(pic.copy(), "00:00", "", 480, rec=True)
    assert a.size == b.size and _reds(a) == _reds(b)                       # same dot pixels
    body = Image.new("RGBA", (300, 200), (40, 40, 60, 255))
    for style in ("glass", "chips", "line"):
        ca = skin.map_card(body, "Coal Tower", "MacMillan", "11:11", "", "", "", None, (), 480, style, "#c9a227", rec=True)
        cb = skin.map_card(body, "Coal Tower", "MacMillan", "00:00", "", "", "", None, (), 480, style, "#c9a227", rec=True)
        assert ca.size == cb.size and _reds(ca) == _reds(cb), style
    # the chip of the timer alone has one width for every time of the same length
    assert skin.chip("11:11", 1.0, width_text="00:00").width == skin.chip("00:00", 1.0, width_text="00:00").width


def test_an_unreadable_globe_crop_is_kept_for_a_look(tmp_path):
    import numpy as np
    from types import SimpleNamespace
    from dbdmapscout import worker
    fake = SimpleNamespace(root_dir=str(tmp_path))
    img = np.zeros((20, 40, 3), dtype=np.uint8)
    for i in range(worker.GLOBE_KEPT + 3):
        worker.DetectionWorker._save_globe(fake, img, "cancel")
        time.sleep(0.001)
    files = os.listdir(os.path.join(str(tmp_path), "debug", "lobby"))
    assert files and len(files) <= worker.GLOBE_KEPT and all("-crossplay-cancel.png" in f for f in files)


def test_a_farming_mark_from_the_statistics_moves_the_recording(tmp_path):
    folder = str(tmp_path)
    for name in ("a.mkv", "a (Vorlauf).mkv"):
        with open(os.path.join(folder, name), "wb") as f:
            f.write(b"\0" * 10)
    obsrec.save_index(folder, [obsrec.Recording(t=1.0, file="a.mkv", pre="a (Vorlauf).mkv")])
    posted = []
    r = obsrec.Recorder(lambda kind, **d: posted.append((kind, d)))
    r.cfg = obsrec.Config(on=True, folder=folder, farming_sub=True)
    r._set_farming(1.0, True)
    rec = obsrec.load_index(folder)[0]
    assert rec.farming and rec.file == "Farming/a.mkv" and rec.pre == "Farming/a (Vorlauf).mkv"
    assert os.path.exists(os.path.join(folder, "Farming", "a.mkv")) and not os.path.exists(os.path.join(folder, "a.mkv"))
    assert posted[-1][0] == "changed" and posted[-1][1]["what"] == "farming"
    r._set_farming(1.0, False)                                  # back to the main folder
    rec = obsrec.load_index(folder)[0]
    assert not rec.farming and rec.file == "a.mkv" and os.path.exists(os.path.join(folder, "a (Vorlauf).mkv"))
    r.cfg.farming_sub = False                                   # switch off: only the flag changes
    r._set_farming(1.0, True)
    rec = obsrec.load_index(folder)[0]
    assert rec.farming and rec.file == "a.mkv"
    r._set_farming(99.0, True)                                  # unknown round: nothing happens
    assert len(obsrec.load_index(folder)) == 1


# ------------------------------------------------------------------ 1.6
def test_the_match_start_comes_after_the_loading_screen_of_a_found_lobby_only():
    from dbdmapscout.matchstart import MatchStart
    m = MatchStart()
    assert not m.update(0, True, True, False)                       # not armed: a loading screen does nothing
    m.arm(10)
    seq = [(11, False, False, True),    # lobby, READY pressed
           (12, True, True, False), (13, True, True, False),        # loading screen
           (14, False, True, False),                                 # black in between
           (15, False, False, False), (16, False, False, False)]     # the match
    fired = [t for t, bar, dark, btn in seq if m.update(t, bar, dark, btn)]
    assert fired == [16] and not m.armed and m.started_t == 16
    assert not m.update(30, True, True, False) and not m.update(31, False, False, False)   # back to the menus
    m.arm(40)                                                        # bright lobby looks without a loading screen
    assert not any(m.update(t, False, False, False) for t in range(41, 50))
    m.arm(60)                                                        # loading screen, then a lobby again (dodge)
    for t in (61, 62):
        m.update(t, True, True, False)
    m.update(63, False, False, True)
    assert not m.update(64, False, False, False) and not m.update(65, False, False, False)
    m.arm(0)
    assert not m.update(16 * 60, True, True, False) and not m.armed  # an old lobby arms nothing any more


def test_the_banner_names_the_recording_started_at_the_loading_screen(obs, tmp_path):
    folder = str(tmp_path)
    r, posted = _recorder(obs, folder, pre=True, early=True)
    r._begin_early({"t": 100.0, "role": "survivor", "farming": True})
    assert r.active["early"] and ("SaveReplayBuffer", {}) not in obs.requests     # no pre-roll, no lobby
    r._mark()
    r._begin({"t": 130.0, "map_id": "coal", "label": "Coal Tower", "role": "survivor", "killer": "",
              "farming": False})
    starts = [k for k, _d in obs.requests].count("StartRecord")
    assert starts == 1 and not r.active["early"] and r.active["t"] == 130.0 and r.active["farming"]
    assert len(r.active["marks"]) == 1
    r._finish({})
    rec = obsrec.load_index(folder)[0]
    assert rec.t == 130.0 and rec.label == "Coal Tower" and rec.farming and rec.file.startswith("Farming/")
    # off: the loading screen starts nothing
    r.cfg.early = False
    r._begin_early({"t": 200.0})
    assert r.active is None


def test_a_recording_from_the_loading_screen_without_a_banner_is_filed_as_it_is(obs, tmp_path, monkeypatch):
    folder = str(tmp_path)
    r, posted = _recorder(obs, folder, pre=False)
    r._begin_early({"t": 100.0, "role": "killer", "killer": "Nurse"})
    monkeypatch.setattr(obsrec, "EARLY_WAIT_S", -1)
    r._watchdog()
    assert r.active is None
    rec = obsrec.load_index(folder)[0]
    assert rec.label == "Unbekannte Map" and os.path.exists(os.path.join(folder, rec.file))
    # a banner long after the start is a new round: the old one is closed first
    r._begin_early({"t": 300.0})
    r.active["since"] -= 10 ** 4
    monkeypatch.setattr(obsrec, "EARLY_WAIT_S", 180)
    r._begin({"t": 400.0, "label": "B"})
    assert [k for k, _d in obs.requests].count("StopRecord") == 2 and r.active["t"] == 400.0


def test_the_sound_sources_are_created_once_and_switched(obs, tmp_path):
    r, posted = _recorder(obs, str(tmp_path), pre=False)
    c = r._client()
    try:
        r._audio(c)
        dbd, disc = obsrec.AUDIO_APPS["dbd"][0], obsrec.AUDIO_APPS["discord"][0]
        assert obs.inputs[dbd]["inputKind"] == obsrec.AUDIO_KIND and obs.inputs[dbd]["sceneName"] == "Szene"
        assert obs.inputs[dbd]["inputSettings"]["window"].endswith(":DeadByDaylight-Win64-Shipping.exe")
        assert obs.inputs[dbd]["inputSettings"]["priority"] == obsrec.AUDIO_PRIORITY_EXE
        assert not obs.inputs[dbd]["muted"] and not obs.inputs[disc]["muted"]
        assert obs.inputs["Desktop-Audio"]["muted"] and obs.inputs["Mic/Aux"]["muted"]
        r.cfg.audio_discord, r.cfg.audio_mic = False, True
        r._audio(c)
    finally:
        c.close()
    assert [k for k, _d in obs.requests].count("CreateInput") == 2           # not created again
    assert obs.inputs[disc]["muted"] and not obs.inputs["Mic/Aux"]["muted"]
    assert "CreateSceneItem" not in [k for k, _d in obs.requests]           # in the scene already: left alone
    obs.requests.clear()
    r._game = True
    r.cfg.audio = False
    r._audio_now()                                                           # switched off: OBS is left alone
    assert not obs.requests


def test_a_sound_source_missing_from_the_scene_on_air_is_put_back_into_it(obs, tmp_path):
    """1.8.18 (user: "Discord hört man gar nicht"): an application audio source is recorded only while it is in
    the scene on air – created once in another scene, its track stayed silent. A wanted one is added to the
    program scene, a hidden one shown again; an unwanted one is left where it is."""
    r, posted = _recorder(obs, str(tmp_path), pre=False)
    dbd, disc = obsrec.AUDIO_APPS["dbd"][0], obsrec.AUDIO_APPS["discord"][0]
    c = r._client()
    try:
        r._audio(c)
        obs.scenes = {"Szene": [{"sourceName": dbd, "sceneItemId": 7, "sceneItemEnabled": False}]}
        r._audio(c)                                         # Discord gone from the scene, DBD hidden
        names = [(i["sourceName"], i["sceneItemEnabled"]) for i in obs.scenes["Szene"]]
        assert (dbd, True) in names and (disc, True) in names and len(names) == 2
        obs.requests.clear()
        r._audio(c)
        assert not {"CreateSceneItem", "SetSceneItemEnabled"} & {k for k, _d in obs.requests}   # in place now
        obs.scenes = {"Szene": []}
        r.cfg.audio_discord = False
        r._audio(c)
        assert [i["sourceName"] for i in obs.scenes["Szene"]] == [dbd]                   # Discord not wanted
    finally:
        c.close()


def test_every_source_gets_its_own_track_and_the_profile_is_only_read(obs, tmp_path):
    """1.8.6: every source on track 1 (everything) and its own track – game + desktop 2, Discord 3, microphone 4;
    the profile is read, never written – a hint names what to tick when OBS is not in the advanced mode with
    tracks 1 to 4."""
    r, posted = _recorder(obs, str(tmp_path), pre=False)
    dbd, disc = obsrec.AUDIO_APPS["dbd"][0], obsrec.AUDIO_APPS["discord"][0]
    c = r._client()
    try:
        r._audio(c)
        on = lambda *ns: {str(n): n in ns for n in range(1, 5)}                   # noqa: E731
        assert obs.inputs[dbd]["tracks"] == obs.inputs["Desktop-Audio"]["tracks"] == on(1, 2)
        assert obs.inputs[disc]["tracks"] == on(1, 3) and obs.inputs["Mic/Aux"]["tracks"] == on(1, 4)
        kinds = [k for k, _d in obs.requests]
        assert "GetProfileParameter" in kinds and not [k for k in kinds if "Profile" in k and k.startswith("Set")]
        assert "Erweitert" not in r.status                                       # profile fine: no hint
        obs.profile[("Output", "Mode")] = "Simple"
        r._audio(c)
        assert "Ausgabemodus „Erweitert“" in r.status and "Audiospur 1 bis 4" in r.status
        assert _drain(posted)[-1] == ("status", {"text": r.status, "ok": False})
        obs.profile[("Output", "Mode")], obs.profile[("AdvOut", "RecTracks")] = "Advanced", "3"
        r.status = ""
        r._audio(c)
        assert "Audiospur 1 bis 4" in r.status                                   # advanced, but only tracks 1 + 2
        obs.requests.clear()
        r.cfg.tracks = False
        r._audio(c)
        kinds = [k for k, _d in obs.requests]
        assert "SetInputAudioTracks" not in kinds and "GetProfileParameter" not in kinds   # off: OBS left alone
    finally:
        c.close()
    assert obsrec.profile_hint("Advanced", "15") == "" == obsrec.profile_hint("advanced", "63")
    assert obsrec.profile_hint("Simple", "15") and obsrec.profile_hint("Advanced", "7") and obsrec.profile_hint("Advanced", "")
    assert obsrec.profile_hint("Advanced", "x") and obsrec.profile_hint("", "")


def test_the_audio_graph_mixes_the_wanted_sources_from_the_tracks():
    """1.8.6 (pure): one track as it is = plain map (stream copy stays possible), levels or several sources =
    volume/amix graph, nothing = no sound, a 1.8.5 two-track file = all or all-but-Discord."""
    g = obsrec.audio_graph
    assert g(4, None) == ("", "0:a?") and g(1, {"dbd": 1.0}) == ("", "0:a?")
    assert g(4, {"dbd": 1.0, "discord": 0, "mic": 0}) == ("", "0:a:1")
    assert g(4, {"dbd": 0, "discord": 0, "mic": 1.0}) == ("", "0:a:3")
    assert g(3, {"dbd": 0, "discord": 0, "mic": 1.0}) == ("", None)            # no microphone track in the file
    assert g(4, {"dbd": 0, "discord": 0, "mic": 0}) == ("", None)
    assert g(4, {"dbd": 0.5}) == ("[0:a:1]volume=0.500[aout]", "[aout]")
    flt, amap = g(4, {"dbd": 1.0, "discord": 0.8, "mic": 1.5})
    assert amap == "[aout]" and flt == ("[0:a:1]volume=1.000[a0];[0:a:2]volume=0.800[a1];[0:a:3]volume=1.500[a2];"
                                        "[a0][a1][a2]amix=inputs=3:normalize=0[aout]")
    assert obsrec.track_sources(4) == {"dbd": 1, "discord": 2, "mic": 3} and obsrec.track_sources(3) == {"dbd": 1, "discord": 2}
    assert obsrec.track_sources(2) == {"dbd": 1, "discord": obsrec.LEGACY} and obsrec.track_sources(1) == {}
    assert g(2, {"dbd": 1.0, "discord": 1.0}) == ("", "0:a:0") and g(2, {"dbd": 1.0, "discord": 0}) == ("", "0:a:1")
    assert g(2, {"dbd": 0, "discord": 0}) == ("", None) and g(2, {"dbd": 0.5, "discord": 0}) == ("[0:a:1]volume=0.500[aout]", "[aout]")


def test_the_track_hint_stays_in_the_status_when_dbd_starts(obs, tmp_path):
    """1.8.7: "OBS bereit" used to overwrite the hint about the missing audio tracks right away – now it keeps it."""
    r, posted = _recorder(obs, str(tmp_path), pre=False)
    obs.profile[("Output", "Mode")] = "Simple"
    r._game_changed(True)
    assert r.status.startswith("OBS bereit") and "Audiospur 1 bis 4" in r.status
    assert _drain(posted)[-1] == ("status", {"text": r.status, "ok": False})
    obs.profile[("Output", "Mode")] = "Advanced"
    r._game_changed(True)
    assert r.status == "OBS bereit – Runden werden aufgenommen"


def test_the_buffer_runs_for_instant_clips_without_a_pre_roll(obs, tmp_path):
    r, posted = _recorder(obs, str(tmp_path), pre=False, instant=True, buffer_auto=True)
    r._game_changed(True)
    assert obs.replay and r._buffer_ours


def _instant(tmp_path, monkeypatch, ffmpeg, streams=1, **kw):
    obs = FakeObs(record_dir=str(tmp_path), replay=True)
    obs.start()
    try:
        r, posted = _recorder(obs, str(tmp_path), pre=False, instant=True, clip_s=45, **kw)
        monkeypatch.setattr(obsrec, "ffmpeg_exe", lambda: ffmpeg)
        calls = []

        def run(args, timeout=0):
            calls.append(args)
            if args[-2] == "-i":                      # 1.8.5: the look at the file – this many audio tracks
                return 1, b"".join(b"  Stream #0:%d: Audio: aac, 48000 Hz, stereo\n" % (n + 1) for n in range(streams))
            with open(args[-1], "wb") as f:
                f.write(b"clip")
            return 0, b""
        monkeypatch.setattr(obsrec, "_run", run)
        r._instant_clip({"label": "Coal Tower", "role": "killer", "killer": "Nurse"})
        return posted, calls
    finally:
        obs.stop()


def test_f8_cuts_the_last_seconds_of_the_buffer_into_the_clips_folder(tmp_path, monkeypatch):
    posted, calls = _instant(tmp_path, monkeypatch, "ffmpeg")
    kind, d = _drain(posted)[-1]
    cdir = os.path.join(str(tmp_path), obsrec.CLIPS_DIR)
    clips = sorted(os.listdir(cdir))
    assert kind == "clip" and d["ok"] and d["seconds"] == 45 and clips == [d["file"], obsrec.CLIPS_INDEX]
    assert d["file"].endswith("Coal Tower – Nurse (Sofort-Clip).mp4")
    [c] = obsrec.load_clips(cdir)                                    # 1.8.13: in the clips list with its round
    assert (c.file, c.kind, c.role, c.killer, c.label, c.seconds) == (d["file"], "instant", "killer", "Nurse",
                                                                       "Coal Tower", 45.0)
    cut = calls[-1]
    assert cut[cut.index("-sseof") + 1] == "-45" and "copy" in cut
    assert cut[cut.index("-map"):][:2] == ["-map", "0"]                            # one track: as it is
    assert not [f for f in os.listdir(str(tmp_path)) if f.startswith("Replay_")]   # our replay is gone


def test_the_f8_clip_mixes_its_sources_from_the_buffer_files_tracks(tmp_path, monkeypatch):
    """1.8.6: with the four tracks in the buffer file the instant clip keeps the chosen sources – game + microphone
    mixed (sound re-encoded, picture copied), one source as a plain stream copy, none = no sound."""
    posted, calls = _instant(tmp_path, monkeypatch, "ffmpeg", streams=4)
    cut = calls[-1]
    assert _drain(posted)[-1][1]["ok"] and calls[0][-2:] == ["-i", cut[cut.index("-i") + 1]]   # looked at the file
    i = cut.index("-filter_complex")
    assert cut[i + 1] == "[0:a:1]volume=1.000[a0];[0:a:3]volume=1.000[a1];[a0][a1]amix=inputs=2:normalize=0[aout]"
    assert cut[i + 2:i + 10] == ["-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac"]
    posted, calls = _instant(tmp_path, monkeypatch, "ffmpeg", streams=4, clip_sources=("dbd",))
    cut = calls[-1]
    i = cut.index("-map")
    assert cut[i:i + 6] == ["-map", "0:v", "-map", "0:a:1", "-c", "copy"]
    posted, calls = _instant(tmp_path, monkeypatch, "ffmpeg", streams=4, clip_sources=())
    cut = calls[-1]
    assert cut[cut.index("-map"):][:3] == ["-map", "0:v", "-an"]
    posted, calls = _instant(tmp_path, monkeypatch, "ffmpeg", streams=2)         # 1.8.5 file: all but Discord
    cut = calls[-1]
    assert cut[cut.index("-map"):][:4] == ["-map", "0:v", "-map", "0:a:1"]


def test_without_ffmpeg_the_whole_buffer_becomes_the_clip(tmp_path, monkeypatch):
    posted, calls = _instant(tmp_path, monkeypatch, None)
    kind, d = _drain(posted)[-1]
    assert d["ok"] and d["file"].endswith("(Sofort-Clip).mkv") and not calls
    assert sorted(os.listdir(os.path.join(str(tmp_path), obsrec.CLIPS_DIR))) == [d["file"], obsrec.CLIPS_INDEX]


def test_no_instant_clip_without_the_replay_buffer(obs, tmp_path):
    r, posted = _recorder(obs, str(tmp_path), pre=False, instant=True)
    r._instant_clip({})
    kind, d = _drain(posted)[-1]
    assert kind == "clip" and not d["ok"] and "Wiederholungspuffer" in d["why"]


def test_the_clips_list_knows_the_programs_clips_and_their_rounds_and_filters_them(tmp_path):
    """1.8.13 (user: clips list, "filtern nach Killer/Survivor"): the clips index plus the program's older clips,
    told by their names (editor clip/still named after a recording, "(Sofort-Clip)"); someone else's file in the
    folder is not listed."""
    folder = str(tmp_path)
    cdir = obsrec.clips_dir(folder)
    os.makedirs(cdir)
    recs = [obsrec.Recording(t=100.0, file="2026-10-17 21-40 Coal Tower – Nurse.mkv", label="Coal Tower",
                             role="killer", killer="Nurse"),
            obsrec.Recording(t=200.0, file="Farming/2026-10-17 22-10 Badham – Survivor.mkv", label="Badham",
                             role="survivor", farming=True)]
    names = {"new.mp4": b"x" * 10,
             "2026-10-17 21-40 Coal Tower – Nurse – Clip 3m12s-3m40s.mp4": b"x" * 20,
             "2026-10-17 22-10 Badham – Survivor – Bild 1-02.5.png": b"x",
             "2026-10-18 20-05 Gas Heaven – Survivor (Sofort-Clip) (2).mp4": b"x",
             "2026-10-18 20-30 Ormond – Huntress (Sofort-Clip).mkv": b"x",
             "my own video.mp4": b"x", "notes.txt": b"x"}
    for n, data in names.items():
        with open(os.path.join(cdir, n), "wb") as f:
            f.write(data)
    obsrec.save_clips(cdir, [obsrec.Clip(file="new.mp4", t=500.0, kind="clip", source=100.0, label="Coal Tower",
                                         role="killer", killer="Nurse", seconds=12.5),
                             obsrec.Clip(file="gone.mp4", t=400.0)])               # its file was removed by hand
    clips = obsrec.list_clips(cdir, recs)
    by = {c.file: c for c in clips}
    assert set(by) == set(names) - {"my own video.mp4", "notes.txt"}
    assert (by["new.mp4"].size, by["new.mp4"].adopted, by["new.mp4"].seconds) == (10, False, 12.5)
    editor = by["2026-10-17 21-40 Coal Tower – Nurse – Clip 3m12s-3m40s.mp4"]
    assert (editor.kind, editor.source, editor.role, editor.killer, editor.adopted) == ("clip", 100.0, "killer",
                                                                                         "Nurse", True)
    still = by["2026-10-17 22-10 Badham – Survivor – Bild 1-02.5.png"]
    assert (still.kind, still.role, still.farming, still.label) == ("still", "survivor", True, "Badham")
    f8 = by["2026-10-18 20-05 Gas Heaven – Survivor (Sofort-Clip) (2).mp4"]
    assert (f8.kind, f8.label, f8.role, f8.killer) == ("instant", "Gas Heaven", "survivor", "")
    hunt = by["2026-10-18 20-30 Ormond – Huntress (Sofort-Clip).mkv"]
    assert (hunt.role, hunt.killer, hunt.label) == ("killer", "Huntress", "Ormond")
    assert [c.t for c in clips] == sorted((c.t for c in clips), reverse=True)    # newest first
    pick = lambda **kw: {c.file for c in obsrec.select_clips(clips, **kw)}          # noqa: E731
    assert pick(role="killer") == {"new.mp4", editor.file, hunt.file}
    assert pick(role="survivor") == {f8.file}                                     # farming rounds apart
    assert pick(role="farming") == {still.file}
    assert pick(killer="Nurse") == {"new.mp4", editor.file}
    assert pick(kind="still") == {still.file} and pick(kind="instant") == {f8.file, hunt.file}
    assert pick(since=600.0) == {c.file for c in clips if c.adopted}             # adopted: the file's time (now)


def test_only_the_programs_clips_are_deleted_and_saved_ones_join_the_list(tmp_path):
    folder = str(tmp_path)
    cdir = obsrec.clips_dir(folder)
    os.makedirs(cdir)
    for n in ("mine.mp4", "2026-10-18 20-05 Gas Heaven – Survivor (Sofort-Clip).mp4", "foreign.mp4"):
        with open(os.path.join(cdir, n), "wb") as f:
            f.write(b"x")
    r = obsrec.Recorder(lambda kind, **d: posted.append((kind, d)))
    posted = []
    r.folder = lambda: folder
    r._add_clip({"file": "mine.mp4", "kind": "clip", "role": "survivor", "label": "Badham", "seconds": 8.0,
                 "size": 999, "evil": 1})
    r._add_clip({"file": "not-there.mp4"})                                       # not in Clips/: not listed
    [c] = obsrec.load_clips(cdir)
    assert (c.file, c.role, c.label, c.seconds, c.size) == ("mine.mp4", "survivor", "Badham", 8.0, 1)
    assert ("changed", {"what": "clip", "file": "mine.mp4"}) in posted
    for n in ("foreign.mp4", "../" + "foreign.mp4", obsrec.CLIPS_INDEX):          # someone else's / outside: never
        r._delete_clip(n)
    assert os.path.exists(os.path.join(cdir, "foreign.mp4")) and os.path.exists(os.path.join(cdir, obsrec.CLIPS_INDEX))
    r._delete_clip("2026-10-18 20-05 Gas Heaven – Survivor (Sofort-Clip).mp4")    # an older one of ours
    r._delete_clip("mine.mp4")
    assert sorted(os.listdir(cdir)) == [obsrec.CLIPS_INDEX, "foreign.mp4"] and obsrec.load_clips(cdir) == []
    assert [d["file"] for k, d in posted if k == "changed" and d["what"] == "clip_delete"] == [
        "2026-10-18 20-05 Gas Heaven – Survivor (Sofort-Clip).mp4", "mine.mp4"]
