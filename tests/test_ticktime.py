"""1.8.31: the overlay tick's steps timed for the diagnosis (ticktime.TickTimes)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dbdmapscout.ticktime import TickTimes  # noqa: E402


def test_steps_add_up_and_the_map_is_the_rest():
    tt = TickTimes(kept=3)
    for total, hud, music in ((20.0, 5.0, 8.0), (40.0, 6.0, 20.0), (10.0, 1.0, 2.0), (12.0, 2.0, 3.0)):
        tt.start()
        tt.add("hud", hud)
        tt.add("music", music / 2)
        tt.add("music", music / 2)                     # one step called twice in a tick: summed
        tt.end(total)
    assert len(tt.ticks) == 3                          # the oldest went
    assert tt.ticks[0] == {"hud": 6.0, "music": 20.0, "total": 40.0, "map": 14.0}
    line = tt.line()
    assert "gesamt 20.7/40" in line and "≥ 30 ms: 1×" in line and "Systemwerte 3.0/6" in line
    assert "Karte 9.3/14" in line and "Musik 8.3/20" in line and "Infos" not in line   # steps that never ran: left out
    tt.add("hud", 99)                                  # outside a tick: not counted
    assert len(tt.ticks) == 3 and TickTimes().line() == "Overlay-Takt: noch keine Messung"


def test_a_wrapped_step_counts_its_time_and_keeps_its_result():
    tt = TickTimes()
    tt.start()
    f = tt.timed("info", lambda x: x * 2)
    assert f(21) == 42 and f.__wrapped__(1) == 2
    tt.end(5.0)
    assert set(tt.ticks[0]) == {"info", "total", "map"} and tt.ticks[0]["info"] >= 0
