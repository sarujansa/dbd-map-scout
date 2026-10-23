"""1.8.91: the export of rounds – time texts, presets, the filter, the cells, CSV and text list."""
import datetime
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dbdmapscout import history, official, roundexport as rx  # noqa: E402


def _round(t, seconds=600, **kw):
    kw.setdefault("map_id", "coal")
    kw.setdefault("map", "Coal Tower")
    return history.Round(t, seconds, kw.pop("map_id"), kw.pop("map"), **kw)


def test_times_as_the_user_types_them():
    t = rx.parse_when("23.10.2026 18:30")
    assert datetime.datetime.fromtimestamp(t) == datetime.datetime(2026, 10, 23, 18, 30)
    assert rx.parse_when("23.10.2026 18:30:15") == t + 15
    assert rx.parse_when("23.10.26 18:30") == t
    day = rx.parse_when("23.10.2026")
    assert datetime.datetime.fromtimestamp(day) == datetime.datetime(2026, 10, 23)
    assert rx.parse_when("23.10.2026", end=True) == day + 86400          # "Bis" a date: the whole day
    assert rx.parse_when(" 23.10.2026   18:30 ") == t                     # stray blanks
    today = datetime.datetime.now().replace(hour=7, minute=5, second=0, microsecond=0)
    assert rx.parse_when("07:05") == today.timestamp()                   # a time alone: today
    assert rx.parse_when("") is None and rx.parse_when(None) is None
    with pytest.raises(ValueError):
        rx.parse_when("gestern abend")
    assert rx.fmt_when(t) == "23.10.2026 18:30"


def test_presets_give_since_and_until():
    now = time.mktime((2026, 10, 23, 15, 0, 0, 0, 0, -1))
    midnight = time.mktime((2026, 10, 23, 0, 0, 0, 0, 0, -1))
    assert rx.preset_range("day", now) == (midnight, None)
    assert rx.preset_range("yesterday", now) == (midnight - 86400, midnight)
    assert rx.preset_range("7d", now) == (history.period_start("7d", now), None)
    assert rx.preset_range("all", now) == (None, None) and rx.preset_range("custom", now) == (None, None)
    assert [k for k, _l in rx.PRESETS][-1] == "custom" and dict(rx.PRESETS)["day"] == "Heute"


def test_the_filter_keeps_what_is_asked_for():
    t0 = time.mktime((2026, 10, 23, 18, 0, 0, 0, 0, -1))
    rs = [_round(t0, role="killer", killer="The Nurse", region="eu-central-1"),
          _round(t0 + 600, role="survivor", region="eu-west-2"),
          _round(t0 + 1200, role="killer", killer="The Trapper", custom=True),
          _round(t0 + 1800, role="survivor", farming=True),
          _round(t0 + 2400, role="killer", killer="The Nurse", map="Shattered Square", map_id="shattered")]
    assert rx.select(rs, rx.Filter()) == rs
    assert rx.select(rs[::-1], rx.Filter()) == rs                                    # oldest first
    assert rx.select(rs, rx.Filter(since=t0 + 600, until=t0 + 1800)) == rs[1:3]      # until exclusive
    assert rx.select(rs, rx.Filter(role="killer")) == [rs[0], rs[2], rs[4]]
    assert rx.select(rs, rx.Filter(role="killer", custom=False)) == [rs[0], rs[4]]
    assert rx.select(rs, rx.Filter(farming=False)) == [rs[0], rs[1], rs[2], rs[4]]
    assert rx.select(rs, rx.Filter(killer="The Nurse")) == [rs[0], rs[4]]
    assert rx.select(rs, rx.Filter(map_label="Shattered Square")) == [rs[4]]
    assert rx.select(rs, rx.Filter(region="eu-west-2")) == [rs[1]]
    assert rx.select(rs, rx.Filter(region=history.NO_REGION)) == rs[2:]


def test_cells_table_csv_and_text():
    t0 = time.mktime((2026, 10, 23, 18, 32, 0, 0, 0, -1))
    r = _round(t0, 754, role="killer", killer="The Nurse", region="eu-central-1", wait=83.0, ping=47.4)
    m = official.Match(t=t0 - 38, map="Coal Tower", role="killer", seconds=720, bp=31500,
                       opp=[official.Player(role="survivor", character="Meg Thomas", status="Sacrificed"),
                            official.Player(role="survivor", character="Dwight Fairfield", status="Escaped")])
    names = rx.Names(role=lambda role: {"killer": "Killer", "survivor": "Survivor"}.get(role, ""),
                     region=lambda code: {"eu-central-1": "Frankfurt"}.get(code, code), realm=lambda mid: "MacMillan")
    keys = [k for k, _l in rx.COLUMNS]
    row = rx.table([r], {id(r): m}, keys, names)[0]
    assert dict(zip(keys, row)) == {"start": "23.10.2026 18:32", "end": "23.10.2026 18:44", "duration": "12:34",
                                    "map": "Coal Tower", "realm": "MacMillan", "role": "Killer", "killer": "Nurse",
                                    "kind": "Normal", "wait": "01:23", "region": "Frankfurt", "ping": "47",
                                    "kills": "1", "escaped": "", "bp": "31500", "opponents": "Dwight Fairfield, Meg Thomas"}
    farm = _round(t0 + 900, 120, role="survivor", farming=True)
    surv = official.Match(t=t0 + 900 - 38, map="Coal Tower", role="survivor", status="Escaped")
    row2 = rx.table([farm], {id(farm): surv}, keys, names)[0]
    d2 = dict(zip(keys, row2))
    assert (d2["kind"], d2["wait"], d2["killer"], d2["kills"], d2["escaped"], d2["bp"]) == ("Farming", "sofort", "", "", "ja", "")
    none = dict(zip(keys, rx.table([_round(t0, custom=True)], {}, keys, rx.Names())[0]))
    assert (none["kind"], none["role"], none["realm"], none["region"], none["ping"], none["opponents"]) == ("Custom Game", "", "", "", "", "")
    head = rx.header(["start", "map", "kills"])
    assert head == ["Start", "Map", "Kills"]
    rows = rx.table([r, farm], {id(r): m}, ["start", "map", "kills"], names)
    assert rx.csv_text(head, rows) == "Start;Map;Kills\n23.10.2026 18:32;Coal Tower;1\n23.10.2026 18:47;Coal Tower;\n"
    assert rx.text_lines(rows) == ["23.10.2026 18:32 · Coal Tower · 1", "23.10.2026 18:47 · Coal Tower"]
    assert rx.preview("text", head, rows) == "23.10.2026 18:32 · Coal Tower · 1\n23.10.2026 18:47 · Coal Tower"
    assert rx.preview("csv", head, rows * 2).splitlines()[-1] == "…"                 # more than the first lines


def test_write_csv_with_bom_and_text_file(tmp_path):
    head, rows = ["Start", "Map"], [["23.10.2026 18:32", "Coal Tower"], ["23.10.2026 18:47", "Léry's"]]
    csv_path = tmp_path / "r.csv"
    assert rx.write(str(csv_path), "csv", head, rows) == 2
    raw = csv_path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf") and raw.decode("utf-8-sig") == "Start;Map\n23.10.2026 18:32;Coal Tower\n23.10.2026 18:47;Léry's\n"
    txt = tmp_path / "r.txt"
    assert rx.write(str(txt), "text", head, rows) == 2
    assert txt.read_text(encoding="utf-8") == "23.10.2026 18:32 · Coal Tower\n23.10.2026 18:47 · Léry's\n"
    assert rx.write(str(txt), "text", head, []) == 0 and txt.read_text(encoding="utf-8") == ""
