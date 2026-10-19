"""Restart after "Aktualisieren und neu starten": wait for the program to end, then start.bat."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dbdmapscout import restart  # noqa: E402

ROOT = r"C:\Users\Player\Desktop\dbd-map-scout"


def test_start_command_runs_start_bat_minimised():
    cmd = restart.start_command()
    # 1.8.45: start.bat from the working directory – the folder ("&", "%") never on cmd's command line
    assert cmd.endswith(' /c start "" /min cmd /c .\\start.bat')


def test_the_helper_starts_in_the_program_folder(monkeypatch):
    calls = []
    monkeypatch.setattr(restart.subprocess, "Popen", lambda cmd, **kw: calls.append((cmd, kw["cwd"])))
    assert restart.wait_and_start(r"C:\Spiele & Tools\dbd-map-scout", running=lambda: False)
    assert calls == [(restart.start_command(), r"C:\Spiele & Tools\dbd-map-scout")]


def test_helper_is_the_program_itself():
    assert restart.helper_args("pythonw.exe") == ["pythonw.exe", "-m", "dbdmapscout", "--restart"]


def test_waits_until_the_program_has_ended(monkeypatch):
    monkeypatch.setattr(restart.time, "sleep", lambda s: None)
    monkeypatch.setenv("DBDMS_UPDATED", "1")          # the program was started by start.bat after an update
    states = iter([True, True, False])
    started = []
    assert restart.wait_and_start(ROOT, running=lambda: next(states), run=lambda cmd, env: started.append(env))
    assert len(started) == 1 and started[0]["DBDMS_FORCE_UPDATE"] == "1"     # installs even if start update is off
    assert "DBDMS_UPDATED" not in started[0]                                  # else start.bat skips the update


def test_never_starts_a_second_copy(monkeypatch):
    monkeypatch.setattr(restart.time, "sleep", lambda s: None)
    clock = iter(range(0, 1000, 5))
    monkeypatch.setattr(restart.time, "time", lambda: next(clock))
    started = []
    told = []
    assert not restart.wait_and_start(ROOT, timeout=30, running=lambda: True, run=lambda c, e: started.append(c),
                                      stuck=lambda: told.append(1))
    assert started == [] and told == [1]          # 1.65.1: says so instead of silently giving up


def test_plain_restart_does_not_force_the_update(monkeypatch):
    """Switching Tk ↔ Qt restarts without pulling updates the user switched off."""
    monkeypatch.setenv("DBDMS_FORCE_UPDATE", "1")
    started = []
    assert restart.helper_args("p.exe", update=False)[-1] == "--no-update"
    assert restart.wait_and_start(ROOT, running=lambda: False, run=lambda cmd, env: started.append(env), update=False)
    assert "DBDMS_FORCE_UPDATE" not in started[0]
