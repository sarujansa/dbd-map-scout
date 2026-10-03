"""Official match data (dbdmapscout/official.py) and the userscript that saves it (matchexport.user.js)."""
import json
import os
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dbdmapscout import history  # noqa: E402
from dbdmapscout import official as o  # noqa: E402
from dbdmapscout.textnorm import fold  # noqa: E402

T0 = 1791030420.0           # 3 Oct 2026, 12:27 UTC
SCRIPT = os.path.join(os.path.dirname(o.__file__), o.SCRIPT)


def survivor(status, img="", character="Meg Thomas"):
    return {"role": "VE_Camper", "character": character, "status": {"name": status, "image": img} if status or img
            else None}


def entry(t, map_name="Mother's Dwelling", role="VE_Slasher", statuses=("Sacrificed",) * 4, own=None, custom=False):
    return {"start": t, "map": map_name, "custom": custom,
            "player": {"role": role, "character": "The Nurse" if role == "VE_Slasher" else "Dwight Fairfield",
                       "status": own, "seconds": 440, "bp": 241377},
            "opponents": [survivor(s) for s in statuses] if role == "VE_Slasher" else
            [survivor("Escaped"), {"role": "VE_Slasher", "character": "The Hag", "status": None}]}


def export(*entries, script=1):
    return {"format": o.FORMAT, "version": 1, "script": script, "exported": T0 + 3600, "matches": list(entries)}


def write(folder, name, data):
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(data if isinstance(data, str) else json.dumps(data))
    return path


# ------------------------------------------------------------------ reading
def test_parse_keeps_only_the_needed_fields():
    ms, script = o.parse(export(entry(T0), entry(T0 - 600, role="VE_Camper", own={"name": "Escaped"})), now=T0)
    assert script == 1 and len(ms) == 2
    k, s = ms
    assert (k.t, k.map, k.role, k.character, k.seconds, k.bp, k.custom) == (T0, "Mother's Dwelling", "killer",
                                                                            "The Nurse", 440, 241377, False)
    assert [(p.role, p.status) for p in k.opp] == [("survivor", "Sacrificed")] * 4
    assert (s.role, s.status) == ("survivor", "Escaped")
    assert [p.role for p in s.opp] == ["survivor", "killer"]


def test_status_from_the_picture_when_there_is_no_name():
    m, _s = o.parse(export(entry(T0, statuses=())), now=T0)
    m = m[0]
    m2 = o._player({"role": "VE_Camper", "status": {"image": "display/status/StatusIcon_escaped.png"}})
    assert (m2.status, m2.img) == ("", "StatusIcon_escaped") and o.classify(m2.status, m2.img) == "escaped"
    assert o._player({"role": "VE_Camper", "status": {"id": 3}}).status == "3"
    assert m.opp == []


def test_not_our_file_or_broken_entries():
    for bad in ([], {"matches": []}, {"format": "other", "matches": []}, {"format": o.FORMAT, "matches": "x"}):
        with pytest.raises(ValueError):
            o.parse(bad)
    ms, script = o.parse({"format": o.FORMAT, "script": True, "matches": [
        None, {"start": "x"}, {"start": 1000.0}, {"start": T0 + 10 * 86400}, {"start": float("nan")},
        {"start": T0, "map": 5, "player": "x", "opponents": "x"}]}, now=T0)
    assert script == 0 and len(ms) == 1                     # only the last one, with defaults
    assert (ms[0].map, ms[0].role, ms[0].bp, ms[0].opp) == ("", "", 0, [])


def test_bundled_userscript_version():
    assert o.script_version(SCRIPT) >= 1
    with open(SCRIPT, encoding="utf-8") as fh:
        js = fh.read()
    assert f"SCRIPT_VERSION = {o.script_version(SCRIPT)};" in js        # header and code agree
    assert f"'{o.FORMAT}'" in js and f"'{o.PREFIX}.json'" in js
    assert o.script_version("/does/not/exist") == 0


