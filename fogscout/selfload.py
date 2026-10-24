"""1.11.3 (user: "wie viel Leistung braucht das Programm alleine?"): what Fog Scout itself costs – the CPU share
and the memory of **this** process only.

Reads nothing but the own process: ``time.process_time()`` (CPU seconds of all own threads – worker, OCR, overlay,
window) and the working set via ``GetProcessMemoryInfo(GetCurrentProcess())``, the pseudo handle to itself – no
``OpenProcess``, no other process, no PID (CLAUDE.md). A GPU share per process would need NVML's process list,
which is ruled out; the GPU line stays system-wide. On Linux the working set comes from ``/proc/self/statm``.

The percent is the task manager's: CPU seconds per wall second, divided by the number of cores.
"""
from __future__ import annotations

import collections
import ctypes
import os
import sys
import time
from dataclasses import dataclass

IS_WIN = sys.platform == "win32"
KEPT = 600                        # samples for average and peak: ten minutes at one per second
EVERY_S = 1.0                     # how often the app samples (App._selfload_tick)


@dataclass
class Load:
    cpu: float | None = None      # percent of the whole machine (all cores); None until the second sample
    rss: int = 0                  # working set in bytes
    t: float = 0.0


class SelfLoad:
    """Pure apart from ``tick`` – ``sample(now, cpu_seconds, rss)`` takes the readings, the tests feed their own."""

    def __init__(self, cores: int | None = None):
        self.cores = max(1, int(cores or os.cpu_count() or 1))
        self._last = None             # (now, cpu seconds) of the previous sample
        self.current = Load()
        self.samples = collections.deque(maxlen=KEPT)
        self.peak = 0.0
        self.peak_rss = 0

    def sample(self, now: float, cpu_seconds: float, rss: int) -> Load:
        cpu = None
        if self._last is not None:
            dt = now - self._last[0]
            if dt > 0:
                cpu = max(0.0, min(100.0, 100.0 * (cpu_seconds - self._last[1]) / dt / self.cores))
        self._last = (now, cpu_seconds)
        self.current = Load(cpu, int(rss), now)
        if cpu is not None:
            self.samples.append(cpu)
            self.peak = max(self.peak, cpu)
        self.peak_rss = max(self.peak_rss, int(rss))
        return self.current

    def tick(self, now: float | None = None) -> Load:
        """The real readings (the app calls this once a second)."""
        return self.sample(time.time() if now is None else now, cpu_seconds(), rss_bytes())

    @property
    def average(self) -> float | None:
        return sum(self.samples) / len(self.samples) if self.samples else None

    def text(self) -> str:
        """For the overview's system card: "1,8 % CPU · 310 MB"."""
        c = self.current
        if c.cpu is None:
            return ""
        return f"{c.cpu:.1f} % CPU · {c.rss / 2 ** 20:.0f} MB"

    def diag_line(self) -> str:
        c = self.current
        if c.cpu is None:
            return "Eigene Last: noch keine Messung"
        return (f"Eigene Last (nur dieser Prozess, {self.cores} Kerne): CPU jetzt {c.cpu:.1f} %, Ø {self.average:.1f} %, "
                f"Spitze {self.peak:.1f} % (letzte {len(self.samples)} s) · RAM {c.rss / 2 ** 20:.0f} MB, "
                f"Spitze {self.peak_rss / 2 ** 20:.0f} MB")


# ------------------------------------------------------------------ the readers (own process only)
def cpu_seconds() -> float:
    """CPU time of this process, all threads, user + system."""
    return time.process_time()


class _MemoryCounters(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_uint32), ("PageFaultCount", ctypes.c_uint32),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


def rss_bytes() -> int:
    """Working set of this process in bytes (0 when it cannot be read)."""
    if IS_WIN:
        try:
            pmc = _MemoryCounters()
            pmc.cb = ctypes.sizeof(pmc)
            me = ctypes.windll.kernel32.GetCurrentProcess()          # the pseudo handle (-1): never another process
            if ctypes.windll.psapi.GetProcessMemoryInfo(me, ctypes.byref(pmc), pmc.cb):
                return int(pmc.WorkingSetSize)
        except (AttributeError, OSError):
            pass
        return 0
    try:
        with open("/proc/self/statm", "r", encoding="ascii") as fh:
            return int(fh.read().split()[1]) * (os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096)
    except (OSError, ValueError, IndexError):
        return 0
