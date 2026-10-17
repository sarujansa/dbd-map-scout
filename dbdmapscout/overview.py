"""Everything the page "Übersicht" of the Qt window shows, collected from the running App (no Qt calls).

Called on the main thread from App._tick_overlay (4×/s); the only expensive part – rounds and official
matches from the files – comes from App._joined(), which is cached by file time.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import history, obsrec, official, sysinfo, theme
from .connwatch import UNKNOWN, region_name
from .i18n import _
from .lobby import killer_label
from .overlay_win32 import ping_colour
from .status import DOT_STYLE, user_state
from .textnorm import fmt_duration, roman

LAST_ROUNDS = 5


@dataclass
class Fact:
    """One value of the map card or one tile: title, big value, small line below, bar 0..1, colour."""
    title: str
    value: str = "–"
    sub: str = ""
    frac: float | None = None
    colour: object = None
    action: str = ""          # 1.2.15: a small button on the fact (posted to the App), "" = none
    action_label: str = ""


@dataclass
class Overview:
    status_kind: str = "idle"                 # DOT style: ok | warn | err | info | idle
    status_text: str = ""
    map_label: str = ""                       # "" = no map yet
    map_line: str = ""                        # realm · how it was found
    queue: str = ""                           # search / lobby / custom game
    thumb_rev: int = 0
    facts: list = field(default_factory=list)          # round time, server, ping, role
    actions: dict = field(default_factory=dict)        # name -> (enabled, label) / None = not shown
    note: str = ""                            # doubtful detection
    unknown: str = ""                         # banner without a known map
    today: list = field(default_factory=list)
    today_note: str = ""
    system: list = field(default_factory=list)         # [(label, text, frac | None, colour | None)]
    system_note: str = ""
    rounds: list = field(default_factory=list)         # [(map, right-hand text)]
    log_alert: bool = False


def _num(v: float, digits: int = 1) -> str:
    return f"{v:.{digits}f}"


def map_facts(app, now: float) -> list:
    r = app.round
    if r.start_t is None:
        timer = Fact(_("Rundenzeit"))
    elif r.running:
        timer = Fact(_("Rundenzeit"), fmt_duration(r.elapsed(now)), _("läuft"))
    else:
        timer = Fact(_("Rundenzeit"), fmt_duration(r.elapsed(0)), _("letzte Runde"))
    conn = app.conn
    srv = conn.server if conn.running else None            # read once: the netwatch thread replaces it
    if srv:
        server = Fact(_("Server"), region_name(srv["region"]))
    elif getattr(app, "_conn_busy", False):
        server = Fact(_("Server"), "…", _("startet"))
    elif conn.running:
        server = Fact(_("Server"), "–", _("Warte auf Match …"))
    else:
        server = Fact(_("Server"), "–", _("aus"), action="server_page", action_label=_("Server-Tab öffnen"))
    ms = conn.ping_ms if srv and srv["region"] != UNKNOWN else None
    ping = Fact(_("Ping"), f"{ms:.0f} ms", colour=ping_colour(ms)) if ms is not None else Fact(_("Ping"))
    hist, q = app._hist or {}, app._queue
    role = hist.get("role") or q.get("role")
    killer = hist.get("killer") or q.get("killer")
    if role == "killer" and killer:
        who = Fact(_("Rolle"), killer_label(app._killer_of(killer)), _("Killer"))
    elif role:
        who = Fact(_("Rolle"), app._role_name(role))
    else:
        who = Fact(_("Rolle"))
    return [timer, server, ping, who]


def actions(app) -> dict:
    has_map = app.overlay.has_map()
    on = app.user_visible and not app.hidden_after_match and not app.menu_paused
    # 1.66.3: a button that can do nothing now is not shown (it was greyed out); without a map: "Map wählen"
    out = {"scan": (True, _("Scannen")),
           "choose": None if has_map else (True, _("Map wählen …")),
           "rotate": (True, _("Drehen ↻")) if app.current is not None else None,
           "toggle": (True, _("Overlay ausblenden") if on else _("Overlay einblenden")) if has_map else None,
           "reject": (True, _("Falsch erkannt")) if app.current is not None and app.source == "auto"
           and not app.hidden_after_match else None,
           "confirm": None, "layout": None, "floor": None}
    u = app._unsure
    if u and u.get("shown"):
        out["confirm"] = (True, _("Stimmt"))
    vs = app._layouts()
    if len(vs) >= 2:
        out["layout"] = (True, _("Layout {n} von {total}", n=roman(app.current[1]), total=roman(vs[-1])) + " ▸"
                         + (" " + _("(unsicher)") if app._layout_unsure else ""))
    floors = app.overlay.floors() if app.current else []
    if floors:
        f = app._floor
        out["floor"] = (True, (_("Etage {n} von {total}", n=f + 1, total=len(floors)) if f is not None
                               else _("Beide Etagen")) + " ▸")
    return out


def today(app, now: float) -> tuple[list, str]:
    j = app._joined()
    d = history.today(j.rounds, now)
    day = history.period_start("day", now)
    s = official.summary([j.off[id(r)] for r in j.rounds if r.t >= day and id(r) in j.off and history.normal(r)])
    rounds = Fact(_("Runden"), str(d["count"]),
                  _("{k} Killer / {s} Survivor", k=d["killer"], s=d["survivor"]) if d["count"] else "")
    if s["killer"]:
        kills = Fact(_("Ø Kills"), _num(s["kills"]), _("4K: {n} von {total}", n=s["four"], total=s["killer"]),
                     frac=s["kills"] / 4)
    elif getattr(j, "matches", None):
        kills = Fact(_("Ø Kills"), sub=_("noch keine Stats-Daten"))
    else:                                      # 1.2.15: never set up – say where (it hides under "Mehr")
        kills = Fact(_("Ø Kills"), sub=_("Kills und Entkommen kommen von der Stats-Seite"),
                     action="official_setup", action_label=_("Match-Daten einrichten …"))
    if s["survivor"]:
        esc = Fact(_("Entkommen"), f"{s['escaped']:.0%}", _("{n} Survivor-Runden", n=s["survivor"]),
                   frac=s["escaped"])
    else:
        esc = Fact(_("Entkommen"), sub=_("noch keine Stats-Daten"))
    wait = Fact(_("Ø Wartezeit"), fmt_duration(d["wait"]) if d["wait"] is not None else "–",
                _("Ping {ms} ms", ms=f"{d['ping']:.0f}") if d["ping"] is not None else "")
    note = _("Spielzeit heute: {time}", time=fmt_duration(d["total"])) if d["count"] else ""
    rec = recordings(app)
    return [rounds, kills, esc, wait] + ([rec] if rec else []), note


def _gb(n: float) -> str:
    gb = n / 1024 ** 3
    return f"{gb / 1024:.2f} TB" if gb >= 1000 else f"{gb:.0f} GB"


def recordings(app) -> Fact | None:
    """1.4.2: the tile "Aufnahmen" – room on the recording drive, how many rounds, the oldest (user's wish 9).
    None while recording is off. The numbers come from the recorder thread (obsrec.Space), nothing is measured here."""
    if not app.settings.get("rec_on", False):
        return None
    sp = app.recorder.space
    if not sp.t:                                   # the recorder thread has not looked yet (first seconds)
        return Fact(_("Aufnahmen"), "–", _("Platz wird gemessen …"))
    if not sp.folder:
        why = _("Platte nicht angeschlossen") if app.settings.get("rec_folder") else _("kein Ordner gewählt")
        return Fact(_("Aufnahmen"), "–", why, colour=theme.DOT["warn"], action="rec_setup",
                    action_label=_("Aufnahmen einrichten …"))
    if not sp.total:
        return Fact(_("Aufnahmen"), "–", _("Platz wird gemessen …"))
    bits = [_("{n} Runden", n=sp.count) if sp.count != 1 else _("1 Runde"), _gb(sp.used)]
    if sp.marked:
        bits.append(_("{n} mit Marke", n=sp.marked))
    if sp.oldest:
        bits.append(_("älteste {date}", date=time.strftime("%d.%m.", time.localtime(sp.oldest))))
    colour = theme.DOT["err"] if sp.free < obsrec.MIN_FREE else theme.DOT["warn"] if sp.free < obsrec.RESERVE else None
    return Fact(_("Aufnahmen"), _("{size} frei", size=_gb(sp.free)), " · ".join(bits),
                frac=1 - sp.free / sp.total, colour=colour)


def system(app, now: float, is_win: bool) -> tuple[list, str]:
    if app.settings.get("sysinfo", "off") == "off":
        return [], _("Systemwerte sind aus (Tab Overlay → Systemwerte).")
    if not is_win:
        return [], _("Systemwerte gibt es nur unter Windows.")
    s = app.sysmon.snapshot
    if not app.sysmon.active or now - s.t > 3:
        return [], _("Erscheinen, sobald DBD läuft.")
    rows = []
    for name, temp, load, warm, hot, power in (("GPU", s.gpu_temp, s.gpu_load, sysinfo.GPU_WARM, sysinfo.GPU_HOT,
                                                s.gpu_power),
                                               ("CPU", s.cpu_temp, s.cpu_load, sysinfo.CPU_WARM, sysinfo.CPU_HOT,
                                                None)):
        parts = ([f"{temp:.0f} °C"] if temp is not None else []) + ([f"{load:.0f} %"] if load is not None else []) \
            + ([f"{power:.0f} W"] if power is not None else [])
        if parts:
            rows.append((name, " · ".join(parts), None if load is None else load / 100,
                         sysinfo.temp_colour(temp, warm, hot) if temp is not None else None))
    for name, t in (("Hotspot", s.gpu_hot), ("MEM", s.gpu_mem)):
        if t is not None:
            rows.append((name, f"{t:.0f} °C", None, sysinfo.temp_colour(t, sysinfo.SPOT_WARM, sysinfo.SPOT_HOT)))
    for name, used, total in (("VRAM", s.vram_used, s.vram_total), ("RAM", s.ram_used, s.ram_total)):
        if used is not None and total:
            rows.append((name, f"{used:.1f} / {total:.0f} GB", used / total, None))
    note = ""
    if s.throttle:
        note = _("GPU DROSSELT (TEMP.)") if s.throttle == "thermal" else _("GPU DROSSELT (HW)")
    return rows, note


def last_rounds(app, n: int = LAST_ROUNDS) -> list:
    j = app._joined()
    out = []
    for r in sorted(j.rounds, key=lambda r: r.t, reverse=True)[:n]:
        if r.custom:
            who = _("Custom Game")
        elif r.role == "killer" and r.killer:
            who = killer_label(r.killer)
        else:
            who = app._role_name(r.role)
        if r.farming and not r.custom:
            who = (who + " · " if who else "") + _("Farming")
        res = app._official_result(j.off.get(id(r)))
        parts = [p for p in (who, res if res != "–" else "", fmt_duration(r.seconds)) if p]
        out.append((r.map, " · ".join(parts)))
    return out


def overview_model(app, now: float, is_win: bool) -> Overview:
    o = Overview()
    m = app.catalog.maps.get(app.current[0]) if app.current else None
    label = m.label(app.current[1]) if m else ""
    st = user_state(app._worker_status, auto_detect=bool(app.settings.get("auto_detect", True)),
                    game_found=app.game is not None, simulate=bool(app.simulate), has_map=app.overlay.has_map(),
                    map_label=label, visible_wanted=app.user_visible, hidden_after_match=app.hidden_after_match,
                    menu_paused=app.menu_paused)
    o.status_kind, o.status_text = DOT_STYLE[st.kind], st.text
    if m:
        o.map_label = label
        o.map_line = " · ".join(t for t in (app.catalog.realm_display(m), getattr(app, "_detail", "")) if t)
    else:
        o.map_line = _("Erscheint automatisch, sobald im Match das Map-Banner kommt – oder von Hand über "
                       "„Map wählen“.")
    o.queue = app._queue_text(now)
    o.thumb_rev = getattr(app, "_thumb_rev", 0)
    o.facts = map_facts(app, now)
    o.actions = actions(app)
    u = app._unsure
    if u and u.get("shown"):
        o.note = _("Unsicher erkannt: {map} (gelesen „{name}“)", map=u["label"], name=u["name"])
    if app._unknown:
        o.unknown = _("Unbekannte Map gelesen: „{text}“", text=app._unknown[0])
    j = app._joined()                       # today and the last rounds: again only when the files or the minute change
    cache = getattr(app, "_ov_cache", None)
    if cache is None or cache[0] is not j or cache[1] != int(now // 60):
        cache = app._ov_cache = (j, int(now // 60), today(app, now), last_rounds(app))
    (o.today, o.today_note), o.rounds = cache[2], cache[3]
    o.system, o.system_note = system(app, now, is_win)
    o.log_alert = bool(getattr(app, "_log_alert", False))
    return o
