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
                    f.write(b"\0" * 1000)
            elif kind == "StopRecord":
                out, self.recording = {"outputPath": self.recording}, None
            elif kind == "GetReplayBufferStatus":
                out = {"outputActive": self.replay}
            elif kind == "SaveReplayBuffer":
                self.last_replay = os.path.join(self.record_dir, "Replay.mkv")
                with open(self.last_replay, "wb") as f:
                    f.write(b"\0" * 300)
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
    r._start({"t": t, "map_id": "coal", "label": "Coal Tower", "role": "killer", "killer": "Nurse"})
    assert obs.recording and ("SetRecordDirectory", {"recordDirectory": folder}) in obs.requests
    assert posted.get(timeout=1)[0] == "status" and posted.get(timeout=1)[0] == "started"
    r._stop({})
    names = sorted(os.listdir(folder))
    assert names == ["2026-10-17 21-40 Coal Tower – Nurse.mkv", obsrec.INDEX]
    recs = obsrec.load_index(folder)
    assert len(recs) == 1 and recs[0].t == t and recs[0].killer == "Nurse" and recs[0].size == 1000
    kinds = [posted.get(timeout=1)[0] for _i in range(2)]
    assert kinds == ["status", "saved"]
    # survivor round, no killer: the role names the file; a second file of the same minute gets "(2)"
    r._start({"t": t, "map_id": "coal", "label": "Coal Tower", "role": "survivor"})
    r._stop({})
    assert "2026-10-17 21-40 Coal Tower – Survivor.mkv" in os.listdir(folder)


def test_the_replay_buffer_becomes_the_pre_roll(tmp_path):
    obs = FakeObs(record_dir=str(tmp_path), replay=True)
    obs.start()
    try:
        r, posted = _recorder(obs, str(tmp_path), pre=True)
        r._start({"t": 1.0, "label": "Gas Heaven", "role": "killer", "killer": "Hag"})
        assert ("SaveReplayBuffer", {}) in obs.requests
        r._stop({})
        rec = obsrec.load_index(str(tmp_path))[0]
        assert rec.pre.endswith("(Vorlauf).mkv") and os.path.exists(os.path.join(str(tmp_path), rec.pre))
        assert rec.size == 1300                           # round + pre-roll
    finally:
        obs.stop()


def test_a_new_banner_while_recording_closes_the_old_round_first(obs, tmp_path):
    r, posted = _recorder(obs, str(tmp_path), pre=False)
    r._start({"t": 1.0, "label": "A"})
    r._start({"t": 2.0, "label": "B"})
    assert [k for k, _d in obs.requests].count("StopRecord") == 1
    r._stop({})
    assert len(obsrec.load_index(str(tmp_path))) == 2


def test_nothing_is_recorded_without_the_drive_or_when_obs_records_by_hand(obs, tmp_path):
    r, posted = _recorder(obs, os.path.join(str(tmp_path), "missing"), pre=False)
    r._start({"t": 1.0, "label": "A"})
    assert r.active is None and "nicht angeschlossen" in posted.get(timeout=1)[1]["text"]
    assert not obs.requests                                  # OBS was not even asked
    r.cfg.folder = str(tmp_path)
    obs.recording = "/somewhere/manual.mkv"
    r._start({"t": 1.0, "label": "A"})
    assert r.active is None and "schon auf" in posted.get(timeout=1)[1]["text"]
    r.cfg.on = False
    obs.recording = None
    r._start({"t": 1.0, "label": "A"})
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
