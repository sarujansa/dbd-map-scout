"""Qt control window (stage 1): colours, the overview model (pure) and the window itself (offscreen on Linux)."""
import importlib.util
import queue
import sys
import time
from types import SimpleNamespace
from unittest import mock

if "tkinter" not in sys.modules and importlib.util.find_spec("tkinter") is None:   # headless CI: Tk only imported
    sys.modules["tkinter"] = mock.MagicMock()
if isinstance(sys.modules.get("tkinter"), mock.MagicMock):
    sys.modules.setdefault("tkinter.font", mock.MagicMock())
    sys.modules.setdefault("tkinter.ttk", mock.MagicMock())

import pytest  # noqa: E402

from dbdmapscout import history, overview, qt_theme, theme  # noqa: E402
from dbdmapscout.roundtimer import RoundTimer  # noqa: E402


# ------------------------------------------------------------------ colours
def test_qt_uses_the_original_palette():
    css = qt_theme.stylesheet(True)
    for colour in (theme.DARK["bg"], theme.DARK["panel"], theme.DARK["accent"], theme.DARK["border"]):
        assert colour in css
    assert qt_theme.stylesheet(False) != css
    assert "font-size: 26px" in qt_theme.stylesheet(True, 2.0)          # zoom 200 %: 13 px -> 26 px
    assert qt_theme.hex_colour((134, 239, 172, 255)) == "#86efac"
    assert qt_theme.rgba("#3fb950", 0.5) == "rgba(63, 185, 80, 128)"
    assert theme.DOT["ok"] in qt_theme.pill_style("ok")


# ------------------------------------------------------------------ overview model
class _Map:
    custom = False

    def label(self, v):
        return "Coal Tower" + (" II" if v == 2 else "")


def fake_app(**kw):
    """The attributes and helpers overview_model() reads from App."""
    rounds = kw.pop("rounds", [])
    j = SimpleNamespace(rounds=rounds, off={})
    app = SimpleNamespace(
        current=None, source=None, catalog=SimpleNamespace(maps={"coal": _Map()}, realm_display=lambda m: "MacMillan"),
        _detail="", _worker_status="", settings={"auto_detect": True, "sysinfo": "off", "welcome_seen": True},
        game=None, simulate=False, user_visible=True, hidden_after_match=False, menu_paused=False,
        overlay=SimpleNamespace(has_map=lambda: app.current is not None, floors=lambda: []),
        round=RoundTimer(), conn=SimpleNamespace(running=False, server=None, ping_ms=None), _hist=None,
        _queue={"state": "idle"}, _unsure=None, _unknown=None, _floor=None, _layouts=lambda: [1],
        _queue_text=lambda now: "", _killer_of=lambda n: n, _role_name=lambda r: {"killer": "Killer"}.get(r, r),
        _official_result=lambda m: "–", _joined=lambda: j, sysmon=SimpleNamespace(active=False, snapshot=None))
    for k, v in kw.items():
        setattr(app, k, v)
    return app


def test_overview_without_a_map():
    o = overview.overview_model(fake_app(), time.time(), is_win=True)
    assert o.map_label == "" and o.status_kind == "idle" and "Wartet auf DBD" in o.status_text
    assert o.actions["scan"][0] and not o.actions["rotate"][0] and not o.actions["toggle"][0]
    assert not o.actions["reject"][0] and o.actions["confirm"] is None and o.actions["layout"] is None
    assert [f.title for f in o.facts] == ["Rundenzeit", "Server", "Ping", "Rolle"]
    assert o.today[0].value == "0" and o.rounds == [] and not o.welcome
    assert "aus" in o.system_note                                   # system values switched off


