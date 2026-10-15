"""System values for the HUD line at the top of a black bar: CPU/GPU temperature, load, VRAM, RAM.

Sources (no driver of our own, nothing about the game process):
- CPU load / RAM: GetSystemTimes / GlobalMemoryStatusEx (plain Windows functions).
- NVIDIA GPU: nvml.dll, installed with the NVIDIA driver (System32). Only device values (temperature,
  load, memory, power) – never the process lists NVML also offers.
- CPU temperature: Windows has no driver-free way. Read from HWiNFO's shared memory when the user runs
  HWiNFO with "Shared Memory Support" on (HWiNFO publishes its sensors there for other programs).
  WinRing0/LibreHardwareMonitor would load a kernel driver: ruled out (anti-cheat, blocked driver).
"""
from __future__ import annotations

import ctypes
import os
import struct
import sys
import threading
import time
from dataclasses import dataclass

from .i18n import _

IS_WIN = sys.platform == "win32"
POLL_EVERY = 1.0             # seconds between two readings
HWINFO_MAP = "Global\\HWiNFO_SENS_SM2"
HWINFO_SIGS = (0x53695748, 0x48576953)     # "HWiS" (either byte order); "DEAD" = HWiNFO stopped sharing
HWINFO_HEADER = struct.Struct("<IIIqIIIIII")   # signature … number of readings (pack 1, 44 bytes)
HWINFO_READING = struct.Struct("<III128s128s16sdddd")
HWINFO_STALE = 10.0          # HWiNFO's last poll older than this: values are not current any more
HWINFO_MAX = 16 << 20        # sanity limit for the shared memory size
TEMP = 1                     # SENSOR_TYPE_TEMP
# HWiNFO labels of the CPU temperature, best first (Intel, AMD, fallbacks)
CPU_LABELS = ("cpu package", "cpu (tctl/tdie)", "cpu die (average)", "cpu (tctl)", "cpu tdie", "cpu (tdie)",
              "core max", "cpu")
GPU_LABELS = ("gpu temperature",)
HOT_LABELS = ("gpu hot spot temperature", "gpu hotspot temperature", "gpu hot spot")
MEM_LABELS = ("gpu memory junction temperature", "gpu memory temperature")
# thresholds (°C): green up to the first, amber up to the second, red above
CPU_WARM, CPU_HOT = 80, 90
GPU_WARM, GPU_HOT = 75, 85
SPOT_WARM, SPOT_HOT = 95, 105    # GPU hot spot and memory junction run 10–20 °C above the core
# NVML clock event reasons: only these mean "slowed down because of a problem". SW power cap (0x4) is the
# normal state of a boosting card under full load – showing it would be a permanent warning.
THROTTLE_THERMAL = 0x20 | 0x40   # SW / HW thermal slowdown
THROTTLE_HW = 0x08 | 0x80        # HW slowdown / power brake (power supply, external signal)


@dataclass
class Snapshot:
    cpu_load: float | None = None      # %
    cpu_temp: float | None = None      # °C (HWiNFO)
    gpu_name: str = ""
    gpu_load: float | None = None      # %
    gpu_temp: float | None = None      # °C
    gpu_power: float | None = None     # W
    gpu_hot: float | None = None       # °C hot spot (HWiNFO)
    gpu_mem: float | None = None       # °C memory junction (HWiNFO)
    throttle: str = ""                 # "" | "thermal" | "hw" (NVML clock event reasons)
    vram_used: float | None = None     # GB
    vram_total: float | None = None
    ram_used: float | None = None      # GB
    ram_total: float | None = None
    hwinfo: bool = False               # HWiNFO shared memory was readable and current
    t: float = 0.0


