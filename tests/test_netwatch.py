"""Connected game server: packet headers, flow table, region from reverse DNS, server choice."""
import json
import os
import socket
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fogscout import connwatch, netwatch  # noqa: E402
from fogscout.connwatch import pick_server, region_from_ptr  # noqa: E402

LOCAL = "192.168.1.20"
SERVER = "3.120.45.67"


def packet(src, dst, sport, dport, proto=17, frag=0, ihl=5, payload=b"game data"):
    hdr = struct.pack("!BBHHHBBH4s4s", 0x40 | ihl, 0, 20 + 8 + len(payload), 1, frag, 64, proto, 0,
                      socket.inet_aton(src), socket.inet_aton(dst))
    hdr += b"\0" * ((ihl - 5) * 4)
    return hdr + struct.pack("!HHHH", sport, dport, 8 + len(payload), 0) + payload


def test_parse_udp_headers_only():
    assert netwatch.parse(packet(LOCAL, SERVER, 50000, 7777)) == (LOCAL, SERVER, 50000, 7777)
    assert netwatch.parse(packet(SERVER, LOCAL, 7777, 50000, ihl=6)) == (SERVER, LOCAL, 7777, 50000)


def test_parse_rejects_other_packets():
    assert netwatch.parse(packet(LOCAL, SERVER, 1, 2, proto=6)) is None          # TCP
    assert netwatch.parse(packet(LOCAL, SERVER, 1, 2, frag=0x0010)) is None      # later fragment
    assert netwatch.parse(b"\x60" + b"\0" * 40) is None                           # IPv6
    assert netwatch.parse(b"\x45\0\0") is None                                    # truncated


def feed(table, t0, seconds, pps, remote=SERVER, port=7777, both=True):
    for i in range(int(seconds * pps)):
        t = t0 + i / pps
        table.add(t, LOCAL, (LOCAL, remote, 50000, port))
        if both:
            table.add(t, LOCAL, (remote, LOCAL, port, 50000))


def test_flow_table_rates_and_filters():
    tab = netwatch.FlowTable(window=5.0)
    feed(tab, 100.0, 5, 30)                                   # game server, 30 packets/s each way
    feed(tab, 100.0, 5, 50, remote="142.250.1.1", port=443)   # QUIC video: ignored port
    feed(tab, 100.0, 5, 50, remote="10.0.0.5", port=9999)     # LAN: not public
    tab.add(101.0, LOCAL, ("8.8.8.8", "1.1.1.1", 53, 53))     # not ours
    snap = tab.snapshot(105.0)
    assert [f["ip"] for f in snap] == [SERVER]
    assert snap[0]["port"] == 7777 and snap[0]["pps"] == 60.0
    assert snap[0]["sent"] == 150 and snap[0]["recv"] == 150
    assert snap[0]["lports"] == [50000]                       # 1.11.6: the local port it talked to


def test_flow_table_forgets_old_traffic():
    tab = netwatch.FlowTable(window=5.0)
    feed(tab, 100.0, 5, 30)
    assert tab.snapshot(104.9)
    assert tab.snapshot(120.0) == [] and tab.flows == {}


def test_region_from_ptr():
    assert region_from_ptr("ec2-3-120-45-67.eu-central-1.compute.amazonaws.com") == "eu-central-1"
    assert region_from_ptr("EC2-18-130-1-2.EU-WEST-2.compute.amazonaws.com.") == "eu-west-2"
    assert region_from_ptr("ec2-54-1-2-3.compute-1.amazonaws.com") == "us-east-1"
    assert region_from_ptr("ec2-1-2-3-4.ap-southeast-2.compute.amazonaws.com") == "ap-southeast-2"
    assert region_from_ptr("server.discord.gg") is None
    assert region_from_ptr("") is None


def test_pick_server():
    flows = [{"ip": "162.159.1.1", "port": 50001, "pps": 50.0},       # voice chat: not AWS
             {"ip": SERVER, "port": 7777, "pps": 40.0},
             {"ip": "52.1.1.1", "port": 7000, "pps": 3.0}]            # too little traffic
    known = {SERVER: "eu-central-1", "52.1.1.1": "us-east-1"}
    got = pick_server(flows, known.get)
    assert got["ip"] == SERVER and got["region"] == "eu-central-1"
    assert pick_server(flows[2:], known.get) is None
    assert pick_server([], known.get) is None


