"""1.11.3: what the program itself costs (selfload.py) – pure arithmetic with fed readings, the real readers once."""
import time

import pytest

from fogscout import selfload


def test_the_cpu_share_is_per_core_and_clamped_and_the_peaks_are_kept():
    s = selfload.SelfLoad(cores=4)
    first = s.sample(100.0, 10.0, 200 << 20)
    assert first.cpu is None and first.rss == 200 << 20 and s.average is None      # no span yet
    assert s.text() == "" and s.diag_line() == "Eigene Last: noch keine Messung"
    second = s.sample(101.0, 10.2, 210 << 20)                                      # 0.2 s CPU in 1 s on 4 cores
    assert second.cpu == pytest.approx(5.0) and s.text() == "5.0 % CPU · 210 MB"
    s.sample(102.0, 10.2, 205 << 20)                                               # idle second
    assert s.current.cpu == 0.0 and s.average == pytest.approx(2.5) and s.peak == pytest.approx(5.0)
    assert s.peak_rss == 210 << 20
    s.sample(103.0, 20.2, 205 << 20)                                               # more than the cores: clamped
    assert s.current.cpu == 100.0
    s.sample(103.0, 20.2, 205 << 20)                                               # no time passed: no reading
    assert s.current.cpu is None
    line = s.diag_line()
    assert line == "Eigene Last: noch keine Messung"
    s.sample(104.0, 20.4, 300 << 20)
    assert "4 Kerne" in s.diag_line() and "Spitze 100.0 %" in s.diag_line() and "Spitze 300 MB" in s.diag_line()
    assert len(s.samples) == 4


def test_the_readers_see_this_process_only():
    """process_time grows with our own work; the working set is a real size (Windows: GetProcessMemoryInfo on the
    pseudo handle, Linux: /proc/self/statm) – nothing of this touches another process."""
    before = selfload.cpu_seconds()
    end = time.perf_counter() + 0.05
    x = 0
    while time.perf_counter() < end:
        x += 1
    assert selfload.cpu_seconds() > before and x
    rss = selfload.rss_bytes()
    assert rss > 10 << 20                                                          # a Python process with numpy
    s = selfload.SelfLoad()
    s.tick(1000.0)
    s.tick(1001.0)
    assert s.current.cpu is not None and s.current.rss == rss or s.current.rss > 0
    assert s.cores >= 1
