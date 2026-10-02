"""Round timer: starts when a map appears, stops when it is gone."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dbdmapscout.roundtimer import RoundTimer  # noqa: E402


def test_idle():
    r = RoundTimer()
    assert not r.running and r.elapsed(100) == 0.0
    assert not r.stop(5.0)


def test_start_stop_and_restart_from_zero():
    r = RoundTimer()
    r.start(10.0)
    assert r.running and r.elapsed(70.0) == 60.0
    assert r.stop(100.0)
    assert not r.running and r.elapsed(9999.0) == 90.0      # frozen
    assert not r.stop(200.0)                                 # second stop changes nothing
    r.start(300.0)                                           # map shown again -> from zero
    assert r.running and r.elapsed(305.0) == 5.0


def test_stop_never_before_start():
    r = RoundTimer()
    r.start(50.0)
    r.stop(40.0)                                             # end hint older than the start
    assert r.elapsed(0) == 0.0


def test_detection_resets_except_same_banner():
    r = RoundTimer()
    assert r.detected(0.0)                                   # nothing running -> start
    assert not r.detected(5.0)                               # same banner read again
    assert r.elapsed(10.0) == 10.0
    assert r.detected(600.0)                                 # next match, end was missed -> new round
    assert r.elapsed(610.0) == 10.0
    r.stop(700.0)
    assert r.detected(710.0)                                 # stopped -> always a new round
    assert r.running


def test_clear_forgets_the_round():
    r = RoundTimer()
    r.start(100.0)
    r.clear()
    assert not r.running and r.start_t is None and r.elapsed(200.0) == 0.0
