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