# ------------------------------------------------------------------ status -> result
def test_classify_the_statuses_seen_on_the_page():
    # name / picture as in the user's diagnostics (Oct 2026)
    assert o.classify("ESCAPED", "VE_Escaped") == "escaped"
    assert o.classify("SACRIFICED", "VE_Sacrificed") == o.classify("DEAD", "VE_Killed") == "dead"
    assert o.classify("VE_SurrenderLoss", "VE_SurrenderDraw") == "abandoned"
    assert o.classify("ESCAPED", "VE_SurrenderDraw") == "abandoned"   # the page calls some abandons "escaped"
    assert o.classify("VE_ManuallyLeftMatch", "VE_ManuallyLeftMatch") == "gone"


def test_classify_other_names():
    assert o.classify("BledOut") == o.classify("", "status_mori") == "dead"
    assert o.classify("Abandoned") == "abandoned" and o.classify("Disconnected") == "gone"
    assert o.classify("Escaped", "killed") == "escaped"           # the name decides, the picture only without one
    assert o.classify("EscapedButKilled") is None                 # contradicting: rather unknown than wrong
    assert o.classify("") is None and o.classify("Killer") is None and o.classify("VE_Unknown") is None


def test_kills_and_escapes():
    ms, _s = o.parse(export(entry(T0, statuses=("Sacrificed", "Killed", "Escaped", "Disconnected")),
                            entry(T0 + 1, statuses=("Sacrificed", "VE_SurrenderLoss", "VE_SurrenderLoss", "Dead")),
                            entry(T0 + 2, statuses=("Sacrificed", "VE_Mystery", "Escaped", "Escaped")),
                            entry(T0 + 3, role="VE_Camper", own={"name": "Escaped"}),
                            entry(T0 + 4, role="VE_Camper", own={"name": "Sacrificed"}),
                            entry(T0 + 5, role="VE_Camper", own={"name": "ESCAPED", "image": "x/VE_SurrenderDraw.png"}),
                            entry(T0 + 6, role="VE_Camper", own=None)), now=T0)
    assert [o.kills(m) for m in ms] == [2, 4, None, None, None, None, None]
    assert [o.abandons(m) for m in ms] == [0, 2, 0, 0, 0, 0, 0]
    assert [o.escaped(m) for m in ms] == [None, None, None, True, False, False, None]
    assert o.unknown_statuses(ms) == {"VE_Mystery": 1, "–": 1}
    s = o.summary(ms)
    assert (s["killer"], s["kills"], s["four"], s["abandons"], s["survivor"], s["escaped"]) == \
        (2, 3.0, 1, 2, 3, 1 / 3)


def test_results_grouped_by_round():
    ms, _s = o.parse(export(entry(T0), entry(T0 + 1, statuses=("Escaped",) * 4), entry(T0 + 2, map_name="Coal Tower"),
                            entry(T0 + 3, role="VE_Camper", own={"name": "Escaped"}),
                            entry(T0 + 4, statuses=("VE_Mystery",) * 4, map_name="Dead Dawg Saloon")), now=T0)
    rounds = [rnd(m.t, "x") for m in ms]
    for r, m in zip(rounds, ms):
        r.map = m.map                                          # the label the program stored
    got = o.results(list(zip(rounds, ms)), lambda r: r.map)
    assert got["Mother's Dwelling"] == {"kills": [4, 0], "escaped": [True], "bp": [241377] * 3}
    assert got["Coal Tower"]["kills"] == [4]
    assert got["Dead Dawg Saloon"] == {"kills": [], "escaped": [], "bp": [241377]}   # result unknown, BP count
    assert o.mean([1, 2, 6]) == 3 and o.mean([]) is None and o.mean(None) is None


