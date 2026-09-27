"""Dead by Daylight server regions (AWS GameLift): latency and region choice.

Idea as in "Make Your Choice" (independent implementation): DBD measures the
latency to every GameLift region and matchmakes only in regions that answer.
Server names of unwanted regions are pointed to 0.0.0.0 in the Windows hosts
file, so DBD cannot reach them and uses the chosen ones. The game itself is
not touched; the hosts file is a Windows system file (administrator rights,
Windows asks via UAC).

Latency is measured the way GameLift intends it: a small UDP packet to the
region's ping beacon (``gamelift-ping.<region>.api.aws``, port 7770), which
echoes it back. The name is resolved with the DNS server directly (ignoring
the hosts file), so blocked regions can be measured too. If UDP gets no
answer, ICMP (normal ping) is used.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import socket
import statistics
import struct
import sys
import tempfile
import time

from . import hostsedit

IS_WIN = sys.platform == "win32"

# code, display name, group
REGIONS = [
    ("eu-central-1", "Frankfurt", "Europa"),
    ("eu-west-1", "Irland", "Europa"),
    ("eu-west-2", "London", "Europa"),
    ("us-east-1", "USA Ost (N. Virginia)", "Amerika"),
    ("us-east-2", "USA Ost (Ohio)", "Amerika"),
    ("us-west-1", "USA West (N. Kalifornien)", "Amerika"),
    ("us-west-2", "USA West (Oregon)", "Amerika"),
    ("ca-central-1", "Kanada (Zentral)", "Amerika"),
    ("sa-east-1", "Südamerika (São Paulo)", "Amerika"),
    ("ap-northeast-1", "Tokio", "Asien"),
    ("ap-northeast-2", "Seoul", "Asien"),
    ("ap-south-1", "Mumbai", "Asien"),
    ("ap-southeast-1", "Singapur", "Asien"),
    ("ap-east-1", "Hongkong", "Asien"),
    ("ap-southeast-2", "Sydney", "Ozeanien"),
]
GROUPS = ["Europa", "Amerika", "Asien", "Ozeanien"]
NAMES = {c: n for c, n, _ in REGIONS}
BEACON_PORT = 7770

# the server-name list lives in hostsedit.py (the elevated helper must not trust anything else)
UNUSED = hostsedit.UNUSED                 # GameLift regions DBD does not use; blocked with every selection
ALL_CODES = hostsedit.ALL_CODES
MANAGED = hostsedit.MANAGED
hosts_for = hostsedit.hosts_for
assert [c for c, _, _ in REGIONS] == hostsedit.VISIBLE_CODES


# ------------------------------------------------------------------ state of the hosts file
def current_state(text: str | None = None) -> dict:
    """{code: "frei" | "gesperrt" | "gesperrt (fremd)" | "umgeleitet (fremd)"} + summary keys."""
    if text is None:
        try:
            text = hostsedit.read_text()
        except OSError as e:
            return {"error": str(e), "regions": {}, "own": False, "myc": False, "foreign": 0}
    a = hostsedit.analyse(text, MANAGED)
    regions = {}
    for code in ALL_CODES:
        hs = set(hosts_for(code))
        if hs & a["redirected_foreign"]:
            regions[code] = "umgeleitet (fremd)"
        elif hs & a["blocked_foreign"]:
            regions[code] = "gesperrt (fremd)"
        elif hs & a["blocked_own"]:
            regions[code] = "gesperrt"
        else:
            regions[code] = "frei"
    return {"regions": regions, "own": a["own"], "myc": a["myc"], "foreign": a["foreign_lines"]}


def block_list(selected) -> list[str]:
    """Server names to block so that only ``selected`` regions stay reachable."""
    sel = set(selected)
    return [h for c in ALL_CODES if c not in sel for h in hosts_for(c)]


# ------------------------------------------------------------------ latency
if IS_WIN:
    import ctypes
    from ctypes import wintypes

    class _DNS_RECORD(ctypes.Structure):
        pass

    _DNS_RECORD._fields_ = [("pNext", ctypes.POINTER(_DNS_RECORD)), ("pName", ctypes.c_void_p),
                            ("wType", wintypes.WORD), ("wDataLength", wintypes.WORD), ("Flags", wintypes.DWORD),
                            ("dwTtl", wintypes.DWORD), ("dwReserved", wintypes.DWORD), ("IpAddress", wintypes.DWORD)]

    class _ICMP_ECHO_REPLY(ctypes.Structure):
        _fields_ = [("Address", wintypes.DWORD), ("Status", wintypes.ULONG), ("RoundTripTime", wintypes.ULONG),
                    ("DataSize", wintypes.USHORT), ("Reserved", wintypes.USHORT), ("Data", ctypes.c_void_p),
                    ("Ttl", ctypes.c_ubyte), ("Tos", ctypes.c_ubyte), ("OptFlags", ctypes.c_ubyte),
                    ("OptionsSize", ctypes.c_ubyte), ("OptionsData", ctypes.c_void_p)]


def resolve(name: str) -> list[str]:
    """IPv4 addresses from the DNS server, ignoring the hosts file (Windows)."""
    if IS_WIN:
        try:
            dns = ctypes.WinDLL("dnsapi")
            dns.DnsQuery_W.argtypes = [wintypes.LPCWSTR, wintypes.WORD, wintypes.DWORD, ctypes.c_void_p,
                                       ctypes.POINTER(ctypes.POINTER(_DNS_RECORD)), ctypes.c_void_p]
            dns.DnsQuery_W.restype = wintypes.LONG
            dns.DnsFree.argtypes = [ctypes.c_void_p, ctypes.c_int]
            res = ctypes.POINTER(_DNS_RECORD)()
            # DNS_QUERY_BYPASS_CACHE | DNS_QUERY_NO_HOSTS_FILE
            if dns.DnsQuery_W(name, 1, 0x8 | 0x40, None, ctypes.byref(res), None) == 0:
                ips, p = [], res
                try:
                    while p:
                        rec = p.contents
                        if rec.wType == 1:
                            ips.append(socket.inet_ntoa(struct.pack("<I", rec.IpAddress)))
                        p = rec.pNext
                finally:
                    dns.DnsFree(res, 1)
                ips = [ip for ip in dict.fromkeys(ips) if ip not in hostsedit.BLOCK_IPS]   # e.g. Pi-hole
                if ips:
                    return ips
        except Exception:
            pass
    try:
        ips = [ai[4][0] for ai in socket.getaddrinfo(name, None, socket.AF_INET, socket.SOCK_DGRAM)]
    except OSError:
        return []
    return [ip for ip in dict.fromkeys(ips) if ip not in hostsedit.BLOCK_IPS]


def udp_ping(ip: str, timeout: float = 1.0) -> float | None:
    """Round trip to a GameLift UDP ping beacon in ms (None = no answer)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(timeout)
            t0 = time.perf_counter()
            s.sendto(b"DbD Map Scout ping", (ip, BEACON_PORT))
            s.recvfrom(512)
            return (time.perf_counter() - t0) * 1000
    except OSError:
        return None


