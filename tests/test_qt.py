"""Control window (Qt): colours, the overview model (pure) and the window itself (offscreen on Linux)."""
import queue
import time
from types import SimpleNamespace

import pytest

from dbdmapscout import history, overview, qt_theme, theme
from dbdmapscout.roundtimer import RoundTimer


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
        _queue={"state": "idle"}, _unsure=None, _unknown=None, _floor=None, _layouts=lambda: [1], _layout_unsure=False,
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
                   rounds=[history.Round(max(now - 600, history.period_start("day", now)), 540, "coal", "Coal Tower",
                                         role="killer", killer="The Oni")])
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


@pytest.fixture
def keep(qapp):
    """Qt widgets of a test, deleted right after it: none may live on until the interpreter shuts down (the
    Windows job ended with a crash after all tests had passed when they did)."""
    import shiboken6
    widgets = []
    yield lambda w: widgets.append(w) or w
    for w in widgets:
        if shiboken6.isValid(w):
            w.hide()
            shiboken6.delete(w)
    qapp.processEvents()


def test_window_shows_the_model_and_posts_clicks(qapp, keep):
    from PIL import Image
    from dbdmapscout import qt_window
    posted = queue.Queue()
    win = keep(qt_window.MainWindow(lambda a, arg=None: posted.put((a, arg))))
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
    win.nav.setCurrentRow(6)                                         # another page: the App fills it
    win.close()                                                      # closing = quitting, through the App
    assert [posted.get_nowait() for _i in range(3)] == [("rotate", None), ("page", "detect"), ("quit", None)]
    text = win.geometry_b64()
    assert text and win.restore_b64(text) and not win.restore_b64("kein base64")
    o.log_alert = True
    win.show_model(o)
    assert win._log_alert and win.nav.item(len(qt_window.PAGES) - 1).text() == "Log"   # amber dot in the icon
    win.allow_close = True
    win.close()


def test_pixmap_from_pil_keeps_the_shape(qapp):
    from PIL import Image
    from dbdmapscout import qt_window
    pm = qt_window.pixmap_from_pil(Image.new("RGBA", (100, 200)), 50, ratio=2.0)
    assert (pm.width(), pm.height()) == (50, 100) and pm.devicePixelRatio() == 2.0


# ------------------------------------------------------------------ hand-made pages (SPECS)
def _registered_keys():
    """Keys passed to self._reg("…") / _slider(key=…) in the App's source (f-strings with one loop over known names expanded)."""
    import ast
    import glob
    import os
    from dbdmapscout.app_hotkeys import HOTKEY_LABELS
    pkg = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dbdmapscout")
    keys = set()
    for path in glob.glob(os.path.join(pkg, "app*.py")):
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "_slider":
                keys.update(k.value.value for k in n.keywords if k.arg == "key" and isinstance(k.value, ast.Constant))
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "_reg" and n.args:
                a = n.args[0]
                if isinstance(a, ast.Constant):
                    keys.add(a.value)
                elif isinstance(a, ast.JoinedStr):
                    pattern = "".join(v.value if isinstance(v, ast.Constant) else "{}" for v in a.values)
                    names = [k for k, _l in HOTKEY_LABELS] + ["lobby_notify", "lobby_remind", "notify_background_only",
                                                              "show_map", "focus", "caption", "timer", "server",
                                                              "waiting", "floors", "record", "transparent"]
                    keys.update(pattern.format(k) for k in names)
    return keys


def test_every_control_of_the_hand_made_pages_exists():
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from dbdmapscout import qt_window
    missing = qt_window.page_keys() - _registered_keys()
    assert not missing, sorted(missing)
    assert {"ov.caption", "st.dark", "st.hk.reject_map"} <= qt_window.page_keys()
    assert qt_window.page_keys("overview") == set()


