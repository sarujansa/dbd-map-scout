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
    # 1.66.3: buttons that can do nothing now are not there (were greyed out); "Map wählen" leads to the maps
    assert o.actions["scan"][0] and o.actions["choose"] == (True, "Map wählen …")
    assert o.actions["rotate"] is None and o.actions["toggle"] is None and o.actions["reject"] is None
    assert o.actions["confirm"] is None and o.actions["layout"] is None
    assert [f.title for f in o.facts] == ["Rundenzeit", "Server", "Ping", "Rolle"]
    assert o.today[0].value == "0" and o.rounds == []
    # 1.2.15: dead ends get a button – "Server aus" leads to the server tab, no stats data ever to the setup
    assert (o.facts[1].action, o.facts[1].action_label) == ("server_page", "Server-Tab öffnen")
    assert o.today[1].action == "official_setup" and o.today[2].action == ""
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
    assert o.status_kind == "ok" and o.actions["reject"][0] and o.actions["rotate"][0] and o.actions["choose"] is None
    assert o.actions["layout"][1].startswith("Layout II von II")
    timer, server, ping, who = o.facts
    assert timer.value == "01:05" and server.value == "Frankfurt" and ping.value == "31 ms" and who.value == "Oni"
    assert "1.2.3.4" not in repr(o)                                 # never the server address
    assert o.today[0].value == "1" and o.rounds == [("Coal Tower", "Oni · 09:00")]


def test_overview_doubt_and_unknown():
    app = fake_app(current=("coal", 1), source="auto", _unsure={"shown": True, "label": "Coal Tower", "name": "COAL"},
                   _unknown=("SHATTERED SQUARE", ""))
    o = overview.overview_model(app, time.time(), is_win=True)
    assert o.actions["confirm"] == (True, "Stimmt") and "COAL" in o.note
    assert "SHATTERED SQUARE" in o.unknown


def test_overview_system_values():
    from dbdmapscout.sysinfo import Snapshot
    now = time.time()
    snap = Snapshot(gpu_temp=88, gpu_load=97, gpu_power=220, cpu_load=51, vram_used=6, vram_total=12, t=now,
                    throttle="thermal")
    app = fake_app(sysmon=SimpleNamespace(active=True, snapshot=snap))
    app.settings["sysinfo"] = "right"
    o = overview.overview_model(app, now, is_win=True)
    names = [r[0] for r in o.system]
    assert names == ["CPU", "GPU", "VRAM"] and o.system[1][1] == "88 °C · 97 % · 220 W"   # 1.7.5: HUD order
    assert o.system[1][3] is not None and o.system[2][2] == 0.5 and "DROSSELT" in o.system_note
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
    win.nav.setCurrentRow([k for k, _l in qt_window.PAGES].index("detect"))   # another page: the App fills it
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
    from dbdmapscout.app import LANGS
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
                                                              "waiting", "floors", "record", "transparent"] + \
                        [code for code, _l in LANGS]
                    keys.update(pattern.format(k) for k in names)
    return keys


def test_every_control_of_the_hand_made_pages_exists():
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from dbdmapscout import qt_window
    missing = qt_window.page_keys() - _registered_keys()
    assert not missing, sorted(missing)
    assert {"ov.caption", "st.dark", "st.hk.reject_map"} <= qt_window.page_keys()
    assert qt_window.page_keys("overview") == set()
    from dbdmapscout.app import LANGS
    assert qt_window.GAME_LANGS == tuple(code for code, _l in LANGS)


def test_form_page_shows_states_and_posts_clicks(qapp, keep):
    from dbdmapscout import qt_window
    posted = queue.Queue()
    page = keep(qt_window.FormPage(lambda a, arg=None: posted.put((a, arg)), "Overlay", qt_window.SPECS["overlay"]))
    states = {"ov.pos": {"text": "Position"}, "ov.caption": {"text": "Map-Namen", "value": False, "enabled": True,
                                                             "visible": True, "tip": "Tipp"},
              "ov.anchor": {"value": "oben links", "values": ["automatisch", "oben links"], "enabled": True,
                            "visible": True},
              "ov.sel_size": {"value": 36.0, "lo": 15.0, "hi": 90.0, "label": "Grösse", "text": "36 %", "visible": True},
              "ov.map_size_reset": {"text": "Zurücksetzen", "visible": False, "enabled": True},
              "ov.pos_hint": {"text": "", "visible": True}}
    page.show_states(states)
    kind, check, _x = page.controls["ov.caption"]
    assert check.text() == "Map-Namen" and not check.isChecked() and check.toolTip() == "Tipp"
    combo = page.controls["ov.anchor"][1]
    assert combo.currentText() == "oben links" and combo.count() == 2
    name, slider, value = page.controls["ov.sel_size"][2]
    assert (slider.minimum(), slider.maximum(), slider.value(), value.text()) == (15, 90, 36, "36 %")
    assert page.controls["ov.map_size_reset"][1].isHidden() and page.controls["ov.pos_hint"][1].isHidden()
    kind, tabs, body = page.controls["ov.pos"]                 # 1.66.4: the cards of the page are tabs
    index = tabs.indexOf(body)                                 # 1.7.6: addressed by widget – tabs can be moved
    assert kind == "tab" and tabs.tabText(index) == "Allgemein" and tabs.count() == 5   # 1.2.12: one per element
    assert [tabs.tabText(i) for i in range(5)] == ["Karte", "Systemwerte", "Heute", "Musik", "Allgemein"]
    page.show_states({"ov.sys": {"text": "Systemwerte", "visible": False}})
    assert not tabs.isTabVisible(tabs.indexOf(page.controls["ov.sys"][2])) and tabs.isTabVisible(index)
    assert posted.empty()                                   # showing a state never sends anything back
    check.click()
    combo.activated.emit(0)
    slider.setValue(50)
    assert [posted.get_nowait() for _i in range(3)] == [("act", ("ov.caption", True)), ("act", ("ov.anchor", "automatisch")),
                                                        ("act", ("ov.sel_size", 50))]