# ------------------------------------------------------------------ official.jsonl
def test_merge_replaces_and_finds_gaps(tmp_path):
    p = str(tmp_path / o.FILE)
    first, _s = o.parse(export(*[entry(T0 + i * 600) for i in range(5)]), now=T0 + 10 ** 6)
    assert o.merge(p, first) == (5, None)                     # first import: no gap
    again, _s = o.parse(export(*[entry(T0 + i * 600, map_name="Coal Tower") for i in range(3, 8)]), now=T0 + 10 ** 6)
    assert o.merge(p, again) == (3, None)                     # overlaps: no gap, 3 new
    got = o.load(p)
    assert [m.t for m in got] == [T0 + i * 600 for i in range(8)]
    assert got[3].map == "Coal Tower"                         # the newer copy wins
    full, _s = o.parse(export(*[entry(T0 + 10 ** 5 + i * 600) for i in range(o.PAGE_LIMIT)]), now=T0 + 10 ** 6)
    new, gap = o.merge(p, full)
    assert new == o.PAGE_LIMIT and gap == (T0 + 7 * 600, T0 + 10 ** 5)
    assert o.load_gaps(p) == [gap] and len(o.load(p)) == 8 + o.PAGE_LIMIT
    with open(p, "a", encoding="utf-8") as fh:
        fh.write("kaputt\n{}\n")
    assert len(o.load(p)) == 8 + o.PAGE_LIMIT
    o.clear(p)
    assert o.load(p) == [] and o.load_gaps(p) == []


def test_merge_keeps_the_newest(tmp_path, monkeypatch):
    monkeypatch.setattr(o, "KEEP", 3)
    p = str(tmp_path / o.FILE)
    ms, _s = o.parse(export(*[entry(T0 + i * 600) for i in range(5)]), now=T0 + 10 ** 6)
    o.merge(p, ms)
    assert [m.t for m in o.load(p)] == [T0 + i * 600 for i in (2, 3, 4)]


# ------------------------------------------------------------------ download folder
def test_take_downloads_reads_ours_and_deletes_only_ours(tmp_path):
    dl, store = tmp_path / "Downloads", str(tmp_path / o.FILE)
    dl.mkdir()
    a = write(dl, "dbdmapscout-matches.json", export(entry(T0), entry(T0 + 600)))
    b = write(dl, "dbdmapscout-matches (1).json", export(entry(T0 + 600), entry(T0 + 1200), script=2))
    foreign = write(dl, "dbdmapscout-matches (2).json", {"something": "else"})
    half = write(dl, "DBDMAPSCOUT-MATCHES (3).json", '{"format": "dbdmapscout-matches", "matc')
    other = write(dl, "other.json", export(entry(T0 + 5000)))
    res = o.take_downloads(str(dl), store, now=T0 + 3600)
    assert (res.files, res.matches, res.new, res.script) == (2, 4, 3, 1)
    assert not os.path.exists(a) and not os.path.exists(b)
    assert os.path.exists(foreign) and os.path.exists(half) and os.path.exists(other)
    assert res.foreign == [foreign] and res.unreadable == [half] and res.undeleted == []
    assert [m.t for m in o.load(store)] == [T0, T0 + 600, T0 + 1200]
    assert o.take_downloads(str(tmp_path / "missing"), store).files == 0


def test_take_downloads_skips_huge_files(tmp_path, monkeypatch):
    monkeypatch.setattr(o, "MAX_FILE", 10)
    big = write(tmp_path, "dbdmapscout-matches.json", export(entry(T0)))
    res = o.take_downloads(str(tmp_path), str(tmp_path / o.FILE), now=T0)
    assert res.files == 0 and res.foreign == [big] and os.path.exists(big)


def test_downloads_dir_is_a_path():
    assert os.path.isabs(o.downloads_dir())


# ------------------------------------------------------------------ tying matches to rounds
def rnd(t, map_id):
    return history.Round(t=t, seconds=600, map_id=map_id, map=map_id, source="auto")


def match(t, name):
    return o.Match(t=t, map=name)


def test_bloodpoints():
    ms, _s = o.parse(export(entry(T0), entry(T0 + 1, role="VE_Camper", own={"name": "Escaped"})), now=T0)
    ms[1].bp, ms[1].seconds = 100000, 360
    s = o.summary(ms)
    assert (s["bp"], s["bp_matches"]) == (341377, 2)
    assert (o.summary([])["bp"], o.summary([])["kills"]) == (0, None)