def test_form_page_shows_states_and_posts_clicks(qapp, keep):
    from dbdmapscout import qt_window
    posted = queue.Queue()
    page = keep(qt_window.FormPage(lambda a, arg=None: posted.put((a, arg)), "Overlay", qt_window.SPECS["overlay"]))
    states = {"ov.pos": {"text": "Position"}, "ov.caption": {"text": "Map-Namen", "value": False, "enabled": True,
                                                             "visible": True, "tip": "Tipp"},
              "ov.anchor": {"value": "oben links", "values": ["automatisch", "oben links"], "enabled": True,
                            "visible": True},
              "ov.size": {"value": 36.0, "lo": 15.0, "hi": 90.0, "label": "Grösse", "text": "36 %", "visible": True},
              "ov.map_size_reset": {"text": "Zurücksetzen", "visible": False, "enabled": True},
              "ov.pos_hint": {"text": "", "visible": True}}
    page.show_states(states)
    kind, check, _x = page.controls["ov.caption"]
    assert check.text() == "Map-Namen" and not check.isChecked() and check.toolTip() == "Tipp"
    combo = page.controls["ov.anchor"][1]
    assert combo.currentText() == "oben links" and combo.count() == 2
    name, slider, value = page.controls["ov.size"][2]
    assert (slider.minimum(), slider.maximum(), slider.value(), value.text()) == (15, 90, 36, "36 %")
    assert page.controls["ov.map_size_reset"][1].isHidden() and page.controls["ov.pos_hint"][1].isHidden()
    assert page.controls["ov.pos"][1].text() == "POSITION"
    assert posted.empty()                                   # showing a state never sends anything back
    check.click()
    combo.activated.emit(0)
    slider.setValue(50)
    assert [posted.get_nowait() for _i in range(3)] == [("act", ("ov.caption", True)), ("act", ("ov.anchor", "automatisch")),
                                                        ("act", ("ov.size", 50))]


def test_maps_page_lists_by_realm_and_posts_the_pick(qapp, keep):
    from dbdmapscout import qt_window
    posted = queue.Queue()
    page = keep(qt_window.MapsPage(lambda a, arg=None: posted.put((a, arg))))
    items = [("MacMillan", "Coal Tower", "coal", 1), ("MacMillan", "Suffocation Pit", "pit", 1),
             ("Autohaven", "Azarov's Resting Place", "azarov", 1)]
    page.show_maps(items, ("pit", 1))
    assert page.tree.topLevelItemCount() == 2 and page.tree.topLevelItem(0).childCount() == 2
    assert page.tree.topLevelItem(0).child(1).font(0).bold()
    page.search.setText("coal")
    page._picked(page.tree.topLevelItem(0).child(0))
    page._pick_first()
    assert [posted.get_nowait() for _i in range(3)] == [("search", "coal"), ("show_map", ("coal", 1)),
                                                        ("show_map", ("coal", 1))]


def test_maps_page_previews_the_selected_map(qapp, keep):
    from PIL import Image
    from dbdmapscout import qt_window
    posted = queue.Queue()
    page = keep(qt_window.MapsPage(lambda a, arg=None: posted.put((a, arg))))
    page.resize(900, 700)
    items = [("MacMillan", "Coal Tower", "coal", 1), ("MacMillan", "Suffocation Pit", "pit", 1),
             ("Autohaven", "Azarov's Resting Place", "azarov", 1)]
    assert not page.p_show.isEnabled()                        # nothing selected yet: a hint, no button
    page.show_maps(items, ("pit", 1))
    pit = page.tree.topLevelItem(0).child(1)
    assert page.tree.topLevelItem(0).isExpanded() and page.tree.currentItem() is pit   # the shown map, opened
    assert posted.empty()                                     # marking it is no click
    page.tree.setCurrentItem(page.tree.topLevelItem(0).child(0))
    assert posted.get_nowait() == ("map_preview", ("coal", 1))
    page.show_preview(("coal", 1, "Coal Tower", "The MacMillan Estate", Image.new("RGBA", (200, 400), "red")))
    assert page.p_name.text() == "Coal Tower" and page.p_show.isEnabled()
    assert page.p_pic.pixmap() is not None and not page.p_pic.pixmap().isNull()
    page.p_show.click()
    assert posted.get_nowait() == ("show_map", ("coal", 1))