def test_maps_page_lists_by_realm_and_posts_the_pick(qapp, keep, tmp_path):
    """1.66.4 (variant A): realms left with counts, "Alle Maps" / "Zuletzt gespielt" on top, the tiles of the
    chosen realm; the realm of the shown map first; the search shows all realms."""
    from PIL import Image
    from PySide6.QtCore import Qt
    from dbdmapscout import qt_window
    posted = queue.Queue()
    page = keep(qt_window.MapsPage(lambda a, arg=None: posted.put((a, arg))))
    items = [("MacMillan", "Coal Tower", "coal", 1), ("MacMillan", "Suffocation Pit", "pit", 1),
             ("Autohaven", "Azarov's Resting Place", "azarov", 1)]
    pic = tmp_path / "coal.png"
    Image.new("RGBA", (300, 600), "red").save(pic)
    page.show_maps(items, ("pit", 1), {("coal", 1): str(pic)}, ["azarov"])
    rows = [page.realms.item(i).text() for i in range(page.realms.count())]
    assert rows == ["Alle Maps\t3", "Zuletzt gespielt\t1", "MacMillan\t2", "Autohaven\t1"]
    assert page.realms.currentItem().data(Qt.UserRole) == "MacMillan"           # the realm of the shown map
    assert set(page._tiles) == {("coal", 1), ("pit", 1)} and page._tiles[("pit", 1)].property("current")
    while page._todo:
        page._load_some()
    assert not page._tiles[("coal", 1)].pic.pixmap().isNull()
    page.realms.setCurrentRow(1)
    assert set(page._tiles) == {("azarov", 1)}
    page.realms.setCurrentRow(0)
    assert len(page._tiles) == 3
    page.search.setText("coal")
    page.show_in_game(("coal", 1))
    page._pick_first()
    assert [posted.get_nowait() for _i in range(3)] == [("search", "coal"), ("show_map", ("coal", 1)),
                                                        ("show_map", ("coal", 1))]


def test_maps_page_shows_a_map_big_after_a_click(qapp, keep):
    from PIL import Image
    from dbdmapscout import qt_window
    posted = queue.Queue()
    page = keep(qt_window.MapsPage(lambda a, arg=None: posted.put((a, arg))))
    page.resize(900, 700)
    items = [("MacMillan", "Coal Tower", "coal", 1), ("MacMillan", "Suffocation Pit", "pit", 1)]
    page.show_maps(items, ("pit", 1))
    assert posted.empty() and page.stack.currentIndex() == 0          # marking the shown map is no click
    page.clicked(("coal", 1))
    page.show_in_game(("coal", 1))                                     # a double click: no big view
    page._clicker.timeout.emit()
    assert posted.get_nowait() == ("show_map", ("coal", 1)) and page.stack.currentIndex() == 0
    page.clicked(("coal", 1))
    page._clicker.timeout.emit()
    assert posted.get_nowait() == ("map_preview", ("coal", 1)) and page.stack.currentIndex() == 1
    page.show_preview(("coal", 1, "Coal Tower", "The MacMillan Estate", Image.new("RGBA", (200, 400), "red")))
    assert page.p_name.text() == "Coal Tower" and page.p_show.isEnabled()
    assert page.p_pic.pixmap() is not None and not page.p_pic.pixmap().isNull()
    page.p_show.click()
    assert posted.get_nowait() == ("show_map", ("coal", 1))
    page.p_back.click()
    assert page.stack.currentIndex() == 0


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


