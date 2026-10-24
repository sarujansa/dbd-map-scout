"""Parsed lines of an append-only JSON-lines file, kept between reads (1.11.10, user: "optimiere das aktuelle").

rounds.jsonl and official.jsonl only ever grow at the end (a new round, a new match) or are replaced as a whole
(a correction, an import, trimming). The statistics read both after every round: with 3000 rounds and matches
that was ~250 ms of JSON parsing in the window's thread, nearly all of it for lines that had not changed. Here a
file is read as bytes, the part parsed last time is checked by its hash, and only the lines after it are parsed;
anything else (shorter file, other bytes) parses it again from the start. Pure; thread-safe; the parsed objects
are shared – callers hand out copies when they change them.
"""
from __future__ import annotations

import hashlib
import threading


class LineCache:
    """``parse(line: str) -> object | None`` for one line; None = skip it (broken, another kind of line)."""

    def __init__(self, parse):
        self.parse = parse
        self._files = {}                # path -> (consumed bytes, hash of them, [objects of those lines])
        self._lock = threading.Lock()
        self.full = self.tail = 0       # how often a file was parsed from the start / only its new lines (tests)

    def items(self, path: str) -> list:
        """The objects of the file's lines in file order (None ones left out); [] when it cannot be read."""
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError:
            with self._lock:
                self._files.pop(path, None)
            return []
        end = data.rfind(b"\n") + 1                     # complete lines only are kept
        with self._lock:
            consumed, digest, objs = self._files.get(path, (0, None, []))
            if consumed and (len(data) < consumed or _hash(data[:consumed]) != digest):
                consumed, objs = 0, []                  # replaced / changed: from the start
            if consumed:
                self.tail += 1
            else:
                self.full += 1
            if end > consumed:
                objs = objs + self._parse(data[consumed:end])
                self._files[path] = (end, _hash(data[:end]), objs)
            elif not consumed:
                self._files[path] = (0, None, [])
            last = self._parse(data[end:]) if end < len(data) else []    # a line still without its break
        return objs + last

    def forget(self, path: str) -> None:
        with self._lock:
            self._files.pop(path, None)

    def _parse(self, chunk: bytes) -> list:
        out = []
        for raw in chunk.split(b"\n"):
            if not raw.strip():
                continue
            try:
                obj = self.parse(raw.decode("utf-8"))
            except (ValueError, KeyError, TypeError, UnicodeDecodeError):
                continue
            if obj is not None:
                out.append(obj)
        return out


def clone(obj):
    """A shallow copy of a cached object (Round, Match): its own attributes, the values inside shared – callers
    change attributes (the statistics set killer, role, farming …), never the lists inside."""
    c = object.__new__(type(obj))
    c.__dict__.update(obj.__dict__)
    return c


def _hash(b: bytes) -> bytes:
    return hashlib.blake2b(b, digest_size=16).digest()
