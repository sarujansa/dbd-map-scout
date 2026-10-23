"""Daily snapshots of the round history (1.8.80): rounds.jsonl and official.jsonl copied into backup/.

Pure. ``snapshot`` copies each file once per day – and only when its content differs from the newest copy – to
``backup/<stem>-YYYY-MM-DD.jsonl`` and keeps the newest ``KEEP`` copies per file; "Verlauf löschen" takes one
more copy first (``tag``). Nothing is read back by the program: the copies are for the user (a broken file, a
wrong click)."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import time

DIR = "backup"
KEEP = 14                                   # copies kept per file (the newest)
FILES = ("rounds.jsonl", "official.jsonl")  # history.FILE, official.FILE
_NAME = re.compile(r"^(?P<stem>[a-z]+)-(?P<day>\d{4}-\d{2}-\d{2})(?:-[a-z]+)?\.jsonl$")


def _digest(path: str):
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return None


def copies(folder: str, stem: str) -> list:
    """The copies of one file in ``folder``, oldest first (the names sort by day)."""
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    return sorted(n for n in names if (m := _NAME.match(n)) and m.group("stem") == stem)


def snapshot(root: str, now: float | None = None, tag: str = "") -> dict:
    """Copy the files of ``root`` that exist and changed; prune. {"copied": [names], "pruned": [names], "day"}.
    With ``tag`` (letters) the copy is taken even when today's exists – before the history is cleared."""
    folder = os.path.join(root, DIR)
    day = time.strftime("%Y-%m-%d", time.localtime(time.time() if now is None else now))
    out = {"copied": [], "pruned": [], "day": day}
    for name in FILES:
        src = os.path.join(root, name)
        if not os.path.isfile(src):
            continue
        stem = name.split(".")[0]
        target = f"{stem}-{day}{'-' + tag if tag else ''}.jsonl"
        had = copies(folder, stem)
        if target in had:
            continue
        if had and not tag and _digest(os.path.join(folder, had[-1])) == _digest(src):
            continue                                                    # nothing new since the last copy
        try:
            os.makedirs(folder, exist_ok=True)
            tmp = os.path.join(folder, target + ".tmp")
            shutil.copy2(src, tmp)
            os.replace(tmp, os.path.join(folder, target))
        except OSError:
            continue
        out["copied"].append(target)
        for old in copies(folder, stem)[:-KEEP]:
            try:
                os.remove(os.path.join(folder, old))
                out["pruned"].append(old)
            except OSError:
                pass
    return out


def status(root: str) -> tuple:
    """(number of copies, day of the newest or "") – for the settings' hint."""
    folder = os.path.join(root, DIR)
    all_names = [n for name in FILES for n in copies(folder, name.split(".")[0])]
    days = sorted(_NAME.match(n).group("day") for n in all_names)
    return len(all_names), days[-1] if days else ""