def test_moved_card_keeps_the_page_still_and_tabs_in_shown_order(qapp, keep):
    """1.62.2 (user: Updates at position 2, a click made the page jump down): a button that disables itself
    took the focus by click and passed it on in the tab order of creation – to a card far below."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QPushButton, QScrollArea
    from dbdmapscout import qt_window
    posted = queue.Queue()
    spec = tuple(("card", k, (("button", k + ".b"),) + tuple(("hint", f"{k}.h{i}") for i in range(12)))
                 for k in "abcd")
    page = keep(qt_window.FormPage(lambda a, arg=None: posted.put((a, arg)), "Einstellungen", spec, "settings"))
    page.resize(700, 400)
    page.show()
    for k in "abcd":
        page.controls[k + ".h0"][1].setText("Zeile\n" * 4)
    page.apply_order({"0": ["a", "d", "b", "c"]})
    qapp.processEvents()
    button = page.controls["d.b"][1]
    assert isinstance(button, QPushButton) and not button.focusPolicy() & Qt.ClickFocus
    bar = page.findChildren(QScrollArea)[0].verticalScrollBar()
    bar.setValue(0)
    button.clicked.connect(lambda: button.setEnabled(False))   # like "Jetzt nach Updates suchen"
    QTest.mouseClick(button, Qt.LeftButton, Qt.NoModifier, QPoint(5, 5))
    qapp.processEvents()
    assert bar.value() == 0
    chain, w = [], page.controls["a.b"][1]
    for _ in range(4):
        chain.append(w)
        w = w.nextInFocusChain()
        while not isinstance(w, QPushButton):
            w = w.nextInFocusChain()
    assert chain == [page.controls[k + ".b"][1] for k in "adbc"]


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


def test_setup_assistant_goes_through_its_steps(qapp, keep):
    """1.60: first start = three steps (language, overlay, keys) with the widgets of the pages; done or skipped
    posts setup_done; the navigation leads away from it."""
    from dbdmapscout import qt_window
    posted = queue.Queue()
    win = keep(qt_window.MainWindow(lambda a, arg=None: posted.put((a, arg))))
    win.show_setup(True)
    assert win.current_key() == "setup" and win.stack.currentWidget() is win.setup
    s = win.setup
    assert s.steps.currentIndex() == 0 and not s.back.isEnabled() and s.next.text() == "Weiter"
    assert qt_window.page_keys("setup") >= {"det.lang.en", "ov.anchor", "ov.test", "st.hk.toggle_overlay"}
    win.show_states("setup", {"det.lang.en": {"text": "EN", "value": True, "enabled": True, "visible": True}})
    assert s.pages[0].controls["det.lang.en"][1].isChecked()
    s.next.click()
    s.next.click()
    assert s.steps.currentIndex() == 2 and s.next.text() == "Weiter"
    s.next.click()                                            # 1.2.15: step 4 "Match-Daten" (stats page link)
    assert s.steps.currentIndex() == 3 and s.next.text() == "Fertig"
    assert qt_window.page_keys("setup") >= {"setup.script", "setup.open_site", "setup.off_notify"}
    s.next.click()
    s.skip.click()
    assert [posted.get_nowait()[0] for _i in range(2)] == ["setup_done", "setup_done"]
    win.show_page("stats")
    assert win.current_key() == "stats" and win.stack.currentWidget() is not win.setup


def test_search_finds_a_setting_and_lights_its_card(qapp, keep):
    from dbdmapscout import qt_window
    posted = queue.Queue()
    win = keep(qt_window.MainWindow(lambda a, arg=None: posted.put((a, arg))))
    win.resize(1100, 800)
    win.show()
    qapp.processEvents()
    assert posted.empty()                                     # opening the window does not focus the search
    win.search.setFocus()
    qapp.processEvents()
    assert ("search_open", None) in [posted.get_nowait() for _i in range(posted.qsize())]   # App fills the pages
    win.show_states("overlay", {"ov.caption": {"text": "Map-Namen über der Karte anzeigen", "value": False,
                                               "enabled": True, "visible": True},
                                "ov.look": {"text": "Darstellung", "visible": True}})
    win.update_search_index()
    hits = [e for e in win._found if e.startswith("Map-Namen über")]
    assert hits == ["Map-Namen über der Karte anzeigen  ·  Overlay"]
    win.go_to_found(hits[0])
    assert win.current_key() == "overlay" and win.search.text() == ""
    qapp.processEvents()
    tabs = win.forms["overlay"].controls["ov.look"][1]      # 1.66.4: on another tab – that tab is opened
    assert tabs.currentWidget() is win.forms["overlay"].controls["ov.look"][2] and tabs.property("found") is True


def test_open_tab_shows_an_elements_settings(qapp, keep):
    """1.2.12 (analysis point 10): a click on an element in the preview opens its tab of the overlay page."""
    from dbdmapscout import qt_window
    win = keep(qt_window.MainWindow(lambda a, arg=None: None))
    tabs = win.forms["overlay"].controls["ov.music_f"][1]
    assert tabs.currentIndex() == 0
    win.open_tab("overlay", "ov.music_f")
    assert tabs.currentWidget() is win.forms["overlay"].controls["ov.music_f"][2]
    win.open_tab("overlay", "ov.sys")
    assert tabs.currentWidget() is win.forms["overlay"].controls["ov.sys"][2]
    win.open_tab("overlay", "ov.caption")                     # not a tab: nothing happens
    win.open_tab("stats", "ov.sys")
    assert tabs.currentWidget() is win.forms["overlay"].controls["ov.sys"][2]


def test_tiles_view_shows_the_system_averages(qapp, keep):
    from dbdmapscout import qt_window
    from dbdmapscout.app_stats import sys_tiles
    view = keep(qt_window.TilesView())
    tiles = sys_tiles({"n": 17, "gpu_temp": 76.2, "gpu_load": 75, "throttle_rounds": 2, "throttle_s": 95})
    assert [t.value for t in tiles] == ["76 °C", "75 %", "2 von 17"]
    view.show_state({"data": tiles, "visible": True})
    shown = [box.value.text() for card, box in view._tiles if not card.isHidden()]
    assert shown == ["76 °C", "75 %", "2 von 17"]
    view.show_state({"data": [], "visible": True})
    assert view.isHidden()


def test_preview_draws_the_screen_and_posts_a_click(qapp, keep):
    from PIL import Image
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from dbdmapscout import qt_window
    posted = queue.Queue()
    view = keep(qt_window.PreviewView("ov.preview", lambda a, arg=None: posted.put((a, arg))))
    view.resize(1000, 419)
    pic, hud = Image.new("RGBA", (300, 400), "blue"), Image.new("RGBA", (200, 100), "white")
    data = {"screen": (3440, 1440), "bar": 440, "rect": (26, 17, 388, 603, 603),
            "layers": [("map", 26, 17, 300, 400), ("hud", 3200, 17, 200, 100)], "pics": {"map": pic, "hud": hud},
            "opacity": 0.85, "editing": True}
    view.show_state({"data": data, "visible": True})
    assert view.heightForWidth(1000) == view.MAX_H             # 3440:1440 would be 419 – capped
    shot = view.grab().toImage()                              # paints every layer (1.64: real pictures)
    ox, oy, s = view._frame()
    assert shot.pixelColor(round(ox + 3300 * s), round(oy + 60 * s)).lightness() > 150     # the white "hud" layer
    assert set(view._pix) == {"map", "hud"}
    ox, oy, s = view._frame()
    QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, QPoint(round(ox + 3000 * s), round(oy + 900 * s)))
    action, (key, (what, x, y)) = posted.get_nowait()
    assert action == "act" and key == "ov.preview" and what == "move" and abs(x - 3000) < 8 and abs(y - 900) < 8


def test_preview_drags_the_element_under_the_mouse(qapp, keep):
    """1.64.1 (user: "nur die Map moven, nicht das andere"): the element under the mouse is grabbed and its corner
    follows the mouse; an empty spot still moves the map's centre there."""
    from PIL import Image
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from dbdmapscout import qt_window
    posted = queue.Queue()
    view = keep(qt_window.PreviewView("ov.preview", lambda a, arg=None: posted.put((a, arg))))
    view.resize(1000, 419)
    pics = {n: Image.new("RGBA", (200, 100), "white") for n in ("map", "hud", "music")}
    data = {"screen": (3440, 1440), "bar": 440, "rect": (20, 20, 300, 400, 400), "opacity": 1.0, "pics": pics,
            "layers": [("map", 20, 20, 300, 400), ("hud", 3100, 20, 300, 200), ("music", 3100, 300, 300, 100)]}
    view.show_state({"data": data, "visible": True})
    view.show()
    ox, oy, s = view._frame()
    QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, QPoint(round(ox + 3150 * s), round(oy + 320 * s)))
    assert posted.get_nowait() == ("act", ("ov.preview", ("select", "music")))    # picks it (1.64.9) …
    assert posted.empty()                                     # … moves nothing before "Mit der Maus verschieben"
    view.show_state({"data": dict(data, editing=True), "visible": True})
    view.grab()                                               # frame + note "Verschieben aktiv"
    ox, oy, s = view._frame()

    def at(x, y):
        return QPoint(round(ox + x * s), round(oy + y * s))
    assert view.layer_at(3150, 320)[0] == "music" and view.layer_at(1700, 700) is None
    QTest.mousePress(view, Qt.LeftButton, Qt.NoModifier, at(3150, 320))      # grab the music card …
    assert posted.get_nowait()[1][1] == ("select", "music")
    assert posted.empty()                                                    # … no jump on the press
    QTest.mouseMove(view, at(3150, 1020))
    QTest.mouseRelease(view, Qt.LeftButton, Qt.NoModifier, at(3150, 1020))
    action, (key, (what, name, x, y)) = posted.get_nowait()
    assert (what, name) == ("place", "music") and abs(x - 3100) < 8 and abs(y - 1000) < 8
    QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, at(1700, 700))     # empty spot: the map goes there
    assert posted.get_nowait()[1][1][0] == "move"


