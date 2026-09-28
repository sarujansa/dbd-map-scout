"""Round history (dbdmapscout/history.py)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dbdmapscout import history as h  # noqa: E402


def rnd(m, s, t=0.0, region=""):
    return h.Round(t=t, seconds=s, map_id=m.lower(), map=m, region=region, source="auto")


def test_short_rounds_do_not_count():
    assert not h.should_record(12) and not h.should_record(59.9) and h.should_record(60)


def test_file_round_trip(tmp_path):
    p = str(tmp_path / h.FILE)
    assert h.load(p) == []                                           # no file yet
    h.append(p, rnd("Coal Tower", 600, 1.0, "eu-central-1"))
    h.append(p, rnd("Léry's Memorial Institute", 420, 2.0))
    with open(p, "a", encoding="utf-8") as fh:
        fh.write("kaputt\n{}\n")                                     # broken lines are skipped
    got = h.load(p)
    assert [r.map for r in got] == ["Coal Tower", "Léry's Memorial Institute"]
    assert got[0].region == "eu-central-1" and got[0].seconds == 600
    h.clear(p)
    assert h.load(p) == [] and not os.path.exists(p)


def test_statistics():
    rs = [rnd("Coal Tower", 600), rnd("Coal Tower", 300), rnd("Badham Preschool II", 900)]
    assert h.summary(rs) == {"count": 3, "total": 1800, "avg": 600}
    assert h.summary([]) == {"count": 0, "total": 0, "avg": 0.0}
    assert h.per_map(rs) == [("Coal Tower", 2, 450, 600), ("Badham Preschool II", 1, 900, 900)]


def test_file_is_tidied(tmp_path, monkeypatch):
    monkeypatch.setattr(h, "KEEP", 10)
    p = str(tmp_path / h.FILE)
    for i in range(30):
        h.append(p, rnd("Coal Tower", 100 + i, float(i)))
    got = h.load(p)
    assert len(got) <= 30 and got[-1].seconds == 129                # newest kept
    assert len(got) >= 10


def test_periods_are_calendar_based():
    import datetime
    now = datetime.datetime(2026, 9, 30, 15, 30).timestamp()            # a Wednesday
    ts = lambda *a: datetime.datetime(*a).timestamp()                   # noqa: E731
    assert h.period_start("all", now) is None
    assert h.period_start("day", now) == ts(2026, 9, 30)
    assert h.period_start("week", now) == ts(2026, 9, 28)              # Monday
    assert h.period_start("month", now) == ts(2026, 9, 1)
    assert h.period_start("year", now) == ts(2026, 1, 1)


def test_select_and_per_region():
    rs = [rnd("A", 100, 10, "eu-central-1"), rnd("B", 300, 20, "eu-central-1"), rnd("C", 200, 30, "eu-west-2"),
          rnd("D", 400, 40)]
    assert [r.map for r in h.select(rs, since=25)] == ["C", "D"]
    assert [r.map for r in h.select(rs, region="eu-central-1")] == ["A", "B"]
    assert [r.map for r in h.select(rs, region=h.NO_REGION)] == ["D"]
    assert h.regions_used(rs) == ["eu-central-1", "eu-west-2"]
    assert h.per_region(rs) == [("eu-central-1", 2, 200, 0.5), ("eu-west-2", 1, 200, 0.25),
                                (h.NO_REGION, 1, 400, 0.25)]
    assert h.per_region([]) == []
