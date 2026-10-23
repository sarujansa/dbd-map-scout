"""1.8.91 (user: "Mach für Export so ein Fenster, wo ich alles auswählen kann, Killer, Zeit etc."): export of rounds.

Pure logic for the dialog in app_export.py: a time range (presets or from/to typed as TT.MM.JJJJ HH:MM), the filters
(role, killer, map, region, custom games and farming rounds in or out), a choice of columns, and the two outputs –
a CSV file for Excel (semicolon, UTF-8 with BOM) or a plain text list, one line per round, for the clipboard.
"""
from __future__ import annotations

import csv
import datetime
import io
import time
from dataclasses import dataclass, field

from . import history, official
from .i18n import N_, _
from .lobby import killer_label
from .textnorm import fmt_duration

# (key, label) – the order of the columns in the file and the list
COLUMNS = (("start", N_("Start")), ("end", N_("Ende")), ("duration", N_("Dauer")), ("map", N_("Map")),
           ("realm", N_("Realm")), ("role", N_("Rolle")), ("killer", N_("Killer")), ("kind", N_("Art")),
           ("wait", N_("Wartezeit")), ("region", N_("Region")), ("ping", N_("Ping (ms)")), ("kills", N_("Kills")),
           ("escaped", N_("Entkommen")), ("bp", N_("Bloodpoints")), ("opponents", N_("Gegner")))
DEFAULT_COLUMNS = ("start", "duration", "map", "role", "killer", "kills", "escaped", "bp")
PRESETS = (("day", N_("Heute")), ("yesterday", N_("Gestern")), ("7d", N_("Letzte 7 Tage")),
           ("30d", N_("Letzte 30 Tage")), ("week", N_("Diese Woche")), ("month", N_("Dieser Monat")),
           ("year", N_("Dieses Jahr")), ("all", N_("Alles")), ("custom", N_("Eigener Zeitraum")))
FORMATS = (("csv", N_("CSV-Datei (Excel)")), ("text", N_("Textliste (eine Zeile je Runde)")))
WHEN = "%d.%m.%Y %H:%M"
PREVIEW_LINES = 3


def fmt_when(t: float) -> str:
    return time.strftime(WHEN, time.localtime(t))


def parse_when(text: str, end: bool = False):
    """``text`` as the user types it: "23.10.2026 18:30", "23.10.2026" (midnight; ``end``: the end of that day),
    "18:30" (today) or "" (None = open). ValueError when it is none of these."""
    s = " ".join(str(text or "").split())
    if not s:
        return None
    now = datetime.datetime.now()
    for fmt, date_only, time_only in ((WHEN, False, False), ("%d.%m.%Y %H:%M:%S", False, False),
                                      ("%d.%m.%Y", True, False), ("%d.%m.%y %H:%M", False, False),
                                      ("%d.%m.%y", True, False), ("%H:%M", False, True)):
        try:
            d = datetime.datetime.strptime(s, fmt)
        except ValueError:
            continue
        if time_only:
            d = now.replace(hour=d.hour, minute=d.minute, second=0, microsecond=0)
        if date_only and end:
            d += datetime.timedelta(days=1)
        return d.timestamp()
    raise ValueError(s)


def preset_range(key: str, now: float):
    """(since, until) of a preset; until is exclusive, None = open. "custom" keeps what the user typed (None, None)."""
    if key == "yesterday":
        today = history.period_start("day", now)
        return today - 86400.0, today
    if key in history.PERIODS:
        return history.period_start(key, now), None
    return None, None


@dataclass
class Filter:
    since: float | None = None
    until: float | None = None           # exclusive
    role: str = "all"                    # all | killer | survivor
    killer: str | None = None
    map_label: str | None = None
    region: str | None = None            # history.NO_REGION = rounds without a known server
    custom: bool = True                  # custom games in
    farming: bool = True                 # farming rounds in


def select(rounds, f: Filter) -> list:
    out = []
    for r in rounds:
        if f.since is not None and r.t < f.since:
            continue
        if f.until is not None and r.t >= f.until:
            continue
        if r.custom and not f.custom:
            continue
        if r.farming and not r.custom and not f.farming:
            continue
        if f.role in ("killer", "survivor") and r.role != f.role:
            continue
        if f.killer and (r.killer != f.killer or r.role != "killer"):
            continue
        if f.map_label and r.map != f.map_label:
            continue
        if f.region == history.NO_REGION:
            if r.region:
                continue
        elif f.region and r.region != f.region:
            continue
        out.append(r)
    return sorted(out, key=lambda r: r.t)


@dataclass
class Names:
    """How the App names things (the pure functions default to the raw values)."""
    role: object = field(default=lambda role: role or "")
    region: object = field(default=lambda code: code or "")
    realm: object = field(default=lambda map_id: "")


def cell(key: str, r, m, names: Names) -> str:
    if key == "start":
        return fmt_when(r.t)
    if key == "end":
        return fmt_when(r.t + r.seconds)
    if key == "duration":
        return fmt_duration(r.seconds)
    if key == "map":
        return r.map
    if key == "realm":
        return names.realm(r.map_id) if r.map_id else ""
    if key == "role":
        return names.role(r.role)
    if key == "killer":
        return killer_label(r.killer) if r.killer else ""
    if key == "kind":
        return _("Custom Game") if r.custom else _("Farming") if r.farming else _("Normal")
    if key == "wait":
        if r.wait is not None:
            return fmt_duration(r.wait)
        return _("sofort") if r.farming and not r.custom else ""
    if key == "region":
        return names.region(r.region) if r.region else ""
    if key == "ping":
        return f"{r.ping:.0f}" if r.ping is not None else ""
    if key == "kills":
        k = official.kills(m) if m is not None else None
        return "" if k is None else str(k)
    if key == "escaped":
        e = official.escaped(m) if m is not None else None
        return "" if e is None else (_("ja") if e else _("nein"))
    if key == "bp":
        return str(m.bp) if m is not None and m.bp else ""
    if key == "opponents":
        return ", ".join(sorted(official.opponent_names(m))) if m is not None else ""
    return ""


def table(rounds, off: dict, keys, names: Names) -> list:
    """[[cell, …] per round] for the chosen column ``keys``; ``off`` = {id(round): official match}."""
    return [[cell(k, r, off.get(id(r)), names) for k in keys] for r in rounds]


def header(keys) -> list:
    labels = dict(COLUMNS)
    return [_(labels[k]) for k in keys]


def csv_text(head, rows) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\n")
    w.writerow(head)
    w.writerows(rows)
    return buf.getvalue()


def text_lines(rows) -> list:
    """One line per round, the empty cells left out: "23.10.2026 18:32 · Coal Tower · Killer · Nurse"."""
    return [" · ".join(c for c in row if c) for row in rows]


def write(path: str, fmt: str, head, rows) -> int:
    """The CSV (UTF-8 with BOM, so Excel reads the umlauts) or the text list into ``path``; rounds written."""
    text = csv_text(head, rows) if fmt == "csv" else "\n".join(text_lines(rows)) + ("\n" if rows else "")
    with open(path, "w", encoding="utf-8-sig" if fmt == "csv" else "utf-8", newline="") as fh:
        fh.write(text)
    return len(rows)


def preview(fmt: str, head, rows, limit: int = PREVIEW_LINES) -> str:
    lines = csv_text(head, rows[:limit]).splitlines() if fmt == "csv" else text_lines(rows[:limit])
    if len(rows) > limit:
        lines.append("…")
    return "\n".join(lines)