def test_preview_sizes_the_picked_element_by_its_corner_and_the_wheel(qapp, keep):
    """1.64.9 (user: pick something and size it right there instead of three sliders)."""
    from PIL import Image
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtTest import QTest
    from dbdmapscout import qt_window
    posted = queue.Queue()
    view = keep(qt_window.PreviewView("ov.preview", lambda a, arg=None: posted.put((a, arg))))
    view.resize(1000, 419)
    pics = {n: Image.new("RGBA", (200, 100), "white") for n in ("map", "music")}
    data = {"screen": (3440, 1440), "bar": 440, "rect": (20, 20, 300, 400, 400), "opacity": 1.0, "pics": pics,
            "layers": [("map", 20, 20, 300, 400), ("music", 3100, 300, 300, 100)], "editing": True,
            "selected": "music"}
    view.show_state({"data": data, "visible": True})
    view.show()
    view.grab()                                               # draws the corner
    ox, oy, s = view._frame()

    def at(x, y):
        return QPoint(round(ox + x * s), round(oy + y * s))
    QTest.mousePress(view, Qt.LeftButton, Qt.NoModifier, at(3400, 400))     # the music card's corner
    QTest.mouseMove(view, at(3400, 500))                                       # twice as tall
    QTest.mouseRelease(view, Qt.LeftButton, Qt.NoModifier, at(3400, 500))
    action, (key, (what, name, h)) = posted.get_nowait()
    assert (what, name) == ("resize", "music") and abs(h - 200) < 10
    assert posted.empty()                                     # the corner neither picks nor moves anything else

    def wheel(pt, dy, mods=Qt.ControlModifier):
        e = QWheelEvent(QPointF(pt), QPointF(view.mapToGlobal(pt)), QPoint(0, 0), QPoint(0, dy), Qt.NoButton,
                        mods, Qt.NoScrollPhase, False)
        qapp.sendEvent(view, e)
        return e.isAccepted()
    # 1.3.2 (user: the plain wheel kept changing sizes while scrolling the page): only Ctrl + wheel sizes
    assert not wheel(at(100, 100), 120, Qt.NoModifier) and posted.empty()
    assert wheel(at(100, 100), 120)                           # Ctrl + wheel over the map: bigger
    assert posted.get_nowait()[1][1][:2] == ("resize", "map")
    assert not wheel(at(1700, 700), 120) and posted.empty()   # empty spot: the page scrolls
    view.show_state({"data": dict(data, editing=False), "visible": True})
    assert not wheel(at(100, 100), 120) and posted.empty()    # not moving: the wheel never sizes anything


def _contrast(a, b):
    def lum(h):
        h = h.lstrip("#")
        rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        f = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("key", list(qt_theme.THEMES))
def test_colour_themes_stay_readable(key):
    """1.62: every theme in dark and light – accent text on cards and text on accent buttons >= 4.5:1, text on
    the background >= 7:1; unknown themes fall back to gold."""
    for oled in (False, True):
        _check_theme(key, oled)
    qt_theme.set_theme("nope")
    assert qt_theme.colours(True)["accent"] == theme.DARK["accent"]
    qt_theme.set_theme("blue", oled=True)
    assert qt_theme.colours(True)["bg"] == "#000000" and qt_theme.colours(False)["bg"] != "#000000"
    qt_theme.set_theme("gold")


@pytest.mark.parametrize("colour", qt_theme.SWATCHES + ("#ffffff", "#000000", "#808080", "#ffff00", "#000080",
                                                     "#0ff", "nonsense"))