def _watch(tmp_path, monkeypatch, exit_code=None):
    control, result = tmp_path / "c.json", tmp_path / "r.json"
    control.write_text('{"stop": false}')
    result.write_text("")
    w = connwatch.ConnectionWatch()
    w.proc, w.control, w.result = object(), str(control), str(result)
    w._started = w._touched = 1000.0
    monkeypatch.setattr(connwatch.regions, "exit_code", lambda p: exit_code)
    monkeypatch.setattr(connwatch.regions, "close_handle", lambda p: None)
    monkeypatch.setattr(connwatch.regions, "resolve", lambda name: [])     # no real DNS for the ping
    return w, control, result


def test_poll_reads_result_and_loses_server(tmp_path, monkeypatch):
    w, control, result = _watch(tmp_path, monkeypatch)
    w._rdns = {SERVER: ("eu-central-1", time.time())}

    def write(t, flows):
        result.write_text(json.dumps({"ok": True, "t": t, "flows": flows}))

    write(1000.0, [])
    w.poll(1001.0)
    assert w.server is None and w.text() == "Warte auf Match …"
    write(1002.0, [{"ip": SERVER, "port": 7777, "pps": 40.0}])
    w.poll(1002.5)
    assert w.server["region"] == "eu-central-1"
    assert w.text() == f"Frankfurt ({SERVER})"
    write(1005.0, [])
    w.poll(1005.5)
    assert w.server is not None                               # short gap: keep
    write(1012.0, [])
    w.poll(1012.5)
    assert w.server is None                                   # gone -> match over
    w.poll(1030.0)                                            # result not updated any more
    assert w.text() == "keine Daten vom Mitschnitt"


def test_poll_reports_helper_error(tmp_path, monkeypatch):
    w, control, result = _watch(tmp_path, monkeypatch, exit_code=1)
    result.write_text(json.dumps({"ok": False, "t": 1.0, "error": "Keine Berechtigung"}))
    w.poll(1001.0)
    assert not w.running and w.text() == "Fehler: Keine Berechtigung"
    assert not control.exists() and not result.exists()