def icmp_ping(ip: str, timeout_ms: int = 1000) -> float | None:
    """Normal ping (ICMP echo) without administrator rights (Windows IcmpSendEcho)."""
    if not IS_WIN:
        return None
    try:
        ip_hlp = ctypes.WinDLL("iphlpapi")
        ip_hlp.IcmpCreateFile.restype = wintypes.HANDLE
        ip_hlp.IcmpSendEcho.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.WORD,
                                        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD]
        ip_hlp.IcmpSendEcho.restype = wintypes.DWORD
        ip_hlp.IcmpCloseHandle.argtypes = [wintypes.HANDLE]
        h = ip_hlp.IcmpCreateFile()
        if not h or h == wintypes.HANDLE(-1).value:
            return None
        try:
            data = ctypes.create_string_buffer(b"DbDMapScout", 11)
            buf = ctypes.create_string_buffer(ctypes.sizeof(_ICMP_ECHO_REPLY) + 64)
            addr = struct.unpack("<I", socket.inet_aton(ip))[0]
            if ip_hlp.IcmpSendEcho(h, addr, data, 11, None, buf, ctypes.sizeof(buf), timeout_ms) == 0:
                return None
            rep = _ICMP_ECHO_REPLY.from_buffer(buf)
            return float(rep.RoundTripTime) if rep.Status == 0 else None
        finally:
            ip_hlp.IcmpCloseHandle(h)
    except Exception:
        return None


def measure(code: str, samples: int = 3) -> dict:
    """Latency of one region: {"ms": float|None, "how": "UDP"|"ICMP"|"", "ip": str}."""
    ping_host = hosts_for(code)[1]
    ips = resolve(ping_host)
    if not ips:
        return {"ms": None, "how": "", "ip": "", "error": "Name nicht auflösbar"}
    ip = ips[0]
    times = []
    for i in range(samples):
        if i:
            time.sleep(0.35)                      # GameLift allows 3 pings/s per sender
        t = udp_ping(ip)
        if t is not None:
            times.append(t)
    if times:
        return {"ms": statistics.median(times), "how": "UDP", "ip": ip}
    t = icmp_ping(ip)
    if t is None:
        svc = resolve(hosts_for(code)[0])
        t = icmp_ping(svc[0]) if svc else None
    return {"ms": t, "how": "ICMP" if t is not None else "", "ip": ip}


def measure_all(codes=None, workers: int = 8) -> dict:
    codes = list(codes or [c for c, _, _ in REGIONS])
    out = {}
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(measure, c): c for c in codes}
        for f in cf.as_completed(futs):
            try:
                out[futs[f]] = f.result()
            except Exception as e:  # pragma: no cover
                out[futs[f]] = {"ms": None, "how": "", "ip": "", "error": str(e)}
    return out


