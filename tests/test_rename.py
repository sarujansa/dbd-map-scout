"""1.9 (user: the program shared its name with another one): "DbD Map Scout" became "Fog Scout". What the old name
left in the program folder is taken over once at start (fogscout/rename.py); the other migrations are tested where
they live (hosts markers: test_regions, OBS sources and indexes: test_obsrec, match files: test_official, tasks and
shortcuts: test_autostart_tray, update versions: test_update)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fogscout import diagnose, rename  # noqa: E402


def test_old_runtime_files_are_renamed_or_removed_once(tmp_path):
    (tmp_path / "dbdmapscout-crash.txt").write_text("boom", encoding="utf-8")
    (tmp_path / "dbdmapscout-crash-last.txt").write_text("old", encoding="utf-8")
    (tmp_path / "fogscout-crash-last.txt").write_text("new", encoding="utf-8")
    (tmp_path / "dbdmapscout.log").write_text("log", encoding="utf-8")
    (tmp_path / "dbdmapscout.ico").write_bytes(b"\0")
    (tmp_path / "rounds.jsonl").write_text("{}", encoding="utf-8")
    assert dict(rename.RENAME) == {"dbdmapscout-crash.txt": diagnose.CRASH_FILE,
                                   "dbdmapscout-crash-last.txt": diagnose.CRASH_LAST}
    done = rename.migrate(str(tmp_path))
    assert done == ["dbdmapscout-crash.txt", "dbdmapscout-crash-last.txt", "dbdmapscout.log"]
    assert (tmp_path / diagnose.CRASH_FILE).read_text(encoding="utf-8") == "boom"       # renamed
    assert (tmp_path / diagnose.CRASH_LAST).read_text(encoding="utf-8") == "new"        # the newer file stays
    assert sorted(p.name for p in tmp_path.iterdir()) == [rename.OLD_ICON, diagnose.CRASH_LAST, diagnose.CRASH_FILE,
                                                          "rounds.jsonl"]                # the icon: autostart.install
    assert rename.migrate(str(tmp_path)) == []                                          # nothing left: no-op
    assert rename.migrate(str(tmp_path / "missing")) == []                              # no folder: no error


def test_the_old_package_folder_goes_once_only_pycache_is_left(tmp_path):
    """git fetch cannot remove ignored files: after the update dbdmapscout/ stays with __pycache__ in it – gone
    at the next start. A folder with anything else in it (the user's own files) is never touched."""
    old = tmp_path / rename.OLD_PACKAGE
    (old / "__pycache__").mkdir(parents=True)
    (old / "__pycache__" / "app.cpython-312.pyc").write_bytes(b"\0")
    (old / "fonts" / "__pycache__").mkdir(parents=True)
    (old / "fonts" / "__pycache__" / "x.pyc").write_bytes(b"\0")
    assert rename.migrate(str(tmp_path)) == []                                           # fonts/ is not a cache
    (old / "fonts" / "__pycache__" / "x.pyc").unlink()
    (old / "fonts" / "__pycache__").rmdir()
    (old / "fonts").rmdir()
    assert rename.migrate(str(tmp_path)) == [rename.OLD_PACKAGE + "/"] and not old.exists()
    (old / "__pycache__").mkdir(parents=True)
    (old / "notes.txt").write_text("mine", encoding="utf-8")
    assert rename.migrate(str(tmp_path)) == [] and (old / "notes.txt").exists()