def test_end_offset_and_rescued_length():
    m = o.Match(t=T0, map="Coal Tower", seconds=600)
    r = rnd(T0 + 38, "coal")                                  # banner 38 s after the start, 600 s counted
    assert o.end_offset(r, m) == 38                           # end detected 38 s after the end on the page
    assert o.rescued_seconds(r, m) == 562                     # from the banner to the page's end
    assert o.rescued_seconds(rnd(T0 + 550, "coal"), m) is None   # under a minute: not a round


def test_detection_rate():
    ms = [o.Match(t=T0 + i * 600, map="Coal Tower", seconds=500) for i in range(5)]
    ms[4].seconds = 30                                        # too short to be stored as a round
    seen, missed = o.detection(ms, {id(ms[1]), id(ms[2])}, since=T0 + 300)
    assert seen == [ms[1], ms[2]] and missed == [ms[3]]       # ms[0] is older than the program's first round
    assert o.detection(ms, set())[1] == ms[:4]


def test_map_index_over_all_names_and_aliases():
    maps = {"coal-tower": SimpleNamespace(id="coal-tower", names={"en": "Coal Tower", "de": "Kohlelager"},
                                          aliases=["Kohleturm"]),
            "x": SimpleNamespace(id="x", names={"en": "Mother’s Dwelling"}, aliases=None),
            "gs": SimpleNamespace(id="gs", names={"en": "Groaning Storehouse"}, aliases=[], variants={1: "a", 2: "b"},
                                  label=lambda v: "Groaning Storehouse" + (" II" if v == 2 else ""))}
    idx = o.map_index(maps)
    assert idx[fold("Groaning Storehouse II")] == "gs"          # labels as rounds.jsonl stores them
    assert idx[fold("Kohlelager")] == idx[fold("kohleturm")] == "coal-tower"
    assert idx[fold("Mother's Dwelling")] == "x"                # typographic apostrophe


def test_link_prefers_the_same_map():
    # banner minus start: the user's data says +31 … +51 s
    ids = {"Coal Tower": "coal", "Treatment Theater": "tt"}
    rounds = [rnd(T0 + 20, "coal"), rnd(T0 + 900, "coal"), rnd(T0 + 2000, "coal"), rnd(T0 + 4000, "tt")]
    matches = [match(T0 + 900 - 60, "Treatment Theater"),   # other map, close to round 1 …
               match(T0 + 900 - 150, "Coal Tower"),         # … but the same map 150 s off wins
               match(T0, "Coal Tower"),
               match(T0 + 2000 - 60, "Groaning Storehouse"),  # other map, only one there -> tied, flagged
               match(T0 + 4000 - 400, "Treatment Theater")]   # too far
    ids["Groaning Storehouse"] = "gs"
    tied, other = o.link(rounds, matches, ids.get)
    assert tied == {0: matches[2], 1: matches[1], 2: matches[3]}
    assert other == [(rounds[2], matches[3])]


def test_link_other_map_only_when_close_and_unknown_maps_are_not_flagged():
    rounds = [rnd(T0, "coal"), rnd(T0 + 5000, "coal"), rnd(T0 + 9000, "coal")]
    matches = [match(T0 - 120, "Groaning Storehouse"),        # other map 120 s before the banner: too far
               match(T0 + 5000 - 100, "Brand New Map"),       # unknown map: counts as the same one
               match(T0 + 9000 + 90, "Coal Tower")]           # starts 90 s after the banner: not this round
    tied, other = o.link(rounds, matches, {"Groaning Storehouse": "gs", "Coal Tower": "coal"}.get)
    assert tied == {1: matches[1]} and other == []
    assert o.link([], matches, {}.get) == ({}, []) and o.link(rounds, [], {}.get) == ({}, [])


def test_each_match_and_round_used_once():
    rounds = [rnd(T0, "coal"), rnd(T0 + 30, "coal")]
    matches = [match(T0 - 30, "Coal Tower")]                 # +30 s / +60 s: the first is closer to the usual +38
    tied, _other = o.link(rounds, matches, {"Coal Tower": "coal"}.get)
    assert tied == {0: matches[0]}


