"""What changed since the version last run (1.8.79): the rows of HISTORY.md after that version.

Pure. HISTORY.md is a Markdown table whose version rows read "Title 1.8.78 (background …) | …" and are appended in
order of release, so everything after the row of the version the user last ran is news. Rows whose first cell
names a file (`app.py`) or a theme carry no version and are skipped. The overview shows the result once, until
"Verstanden" (App._news_seen)."""
from __future__ import annotations

import re

MAX_ROWS = 8          # the overview shows at most this many versions, the newest first
DETAIL_CHARS = 240    # a longer background is cut with an ellipsis
_VERSION = re.compile(r"\b(\d+\.\d+(?:\.\d+)*)\b")


def parse_version(text) -> tuple:
    """"1.8.79" → (1, 8, 79); anything else → ()."""
    try:
        return tuple(int(p) for p in str(text).strip().split("."))
    except ValueError:
        return ()


def entries(text: str) -> list:
    """[(version, title, detail)] of every version row of the table text, in file order."""
    out = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = line.split("|")
        head = cells[1].strip() if len(cells) > 2 else ""
        if not head or head.startswith("`") or set(head) <= set("-: "):
            continue
        title, _sep, detail = head.partition(" (")
        found = _VERSION.findall(title)
        if not found:
            continue
        version = found[-1]
        title = title[:title.rfind(version)].strip(" –-")
        detail = detail.rstrip()
        if detail.endswith(")"):
            detail = detail[:-1].rstrip()
        if len(detail) > DETAIL_CHARS:
            detail = detail[:DETAIL_CHARS - 1].rstrip() + "…"
        out.append((version, title or version, detail))
    return out


def news(text: str, seen: str, limit: int = MAX_ROWS) -> list:
    """The version rows after ``seen`` (the version last run), the newest first, at most ``limit``. A version the
    table does not name (its row was skipped) falls back to the numbers: every row newer than it."""
    rows = entries(text)
    at = [i for i, r in enumerate(rows) if r[0] == seen]
    if at:
        fresh = rows[at[-1] + 1:]
    else:
        s = parse_version(seen)
        fresh = [r for r in rows if parse_version(r[0]) > s] if s else []
    return list(reversed(fresh))[:limit]


def load(path: str, seen: str, limit: int = MAX_ROWS) -> list:
    """``news`` of the file at ``path``; [] when it cannot be read."""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return []
    return news(text, seen, limit)
