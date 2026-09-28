"""Update on start: pull the newest state from GitHub and keep the packages in step.

Run by start.bat with the program's Python, before the program starts:

    python dbdmapscout\\update.py            update check; exit code 3 = updated (start.bat restarts itself)
    python dbdmapscout\\update.py --deps     install packages if requirements*.txt changed since last time

Standard library only (it runs before anything else and must not depend on the packages).
Only safe updates: on branch main, no own changes to tracked files, fast-forward only.
Anything else (offline, other branch, local commits, git missing, option off) -> skip
quietly and start the version that is there. Only this launcher step talks to GitHub;
the program itself (detection, overlay) still opens no internet connection.

The result is left in .venv\\update_status.txt for the program to show in its log.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

UPDATED, NOTHING, SKIPPED = 3, 0, 1
FETCH_TIMEOUT = 25          # s; offline or a hanging credential prompt must not block the start
STATUS_FILE = "update_status.txt"
REQUIREMENTS = (("requirements.txt", False), ("requirements-extra.txt", True))   # (file, --no-deps)

# Own small translation table: this script runs before the program and may not import it.
EN = {
    "Update-Prüfung ist ausgeschaltet.": "Update check is switched off.",
    "Update übersprungen: git ist nicht installiert.": "Update skipped: git is not installed.",
    "Update übersprungen: kein Git-Ordner (entpackte Kopie).": "Update skipped: not a git folder (unpacked copy).",
    "Update übersprungen: {reason}": "Update skipped: {reason}",
    "Update übersprungen: Zweig „{current}“ statt „{branch}“.":
        "Update skipped: branch “{current}” instead of “{branch}”.",
    "Update übersprungen: eigene Änderungen an Programmdateien.":
        "Update skipped: own changes to program files.",
    "Update übersprungen: GitHub nicht erreichbar": "Update skipped: GitHub not reachable",
    "Update übersprungen: eigene Commits auf main (kein reines Nachziehen möglich).":
        "Update skipped: own commits on main (a plain fast-forward is not possible).",
    "Update fehlgeschlagen, alter Stand bleibt: {error}": "Update failed, the old version stays: {error}",
    "Update installiert: {old} → {new}": "Update installed: {old} → {new}",
    "Update installiert.": "Update installed.",
    "Installiere Pakete aus {name} ...": "Installing packages from {name} ...",
    "Pakete aus {name} installiert.": "Packages from {name} installed.",
    "Pakete aus {name} konnten nicht installiert werden (Internet?) – nächster Start versucht es wieder.":
        "Packages from {name} could not be installed (internet?) – the next start tries again.",
    "Suche nach Updates ...": "Looking for updates ...",
    "Update-Prüfung fehlgeschlagen: {error}": "Update check failed: {error}",
}
_lang = None


def _language(root) -> str:
    """Same choice as the program: settings.json "ui_language", "auto" = Windows language."""
    env = os.environ.get("DBDMS_LANG")
    if env in ("de", "en"):
        return env
    try:
        with open(os.path.join(root, "settings.json"), encoding="utf-8") as fh:
            setting = json.load(fh).get("ui_language", "auto")
    except (OSError, ValueError, AttributeError):
        setting = "auto"
    if setting in ("de", "en"):
        return setting
    try:
        if sys.platform == "win32":
            import ctypes
            return "de" if (ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF) == 0x07 else "en"
        import locale
        return "de" if (locale.getlocale()[0] or os.environ.get("LANG", "")).lower().startswith("de") else "en"
    except Exception:
        return "en"


def _t(root, text, **kw) -> str:
    global _lang
    if _lang is None:
        _lang = _language(root)
    out = EN.get(text, text) if _lang == "en" else text
    return out.format(**kw) if kw else out


def _git(root, *args, timeout=15):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")   # never wait for a password
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=env,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)
    return r.returncode, (r.stdout or r.stderr).strip()


def _enabled(root) -> bool:
    try:
        with open(os.path.join(root, "settings.json"), encoding="utf-8") as fh:
            return bool(json.load(fh).get("auto_update", True))
    except (OSError, ValueError, AttributeError):
        return True


def _version(root, rev) -> str:
    code, text = _git(root, "show", f"{rev}:dbdmapscout/__init__.py")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', text) if code == 0 else None
    return m.group(1) if m else "?"


def update(root: str, branch: str = "main"):
    """Returns (exit code, message for the log)."""
    if not _enabled(root):
        return SKIPPED, _t(root, "Update-Prüfung ist ausgeschaltet.")
    if shutil.which("git") is None:
        return SKIPPED, _t(root, "Update übersprungen: git ist nicht installiert.")
    if not os.path.isdir(os.path.join(root, ".git")):
        return SKIPPED, _t(root, "Update übersprungen: kein Git-Ordner (entpackte Kopie).")
    code, current = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if code != 0:
        return SKIPPED, _t(root, "Update übersprungen: {reason}", reason=current)
    if current != branch:
        return SKIPPED, _t(root, "Update übersprungen: Zweig „{current}“ statt „{branch}“.", current=current,
                          branch=branch)
    if _git(root, "diff", "--quiet", "HEAD")[0] != 0:
        return SKIPPED, _t(root, "Update übersprungen: eigene Änderungen an Programmdateien.")
    _, old = _git(root, "rev-parse", "HEAD")
    code, out = _git(root, "fetch", "--quiet", "origin", branch, timeout=FETCH_TIMEOUT)
    if code != 0:
        return SKIPPED, _t(root, "Update übersprungen: GitHub nicht erreichbar") + (
            f" ({out.splitlines()[-1]})" if out else ".")
    _, new = _git(root, "rev-parse", "FETCH_HEAD")
    if new == old:
        return NOTHING, ""
    if _git(root, "merge-base", "--is-ancestor", "HEAD", "FETCH_HEAD")[0] != 0:
        return SKIPPED, _t(root, "Update übersprungen: eigene Commits auf main (kein reines Nachziehen möglich).")
    code, out = _git(root, "merge", "--ff-only", "--quiet", "FETCH_HEAD")
    if code != 0:
        return SKIPPED, _t(root, "Update fehlgeschlagen, alter Stand bleibt: {error}", error=out)
    # files (maybe start.bat itself) have changed now: whatever happens below, report UPDATED so
    # start.bat restarts itself instead of reading on in its changed file
    try:
        _, log = _git(root, "log", "--format=%s", f"{old}..{new}")
        changes = [line for line in log.splitlines() if line and not line.startswith("Merge pull request")]
        msg = _t(root, "Update installiert: {old} → {new}", old=_version(root, old), new=_version(root, new))
        if changes:
            msg += "\n" + "\n".join(f"  • {c}" for c in changes[:12])
    except Exception:
        msg = _t(root, "Update installiert.")
    return UPDATED, msg


# ------------------------------------------------------------------ packages
def _digest(path) -> str | None:
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return None


def sync_packages(root: str, venv: str, run=None) -> list:
    """pip install for every requirements file that changed since it was last installed.
    Returns messages. ``run(args) -> exit code`` can be replaced in tests."""
    run = run or (lambda args: subprocess.run(args).returncode)
    msgs = []
    for name, no_deps in REQUIREMENTS:
        digest = _digest(os.path.join(root, name))
        if digest is None:
            continue
        stamp = os.path.join(venv, name + ".sha256")
        try:
            with open(stamp, encoding="utf-8") as fh:
                if fh.read().strip() == digest:
                    continue
        except OSError:
            pass
        print(_t(root, "Installiere Pakete aus {name} ...", name=name))
        args = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-r", os.path.join(root, name)]
        if no_deps:
            args.insert(-2, "--no-deps")
        if run(args) == 0:
            with open(stamp, "w", encoding="utf-8") as fh:
                fh.write(digest)
            msgs.append(_t(root, "Pakete aus {name} installiert.", name=name))
        else:
            msgs.append(_t(root, "Pakete aus {name} konnten nicht installiert werden (Internet?) – nächster Start "
                                 "versucht es wieder.", name=name))
    return msgs


def _write_status(venv: str, lines) -> None:
    lines = [line for line in lines if line]
    if not lines:
        return
    try:
        with open(os.path.join(venv, STATUS_FILE), "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except OSError:
        pass


def main(argv) -> int:
    for stream in (sys.stdout, sys.stderr):          # umlauts on an old console code page must not crash
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    venv = os.path.join(root, ".venv")
    if "--deps" in argv:
        _write_status(venv, sync_packages(root, venv))
        return 0
    print(_t(root, "Suche nach Updates ..."))
    try:
        code, msg = update(root)
    except Exception as e:                          # never block the start
        code, msg = SKIPPED, _t(root, "Update-Prüfung fehlgeschlagen: {error}", error=f"{type(e).__name__}: {e}")
    if msg:
        print(msg)
    _write_status(venv, [msg])
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