# ------------------------------------------------------------------ opening the page after DBD
def test_open_after_game():
    g = o.OpenAfterGame()
    assert not g.update(0, False) and not g.update(100, False)         # DBD never seen
    g.update(200, True)
    g.round_recorded()
    assert not g.update(205, False) and not g.update(205 + g.GONE - 1, False)
    g.update(215, True)                                                  # back (restart, loading): starts over
    assert not g.update(220, False)
    assert g.update(220 + g.GONE, False)                                 # gone long enough: open once
    assert not g.update(400, False)
    g.update(500, True)
    assert not g.update(600, False) and not g.update(700, False)         # no round this time: nothing to fetch


# ------------------------------------------------------------------ the userscript itself (needs node)
HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const code = fs.readFileSync(process.argv[2], 'utf8');
const answer = fs.readFileSync(process.argv[3], 'utf8');
const api = 'https://account-backend.bhvr.com/player-stats/match-history/games/dbd/providers/bhvr?lang=en&limit=30';
const saved = { xhr: [], fetch: [], cache: [] };
function context(out, store, cache, fetchAnswer) {
  class XHR { open() {} send() {} addEventListener(ev, fn) { this.onload = fn; } }
  const ctx = {
    console: { log() {} }, setTimeout: fn => setTimeout(fn, 0), clearTimeout,
    XMLHttpRequest: XHR,
    sessionStorage: { getItem: () => cache },
    localStorage: { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = v; } },
    URL: { createObjectURL: b => { out.push(b.text); return 'blob:x'; }, revokeObjectURL() {} },
    Blob: class { constructor(parts) { this.text = parts.join(''); } },
    document: { body: { appendChild() {} }, addEventListener() {},
                createElement: () => ({ click() {}, remove() {}, style: {} }) },
  };
  if (fetchAnswer) ctx.fetch = async () => ({ clone: () => ({ json: async () => JSON.parse(fetchAnswer) }) });
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(code, ctx);
  return ctx;
}
function load(ctx, url) {
  const x = new ctx.XMLHttpRequest();
  x.open('GET', url);
  x.send();
  x.responseType = '';
  x.responseText = answer;
  if (x.onload) x.onload();
}
const store = {};
load(context(saved.xhr, store), 'https://stats.deadbydaylight.com/_next/data/x/faq.json');   // other requests: ignored
load(context(saved.xhr, store), api);
const f = context(saved.fetch, {}, null, answer);
f.window.fetch(api);
const cached = JSON.stringify({ clientState: { queries: [{ queryKey: ['stats.match-history'],
                                                           state: { data: JSON.parse(answer) } }] } });
