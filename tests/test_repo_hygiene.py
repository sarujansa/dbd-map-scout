"""The repository is public (security check, Oct 2026): no runtime files and nothing that looks like a secret in the
tracked files. A cheap guard, not a scanner – it only catches the obvious kinds again."""
import os
import re
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# CLAUDE.md "Laufzeitdateien, nicht committen"
RUNTIME = re.compile(r"(^|/)(settings\.json(\.broken)?|dbdmapscout\.log|diagnose\.txt|rounds\.jsonl|official\.jsonl|"
                     r"update_status\.txt|dbdmapscout-matches.*\.json|dbdmapscout-structure\.json)$|"
                     r"(^|/)(debug|user_maps|cache|\.venv)/")
SECRET = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|"
                    r"github_pat_[A-Za-z0-9_]{40,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35}")
TEXT = (".py", ".js", ".md", ".bat", ".txt", ".json", ".yml", ".yaml", ".cfg", ".toml", ".ini")


def _tracked():
    if not shutil.which("git") or not os.path.isdir(os.path.join(ROOT, ".git")):
        pytest.skip("not a git checkout")
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, timeout=30)
    if out.returncode != 0:
        pytest.skip("git ls-files failed")
    return [p for p in out.stdout.decode("utf-8", "replace").split("\0") if p]


def test_no_runtime_file_is_tracked():
    assert [p for p in _tracked() if RUNTIME.search(p)] == []


def test_no_tracked_text_file_holds_a_key_or_token():
    found = []
    for p in _tracked():
        if not p.lower().endswith(TEXT) or not os.path.isfile(os.path.join(ROOT, p)):
            continue
        with open(os.path.join(ROOT, p), encoding="utf-8", errors="replace") as fh:
            for n, line in enumerate(fh, 1):
                if SECRET.search(line):
                    found.append(f"{p}:{n}")                # the place only, never the value
    assert found == []