# ------------------------------------------------------------------ applying (UAC)
def run_job(job: dict, hwnd: int | None = None, timeout: float = 90.0) -> dict:
    """Write the hosts file through the elevated helper (Windows asks for administrator rights).

    Both files are created here, by the normal user: the elevated helper only
    reads the job and overwrites the result file, so the program can read the
    result back (files created by an elevated process belong to Administrators).
    """
    fd, job_f = tempfile.mkstemp(prefix="dbdmapscout-job-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(job, fh)
    fd, res_f = tempfile.mkstemp(prefix="dbdmapscout-result-", suffix=".json")
    os.close(fd)
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hostsedit.py")
    try:
        exit_code = None
        if not IS_WIN:                              # tests: no elevation, DBDMS_HOSTS_FILE points to a copy
            exit_code = hostsedit.main(["hostsedit.py", job_f, res_f])
        else:
            res, exit_code = _run_elevated(script, job_f, res_f, timeout, hwnd)
            if res is not None:
                return res
        try:
            with open(res_f, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            if exit_code == 0:                      # result not readable, but the helper said "ok"
                return {"ok": True, "changed": True}
            return {"ok": False, "error": f"Das Hilfsprogramm hat kein Ergebnis geliefert (Code {exit_code})."}
    finally:
        for f in (job_f, res_f):
            try:
                os.remove(f)
            except OSError:
                pass


def _python_exe() -> str:
    exe = sys.executable
    d, name = os.path.split(exe)
    if name.lower() == "python.exe" and os.path.exists(os.path.join(d, "pythonw.exe")):
        return os.path.join(d, "pythonw.exe")      # no console window
    return exe


def _run_elevated(script, job_f, res_f, timeout, hwnd=None):
    """Start the helper with "runas" (UAC prompt) and wait.
    Returns (error dict or None, exit code)."""
    proc, err = start_elevated(script, [job_f, res_f], hwnd)
    if err:
        return err, None
    k32 = _kernel32()
    code = None
    try:
        if k32.WaitForSingleObject(proc, int(timeout * 1000)) != 0:
            return {"ok": False, "error": "Zeitüberschreitung beim Schreiben der hosts-Datei."}, None
        code = exit_code(proc)
    finally:
        k32.CloseHandle(proc)
    return None, code


def _kernel32():
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k32.WaitForSingleObject.restype = wintypes.DWORD
    k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k32.GetExitCodeProcess.restype = wintypes.BOOL
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    return k32


def exit_code(proc) -> int | None:
    """Exit code of a helper started with start_elevated (None = still running or unknown)."""
    k32 = _kernel32()
    if k32.WaitForSingleObject(proc, 0) != 0:
        return None
    c = wintypes.DWORD()
    return int(c.value) if k32.GetExitCodeProcess(proc, ctypes.byref(c)) else None


def close_handle(proc) -> None:
    if proc:
        _kernel32().CloseHandle(proc)


def start_elevated(script, args, hwnd=None):
    """Start one of our helper scripts with "runas" (UAC prompt), without waiting.
    Returns (process handle, None) or (None, error dict); the caller closes the handle."""
    class SHELLEXECUTEINFOW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("fMask", ctypes.c_ulong), ("hwnd", wintypes.HWND),
                    ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR),
                    ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE),
                    ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY),
                    ("dwHotKey", wintypes.DWORD), ("hIconOrMonitor", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]

    shell = ctypes.WinDLL("shell32", use_last_error=True)
    shell.ShellExecuteExW.argtypes = [ctypes.POINTER(SHELLEXECUTEINFOW)]
    shell.ShellExecuteExW.restype = wintypes.BOOL
    sei = SHELLEXECUTEINFOW()
    sei.cbSize = ctypes.sizeof(SHELLEXECUTEINFOW)
    sei.fMask = 0x40 | 0x100                        # SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC
    sei.hwnd = hwnd or None                         # UAC prompt belongs to our window (comes to the front)
    sei.lpVerb = "runas"
    sei.lpFile = _python_exe()
    # -I -S: isolated, no site-packages / .pth files – the helpers need the standard library only
    sei.lpParameters = "-I -S " + " ".join(f'"{a}"' for a in [script, *args])
    sei.nShow = 0                                   # SW_HIDE
    if not shell.ShellExecuteExW(ctypes.byref(sei)):
        err = ctypes.get_last_error()
        if err == 1223:                             # ERROR_CANCELLED: user said no to UAC
            return None, {"ok": False, "cancelled": True, "error": "Abgebrochen (keine Administratorrechte erteilt)."}
        return None, {"ok": False, "error": f"Start mit Administratorrechten fehlgeschlagen (Fehler {err})."}
    if not sei.hProcess:
        return None, {"ok": False, "error": "Hilfsprogramm nicht gestartet."}
    return sei.hProcess, None


def myc_firewall_active() -> bool:
    """Firewall rules left by Make Your Choice's "Enforced" mode (they block regions on their own).
    Reading firewall rules needs no administrator rights."""
    if not IS_WIN:
        return False
    try:
        import subprocess
        r = subprocess.run(["netsh", "advfirewall", "firewall", "show", "rule", "name=MakeYourChoice RegionLock 1"],
                           capture_output=True, timeout=8, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        out = r.stdout.decode("mbcs", errors="replace")
        return r.returncode == 0 and "MakeYourChoice RegionLock" in out
    except Exception:
        return False