context(saved.cache, {}, cached);
setTimeout(() => {
  load(context(saved.xhr, store), api);       // same matches on the next visit: no second file
  setTimeout(() => process.stdout.write(JSON.stringify(saved)), 20);
}, 20);
"""


def test_userscript_saves_a_file_the_program_reads(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    page_answer = [{
        "matchStat": {"matchStartTime": T0, "map": {"name": "Mother's Dwelling", "image": {"path": "m.png"}},
                      "isCustomMatch": False, "matchId": "secret-match-id"},
        "playerStat": {"playerRole": "VE_Slasher", "characterName": {"name": "The Nurse"}, "playerTimeInMatch": 440,
                       "bloodpointsEarned": 241377, "playerName": "MyOwnName", "postGameStat": {"x": 1}},
        "opponentStat": [{"playerRole": "VE_Camper", "characterName": {"name": "Meg Thomas"},
                          "playerName": "SomeoneElse", "platformId": "765611",
                          "playerStatus": {"name": "Sacrificed", "image": {"path": "display/status/sacrificed.png"},
                                           "details": {"nested": "dropped"}}}] * 4}]
    script_path = tmp_path / "harness.js"
    answer_path = tmp_path / "answer.json"
    script_path.write_text(HARNESS, encoding="utf-8")
    answer_path.write_text(json.dumps(page_answer), encoding="utf-8")
    out = subprocess.run([node, str(script_path), SCRIPT, str(answer_path)], capture_output=True, text=True,
                         timeout=60)
    assert out.returncode == 0, out.stderr
    saved = json.loads(out.stdout)
    assert len(saved["xhr"]) == 1                            # once; not again for the same matches
    assert len(saved["fetch"]) == 1 and len(saved["cache"]) == 1   # fetch() and the page's cached copy work too
    for secret in ("MyOwnName", "SomeoneElse", "765611", "secret-match-id", "dropped"):
        assert secret not in saved["xhr"][0]                 # only the whitelisted fields leave the page
    ms, script = o.parse(json.loads(saved["xhr"][0]), now=T0)
    assert script == o.script_version(SCRIPT)
    assert len(ms) == 1 and o.kills(ms[0]) == 4 and ms[0].opp[0].img == "sacrificed"


# ------------------------------------------------------------------ map correction, trend
def test_correct_maps_takes_the_page_map_as_layout_one():
    ids = {"Coal Tower": "coal", "Groaning Storehouse": "gs"}.get
    a, b, c = rnd(T0, "coal"), rnd(T0 + 600, "coal"), rnd(T0 + 1200, "")
    a.map, b.map, c.map = "Coal Tower II", "Coal Tower II", "Old Label"
    fixed = o.correct_maps([(a, match(T0, "Coal Tower")), (b, match(T0 + 600, "Groaning Storehouse")),
                            (c, match(T0 + 1200, "Brand New Map"))], ids,
                           lambda mid: {"gs": "Groaning Storehouse I"}.get(mid))
    assert (a.map_id, a.map) == ("coal", "Coal Tower II")          # same map: layout stays as detected
    assert (b.map_id, b.map) == ("gs", "Groaning Storehouse I")     # other map: the page wins
    assert (c.map_id, c.map) == ("", "Old Label")                   # unknown map on the page: left alone
    assert fixed == {id(b): "Coal Tower II"}


def test_bucket_start_hour_day_week():
    import time as _time
    t = T0                                                         # Saturday
    for unit, fmt in (("hour", "%a %H:%M"), ("day", "%a %H:%M"), ("week", "%a %H:%M")):
        b = o.bucket_start(t, unit)
        assert b <= t and o.bucket_start(b, unit) == b
        nxt = o._next_bucket(b, unit)
        assert nxt > t and o.bucket_start(nxt, unit) == nxt
    assert _time.localtime(o.bucket_start(t, "week")).tm_wday == 0  # weeks start on Monday
    assert _time.localtime(o.bucket_start(t, "day")).tm_hour == 0


def test_trend_keeps_empty_buckets_and_the_newest_30(monkeypatch):
    week = 7 * 86400
    ms, _s = o.parse(export(entry(T0), entry(T0 + 60, statuses=("Escaped",) * 4),
                            entry(T0 + 2 * week, role="VE_Camper", own={"name": "Escaped"}),
                            entry(T0 + 3 * week, statuses=("VE_Mystery",) * 4)), now=T0 + 4 * week)
    pairs = [(rnd(m.t, "x"), m) for m in ms]
    got = o.trend(pairs, "week")
    assert [(len(k), len(e)) for _b, k, e in got] == [(2, 0), (0, 0), (0, 1)]   # unknown result: no bucket
    assert got[0][1] == [4, 0] and got[2][2] == [True]
    assert [b for b, _k, _e in got] == sorted(b for b, _k, _e in got)
    assert o.trend([], "day") == []
    monkeypatch.setattr(o, "MAX_BUCKETS", 2)
    assert len(o.trend(pairs, "week")) == 2


def test_chart_columns_stay_thin():
    trendchart = pytest.importorskip("dbdmapscout.trendchart")
    cols = trendchart.columns(3, 600)
    assert len(cols) == 3 and all(x1 - x0 <= trendchart.BAR_MAX + 1e-9 for x0, x1 in cols)
    assert all(a[1] < b[0] for a, b in zip(cols, cols[1:]))     # air between columns
    many = trendchart.columns(30, 400)
    assert all(x1 > x0 for x0, x1 in many) and many[-1][1] <= 400 - trendchart.RIGHT
    assert trendchart.columns(0, 600) == []