def test_in_process_when_already_admin(monkeypatch):
    """Program started as administrator: no UAC, no second process; stopping ends the capture thread."""
    def fake_watch(control, result):
        while netwatch.keep_running(control, time.time()):
            netwatch.write(result, {"ok": True, "t": time.time(),
                                    "flows": [{"ip": SERVER, "port": 7777, "pps": 40.0}]})
            time.sleep(0.02)

    monkeypatch.setattr(connwatch, "IS_WIN", True)
    monkeypatch.setattr(connwatch, "is_admin", lambda: True)
    monkeypatch.setattr(connwatch.regions, "start_elevated", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    monkeypatch.setattr(netwatch, "watch", fake_watch)
    monkeypatch.setattr(connwatch.regions, "resolve", lambda name: [])     # no real DNS for the ping
    w = connwatch.ConnectionWatch()
    w._rdns = {SERVER: ("eu-central-1", time.time())}
    assert w.start() is None and w.running
    thread = w.proc
    time.sleep(0.1)
    w.poll()
    assert w.server and w.server["ip"] == SERVER
    w.stop()
    thread.join(timeout=3)
    assert not thread.is_alive() and not w.running


def test_region_lookup_cached_and_retried(monkeypatch):
    calls = []

    def fake_ptr(ip):
        calls.append(ip)
        if len(calls) == 1:
            raise OSError("DNS timeout")
        return ("ec2-3-120-45-67.eu-central-1.compute.amazonaws.com", [], [ip])

    monkeypatch.setattr(connwatch.socket, "gethostbyaddr", fake_ptr)
    monkeypatch.setattr(connwatch.threading, "Thread", _InlineThread)
    w = connwatch.ConnectionWatch()
    assert w._region(SERVER) is None and calls == [SERVER]            # lookup failed
    assert w._region(SERVER) is None and len(calls) == 1              # not again right away
    ip_code, t = w._rdns[SERVER]
    w._rdns[SERVER] = (ip_code, t - connwatch.RDNS_RETRY - 1)
    assert w._region(SERVER) is None and len(calls) == 2              # retried later (answer arrives async)
    assert w._region(SERVER) == "eu-central-1" and len(calls) == 2    # now cached


class _InlineThread:
    """Runs the target at start() – makes the reverse DNS lookup synchronous in tests."""
    def __init__(self, target=None, args=(), **kw):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


def test_helper_stops_without_program(tmp_path):
    control = tmp_path / "c.json"
    assert not netwatch.keep_running(str(control), 0.0)              # control file gone
    control.write_text('{"stop": false}')
    now = os.stat(control).st_mtime
    assert netwatch.keep_running(str(control), now + 1)
    assert not netwatch.keep_running(str(control), now + netwatch.STALE + 1)   # program no longer refreshes it
    control.write_text('{"stop": true}')
    assert not netwatch.keep_running(str(control), os.stat(control).st_mtime)


def test_helper_never_creates_result_file(tmp_path):
    res = tmp_path / "r.json"
    netwatch.write(str(res), {"ok": True})
    assert not res.exists()                                          # removed by the program -> stays gone
    res.write_text("x" * 100)
    netwatch.write(str(res), {"ok": True})
    assert json.loads(res.read_text()) == {"ok": True}               # overwritten in place, no leftovers


class _FakeSocketModule:
    """Stands in for the Windows socket module: records ioctl calls, never receives anything."""
    AF_INET, SOCK_RAW, SOCK_DGRAM, IPPROTO_IP, IP_HDRINCL = 2, 3, 2, 0, 2
    SIO_RCVALL, RCVALL_OFF = 0x98000001, 0
    timeout = TimeoutError
    inet_ntoa = staticmethod(socket.inet_ntoa)

    def __init__(self, fail_mode=None):
        self.ioctls, self.fail_mode = [], fail_mode

    def socket(self, *a):
        mod = self

        class S:
            def __enter__(self): return self
            def __exit__(self, *e): return False
            def connect(self, addr): pass
            def getsockname(self): return (LOCAL, 50000)
            def bind(self, addr): pass
            def setsockopt(self, *a): pass
            def settimeout(self, t): pass
            def close(self): pass

            def ioctl(self, code, mode):
                mod.ioctls.append(mode)
                if mode == mod.fail_mode:
                    raise OSError(10022, "invalid argument")

            def recv(self, n): raise TimeoutError
        return S()


def test_capture_uses_own_traffic_mode_only(tmp_path, monkeypatch):
    fake = _FakeSocketModule()
    monkeypatch.setattr(netwatch, "socket", fake)
    result = tmp_path / "r.json"
    result.write_text("")
    assert netwatch.main(["netwatch.py", str(tmp_path / "missing-control.json"), str(result)]) == 0
    assert fake.ioctls == [netwatch.RCVALL_IPLEVEL, fake.RCVALL_OFF] == [3, 0]   # never 1 (promiscuous)


def test_capture_refuses_instead_of_promiscuous_fallback(tmp_path, monkeypatch):
    fake = _FakeSocketModule(fail_mode=3)
    monkeypatch.setattr(netwatch, "socket", fake)
    control, result = tmp_path / "c.json", tmp_path / "r.json"
    control.write_text('{"stop": false}')
    result.write_text("")
    assert netwatch.main(["netwatch.py", str(control), str(result)]) == 1
    assert 1 not in fake.ioctls                                    # no silent RCVALL_ON
    err = json.loads(result.read_text())
    assert err["ok"] is False and "RCVALL_IPLEVEL" in err["error"]


def test_ping_to_region_median_and_reset(monkeypatch):
    """Ping goes to the region's GameLift service name (never the game server), median of the last values,
    starts over when the region changes and is gone without a server."""
    resolved, pinged = [], []
    answers = iter([30.0, 90.0, 32.0, 31.0, 150.0])
    monkeypatch.setattr(connwatch.regions, "resolve", lambda name: resolved.append(name) or ["35.1.1.1"])
    monkeypatch.setattr(connwatch.regions, "icmp_ping", lambda ip: pinged.append(ip) or next(answers))
    monkeypatch.setattr(connwatch.regions, "udp_ping", lambda ip: None)
    monkeypatch.setattr(connwatch.threading, "Thread", _InlineThread)
    w = connwatch.ConnectionWatch()
    w.server = {"ip": SERVER, "port": 7777, "region": "eu-central-1"}
    t = 1000.0
    for expected in (30.0, 60.0, 32.0):                                # medians of 30 | 30,90 | 30,90,32
        w._update_ping(t)
        assert w.ping_ms == expected
        t += connwatch.PING_EVERY
    w._update_ping(t - 1)                                              # too soon: no extra packet
    assert len(pinged) == 3
    assert resolved == ["gamelift.eu-central-1.amazonaws.com"]         # resolved once, then cached
    assert SERVER not in pinged                                         # the game server gets nothing
    w.server = {"ip": "3.2.2.2", "port": 7777, "region": "eu-west-1"}  # other region: start over
    w._update_ping(t)
    assert w.ping_ms == 31.0 and resolved[-1] == "gamelift.eu-west-1.amazonaws.com"
    w.server = None
    w._update_ping(t + 100)
    assert w.ping_ms is None


def test_ping_shown_in_text(monkeypatch):
    w = connwatch.ConnectionWatch()
    w.proc = object()
    w.server = {"ip": SERVER, "port": 7777, "region": "eu-central-1"}
    assert w.text() == f"Frankfurt ({SERVER})"
    w.ping_ms = 23.4
    assert w.text() == f"Frankfurt ({SERVER}) · 23 ms"


def test_idle_pause_while_dbd_not_running():
    p = connwatch.IdlePause()
    assert p.update(0.0, True, True, True) is None                    # DBD running: nothing
    assert p.update(10.0, False, True, True) is None                  # just closed
    assert p.update(10.0 + p.AFTER - 0.1, False, True, True) is None
    assert p.update(10.0 + p.AFTER, False, True, True) == "pause"
    assert p.paused
    assert p.update(100.0, False, False, True) is None                # stays paused
    assert p.update(200.0, True, False, True) == "resume"             # DBD back: start again
    assert not p.paused


def test_idle_pause_only_when_restart_is_free():
    p = connwatch.IdlePause()
    assert p.update(0.0, False, True, False) is None
    assert p.update(1000.0, False, True, False) is None               # helper via UAC: keep it running


def test_public_check_is_cached():
    netwatch._PUBLIC.clear()
    assert netwatch.is_public("3.120.19.250") and not netwatch.is_public("192.168.1.20")
    assert netwatch._PUBLIC == {"3.120.19.250": True, "192.168.1.20": False}
    assert not netwatch.is_public("not an ip")


def test_diagnostics_keep_peaks_and_mask_addresses(tmp_path, monkeypatch):
    """After the match the diagnostics still show the busiest partners, without any full address."""
    w, control, result = _watch(tmp_path, monkeypatch)
    w._rdns = {SERVER: ("", time.time()), "52.1.2.3": ("", time.time())}
    w._names = {SERVER: "server-3-120-45-67.fra50.r.cloudfront.net"}

    def write(t, flows):
        result.write_text(json.dumps({"ok": True, "t": t, "local": "192.168.1.20", "flows": flows}))

    write(1000.0, [{"ip": SERVER, "port": 7777, "pps": 45.0, "sent": 100, "recv": 125},
                   {"ip": "52.1.2.3", "port": 3478, "pps": 2.0, "sent": 5, "recv": 5}])
    w.poll(1000.5)
    assert w.server is None                                   # no EC2 name: not chosen
    write(1100.0, [])
    w.poll(1100.5)
    text = "\n".join(w.diag_lines(1101.0))
    assert "schnittstelle=192.168.1.20" in text
    assert "3.120.x.x Port 7777 · 45.0/s" in text and "kein AWS-EC2-Name" in text
    assert "server-….fra50.r.cloudfront.net" in text and "ausstehend" in text
    assert text.index("3.120.x.x") < text.index("52.1.x.x")   # busiest first
    assert SERVER not in text and "52.1.2.3" not in text and "45-67" not in text
    w._note_peaks([], 1100.5 + connwatch.PEAK_KEEP + 1)
    assert not w.peaks                                         # forgotten after 30 min


def test_server_in_aws_global_range_without_region(tmp_path, monkeypatch):
    """GameLift servers in 54.115.0.0/16 have no reverse DNS name: shown as server with unknown region, no ping.
    No guess from the hosts file: in a friend's party their matchmaking picks the region."""
    monkeypatch.setattr(connwatch.socket, "gethostbyaddr", lambda ip: (_ for _ in ()).throw(AssertionError))
    w, control, result = _watch(tmp_path, monkeypatch)
    pinged = []
    monkeypatch.setattr(connwatch.ConnectionWatch, "_ping", lambda self, region: pinged.append(region))
    result.write_text(json.dumps({"ok": True, "t": 1000.0, "flows": [{"ip": "54.115.7.8", "port": 7786, "pps": 180.0}]}))
    w.poll(1000.5)
    assert w.server["region"] == connwatch.UNKNOWN and w.ping_ms is None and not pinged
    assert w.text() == "Global (54.115.7.8)"
    w.poll(1001.0)
    assert w.server["region"] == connwatch.UNKNOWN and not pinged
    assert connwatch.aws_global("54.115.0.1") and not connwatch.aws_global("3.120.45.67")


def test_ping_once_icmp_first_then_udp_beacon(monkeypatch):
    """Like Make Your Choice: ICMP to the GameLift service name (timed by Windows); UDP beacon only without answer."""
    names = {"gamelift.eu-central-1.amazonaws.com": ["52.1.1.1"], "gamelift-ping.eu-central-1.api.aws": ["35.1.1.1"]}
    monkeypatch.setattr(connwatch.regions, "resolve", lambda name: names.get(name, []))
    monkeypatch.setattr(connwatch.regions, "icmp_ping", lambda ip: 21.0)
    monkeypatch.setattr(connwatch.regions, "udp_ping", lambda ip: 25.0)
    assert connwatch.regions.ping_once("eu-central-1") == (21.0, "ICMP", "52.1.1.1")
    monkeypatch.setattr(connwatch.regions, "icmp_ping", lambda ip: None)
    assert connwatch.regions.ping_once("eu-central-1") == (25.0, "UDP", "35.1.1.1")
    monkeypatch.setattr(connwatch.regions, "udp_ping", lambda ip: None)
    assert connwatch.regions.ping_once("eu-central-1") == (None, "", "")
    monkeypatch.setattr(connwatch.regions, "time", type("T", (), {"sleep": staticmethod(lambda s: None)}))
    assert connwatch.regions.measure("eu-central-1")["ms"] is None
    monkeypatch.setattr(connwatch.regions, "resolve", lambda name: [])
    assert connwatch.regions.measure("eu-central-1")["error"] == "Name nicht auflösbar"


# ------------------------------------------------------------------ 1.11.6: DBD's own UDP ports
def _udp_table(rows, family=socket.AF_INET):
    """A MIB_UDP(6)TABLE_OWNER_PID as Windows fills it: count, then rows with the port in network byte order."""
    out = struct.pack("<I", len(rows))
    for port, pid in rows:
        if family == socket.AF_INET:
            out += struct.pack("<I", 0) + struct.pack(">H", port) + b"\0\0" + struct.pack("<I", pid)
        else:
            out += b"\0" * 16 + struct.pack("<I", 0) + struct.pack(">H", port) + b"\0\0" + struct.pack("<I", pid)
    return out


def test_the_udp_table_gives_the_ports_of_one_process():
    """1.11.6 (user: "Spielserver klingt gut"): GetExtendedUdpTable's rows, IPv4 and IPv6 – only DBD's ports, the
    port read in network byte order, a count larger than the buffer cannot read past it."""
    buf = _udp_table([(7777, 4242), (50000, 4242), (53, 1000), (61000, 7)])
    assert connwatch.parse_udp_table(buf, socket.AF_INET, 4242) == {7777, 50000}
    assert connwatch.parse_udp_table(buf, socket.AF_INET, 999) == set()
    six = _udp_table([(52000, 4242), (443, 1)], connwatch.AF_INET6)
    assert connwatch.parse_udp_table(six, connwatch.AF_INET6, 4242) == {52000}
    lying = struct.pack("<I", 1000) + buf[4:]                  # claims 1000 rows, holds 4
    assert connwatch.parse_udp_table(lying, socket.AF_INET, 4242) == {7777, 50000}
    assert connwatch.parse_udp_table(b"", socket.AF_INET, 1) == set()


def test_with_dbds_ports_only_its_partners_count():
    """Another AWS partner busier than the game server (other game, launcher …) is not chosen once DBD's ports are
    known; no DBD port among the partners = not in a match; unknown ports or an old result file: as before."""
    other = {"ip": "52.1.1.1", "port": 7000, "lports": [61000], "pps": 90.0}
    game = {"ip": SERVER, "port": 7777, "lports": [50000], "pps": 40.0}
    known = {SERVER: "eu-central-1", "52.1.1.1": "us-east-1"}.get
    assert pick_server([other, game], known)["ip"] == "52.1.1.1"                 # unknown ports: the busiest
    assert pick_server([other, game], known, {50000, 50001})["ip"] == SERVER
    assert pick_server([other], known, {50000}) is None
    assert pick_server([other, game], known, set()) is None                      # DBD has no UDP socket
    old = [{k: v for k, v in other.items() if k != "lports"}]
    assert pick_server(old, known, {50000})["ip"] == "52.1.1.1"                  # older helper: judged as before


def test_poll_asks_windows_for_dbds_ports_and_says_where_they_came_from(tmp_path, monkeypatch):
    """The ports of the DBD window's process are looked up every PORTS_EVERY s – one window → process lookup per
    window; without a window, a process or the table the old guess runs, and the diagnosis says which."""
    w, control, result = _watch(tmp_path, monkeypatch)
    w._rdns = {SERVER: ("eu-central-1", time.time()), "52.1.1.1": ("us-east-1", time.time())}
    pids, asked = [], []
    monkeypatch.setattr(connwatch, "window_pid", lambda hwnd: pids.append(hwnd) or 4242)
    monkeypatch.setattr(connwatch, "udp_ports", lambda pid: asked.append(pid) or {50000})
    flows = [{"ip": "52.1.1.1", "port": 7000, "lports": [61000], "pps": 90.0, "sent": 1, "recv": 1},
             {"ip": SERVER, "port": 7777, "lports": [50000], "pps": 40.0, "sent": 1, "recv": 1}]
    result.write_text(json.dumps({"ok": True, "t": 1000.0, "flows": flows}))
    w.poll(1000.5, game_hwnd=77)
    assert w.server["ip"] == SERVER and w.ports == {50000} and pids == [77] and asked == [4242]
    w.poll(1001.0, game_hwnd=77)
    assert asked == [4242]                                     # within PORTS_EVERY: not asked again
    w.poll(1000.5 + connwatch.PORTS_EVERY, game_hwnd=77)
    assert asked == [4242, 4242] and pids == [77]              # same window: its process is known
    text = "\n".join(w.diag_lines(1003.0))
    assert "DBD-Ports: 1 aus der Verbindungstabelle von Windows" in text
    assert "52.1.x.x Port 7000 · 90.0/s" in text and "nicht DBD" in text and "3.120.x.x Port 7777 · 40.0/s" in text
    assert "4242" not in text
    w.poll(1004.0, game_hwnd=None)                             # no DBD window: the busiest partner again
    assert w.ports is None and w.server["ip"] == "52.1.1.1" and "kein DBD-Fenster" in w.ports_why
    monkeypatch.setattr(connwatch, "udp_ports", lambda pid: None)
    w.poll(1010.0, game_hwnd=78)
    assert w.ports is None and "nicht lesbar" in w.ports_why and pids == [77, 78]


def test_off_windows_no_port_lookup_is_tried():
    assert connwatch.window_pid(123) is None or sys.platform == "win32"
    assert connwatch.udp_ports(123) is None or sys.platform == "win32"
    assert connwatch.window_pid(0) is None and connwatch.udp_ports(0) is None


def test_the_process_exception_stays_narrow():
    """1.11.6 loosened "no PID" for exactly one path: the DBD window's process id and Windows' UDP table, in connwatch
    only. Nothing anywhere opens a process (OpenProcess, ReadProcessMemory, module/handle queries)."""
    import re
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fogscout")
    calls = re.compile(r"\b(OpenProcess|ReadProcessMemory|EnumProcessModules|CreateToolhelp32Snapshot|"
                       r"GetWindowThreadProcessId|GetExtendedUdpTable)\b")
    found = {}
    for name in sorted(os.listdir(root)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(root, name), encoding="utf-8") as fh:
            for line in fh:
                code = line.split("#", 1)[0]
                if "windll" in code or "ctypes" in code or "." in code:
                    for m in calls.finditer(code):
                        if re.search(r"\.\s*" + m.group(1) + r"\b", code):          # an attribute = a real call
                            found.setdefault(m.group(1), set()).add(name)
    assert found == {"GetWindowThreadProcessId": {"connwatch.py"}, "GetExtendedUdpTable": {"connwatch.py"}}


# ------------------------------------------------------------------ 1.11.9: receive gaps
def test_the_flow_table_times_the_gaps_between_received_packets():
    """1.11.9 (user: "1,2 gern" – connection quality per round): a pause of ≥ STALL_S between two packets *from* a
    partner is one gap, listed with its end for WINDOW seconds; packets we send do not close a gap; quiet = time since
    the last packet from it. Only arrival times – no contents."""
    tab = netwatch.FlowTable(window=5.0)
    for i in range(10):                                        # 30 packets/s from the server
        tab.add(100.0 + i / 30, LOCAL, (SERVER, LOCAL, 7777, 50000))
    tab.add(100.5, LOCAL, (LOCAL, SERVER, 50000, 7777))        # sent: no effect on the gap
    tab.add(101.1, LOCAL, (SERVER, LOCAL, 7777, 50000))        # 0.8 s silent
    tab.add(101.2, LOCAL, (SERVER, LOCAL, 7777, 50000))        # 0.1 s: normal
    snap = tab.snapshot(101.5)[0]
    assert len(snap["gaps"]) == 1 and snap["gaps"][0][0] == 101.1 and abs(snap["gaps"][0][1] - 0.8) < 0.01
    assert abs(snap["quiet"] - 0.3) < 1e-6
    tab.add(104.0, LOCAL, (SERVER, LOCAL, 7777, 50000))
    assert [g[0] for g in tab.snapshot(106.5)[0]["gaps"]] == [104.0]           # the first one left the window


def test_the_servers_gaps_count_once_and_a_stall_shows_live(tmp_path, monkeypatch):
    """The helper lists a gap for 5 s, the program counts it once (take_gaps for the round); a gap ≥ LAG_LIVE_S or a
    silent server makes lagging() true for LAG_HOLD_S; other partners' gaps do not count."""
    w, control, result = _watch(tmp_path, monkeypatch)
    w._rdns = {SERVER: ("eu-central-1", time.time())}
    other = {"ip": "52.9.9.9", "port": 9000, "pps": 5.0, "gaps": [[1000.0, 2.0]], "quiet": 0.0}

    def write(t, gaps, quiet=0.0):
        result.write_text(json.dumps({"ok": True, "t": t, "flows": [
            {"ip": SERVER, "port": 7777, "pps": 40.0, "gaps": gaps, "quiet": quiet}, other]}))

    write(1000.0, [])
    w.poll(1000.2)
    assert w.take_gaps() == [] and not w.lagging(1000.2)
    write(1001.0, [[1000.9, 0.3]])
    w.poll(1001.2)
    write(1002.0, [[1000.9, 0.3], [1001.8, 0.9]])
    w.poll(1002.2)
    assert w.take_gaps() == [0.3, 0.9] and w.take_gaps() == []                 # each once
    assert w.lagging(1002.2) and w.lagging(1001.8 + connwatch.LAG_HOLD_S)
    assert not w.lagging(1001.8 + connwatch.LAG_HOLD_S + 0.1)
    write(1010.0, [], quiet=0.7)                                               # silent right now
    w.poll(1010.2)
    assert w.lagging(1010.2) and abs(w.quiet - 0.9) < 1e-6
    text = "\n".join(w.diag_lines(1011.0))
    assert "Aussetzer des Servers" in text and ": 2, längster 0.90 s" in text
