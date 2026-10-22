"""1.8.66 (user: "das Programm crasht ab und zu, wenn ich Videos öffne"): a hard crash left nothing in the log.
faulthandler writes the thread stacks to a file; a normal end removes it, the next start keeps a crash's file and
"Diagnose kopieren" shows it."""
import os
import subprocess
import sys

from dbdmapscout import diagnose

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run(code, tmp_path):
    env = dict(os.environ, PYTHONPATH=ROOT)
    return subprocess.run([sys.executable, "-c", code, str(tmp_path)], env=env, timeout=60,
                          capture_output=True, text=True)


def test_a_hard_crash_is_kept_for_the_diagnosis_and_a_normal_end_leaves_nothing(tmp_path):
    crash, last = tmp_path / diagnose.CRASH_FILE, tmp_path / diagnose.CRASH_LAST
    assert diagnose.crash_lines(str(tmp_path)) == ["Letzter harter Absturz: keiner aufgezeichnet"]
    r = _run("import sys, faulthandler, threading\n"
             "from dbdmapscout import __main__ as m\n"
             "m._enable_crash_log(sys.argv[1])\n"
             "threading.Thread(target=lambda: __import__('time').sleep(30), name='clip-player', daemon=True).start()\n"
             "faulthandler._sigsegv()\n", tmp_path)
    assert r.returncode != 0 and crash.stat().st_size > 0                  # the process died, the stacks are there
    r = _run("import sys\nfrom dbdmapscout import __main__ as m\n"
             "m._enable_crash_log(sys.argv[1])\nm._crash_log_clear(sys.argv[1])\n", tmp_path)
    assert r.returncode == 0, r.stderr
    assert not crash.exists() and last.stat().st_size > 0                  # kept at the start, a normal end after
    lines = diagnose.crash_lines(str(tmp_path))
    assert lines[0].startswith("Letzter harter Absturz (") and diagnose.CRASH_LAST in lines[0]
    text = "\n".join(lines)
    assert "Fatal Python error" in text and len(lines) <= diagnose.CRASH_LINES + 2
    diagnose.keep_crash(str(tmp_path))                                    # nothing new: the kept one stays
    assert last.stat().st_size > 0