# ------------------------------------------------------------------ HWiNFO
def _cstr(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode("cp1252", "replace").strip()


def parse_hwinfo(buf: bytes, now: float | None = None) -> dict | None:
    """Temperatures from a copy of HWiNFO's shared memory: {"cpu_temp", "gpu_temp", "gpu_hot", "gpu_mem"}
    or None (not HWiNFO, sharing stopped, stale)."""
    if len(buf) < HWINFO_HEADER.size:
        return None
    sig, _ver, _rev, poll, _so, _ss, _sn, r_off, r_size, r_num = HWINFO_HEADER.unpack_from(buf)
    if sig not in HWINFO_SIGS or r_size < HWINFO_READING.size:
        return None
    now = time.time() if now is None else now
    if poll and abs(now - poll) > HWINFO_STALE:
        return None
    temps = {}
    for i in range(r_num):
        at = r_off + i * r_size
        if at + HWINFO_READING.size > len(buf):
            break
        kind, _si, _rid, label, _user, unit, value, *_ = HWINFO_READING.unpack_from(buf, at)
        if kind != TEMP:
            continue
        name = _cstr(label).lower()
        if "f" in _cstr(unit).lower():
            value = (value - 32) * 5 / 9                  # user switched HWiNFO to Fahrenheit
        temps.setdefault(name, value)                     # first sensor with that label wins
    return {"cpu_temp": _pick(temps, CPU_LABELS), "gpu_temp": _pick(temps, GPU_LABELS),
            "gpu_hot": _pick(temps, HOT_LABELS), "gpu_mem": _pick(temps, MEM_LABELS)}


def _pick(temps: dict, labels) -> float | None:
    for want in labels:
        if want in temps and 0 < temps[want] < 150:
            return float(temps[want])
    return None


_KERNEL = None


def _kernel32():
    """kernel32 with the file mapping functions declared (once, not every second)."""
    global _KERNEL
    if _KERNEL is None:
        from ctypes import wintypes
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.OpenFileMappingW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
        k.OpenFileMappingW.restype = wintypes.HANDLE
        k.MapViewOfFile.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                    ctypes.c_size_t]
        k.MapViewOfFile.restype = ctypes.c_void_p
        k.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        _KERNEL = k
    return _KERNEL


def read_hwinfo() -> bytes | None:
    """Copy of HWiNFO's shared memory, or None when HWiNFO does not share its sensors right now."""
    if not IS_WIN:
        return None
    k = _kernel32()
    h = k.OpenFileMappingW(0x0004, False, HWINFO_MAP)    # FILE_MAP_READ; fails when HWiNFO does not share
    if not h:
        return None
    try:
        view = k.MapViewOfFile(h, 0x0004, 0, 0, 0)
        if not view:
            return None
        try:
            head = ctypes.string_at(view, HWINFO_HEADER.size)
            f = HWINFO_HEADER.unpack(head)
            size = max(f[4] + f[5] * f[6], f[7] + f[8] * f[9])
            if f[0] not in HWINFO_SIGS or not HWINFO_HEADER.size <= size <= HWINFO_MAX:
                return None
            return ctypes.string_at(view, size)
        finally:
            k.UnmapViewOfFile(view)
    finally:
        k.CloseHandle(h)


