"""Where the overlay's tick spends its time (1.8.31, user's pick: "Messung unter Windows in die Diagnose") – pure:
per tick the milliseconds of each step, kept for the last ``KEPT`` ticks (≈ 30 s at 4 ticks a second), shown as
one line of the diagnosis: average and maximum of the whole tick and of each step."""
from __future__ import annotations

import time
from collections import deque

KEPT = 120
STEPS = (("hud", "Systemwerte"), ("today", "Heute"), ("music", "Musik"), ("info", "Infos"),
         ("resolve", "Ausweichen"), ("guides", "Hilfslinien"))


class TickTimes:
    def __init__(self, kept: int = KEPT):
        self.ticks = deque(maxlen=kept)          # {step: ms, "total": ms}
        self._now = None

    def start(self):
        self._now = {}

    def add(self, step: str, ms: float):
        if self._now is not None:
            self._now[step] = self._now.get(step, 0.0) + ms

    def end(self, total_ms: float):
        if self._now is None:
            return
        tick = dict(self._now)
        tick["total"] = total_ms
        tick["map"] = max(0.0, total_ms - sum(v for k, v in self._now.items()))   # the rest: map and placing
        self.ticks.append(tick)
        self._now = None

    def timed(self, step: str, fn):
        """``fn`` wrapped so that its time counts for ``step`` of the running tick."""
        def run(*a, **kw):
            t0 = time.perf_counter()
            try:
                return fn(*a, **kw)
            finally:
                self.add(step, (time.perf_counter() - t0) * 1000)
        run.__wrapped__ = fn
        return run

    def line(self) -> str:
        if not self.ticks:
            return "Overlay-Takt: noch keine Messung"
        n = len(self.ticks)

        def stat(key):
            vals = [t.get(key, 0.0) for t in self.ticks]
            return sum(vals) / n, max(vals)
        avg, top = stat("total")
        slow = sum(1 for t in self.ticks if t["total"] >= 30)
        parts = [f"{label} {a:.1f}/{m:.0f}" for key, label in (("map", "Karte"),) + STEPS
                 for a, m in (stat(key),) if m >= 0.05]
        return (f"Overlay-Takt ({n} Takte, Ø/max ms): gesamt {avg:.1f}/{top:.0f}, ≥ 30 ms: {slow}× · "
                + " · ".join(parts))