# ------------------------------------------------------------------ pages built from a tab of the UI model
NODE = {"kind": "box", "key": ".t", "side": "top", "row": False, "children": [
    {"kind": "big", "key": ".t.sum", "side": "top"},
    {"kind": "box", "key": ".t.row", "side": "top", "row": True, "children": [
        {"kind": "button", "key": ".t.row.clear", "side": "left"},
        {"kind": "combo", "key": ".t.row.by", "side": "right"}]},
    {"kind": "tabs", "key": ".t.nb", "side": "top", "children": [
        {"kind": "box", "key": ".t.nb.a", "side": "top", "row": False, "children": [
            {"kind": "table", "key": ".t.nb.a.tree", "side": "top"}]},
        {"kind": "box", "key": ".t.nb.b", "side": "top", "row": False, "children": [
            {"kind": "chart", "key": ".t.nb.b.chart", "side": "top"}]}]}]}


def test_auto_page_shows_a_tab(qapp, keep):
    from dbdmapscout import qt_window
    posted = queue.Queue()
    page = keep(qt_window.AutoPage(lambda a, arg=None: posted.put((a, arg)), "Statistik", NODE))
    assert page.visible_keys() >= {".t.sum", ".t.row.clear", ".t.nb.a.tree"}
    assert ".t.nb.b.chart" not in page.visible_keys()            # the other tab is not read
    states = {".t.sum": {"text": "4 Runden", "visible": True},
              ".t.row.clear": {"text": "Verlauf löschen", "enabled": True, "visible": True, "tip": ""},
              ".t.nb": {"tabs": ["Maps", "Verlauf"], "index": 0, "visible": True},
              ".t.nb.a.tree": {"visible": True, "selectable": True, "selection": ["I002"],
                               "columns": [("#0", "Region", "w"), ("ping", "Ping", "e")],
                               "colours": {"p_bad": "#e06c6c"},
                               "rows": [("g:eu", 0, "☑ Europa", [], [], True),
                                        ("I002", 1, "Frankfurt", ["31 ms"], ["p_bad"], False)]}}
    page.show_states(states)
    tw = page.controls[".t.nb"][1]
    assert [tw.tabText(i) for i in range(tw.count())] == ["Maps", "Verlauf"]
    table = page.controls[".t.nb.a.tree"][1]
    eu = table.topLevelItem(0)
    assert eu.text(0) == "☑ Europa" and eu.child(0).text(1) == "31 ms" and eu.child(0).isSelected()
    assert posted.empty()
    table.itemClicked.emit(eu.child(0), 0)
    table._sort(1)
    tw.setCurrentIndex(1)
    assert [posted.get_nowait() for _i in range(3)] == [("act", (".t.nb.a.tree", ("click", "I002"))),
                                                        ("act", (".t.nb.a.tree", ("sort", "ping"))),
                                                        ("act", (".t.nb", 1))]
    assert ".t.nb.b.chart" in page.visible_keys()


def test_filling_tabs_take_the_page_and_tick_boxes_show(qapp, keep):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QScrollArea
    from dbdmapscout import qt_window
    node = {"kind": "box", "key": ".s", "side": "top", "row": False, "children": [
        {"kind": "tabs", "key": ".s.nb", "side": "top", "fill": True, "children": [
            {"kind": "box", "key": ".s.nb.a", "side": "top", "row": False, "children": [
                {"kind": "table", "key": ".s.nb.a.tree", "side": "top", "fit": False}]}]},
        {"kind": "table", "key": ".s.regions", "side": "top", "fit": True}]}
    page = keep(qt_window.AutoPage(lambda a, arg=None: None, "Statistik", node))
    tw = page.controls[".s.nb"][1]
    assert isinstance(tw.widget(0), QScrollArea)               # the tab's page scrolls, the filters stay
    assert not any(sa.isAncestorOf(tw) for sa in page.findChildren(QScrollArea))   # the page itself does not
    regions = page.controls[".s.regions"][1]
    page.show_states({".s.regions": {"visible": True, "selectable": True, "selection": [], "colours": {},
                                     "columns": [("#0", "Region", "w"), ("ping", "Ping", "e")], "stretch": 0,
                                     "widths": [215, 78],
                                     "rows": [("g:eu", 0, "Europa", [], ["group", "check:part"], True),
                                              ("r:fra", 1, "Frankfurt", ["31 ms"], ["check:on"], False),
                                              ("r:dub", 1, "Irland", ["40 ms"], ["check:off"], False)]}})
    eu = regions.topLevelItem(0)
    assert [eu.checkState(0), eu.child(0).checkState(0), eu.child(1).checkState(0)] == \
        [Qt.PartiallyChecked, Qt.Checked, Qt.Unchecked]
    assert regions.maximumHeight() < 300                      # as tall as its three rows, no empty box
    assert regions.columnWidth(1) >= 78                       # the model's width: room for "31 ms"


