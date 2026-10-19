"""Build statistics (1.8.48, user's pick "Build-Statistik" after the structure of the stats page's answer):
which perks, add-ons, offerings and powers/items you took and how those matches ended – as killer the kills,
as survivor whether you escaped. Pure logic on the statistics' (round, match) pairs; only matches the
userscript (version 3 or newer) saved with a loadout count.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import official

KINDS = ("perk", "addon", "offering", "power")
BUILD_MIN = 2                # a build (the same four perks) is listed from this many matches on


def result(m):
    """The match's result for the table: kills (killer, 0–4) or 1/0 escaped (survivor); None = unknown."""
    if m.role == "killer":
        return official.kills(m)
    e = official.escaped(m)
    return None if e is None else int(e)


def has_loadout(m) -> bool:
    return bool(m.perks or m.addons or m.offering or m.power)


def _key(ref) -> str:
    """Perks are grouped by the page's id (the same perk in another page language), else by name."""
    return ref[0] or ref[1]


@dataclass
class Item:
    kind: str                    # perk | addon | offering | power
    role: str                    # killer | survivor
    key: str
    name: str
    n: int = 0                   # matches with it
    results: list = field(default_factory=list)    # results of those matches (unknown ones left out)
    others: list = field(default_factory=list)     # results of the same role's matches without it
    share: float = 0.0           # n / matches of the role with a loadout

    @property
    def mean(self):
        return sum(self.results) / len(self.results) if self.results else None

    @property
    def mean_without(self):
        return sum(self.others) / len(self.others) if self.others else None


@dataclass
class Build:
    role: str
    character: str
    perks: tuple                 # names, sorted
    n: int = 0
    results: list = field(default_factory=list)

    @property
    def mean(self):
        return sum(self.results) / len(self.results) if self.results else None


def _refs(m, kind) -> list:
    v = getattr(m, kind + "s") if kind in ("perk", "addon") else [getattr(m, kind)]
    return [r for r in v if r]


def items(pairs) -> list:
    """Every perk, add-on, offering and power/item of the own loadouts in ``pairs`` with how its matches ended,
    most used first."""
    matches = [m for _r, m in pairs if m.role in ("killer", "survivor") and has_loadout(m)]
    per_role = {role: [m for m in matches if m.role == role] for role in ("killer", "survivor")}
    found = {}
    for m in matches:
        for kind in KINDS:
            for ref in _refs(m, kind):
                it = found.setdefault((kind, m.role, _key(ref)), Item(kind, m.role, _key(ref), ref[1] or ref[0]))
                it.name = ref[1] or it.name              # the newest name the page gave
    for (kind, role, key), it in found.items():
        for m in per_role[role]:
            used = any(_key(r) == key for r in _refs(m, kind))
            res = result(m)
            if used:
                it.n += 1
            if res is not None:
                (it.results if used else it.others).append(res)
        it.share = it.n / len(per_role[role]) if per_role[role] else 0.0
    return sorted(found.values(), key=lambda i: (-i.n, KINDS.index(i.kind), i.name.lower()))


def builds(pairs, minimum=BUILD_MIN) -> list:
    """The perk sets (all four, any order) played at least ``minimum`` times, per role and character."""
    found = {}
    for _r, m in pairs:
        if m.role not in ("killer", "survivor") or len(m.perks) < 4:
            continue
        names = tuple(sorted((r[1] or r[0] for r in m.perks), key=str.lower))
        key = (m.role, m.character if m.role == "killer" else "", tuple(sorted(_key(r) for r in m.perks)))
        b = found.setdefault(key, Build(m.role, key[1], names))
        b.n += 1
        res = result(m)
        if res is not None:
            b.results.append(res)
    return sorted((b for b in found.values() if b.n >= minimum), key=lambda b: (-b.n, b.role, b.perks))


def with_loadout(pairs) -> int:
    """How many of the pairs' matches have a loadout (userscript 3 or newer)."""
    return sum(1 for _r, m in pairs if has_loadout(m))