# ------------------------------------------------------------------ NVIDIA
class Nvml:
    """NVIDIA GPU values through nvml.dll from the driver (System32 only: the program runs as admin,
    a DLL from the current folder must never be loaded)."""

    def __init__(self):
        self.lib = self.dev = self._reasons = None
        self.name = ""
        self.error = ""
        if not IS_WIN:
            self.error = "nur Windows"
            return
        paths = [os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "nvml.dll"),
                 os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                              "NVIDIA Corporation", "NVSMI", "nvml.dll")]
        path = next((p for p in paths if os.path.isfile(p)), None)
        if path is None:
            self.error = "nvml.dll nicht gefunden (keine NVIDIA-Karte?)"
            return
        try:
            lib = ctypes.CDLL(path)
            if lib.nvmlInit_v2() != 0:
                self.error = "nvmlInit fehlgeschlagen"
                return
            dev = ctypes.c_void_p()
            if lib.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(dev)) != 0:
                self.error = "keine NVIDIA-Karte"
                return
            buf = ctypes.create_string_buffer(96)
            if lib.nvmlDeviceGetName(dev, buf, 96) == 0:
                self.name = buf.value.decode("utf-8", "replace")
            self.lib, self.dev = lib, dev
            # new name first; older drivers only know …ThrottleReasons
            for fn in ("nvmlDeviceGetCurrentClocksEventReasons", "nvmlDeviceGetCurrentClocksThrottleReasons"):
                try:
                    self._reasons = getattr(lib, fn)
                    break
                except AttributeError:
                    continue
        except (OSError, AttributeError) as e:
            self.error = f"{type(e).__name__}: {e}"

    def read(self, snap: Snapshot) -> None:
        if self.lib is None:
            return
        lib, dev, u = self.lib, self.dev, ctypes.c_uint()
        snap.gpu_name = self.name
        if lib.nvmlDeviceGetTemperature(dev, 0, ctypes.byref(u)) == 0:         # NVML_TEMPERATURE_GPU
            snap.gpu_temp = float(u.value)

        class Util(ctypes.Structure):
            _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]

        class Mem(ctypes.Structure):
            _fields_ = [("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong), ("used", ctypes.c_ulonglong)]
        util, mem = Util(), Mem()
        if lib.nvmlDeviceGetUtilizationRates(dev, ctypes.byref(util)) == 0:
            snap.gpu_load = float(util.gpu)
        if lib.nvmlDeviceGetMemoryInfo(dev, ctypes.byref(mem)) == 0 and mem.total:
            snap.vram_used, snap.vram_total = mem.used / 2 ** 30, mem.total / 2 ** 30
        if lib.nvmlDeviceGetPowerUsage(dev, ctypes.byref(u)) == 0:              # milliwatts
            snap.gpu_power = u.value / 1000
        bits = ctypes.c_ulonglong()
        if self._reasons is not None and self._reasons(dev, ctypes.byref(bits)) == 0:
            snap.throttle = throttle_kind(bits.value)

    def close(self):
        if self.lib is not None:
            try:
                self.lib.nvmlShutdown()
            except Exception:
                pass
            self.lib = None


def throttle_kind(bits: int) -> str:
    """NVML clock event reasons -> "thermal" | "hw" | "" (no slowdown worth a warning)."""
    if bits & THROTTLE_THERMAL:
        return "thermal"
    if bits & THROTTLE_HW:
        return "hw"
    return ""


# ------------------------------------------------------------------ CPU, RAM
def cpu_load(prev, now_times):
    """CPU load in % between two (idle, kernel, user) readings of GetSystemTimes (kernel includes idle)."""
    if not prev:
        return None
    idle, kernel, user = (b - a for a, b in zip(prev, now_times))
    total = kernel + user
    return max(0.0, min(100.0, 100.0 * (1 - idle / total))) if total > 0 else None


def _system_times():
    from ctypes import wintypes
    i, k, u = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
    if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(i), ctypes.byref(k), ctypes.byref(u)):
        return None
    return tuple((f.dwHighDateTime << 32) | f.dwLowDateTime for f in (i, k, u))


def _memory():
    class MemStatus(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MemStatus()
    m.dwLength = ctypes.sizeof(m)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        return None
    return (m.ullTotalPhys - m.ullAvailPhys) / 2 ** 30, m.ullTotalPhys / 2 ** 30


# ------------------------------------------------------------------ display
WHITE = (255, 255, 255, 255)
DIM = (150, 156, 170, 255)       # labels and separators: grey, the values stand out
GOOD, WARM, HOT = (134, 239, 172, 255), (251, 191, 36, 255), (248, 113, 113, 255)


def temp_colour(t: float, warm: float, hot: float):
    return GOOD if t <= warm else WARM if t <= hot else HOT


def hud_rows(s: Snapshot) -> list:
    """Rows for the HUD: [[(text, colour), ...], ...]; only values that were read. The GPU's power is not in the
    overlay (1.65.2, user's wish) – it is still recorded for the statistics."""
    rows = []
    for name, temp, load, warm, hot in (
            ("CPU", s.cpu_temp, s.cpu_load, CPU_WARM, CPU_HOT),
            ("GPU", s.gpu_temp, s.gpu_load, GPU_WARM, GPU_HOT)):
        segs = []
        if temp is not None:
            segs.append((f"{temp:.0f}°C", temp_colour(temp, warm, hot)))
        if load is not None:
            segs.append((f"{load:.0f} %", WHITE))
        if segs:
            row = [(name + " ", DIM)]
            for i, seg in enumerate(segs):
                row += ([(" · ", DIM)] if i else []) + [seg]
            rows.append(row)
    spots = [(name, t) for name, t in (("HOTSPOT", s.gpu_hot), ("MEM", s.gpu_mem)) if t is not None]
    if spots:                                   # hot spot / memory junction: only with HWiNFO
        row = []
        for i, (name, t) in enumerate(spots):
            row += ([(" · ", DIM)] if i else []) + [(name + " ", DIM),
                                                   (f"{t:.0f}°C", temp_colour(t, SPOT_WARM, SPOT_HOT))]
        rows.append(row)
    if s.throttle:
        rows.append([(_("GPU DROSSELT (TEMP.)") if s.throttle == "thermal" else
                      _("GPU DROSSELT (HW)"), HOT)])
    for name, used, total in (("VRAM", s.vram_used, s.vram_total), ("RAM", s.ram_used, s.ram_total)):
        if used is not None and total:
            rows.append([(name + " ", DIM), (f"{used:.1f} / {total:.0f} GB", WHITE)])
    return rows


# ------------------------------------------------------------------ per round (tab Statistik)
SYS_KEYS = ("cpu_temp", "gpu_temp", "cpu_load", "gpu_load", "gpu_power", "vram_used", "ram_used", "gpu_hot",
            "gpu_mem")
MIN_SAMPLES = 10             # fewer readings in a round (HUD switched on late, HWiNFO started late): not stored


class SysRecorder:
    """Collects the readings of one round (one per snapshot) -> average and maximum per value."""

    def __init__(self):
        self.values = {k: [] for k in SYS_KEYS}
        self.throttled = 0                           # readings (≈ seconds) with a thermal / hardware slowdown
        self.readings = 0
        self._last_t = None

    def add(self, snap: Snapshot) -> None:
        if not snap.t or snap.t == self._last_t:
            return                                   # same reading as last time (the UI ticks faster)
        self._last_t = snap.t
        self.readings += 1
        self.throttled += bool(snap.throttle)
        for k in SYS_KEYS:
            v = getattr(snap, k)
            if v is not None:
                self.values[k].append(float(v))

    def summary(self) -> dict | None:
        """{"gpu_temp": average, "gpu_temp_max": maximum, …} for values with enough readings, else None."""
        out = {}
        for k, vs in self.values.items():
            if len(vs) >= MIN_SAMPLES:
                out[k] = round(sum(vs) / len(vs), 1)
                out[k + "_max"] = round(max(vs), 1)
        if out and self.readings >= MIN_SAMPLES:
            out["throttle_s"] = float(self.throttled * POLL_EVERY)
        return out or None


# ------------------------------------------------------------------ monitor thread
class SysMonitor:
    """Reads the values once a second in its own thread while ``active`` (set by the app: HUD on and DBD
    running). ``snapshot`` is replaced as a whole – safe to read from the UI thread."""

    def __init__(self):
        self.active = False
        self.snapshot = Snapshot()
        self.nvml_error = ""
        self.hwinfo_seen = False
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._thread is None and IS_WIN:
            self._thread = threading.Thread(target=self._run, daemon=True, name="sysinfo")
            self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        nvml = None
        prev = None
        while not self._stop.wait(POLL_EVERY):
            if not self.active:
                prev = None
                continue
            snap = Snapshot(t=time.time())
            try:
                times = _system_times()
                snap.cpu_load = cpu_load(prev, times) if times else None
                prev = times
                ram = _memory()
                if ram:
                    snap.ram_used, snap.ram_total = ram
                if nvml is None:
                    nvml = Nvml()
                    self.nvml_error = nvml.error
                nvml.read(snap)
                hw = parse_hwinfo(read_hwinfo() or b"")
                if hw:
                    snap.hwinfo = self.hwinfo_seen = True
                    snap.cpu_temp = hw["cpu_temp"]
                    snap.gpu_hot, snap.gpu_mem = hw["gpu_hot"], hw["gpu_mem"]
                    if snap.gpu_temp is None:
                        snap.gpu_temp = hw["gpu_temp"]           # AMD/Intel: GPU temperature from HWiNFO
            except Exception as e:                               # never kill the thread over one reading
                self.nvml_error = self.nvml_error or f"{type(e).__name__}: {e}"
            self.snapshot = snap
        if nvml is not None:
            nvml.close()

    def diag_line(self) -> str:
        s = self.snapshot
        return (f"Systemwerte: aktiv={self.active} GPU={s.gpu_name or '—'} nvml={self.nvml_error or 'ok'} "
                f"HWiNFO={'ja' if s.hwinfo else ('früher ja' if self.hwinfo_seen else 'nein')} "
                f"CPU={s.cpu_temp}°C/{s.cpu_load}% GPU={s.gpu_temp}°C/{s.gpu_load}% "
                f"Hotspot={s.gpu_hot} Mem={s.gpu_mem} drosselt={s.throttle or 'nein'}")
