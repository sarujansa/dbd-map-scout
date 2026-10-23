"""Server-region selection via the hosts file (pure text handling + helper job)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fogscout import hostsedit, regions  # noqa: E402
from conftest import only_linux_hosts  # noqa: E402

WIN_DEFAULT = (
    "# Copyright (c) 1993-2009 Microsoft Corp.\r\n#\r\n# This is a sample HOSTS file used by Microsoft TCP/IP for Windows.\r\n"
    "#\r\n# localhost name resolution is handled within DNS itself.\r\n#\t127.0.0.1       localhost\r\n"
    "#\t::1             localhost\r\n192.168.1.10 nas.local\r\n")

MYC = ("\n\n# --+ Make Your Choice +--\n# Edited by Make Your Choice (DbD Server Selector)\n\n"
       "# gamelift.eu-central-1.amazonaws.com\n# gamelift-ping.eu-central-1.api.aws\n\n"
       "0.0.0.0   gamelift.us-east-1.amazonaws.com\n0.0.0.0   gamelift-ping.us-east-1.api.aws\n"
       "# --+ Make Your Choice +--\n")


def test_hosts_names():
    assert regions.hosts_for("eu-central-1") == ["gamelift.eu-central-1.amazonaws.com",
                                                 "gamelift-ping.eu-central-1.api.aws"]
    assert regions.hosts_for("ap-east-1")[0] == "ec2.ap-east-1.amazonaws.com"
    assert regions.hosts_for("cn-north-1")[0].endswith(".amazonaws.com.cn")
    assert len(regions.MANAGED) == 2 * (len(regions.REGIONS) + len(regions.UNUSED))


def test_apply_and_revert_roundtrip():
    block = regions.block_list(["eu-central-1", "eu-west-1"])
    assert "gamelift.eu-central-1.amazonaws.com" not in block
    assert "gamelift-ping.us-east-1.api.aws" in block and "gamelift.eu-north-1.amazonaws.com" in block
    new = hostsedit.build(WIN_DEFAULT, block, regions.MANAGED)
    assert new.startswith(WIN_DEFAULT.rstrip("\r\n"))            # rest of the file untouched
    st = regions.current_state(new)
    assert st["own"] and st["regions"]["eu-central-1"] == "frei" and st["regions"]["us-east-1"] == "gesperrt"
    again = hostsedit.build(new, regions.block_list(["us-east-1"]), regions.MANAGED)
    assert again.count(hostsedit.BEGIN) == 1 and again.count(hostsedit.END) == 1
    st = regions.current_state(again)
    assert st["regions"]["us-east-1"] == "frei" and st["regions"]["eu-central-1"] == "gesperrt"
    back = hostsedit.build(again, [], regions.MANAGED)
    assert back == WIN_DEFAULT
    assert not regions.current_state(back)["own"]


def test_foreign_entries_detected_and_removed():
    text = WIN_DEFAULT + MYC + "0.0.0.0 gamelift.sa-east-1.amazonaws.com keepme.example\r\n"
    st = regions.current_state(text)
    assert st["myc"] and st["foreign"] == 3
    assert st["regions"]["us-east-1"] == "gesperrt (fremd)" and st["regions"]["sa-east-1"] == "gesperrt (fremd)"
    assert st["regions"]["eu-central-1"] == "frei"
    new = hostsedit.build(text, regions.block_list(["eu-central-1"]), regions.MANAGED, remove_foreign=True)
    assert "Make Your Choice" not in new
    assert "0.0.0.0 keepme.example" in new                        # unrelated name on the same line kept
    assert "192.168.1.10 nas.local" in new
    st = regions.current_state(new)
    assert st["foreign"] == 0 and st["regions"]["sa-east-1"] == "gesperrt"


def test_missing_end_marker_is_repaired():
    broken = WIN_DEFAULT + "\r\n" + hostsedit.BEGIN + "\r\n0.0.0.0 gamelift.us-east-1.amazonaws.com\r\n"
    new = hostsedit.build(broken, [], regions.MANAGED)
    assert hostsedit.BEGIN not in new and "gamelift" not in new


@only_linux_hosts
def test_run_job_writes_file_and_backup(tmp_path, monkeypatch):
    f = tmp_path / "hosts"
    f.write_bytes(WIN_DEFAULT.encode("latin-1"))
    monkeypatch.setenv("DBDMS_HOSTS_FILE", str(f))
    res = regions.run_job({"block": regions.block_list(["eu-central-1"]), "remove_foreign": True})
    assert res["ok"] and res["changed"]
    assert (tmp_path / "hosts.fogscout-backup").read_bytes() == WIN_DEFAULT.encode("latin-1")
    assert regions.current_state()["regions"]["us-west-2"] == "gesperrt"
    res = regions.run_job({"block": [], "remove_foreign": True})
    assert res["ok"] and f.read_bytes() == WIN_DEFAULT.encode("latin-1")
    res = regions.run_job({"block": [], "remove_foreign": True})
    assert res["ok"] and not res["changed"]


@only_linux_hosts
def test_helper_only_touches_gamelift_names(tmp_path, monkeypatch):
    f = tmp_path / "hosts"
    f.write_bytes(WIN_DEFAULT.encode("latin-1"))
    monkeypatch.setenv("DBDMS_HOSTS_FILE", str(f))
    for bad in (["update.microsoft.com"], ["gamelift.us-east-1.api.aws"], ["gamelift-ping.eu-west-\u0661.api.aws"]):
        res = hostsedit.apply_job({"block": bad})
        assert not res["ok"] and f.read_bytes() == WIN_DEFAULT.encode("latin-1")
    res = hostsedit.apply_job({"block": regions.block_list(["eu-west-1"]), "allowed": ["eu-west-1", "x\n1.2.3.4 evil"]})
    lines = f.read_text(encoding="latin-1").splitlines()
    assert res["ok"] and not any("evil" in l for l in lines)
    again = hostsedit.apply_job({"block": regions.block_list(["eu-west-1"]), "allowed": ["eu-west-1"]})
    assert again["ok"] and not again["changed"]                   # identical re-apply: nothing written


def test_the_helpers_errors_show_in_the_ui_language():
    """1.8.45: the elevated helper has no i18n – it answers in German and names its text; the program shows it in
    the UI language (before, the English UI showed these errors in German)."""
    import json
    from fogscout import i18n
    assert set(regions.HELPER_TEXTS) == {hostsedit.BAD_NAME, hostsedit.CHANGED_AFTER, hostsedit.NO_RIGHTS}
    res = json.loads(json.dumps(hostsedit.apply_job({"block": ["update.microsoft.com"]})))   # as in the result file
    assert res["error"] == "Ungültiger Servername im Auftrag: 'update.microsoft.com'"
    try:
        i18n.set_language("en")
        assert regions.helper_result(res)["error"] == "Invalid server name in the job: 'update.microsoft.com'"
        assert regions.helper_result(json.loads(json.dumps(hostsedit._failed(hostsedit.NO_RIGHTS))))["error"] == \
            "No permission to write the hosts file (administrator rights?)."
        other = {"ok": False, "error": "OSError: x", "error_text": "fremd {x}", "error_args": {}}
        assert regions.helper_result(other)["error"] == "OSError: x"          # not one of ours: as it came
        assert regions.helper_result([1])["ok"] is False                      # a broken result file
    finally:
        i18n.set_language("de")
    assert regions.helper_result(res)["error"] == res["error"]


def test_odd_bytes_and_missing_end_marker_keep_other_lines():
    text = "1.2.3.4 caf\x85e.local\r\n# --+ Make Your Choice +--\n0.0.0.0 gamelift.us-east-1.amazonaws.com\n" \
           "\n192.168.1.5 printer.local\r\n"
    new = hostsedit.build(text, [], remove_foreign=True)
    assert "caf\x85e.local" in new and "printer.local" in new and "gamelift" not in new


def test_the_section_written_under_the_old_program_name_is_still_ours():
    """1.9: until 1.8.91 the markers said "DbD Map Scout" – that section is recognised as ours and replaced on the
    next write, never left behind as a foreign block."""
    old = (WIN_DEFAULT + "\r\n" + hostsedit.OLD_BEGIN + "\r\n# Written by DbD Map Scout.\r\n"
           "0.0.0.0 gamelift.us-east-1.amazonaws.com\r\n" + hostsedit.OLD_END + "\r\n")
    a = hostsedit.analyse(old, regions.MANAGED)
    assert a["own"] and a["blocked_own"] == {"gamelift.us-east-1.amazonaws.com"} and a["foreign_lines"] == 0
    new = hostsedit.build(old, ["gamelift.eu-west-2.amazonaws.com"], regions.MANAGED)
    assert hostsedit.OLD_BEGIN not in new and hostsedit.OLD_END not in new and "us-east-1" not in new
    assert hostsedit.BEGIN in new and "0.0.0.0 gamelift.eu-west-2.amazonaws.com" in new
    assert hostsedit.build(old, [], regions.MANAGED) == WIN_DEFAULT


@only_linux_hosts
def test_a_backup_made_under_the_old_name_is_kept_as_the_original(tmp_path, monkeypatch):
    """1.9: the backup is the hosts file from before the program's first change – one made as
    hosts.dbdmapscout-backup stays that, no second "original" is copied from an already changed file."""
    f = tmp_path / "hosts"
    f.write_bytes(WIN_DEFAULT.encode("latin-1"))
    old_backup = tmp_path / ("hosts" + hostsedit.OLD_BACKUP_SUFFIX)
    old_backup.write_bytes(b"# the original\r\n")
    monkeypatch.setenv("DBDMS_HOSTS_FILE", str(f))
    res = regions.run_job({"block": regions.block_list(["eu-central-1"]), "remove_foreign": True})
    assert res["ok"] and res["changed"] and res["backup"] == str(old_backup)
    assert not (tmp_path / ("hosts" + hostsedit.BACKUP_SUFFIX)).exists()
    assert old_backup.read_bytes() == b"# the original\r\n"