def test_own_colour_is_made_readable(colour):
    """1.63: any colour (palette or "Eigene Farbe …") – same checks as the built-in themes, the hover too, white
    text on the selection; a colour that is readable already stays as it is."""
    from dbdmapscout.theme import DARK
    qt_theme.set_theme("custom", custom=colour)
    for oled in (False, True):
        _check_theme("custom", oled, custom=colour)
    try:
        for oled in (False, True):
            qt_theme.set_theme("custom", oled, colour)
            for dark in (True, False):
                c = qt_theme.colours(dark)
                assert _contrast(c["accent"], c["bg"]) >= 4.5 and _contrast(c["accent"], c["nav"]) >= 4.5
                assert _contrast(c["on_accent"], c["accent_hover"]) >= 4.5
                assert _contrast("#ffffff", c["select"]) >= 4.5
    finally:
        qt_theme.set_theme("gold")
    assert qt_theme.derive_accent("#c9a227", True, DARK["panel"], DARK["bg"])["accent"] == "#c9a227"
    assert qt_theme.norm_hex("nonsense") is None and qt_theme.norm_hex("#ABC") == "#aabbcc"


def test_swatches_ring_the_chosen_colour_and_post_clicks(qapp, keep):
    import queue as _q
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from dbdmapscout import qt_window
    posted = _q.Queue()
    view = keep(qt_window.SwatchView("st.swatches", lambda a, arg=None: posted.put((a, arg))))
    view.resize(500, 80)
    view.show_state({"values": [("#c9a227", "a"), ("#2f8fe0", "b")], "current": "#2f8fe0", "dark": True})
    view.show()
    qapp.processEvents()
    gold, blue = view._buttons
    assert "transparent" in gold.styleSheet() and "transparent" not in blue.styleSheet()
    QTest.mouseClick(gold, Qt.LeftButton)
    assert posted.get_nowait() == ("act", ("st.swatches", "#c9a227"))
    view._pick()                                               # "Eigene Farbe …": a non-modal dialog
    assert view._dialog.isVisible()
    view._dialog.colorSelected.emit(qt_window.QColor("#123456"))
    assert posted.get_nowait() == ("act", ("st.swatches", "#123456"))
    view._dialog.close()


def _check_theme(key, oled, custom=None):
    qt_theme.set_theme(key, oled, custom)
    try:
        for dark in (True, False):
            c = qt_theme.colours(dark)
            assert _contrast(c["accent"], c["card"]) >= 4.5, (key, dark)
            assert _contrast(c["on_accent"], c["accent"]) >= 4.5, (key, dark)
            assert _contrast(c["fg"], c["bg"]) >= 7, (key, dark)
            assert c["accent"] in qt_theme.stylesheet(dark)
    finally:
        qt_theme.set_theme("gold")


def test_today_rows_for_the_black_bar():
    """1.62: block "today" below the system values – rounds and play time; kills/escaped only with stats data."""
    from dbdmapscout.app_sysinfo import today_rows
    now = time.time()
    rounds = [history.Round(history.period_start("day", now) + 60, 600, "coal", "Coal Tower", role="killer"),
              history.Round(history.period_start("day", now) - 3600, 600, "coal", "Coal Tower", role="killer")]
    rows = today_rows(SimpleNamespace(rounds=rounds, off={}), now)
    text = ["".join(t for t, _c in row) for row in rows]
    assert text == ["HEUTE 1 RUNDEN · 10:00"]                 # yesterday's round does not count


def test_old_oled_theme_becomes_the_switch(tmp_path):
    """1.62.0 had OLED as a theme: it becomes gold + the OLED switch (1.62.1)."""
    import json
    from dbdmapscout.config import Settings
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"settings_version": 3, "color_theme": "oled"}), encoding="utf-8")
    s = Settings(str(path))
    assert s["color_theme"] == "gold" and s["oled_black"] is True