def test_overview_with_a_map_in_a_round():
    now = time.time()
    app = fake_app(current=("coal", 2), source="auto", _detail="automatisch erkannt (97%)",
                   _layouts=lambda: [1, 2], _queue={"state": "lobby", "role": "killer", "killer": "The Oni"},
                   conn=SimpleNamespace(running=True, server={"region": "eu-central-1", "ip": "1.2.3.4"}, ping_ms=31.0),
                   rounds=[history.Round(now - 600, 540, "coal", "Coal Tower", role="killer", killer="The Oni")])
    app.round.detected(now - 65)
    o = overview.overview_model(app, now, is_win=True)
    assert o.map_label == "Coal Tower II" and o.map_line == "MacMillan · automatisch erkannt (97%)"
    assert o.status_kind == "ok" and o.actions["reject"][0] and o.actions["rotate"][0]
    assert o.actions["layout"][1].startswith("Layout II von II")
    timer, server, ping, who = o.facts
    assert timer.value == "01:05" and server.value == "Frankfurt" and ping.value == "31 ms" and who.value == "Oni"
    assert "1.2.3.4" not in repr(o)                                 # never the server address
    assert o.today[0].value == "1" and o.rounds == [("Coal Tower", "Oni · 09:00")]


def test_overview_doubt_unknown_and_welcome():
    app = fake_app(current=("coal", 1), source="auto", _unsure={"shown": True, "label": "Coal Tower", "name": "COAL"},
                   _unknown=("SHATTERED SQUARE", ""), _qt_welcome=True)
    app.settings["welcome_seen"] = False
    o = overview.overview_model(app, time.time(), is_win=True)
    assert o.actions["confirm"] == (True, "Stimmt") and "COAL" in o.note
    assert "SHATTERED SQUARE" in o.unknown and o.welcome.startswith("So geht's")


def test_overview_system_values():
    from dbdmapscout.sysinfo import Snapshot
    now = time.time()
    snap = Snapshot(gpu_temp=88, gpu_load=97, gpu_power=220, cpu_load=51, vram_used=6, vram_total=12, t=now,
                    throttle="thermal")
    app = fake_app(sysmon=SimpleNamespace(active=True, snapshot=snap))
    app.settings["sysinfo"] = "right"
    o = overview.overview_model(app, now, is_win=True)
    names = [r[0] for r in o.system]
    assert names == ["GPU", "CPU", "VRAM"] and o.system[0][1] == "88 °C · 97 % · 220 W"
    assert o.system[0][3] is not None and o.system[2][2] == 0.5 and "DROSSELT" in o.system_note
    assert overview.overview_model(app, now, is_win=False).system == []          # not on Windows


# ------------------------------------------------------------------ the window (offscreen / Windows)
@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from dbdmapscout import qt_window
    return qt_window.application()


def test_window_shows_the_model_and_posts_clicks(qapp):
    from PIL import Image
    from dbdmapscout import qt_window
    posted = queue.Queue()
    win = qt_window.MainWindow(lambda a, arg=None: posted.put((a, arg)))
    win.apply_theme(True, 1.0)
    now = time.time()
    app = fake_app(current=("coal", 1), source="auto", _thumb_rev=1)
    app.round.detected(now - 5)
    o = overview.overview_model(app, now, is_win=True)
    win.show_model(o, Image.new("RGBA", (300, 400), (200, 0, 0, 255)), lambda k, label: "tip " + k)
    page = win.overview
    assert page.map_name.text() == "Coal Tower" and page.facts[0].value.text() == "00:05"
    assert page.thumb.pixmap() is not None and not page.thumb.pixmap().isNull()
    assert page.buttons["layout"].isHidden() and page.buttons["scan"].toolTip() == "tip scan"
    page.buttons["rotate"].click()
    win.nav.setCurrentRow(3)                                         # a page still in Tk: opens it there
    win.close()                                                      # closing = quitting, through the App
    assert [posted.get_nowait() for _i in range(3)] == [("rotate", None), ("tab", "stats"), ("quit", None)]
    text = win.geometry_b64()
    assert text and win.restore_b64(text) and not win.restore_b64("kein base64")
    o.log_alert = True
    win.show_model(o)
    assert win.nav.item(len(qt_window.PAGES) - 1).text().endswith("⚠")
    win.allow_close = True
    win.close()


def test_pixmap_from_pil_keeps_the_shape(qapp):
    from PIL import Image
    from dbdmapscout import qt_window
    pm = qt_window.pixmap_from_pil(Image.new("RGBA", (100, 200)), 50, ratio=2.0)
    assert (pm.width(), pm.height()) == (50, 100) and pm.devicePixelRatio() == 2.0