def test_cards_can_be_put_in_own_order(qapp, keep):
    """Drag a card at its grip: the others make room, the new order is posted and comes back after a restart;
    an order that does not fit (other version) shows the built-in one."""
    from PySide6.QtCore import Qt
    from dbdmapscout import qt_window
    posted = queue.Queue()
    spec = (("card", "a", (("hint", "a.t"),)), ("card", "b", (("hint", "b.t"),)), ("card", "c", (("hint", "c.t"),)),
            ("row", (("button", "more"), ("stretch",))), ("card", "d", (("hint", "d.t"),)))
    page = keep(qt_window.FormPage(lambda a, arg=None: posted.put((a, arg)), "Einstellungen", spec, "settings"))
    page.resize(700, 900)
    page.show()
    qapp.processEvents()
    first, second = page.columns                              # the "more" button splits the cards
    assert first.ids() == ["a", "b", "c"] and second.ids() == ["d"]
    card_c = dict(first.cards)["c"]
    grip = card_c.findChild(qt_window.Grip)
    assert grip is not None
    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest
    top = dict(first.cards)["a"]
    QTest.mousePress(grip, Qt.LeftButton, Qt.NoModifier, QPoint(8, 9))     # the mouse at the grip
    assert card_c.property("dragging") is True
    target = grip.mapFromGlobal(first.mapToGlobal(top.geometry().topLeft()))
    QTest.mouseMove(grip, target)                                          # up to the top
    QTest.mouseRelease(grip, Qt.LeftButton, Qt.NoModifier, target)
    assert first.ids() == ["c", "a", "b"] and card_c.property("dragging") is False
    assert posted.get_nowait() == ("card_order", ("settings", 0, ["c", "a", "b"]))
    first.begin(card_c)
    first.end()                                                # picked up and put down: nothing to save
    assert posted.empty()
    page.apply_order({"0": ["b", "c", "a"]})
    assert first.ids() == ["b", "c", "a"]
    page.apply_order({"0": ["b", "x", "a"]})                   # unknown card: built-in order
    assert first.ids() == ["a", "b", "c"]


def test_chart_draws_columns_and_a_line(qapp, keep):
    from dbdmapscout import qt_window
    chart = keep(qt_window.Chart())
    chart.resize(600, 400)
    bars = [(2.5, "KW 40", "2,5 Kills · 4 Runden"), (None, "KW 41", ""), (3.0, "KW 42", "3,0 Kills · 2 Runden")]
    temps = [(71.0, "Mo", "71 °C"), (74.0, "Di", "74 °C")]
    chart.show_state({"dark": True, "panels": ("killer", "temp"), "data": {
        "killer": {"title": "Killer", "empty": "", "ticks": [(0, "0"), (4, "4")], "max": 4, "bars": bars,
                   "last": "3,0"},
        "temp": {"title": "GPU", "empty": "", "ticks": [(70, "70")], "max": 76, "min": 70, "bars": temps,
                 "last": "74 °C", "kind": "line"}}})
    img = chart.grab().toImage()
    assert not img.isNull() and len(chart._hits) == 4               # 2 columns + 2 points, hover areas
    assert chart.minimumHeight() == 2 * (chart.PANEL_H + 10)


