"""1.8.80: daily copies of rounds.jsonl / official.jsonl in backup/ (backups.py)."""
import time

from fogscout import backups

DAY = 86400


def _day(t):
    return time.strftime("%Y-%m-%d", time.localtime(t))


def test_a_changed_file_is_copied_once_a_day_and_unchanged_ones_are_not(tmp_path):
    root = str(tmp_path)
    (tmp_path / "rounds.jsonl").write_text("a\n")
    t0 = time.time()
    r = backups.snapshot(root, t0)
    assert r["copied"] == [f"rounds-{_day(t0)}.jsonl"] and r["pruned"] == []     # official.jsonl missing: skipped
    assert (tmp_path / "backup" / r["copied"][0]).read_text() == "a\n"
    assert backups.snapshot(root, t0)["copied"] == []                            # same day: once
    assert backups.snapshot(root, t0 + DAY)["copied"] == []                      # next day, same content: nothing
    (tmp_path / "rounds.jsonl").write_text("a\nb\n")
    (tmp_path / "official.jsonl").write_text("m\n")
    r = backups.snapshot(root, t0 + DAY)
    assert sorted(r["copied"]) == sorted([f"rounds-{_day(t0 + DAY)}.jsonl", f"official-{_day(t0 + DAY)}.jsonl"])
    assert backups.status(root) == (3, _day(t0 + DAY))
    assert backups.copies(str(tmp_path / "backup"), "rounds") == [f"rounds-{_day(t0)}.jsonl",
                                                                  f"rounds-{_day(t0 + DAY)}.jsonl"]


def test_only_the_newest_copies_stay(tmp_path):
    root = str(tmp_path)
    t0 = time.time() - 40 * DAY
    for i in range(backups.KEEP + 3):
        (tmp_path / "rounds.jsonl").write_text(f"{i}\n")
        backups.snapshot(root, t0 + i * DAY)
    kept = backups.copies(str(tmp_path / "backup"), "rounds")
    assert len(kept) == backups.KEEP and kept[0] == f"rounds-{_day(t0 + 3 * DAY)}.jsonl"
    assert (tmp_path / "backup" / kept[-1]).read_text() == f"{backups.KEEP + 2}\n"


def test_a_tagged_copy_is_taken_even_when_today_has_one(tmp_path):
    root = str(tmp_path)
    (tmp_path / "rounds.jsonl").write_text("a\n")
    t0 = time.time()
    backups.snapshot(root, t0)
    r = backups.snapshot(root, t0, tag="vorher")
    assert r["copied"] == [f"rounds-{_day(t0)}-vorher.jsonl"]
    assert backups.snapshot(root, t0, tag="vorher")["copied"] == []               # the same tag once a day too
    assert backups.status(root)[0] == 2


def test_without_files_or_folder_nothing_happens(tmp_path):
    root = str(tmp_path)
    assert backups.snapshot(root) == {"copied": [], "pruned": [], "day": _day(time.time())}
    assert backups.status(root) == (0, "") and not (tmp_path / "backup").exists()
    (tmp_path / "backup").write_text("not a folder")                            # an unusable target: no crash
    (tmp_path / "rounds.jsonl").write_text("a\n")
    assert backups.snapshot(root)["copied"] == []