def test_the_mouse_wheel_scrolls_the_page_not_a_setting(qapp):
    """User: scrolling the page with the mouse wheel changed some random field (combo box, slider)."""
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtWidgets import QComboBox, QScrollArea, QSlider, QVBoxLayout, QWidget
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    body = QWidget()
    lay = QVBoxLayout(body)
    combo, slider = QComboBox(), QSlider()
    combo.addItems(["a", "b", "c"])
    slider.setRange(0, 100)
    slider.setValue(50)
    lay.addWidget(combo)
    lay.addWidget(slider)
    body.setMinimumHeight(3000)
    sa.setWidget(body)
    sa.resize(300, 200)
    sa.show()
    qapp.processEvents()

    def wheel(w):
        e = QWheelEvent(QPointF(5, 5), QPointF(w.mapToGlobal(QPoint(5, 5))), QPoint(0, 0), QPoint(0, -120),
                        Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
        qapp.sendEvent(w, e)

    wheel(combo)
    wheel(slider)
    assert combo.currentIndex() == 0 and slider.value() == 50
    assert sa.verticalScrollBar().value() > 0                         # the page scrolled instead
    sa.close()


def test_preview_snaps_while_dragging_and_moves_by_arrow_keys(qapp, keep):
    """1.65: a dragged element snaps to the centre line (Alt: free); arrow keys move the picked one."""
    from PIL import Image
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from dbdmapscout import qt_window
    posted = queue.Queue()
    view = keep(qt_window.PreviewView("ov.preview", lambda a, arg=None: posted.put((a, arg))))
    view.resize(1000, 419)
    pics = {n: Image.new("RGBA", (200, 100), "white") for n in ("map", "music")}
    data = {"screen": (3440, 1440), "bar": 440, "rect": (20, 20, 300, 400, 400), "opacity": 1.0, "pics": pics,
            "layers": [("map", 20, 20, 300, 400), ("music", 3100, 300, 300, 100)], "editing": True,
            "selected": "music"}
    view.show_state({"data": data, "visible": True})
    view.show()
    ox, oy, s = view._frame()

    def at(x, y):
        return QPoint(round(ox + x * s), round(oy + y * s))
    QTest.mousePress(view, Qt.LeftButton, Qt.NoModifier, at(3150, 320))      # grab the music card at (50, 20)
    QTest.mouseMove(view, at(1625, 800))                                       # its centre near the middle line
    _a, (_k, (what, name, x, y)) = posted.queue[-1]
    assert (what, name) == ("place", "music") and abs(x + 150 - 1720) < 1     # centre exactly on 1720
    assert abs(view._layer("music")[1] - x) < 1               # 1.65.2: drawn there at once, not after the App
    view.grab()                                                                # draws the guide line
    QTest.mouseRelease(view, Qt.LeftButton, Qt.NoModifier, at(1625, 800))
    while not posted.empty():
        posted.get_nowait()
    view.setFocus()
    QTest.keyClick(view, Qt.Key_Left)
    QTest.keyClick(view, Qt.Key_Down, Qt.ShiftModifier)
    assert [posted.get_nowait()[1][1] for _i in range(2)] == [("nudge", -1, 0), ("nudge", 0, 10)]
    view.show_state({"data": dict(data, editing=False), "visible": True})
    QTest.keyClick(view, Qt.Key_Left)
    assert posted.empty()                                     # not moving: arrow keys do nothing


def test_fact_box_shows_its_action_button(qapp, keep):
    """1.2.15: a fact with an action gets a small button that posts the action; without one it is hidden."""
    from dbdmapscout import overview, qt_window
    posted = []
    box = keep(qt_window.FactBox(bar=True, post=posted.append))
    box.show_fact(overview.Fact("Server", "–", "aus", action="server_page", action_label="Server-Tab öffnen"))
    assert not box.link.isHidden() and box.link.text() == "Server-Tab öffnen" and box.link.toolTip()
    box.link.click()
    assert posted == ["server_page"]
    box.show_fact(overview.Fact("Server", "Frankfurt"))
    assert box.link.isHidden()
    plain = keep(qt_window.FactBox())                          # dashboard tiles: no post, never a button
    plain.show_fact(overview.Fact("x", action="server_page", action_label="y"))
    assert plain.link.isHidden()


def test_reveal_opens_the_page_and_lights_the_card(qapp, keep):
    """1.2.15: MainWindow.reveal(page, key) – the overview's "Match-Daten einrichten" lands on the card."""
    from dbdmapscout import qt_window
    win = keep(qt_window.MainWindow(lambda a, arg=None: None))
    win.show()
    win.reveal("settings", "st.more.official")
    assert win.current_key() == "settings"
    for _i in range(5):
        qapp.processEvents()
        time.sleep(0.03)
    head = win.forms["settings"].controls["st.more.official"][1]
    card = head.parentWidget()
    while card is not None and card.property("class") != "card":
        card = card.parentWidget()
    assert card is not None and card.property("found") is True
    win.reveal("settings", "no.such.key")                     # unknown key: nothing happens


def test_dashboard_clicks_post_the_map_and_the_cell(qapp, keep):
    """1.2.16: a click on a map bar posts ("map", name), on a heatmap cell ("cell", map, killer) – the App turns
    them into the map / killer filter of the statistics."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from dbdmapscout import dashboard, qt_window
    posted = queue.Queue()
    view = keep(qt_window.DashboardView("stats.dash", lambda a, arg=None: posted.put((a, arg))))
    d = dashboard.Dashboard(tiles=[], maps=[("Coal Tower", 6, "Ø 2.4"), ("Gas Heaven", 3, "")], maps_max=6,
                            rows=["Coal Tower"], columns=["Nurse"], cells={("Coal Tower", "Nurse"): (3.0, 4)})
    view.resize(700, 500)
    view.show()
    view.show_state({"data": d, "dark": True})
    qapp.processEvents()
    QTest.mouseClick(view.maps, Qt.LeftButton, pos=QPoint(20, int(qt_window.MapBars.ROW * 1.5)))
    assert posted.get_nowait() == ("act", ("stats.dash", ("map", "Gas Heaven")))
    view.heat.repaint()                                       # the cells' rectangles come from painting
    qapp.processEvents()
    assert view.heat._hits, "the heatmap painted its cell"
    rect = view.heat._hits[0][0]
    QTest.mouseClick(view.heat, Qt.LeftButton, pos=rect.center().toPoint())
    assert posted.get_nowait() == ("act", ("stats.dash", ("cell", "Coal Tower", "Nurse")))
    QTest.mouseClick(view.maps, Qt.LeftButton, pos=QPoint(20, qt_window.MapBars.ROW * 5))   # below the rows
    assert posted.empty()
    plain = keep(qt_window.DashboardView())                   # without post: no cursor, no clicks
    assert plain.maps.cursor().shape() != Qt.PointingHandCursor


def test_map_tiles_show_marks_and_a_context_menu(qapp, keep):
    """1.2.18: a tile carries rounds / Ø kills and the map's own settings; the right click offers show, rotate,
    reset (only with own values) and replace picture, each posting ("map_action", (action, key))."""
    from dbdmapscout import qt_window
    posted = queue.Queue()
    page = keep(qt_window.MapsPage(lambda a, arg=None: posted.put((a, arg))))
    items = [("MacMillan", "Coal Tower", "coal", 1), ("MacMillan", "Suffocation Pit", "pit", 1)]
    marks = {("coal", 1): ("6 Runden · Ø 2.4 Kills · 90°", "6 Runden · Ø 2.4 Kills · 90°\nEigene …", True)}
    page.show_maps(items, None, marks=marks)
    coal, pit = page._tiles[("coal", 1)], page._tiles[("pit", 1)]
    assert coal.info.text().startswith("6 Runden") and coal.info.toolTip().endswith("Eigene …") and pit.info.text() == ""
    entries = page.menu_entries(("coal", 1))
    assert [a for a, _l, _e in entries] == ["show", "rotate", "size_reset", "picture"]
    assert all(e for _a, _l, e in entries)
    assert [e for _a, _l, e in page.menu_entries(("pit", 1))] == [True, True, False, True]
    page.open_menu(("coal", 1), coal.mapToGlobal(coal.rect().center()))
    acts = page._menu.actions()
    assert [a.text() for a in acts][:2] == ["Anzeigen", "Drehen ↻"]
    acts[1].trigger()
    assert posted.get_nowait() == ("map_action", ("rotate", ("coal", 1)))
    page._menu.close()
    page.show_maps(items, None, marks={})                      # marks gone: the line empties
    assert coal.info.text() == ""


def test_the_assistant_clears_the_navigation_and_shows_the_preview(qapp, keep):
    """1.2.19: no page stays highlighted behind the assistant; step 2 carries the overlay preview and the
    system values / today / music switches; a hotkey button's right click posts hk_menu."""
    from dbdmapscout import qt_window
    posted = queue.Queue()
    win = keep(qt_window.MainWindow(lambda a, arg=None: posted.put((a, arg))))
    win.show_page("stats")
    win.show_setup(True)
    assert win.nav.currentRow() == -1 and win.current_key() == "setup"
    assert qt_window.page_keys("setup") >= {"ov.preview", "ov.sysinfo", "ov.today", "ov.media"}
    win.show_setup(False)
    assert win.nav.currentRow() == 0 and win.current_key() == "overview"
    btn = win.forms["settings"].controls["st.hk.toggle_overlay"][1]
    btn._post("hk_menu", ("st.hk.toggle_overlay", "off"))
    assert ("hk_menu", ("st.hk.toggle_overlay", "off")) in [posted.get_nowait() for _i in range(posted.qsize())]


def test_maps_page_switches_the_map_style(qapp, keep):
    """1.3.3 (user: "im Maps eine Option, normale Maps anzuzeigen, quasi zu wechseln"): Original / Dunkel on the
    maps page post the style; the shown style is checked."""
    from dbdmapscout import qt_window
    posted = []
    page = keep(qt_window.MapsPage(lambda a, arg=None: posted.append((a, arg))))
    page.show_maps([("MacMillan Estate", "Coal Tower", "coal", 1)], None, {}, [], {}, "dark")
    assert page.style_btns["dark"].isChecked() and not page.style_btns["classic"].isChecked()
    page.style_btns["classic"].click()
    assert posted[-1] == ("map_style", "classic")
    page.show_maps([("MacMillan Estate", "Coal Tower", "coal", 1)], None, {}, [], {}, "classic")
    assert page.style_btns["classic"].isChecked() and not page.style_btns["dark"].isChecked()


def test_style_buttons_switch_at_once_and_pages_can_be_warmed(qapp, keep):
    """1.3.4 (user: "Farbe wechselt erst nach 1 s"): Original / Dunkel are one exclusive group – a click shows at
    once, without waiting for the App; warm_pages lays out the hidden pages without errors."""
    from dbdmapscout import qt_window
    posted = []
    page = keep(qt_window.MapsPage(lambda a, arg=None: posted.append((a, arg))))
    page.show_maps([("MacMillan Estate", "Coal Tower", "coal", 1)], None, {}, [], {}, "classic")
    page.style_btns["dark"].click()
    assert page.style_btns["dark"].isChecked() and not page.style_btns["classic"].isChecked()
    page.style_btns["dark"].click()                                      # a second click keeps it on
    assert page.style_btns["dark"].isChecked() and posted[-1] == ("map_style", "dark")
    win = keep(qt_window.MainWindow(lambda *a: None))
    win.warm_pages()


def test_a_theme_change_styles_the_page_on_display_first(qapp, keep):
    """1.3.4: the style sheet goes to the visible page at once and to the hidden ones one by one (or when opened) –
    on the whole window Qt repolished all 1236 widgets (≈ 250 ms per theme/zoom click)."""
    from dbdmapscout import qt_theme, qt_window
    win = keep(qt_window.MainWindow(lambda *a: None))
    win.apply_theme(True, 1.0)
    win._stale.clear()                                            # as if the idle restyling had finished
    for i in range(win.stack.count()):
        win.stack.widget(i).setStyleSheet(win._qss)
    win.apply_theme(False, 1.0)
    light = qt_theme.stylesheet(False, 1.0)
    assert win.styleSheet() == "" and win.stack.currentWidget().styleSheet() == light
    assert win.stack.widget(3) in win._stale and win.stack.widget(3).styleSheet() != light
    assert not win._style_timer.isActive()                       # hidden window: nothing restyled while idle
    win.show_page("stats")
    assert win.stack.widget(3).styleSheet() == light and win.stack.widget(3) not in win._stale
    while win._stale:
        win._style_next()
    assert all(win.stack.widget(i).styleSheet() == light for i in range(win.stack.count()))


def test_columns_can_be_hidden_by_a_right_click_on_the_heading(qapp, keep):
    """1.3.6: the heading's menu hides columns (one always stays), the stretching column moves to a shown one;
    the choice goes to the App and comes back on the next start."""
    from dbdmapscout import qt_window
    posted = []
    t = keep(qt_window.Table(".nb.f3.treeview9", lambda a, arg=None: posted.append((a, arg))))
    cols = [("map", "Map", "w"), ("n", "Runden", "e"), ("kills", "Ø Kills", "e")]
    rows = [("a", 0, "", ["Gas Heaven", "3", "2.1"], [], False)]
    t.show_state({"columns": cols, "rows": rows, "colours": {}, "selection": [], "selectable": False})
    t._toggle_column("kills", False)
    assert t.isColumnHidden(2) and posted[-1] == ("table_cols", ("map|n|kills", ["kills"]))
    t._toggle_column("map", False)                             # the stretching column: another one stretches
    assert t.isColumnHidden(0) and t.header().sectionResizeMode(1) == t.header().ResizeMode.Stretch
    t._show_all_columns()
    assert not any(t.isColumnHidden(i) for i in range(3)) and posted[-1] == ("table_cols", ("map|n|kills", []))
    t.set_hidden_map({"map|n|kills": ["map", "n", "kills"]})    # an old setting hiding everything: all shown
    assert not any(t.isColumnHidden(i) for i in range(3))
    t.set_hidden_map({"map|n|kills": ["n"], "other|cols": ["x"]})
    rows2 = rows + [("b", 0, "", ["Coal Tower", "1", "–"], [], False)]
    t.show_state({"columns": cols, "rows": rows2, "colours": {}, "selection": [], "selectable": False})
    assert t.isColumnHidden(1)                                  # stays hidden when the table is built anew
    fresh = keep(qt_window.Table(".nb.f4.treeview12", lambda a, arg=None: None))   # next start: set before rows
    fresh.set_hidden_map({"map|n|kills": ["n"]})
    fresh.show_state({"columns": cols, "rows": rows, "colours": {}, "selection": [], "selectable": False})
    assert fresh.isColumnHidden(1) and not fresh.isColumnHidden(0)
    t._column_menu(t.header().rect().center())                 # the menu itself opens without error


def test_a_multi_select_table_posts_the_whole_selection(qapp, keep):
    """1.5.4 (user: mark several rows and set them as farming): selectmode "extended" -> ExtendedSelection; the
    table posts the selected ids as one list and never a single "click" (that would reset a Ctrl-click)."""
    from PySide6.QtCore import Qt
    from dbdmapscout import qt_window
    posted = []
    t = keep(qt_window.Table(".nb.f3.treeview9", lambda a, arg=None: posted.append((a, arg))))
    cols = [("map", "Map", "w"), ("n", "Runden", "e")]
    rows = [(f"r{i}", 0, "", [f"Map {i}", str(i)], [], False) for i in range(3)]
    t.show_state({"columns": cols, "rows": rows, "colours": {}, "selection": [], "selectable": True, "multi": True})
    assert t.selectionMode() == t.SelectionMode.ExtendedSelection
    items = [t.topLevelItem(i) for i in range(3)]
    items[0].setSelected(True)
    items[2].setSelected(True)
    sel = [a for a in posted if a[0] == "act" and a[1][1][0] == "select"]
    assert sel and sorted(sel[-1][1][1][1]) == ["r0", "r2"]
    posted.clear()
    t._clicked(items[1], 0)
    assert posted == []                                          # no single click in multi mode
    t.show_state({"columns": cols, "rows": rows, "colours": {}, "selection": ["r1"], "selectable": True, "multi": True})
    assert [i.data(0, Qt.UserRole) for i in t.selectedItems()] == ["r1"]   # the model's selection wins
    t.show_state({"columns": cols, "rows": rows, "colours": {}, "selection": [], "selectable": True})
    assert t.selectionMode() == t.SelectionMode.SingleSelection
    t._clicked(items[1], 0)
    assert posted[-1] == ("act", (".nb.f3.treeview9", ("click", "r1")))


def test_the_navigation_and_the_overlay_tabs_can_be_reordered_and_remembered(qapp, keep):
    """1.7.6 (user: "move the windows on the left and the tab rows as I like"): set_nav_order puts the pages into
    the saved order (missing ones follow), switching pages works by key, a drag posts the new order; the overlay
    page's tabs follow apply_tab_order, open_tab still finds its tab, a drag posts tab_order, {} restores."""
    from PySide6.QtCore import QModelIndex
    from dbdmapscout import qt_window
    posted = queue.Queue()
    win = keep(qt_window.MainWindow(lambda a, arg=None: posted.put((a, arg))))
    built = [k for k, _l in qt_window.PAGES]
    win.set_nav_order(["log", "stats", "nonsense"])
    assert win.nav_keys() == ["log", "stats"] + [k for k in built if k not in ("log", "stats")]
    assert win.current_key() == "overview" and win.nav.currentRow() == win.nav_keys().index("overview")
    win.show_page("stats")
    assert win.current_key() == "stats" and win.nav.currentRow() == 1 and win.stack.currentWidget() is win._pages["stats"]
    win.nav.setCurrentRow(0)
    assert win.current_key() == "log" and win.stack.currentWidget() is win._pages["log"]
    assert win.nav.item(0).text() == "Log" and not win.nav.item(0).icon().isNull()
    while not posted.empty():
        posted.get()
    assert win.nav.model().moveRow(QModelIndex(), 0, QModelIndex(), 3)      # what a drag does
    assert ("nav_order", win.nav_keys()) in [posted.get() for _ in range(posted.qsize())]
    assert win.nav_keys()[:2] == ["stats", "overview"] and win.current_key() == "log"
    win.set_nav_order([])
    assert win.nav_keys() == built and win.current_key() == "log"
    # the overlay page's tab row
    form = win.forms["overlay"]
    tabs_id, tabs, ids = form._tabsets[0]
    frames = list(ids)
    assert tabs_id == frames[0] and tabs.tabBar().isMovable()
    form.apply_tab_order({tabs_id: list(reversed(frames))})
    assert form._tab_ids(tabs, ids) == list(reversed(frames))
    assert [tabs.tabText(i) for i in range(tabs.count())] == ["Allgemein", "Musik", "Heute", "Systemwerte", "Karte"]
    win.open_tab("overlay", frames[0])
    assert tabs.currentWidget() is form.controls[frames[0]][2]
    form.show_states({"ov.sys": {"text": "Systemwerte", "visible": False}})
    assert not tabs.isTabVisible(tabs.indexOf(form.controls["ov.sys"][2]))
    while not posted.empty():
        posted.get()
    tabs.tabBar().moveTab(0, 1)
    assert ("tab_order", ("overlay", tabs_id, form._tab_ids(tabs, ids))) in [posted.get() for _ in range(posted.qsize())]
    form.apply_tab_order({tabs_id: ["ov.look", "bogus"]})          # no permutation: built-in order
    assert form._tab_ids(tabs, ids) == frames