def test_question_bar_asks_instead_of_a_dialog(qapp, keep):
    from dbdmapscout import qt_window
    posted = queue.Queue()
    win = keep(qt_window.MainWindow(lambda a, arg=None: posted.put((a, arg))))
    win.show_question(("Verlauf löschen", "Alle <Runden> löschen?", True))
    assert not win.question.isHidden() and "&lt;Runden&gt;" in win.question_text.text()
    assert not win.question_cancel.isHidden()
    win.question_ok.click()
    win.show_question(("Hinweis", "Nur zur Info", False))
    assert win.question_cancel.isHidden()
    win.show_question(None)
    assert win.question.isHidden() and posted.get_nowait() == ("answer", True)
    win.allow_close = True
    win.close()


def test_ask_runs_the_action_again_after_ok():
    from dbdmapscout.app_qt import QtShell
    calls = []

    class Shell(QtShell):
        qt = SimpleNamespace(bring_to_front=lambda: None)
        _qt_question = None

        def _qt_refresh(self, force=False):
            pass

        def clear(self):
            if self._ask("Verlauf löschen", "Sicher?", self.clear):
                calls.append("cleared")

    s = Shell()
    s.clear()
    assert calls == [] and s._qt_question[0] == "Verlauf löschen"
    s._qt_answer(False)
    assert calls == [] and s._qt_question is None
    s.clear()
    s._qt_answer(True)
    assert calls == ["cleared"] and s._qt_question is None


# ------------------------------------------------------------------ detection, log, hotkeys, files
def test_log_view_colours_and_escapes(qapp, keep):
    from dbdmapscout import qt_window
    log = keep(qt_window.LogView())
    log.show_state({"dark": True, "lines": [("12:00:01", "Fehler", "<kaputt>"), ("12:00:02", "System", "Bereit.")]})
    text = log.toPlainText()
    assert "<kaputt>" in text and "Bereit." in text and text.index("kaputt") < text.index("Bereit")
    log.show_state({"dark": True, "lines": [("12:00:01", "Fehler", "<kaputt>"), ("12:00:02", "System", "Bereit.")]})



def test_log_view_appends_new_lines_and_rebuilds_only_when_needed(qapp, keep):
    from dbdmapscout import qt_window
    log = keep(qt_window.LogView())
    a, b, c = ("12:00:01", "System", "eins"), ("12:00:02", "System", "zwei"), ("12:00:03", "Fehler", "drei")
    log.show_state({"dark": True, "rev": 0, "lines": [a, b]})
    doc = log.document()
    first = doc.firstBlock()
    log.show_state({"dark": True, "rev": 0, "lines": [a, b, c]})
    assert doc.blockCount() == 3 and doc.firstBlock() == first          # appended, the old lines untouched
    assert log.toPlainText().splitlines()[-1].endswith("drei")
    log.show_state({"dark": True, "rev": 1, "lines": [c]})               # filter changed: shown anew
    assert log.toPlainText().strip().endswith("drei") and "eins" not in log.toPlainText()
    many = [(f"12:{i // 60:02d}:{i % 60:02d}", "System", f"Zeile {i}") for i in range(500)]
    log.show_state({"dark": True, "rev": 2, "lines": many})
    assert doc.blockCount() <= qt_window.LogView.MAX_LINES               # never more than the last 400


def test_table_updates_values_in_place(qapp, keep):
    from dbdmapscout import qt_window
    t = keep(qt_window.Table(".t", lambda a, arg=None: None))
    cols = [("#0", "Region", "w"), ("ping", "Ping", "e")]
    rows = [("g:eu", 0, "Europa", [], [], True), ("r:fra", 1, "Frankfurt", ["31 ms"], ["p_good"], False)]
    colours = {"p_good": "#7cc47f", "p_bad": "#e06c6c"}
    t.show_state({"columns": cols, "rows": rows, "colours": colours, "selection": [], "selectable": True})
    fra = t.topLevelItem(0).child(0)
    rows2 = [rows[0], ("r:fra", 1, "Frankfurt", ["95 ms"], ["p_bad"], False)]
    t.show_state({"columns": cols, "rows": rows2, "colours": colours, "selection": ["r:fra"], "selectable": True})
    assert t.topLevelItem(0).child(0) is fra                             # same item: no rebuild
    assert fra.text(1) == "95 ms" and fra.foreground(1).color().name() == "#e06c6c" and fra.isSelected()
    rows3 = rows2 + [("r:lon", 1, "London", ["40 ms"], [], False)]
    t.show_state({"columns": cols, "rows": rows3, "colours": colours, "selection": [], "selectable": True})
    assert t.topLevelItem(0).childCount() == 2                           # another row: built anew

def test_hotkey_button_sends_the_keys_while_recording(qapp, keep):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from dbdmapscout import qt_window
    posted = queue.Queue()
    b = keep(qt_window.HotkeyButton("st.hk.rotate_map", lambda a, arg=None: posted.put((a, arg))))
    QTest.keyClick(b, Qt.Key_K, Qt.ControlModifier)                 # not recording: nothing
    assert posted.empty()
    b.click()
    QTest.keyClick(b, Qt.Key_Control)                               # a modifier alone: still waiting
    QTest.keyClick(b, Qt.Key_K, Qt.ControlModifier | Qt.AltModifier)
    QTest.keyClick(b, Qt.Key_F5)
    assert [posted.get_nowait() for _i in range(3)] == [
        ("hk_record", "st.hk.rotate_map"), ("hk_key", ("st.hk.rotate_map", ["ctrl", "alt"], "k", None)),
        ("hk_key", ("st.hk.rotate_map", [], "F5", None))]
    b.show_recording(True)
    b.show_recording(False)                                         # the App saved it: stop sending keys
    QTest.keyClick(b, Qt.Key_M, Qt.ControlModifier | Qt.AltModifier)
    assert posted.empty()


def test_auto_page_lays_out_a_grid(qapp, keep):
    from dbdmapscout import qt_window
    node = {"kind": "card", "key": ".l", "row": False, "grid": True, "children": [
        {"kind": "check", "key": f".l.c{i}", "cell": (i // 5, i % 5)} for i in range(9)]}
    page = keep(qt_window.AutoPage(lambda a, arg=None: None, "Erkennung", node))
    page.show_states({f".l.c{i}": {"text": f"L{i}", "value": i < 2, "enabled": True, "visible": True}
                      for i in range(9)})
    checks = [page.controls[f".l.c{i}"][1] for i in range(9)]
    assert [c.isChecked() for c in checks[:3]] == [True, True, False] and checks[8].text() == "L8"


def test_file_choice_is_not_modal(qapp, keep):
    from dbdmapscout import qt_window
    posted = queue.Queue()
    win = keep(qt_window.MainWindow(lambda a, arg=None: posted.put((a, arg))))
    win.choose_file("save", "Einstellungen exportieren", "x.json")
    dlg = win._file_dialog
    assert not dlg.isModal() or dlg.windowModality() != 2               # never application-modal
    dlg.reject()
    assert posted.get_nowait() == ("file", None)


def test_hotkey_from_the_window_is_checked():
    from dbdmapscout.app_hotkeys import Hotkeys
    seen = []

    class H(Hotkeys):
        _hk_rec, _hk_mods = "rotate_map", set()

        def _hk_key(self, e):
            seen.append((set(self._hk_mods), e.keysym, e.keycode))

    h = H()
    h._hk_qt_key("rotate_map", ["ctrl", "alt"], "k", None)
    h._hk_qt_key("scan_now", ["ctrl"], "s", None)                    # not the one recording: ignored
    assert seen == [({"ctrl", "alt"}, "k", None)]


# ------------------------------------------------------------------ dialogs
def test_dialog_window_mirrors_and_closes_both_ways(qapp, keep):
    from PIL import Image
    from dbdmapscout import qt_window
    posted = queue.Queue()
    node = {"kind": "box", "key": ".d", "row": False, "children": [
        {"kind": "radio", "key": ".d.new"}, {"kind": "entry", "key": ".d.name"},
        {"kind": "combo", "key": ".d.realm"}, {"kind": "image", "key": ".d.after"},
        {"kind": "button", "key": ".d.save"}]}
    win = keep(qt_window.MainWindow(lambda a, arg=None: posted.put((a, arg))))
    win.open_dialog(".d", "Kartenbild hinzufügen", node)
    dlg = win.dialogs[".d"]
    pic = Image.new("RGBA", (80, 120), (200, 0, 0, 255))
    win.show_dialog_states(".d", {
        ".d.new": {"text": "Neue Map", "value": True, "enabled": True, "visible": True},
        ".d.name": {"value": "Shattered Square", "enabled": True, "visible": True},
        ".d.realm": {"value": "Ormond", "values": ["Autohaven"], "editable": True, "enabled": True, "visible": True},
        ".d.after": {"text": "Ergebnis", "pil": pic, "visible": True},
        ".d.save": {"text": "Speichern", "enabled": True, "visible": True}})
    c = dlg.page.controls
    assert c[".d.new"][1].isChecked() and c[".d.name"][1].text() == "Shattered Square"
    assert c[".d.realm"][1].isEditable() and c[".d.realm"][1].currentText() == "Ormond"
    assert not c[".d.after"][1].pixmap().isNull()
    assert posted.empty()
    c[".d.name"][1].textEdited.emit("Shattered Sq")
    c[".d.new"][1].click()
    assert [posted.get_nowait() for _i in range(2)] == [("act", (".d.name", "Shattered Sq")), ("act", (".d.new", None))]
    win.close_dialog(".d")                                    # closed by the App (saved): no echo back
    assert posted.empty() and ".d" not in win.dialogs
    win.open_dialog(".d", "x", node)
    win.dialogs[".d"].reject()                                # Esc / X: the model's dialog goes too
    assert posted.get_nowait() == ("dlg_close", ".d")


def test_navigation_icons_are_drawn_alike(qapp, keep):
    """Own line icons (not font characters, which came out in different sizes): every page one, same box, and the
    log's gets an amber dot while there is an unseen error."""
    from dbdmapscout import qt_window
    for key, _label in qt_window.PAGES:
        img = qt_window.nav_icon(key, "#c9a227", 2.0).toImage()
        assert (img.width(), img.height()) == (2 * qt_window.NAV_ICON, 2 * qt_window.NAV_ICON)
        assert any(img.pixelColor(x, y).alpha() > 0 for x in range(0, img.width(), 2) for y in range(0, img.height(), 2))
    plain = qt_window.nav_icon("log", "#9ba1a9").toImage()
    alert = qt_window.nav_icon("log", "#9ba1a9", alert=True).toImage()
    assert plain != alert
    win = keep(qt_window.MainWindow(lambda a, arg=None: None))
    assert all(not win.nav.item(i).icon().isNull() for i in range(win.nav.count()))
    assert [win.nav.item(i).text() for i in range(win.nav.count())][-1] == "Log"
    win.show_log_alert(True)
    assert win.nav.item(win.nav.count() - 1).text() == "Log"           # the dot is in the icon, not in the text


def _dash_data():
    """Rounds with official matches: Nurse on Coal Tower 3 kills ×2, Oni on The Game once (too few for a cell),
    one survivor round escaped."""
    from dbdmapscout.official import Match, Player

    def km(r, n):
        return Match(t=r.t, map=r.map, role="killer", character=r.killer, bp=30000,
                     opp=[Player("survivor", "", "DEAD" if i < n else "ESCAPED") for i in range(4)])
    rs = [history.Round(t=100.0 + i, seconds=600, map_id=m, map=m, role=role, killer=k)
          for i, (m, role, k) in enumerate([("Coal Tower", "killer", "The Nurse"), ("Coal Tower", "killer", "The Nurse"),
                                            ("The Game", "killer", "The Oni"), ("The Game", "survivor", "")])]
    pairs = [(rs[0], km(rs[0], 3)), (rs[1], km(rs[1], 3)), (rs[2], km(rs[2], 4)),
             (rs[3], Match(t=rs[3].t, map="The Game", role="survivor", status="ESCAPED"))]
    return rs, pairs


def test_dashboard_model():
    from dbdmapscout import dashboard
    rs, pairs = _dash_data()
    d = dashboard.build(rs, pairs)
    titles = [t.title for t in d.tiles]
    assert titles[:3] == ["Runden", "Ø Kills", "Entkommen"] and d.tiles[0].value == "4"
    assert d.tiles[1].value == "3.33" and abs(d.tiles[1].frac - 10 / 12) < 1e-9 and d.tiles[2].value == "100%"
    assert [m for m, _n, _r in d.maps] == ["Coal Tower", "The Game"] and d.maps_max == 2
    assert "Ø 3.0 Kills" in d.maps[0][2] and "100% entkommen" in d.maps[1][2]
    assert d.rows == ["Coal Tower"] and d.columns == ["The Nurse"]          # Oni: one round – no cell, no column
    assert d.cells == {("Coal Tower", "The Nurse"): (3.0, 2)}
    assert dashboard.build([], []).empty and dashboard.short_killer("The Nurse") == "Nurse"
    assert dashboard.play_time(7200) == "2.0 h" and ":" in dashboard.play_time(600)


def test_dashboard_view_draws_tiles_bars_and_heatmap(qapp, keep):
    from dbdmapscout import dashboard, qt_window
    rs, pairs = _dash_data()
    v = keep(qt_window.DashboardView())
    v.resize(900, 700)
    v.show_state({"data": dashboard.build(rs, pairs), "dark": True})
    v.show()
    img = v.grab().toImage()
    assert not img.isNull() and not v.tiles_box.isHidden() and not v.heat.isHidden()
    assert v.tiles[0][1].value.text() == "4" and v.tiles[5][0].isVisible()
    assert len(v.heat._hits) == 1 and "Nurse" in v.heat._hits[0][1] and "2 Runden" in v.heat._hits[0][1]
    v.show_state({"data": dashboard.build([], []), "dark": True})
    assert v.tiles_box.isHidden() and not v.empty.isHidden()
    assert qt_window.heat_colour(4, dark=True) != qt_window.heat_colour(0, dark=True)
    assert qt_window.ink_on(qt_window.heat_colour(4, dark=False)).name() == "#f0efec"   # light ink on dark blue


def test_narrow_window_wraps_instead_of_cutting_off(qapp, keep):
    """1.59.1 (user's screenshots): rows of controls wrap, tiles take fewer columns, tick box texts wrap, the
    navigation shows only icons – nothing wider than the window."""
    from PySide6.QtWidgets import QPushButton, QWidget
    from dbdmapscout import qt_window
    from dbdmapscout.qt_layouts import FlowRow, TileGrid, WrapCheck
    host = keep(QWidget())
    row = FlowRow(host)
    row.right = 1
    buttons = [QPushButton(f"Knopf Nummer {i}") for i in range(5)]
    for b in buttons:
        row.addWidget(b)
    wide, narrow = row.sizeHint().width() + 50, 260
    assert row.heightForWidth(wide) < row.heightForWidth(narrow)              # wraps into more lines
    host.resize(wide, 200)
    row.setGeometry(host.rect())
    assert buttons[-1].geometry().right() == wide - 1                         # one line: the last one right
    assert row.minimumSize().width() <= max(b.sizeHint().width() for b in buttons)
    grid = TileGrid(keep(QWidget()), min_width=150, columns=6)
    for _i in range(4):
        grid.addWidget(QWidget())
    assert grid.cols_for(1200) == 4 and grid.cols_for(500) == 2 and grid.cols_for(100) == 1   # 2 × 2, not 3 + 1
    check = keep(WrapCheck())
    check.setText("Etagen (Midwich) untereinander zeigen (aus: nur die untere) " * 3)
    assert check.minimumSizeHint().width() < 300                              # the text wraps
    win = keep(qt_window.MainWindow(lambda a, arg=None: None))
    win.resize(1200, 800)
    win.show()
    qapp.processEvents()
    assert win.nav.maximumWidth() == qt_window.NAV_W and win.nav.item(0).text()
    win.resize(780, 800)
    qapp.processEvents()
    assert win.nav.maximumWidth() == qt_window.NAV_COMPACT_W and not win.nav.item(0).text() and win.nav.item(0).toolTip()
