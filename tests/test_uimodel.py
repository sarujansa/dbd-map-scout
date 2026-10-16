"""The UI model (uimodel.py), how the window reads and operates it (app_qt.ui_layout/ui_state/ui_act), the Qt
overlay, and the whole program started without a screen (Qt offscreen; Linux – the Windows job has its own)."""
import os
import queue
import sys
import time

import pytest

from dbdmapscout import uimodel as ui

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------------------ the model
def test_pack_order_and_hiding():
    root = ui.Root()
    f = ui.Frame(root)
    a, b, c = ui.Label(f, text="a"), ui.Label(f, text="b"), ui.Label(f, text="c")
    a.pack()
    c.pack()
    b.pack(before=c)
    assert f._packed == [a, b, c] and b.winfo_manager() == "pack" and b.pack_info()["side"] == "top"
    b.pack_forget()
    assert not b.winfo_manager() and f._packed == [a, c]
    b.pack(side="left", after=a)
    assert f._packed == [a, b, c] and b.pack_info()["side"] == "left"
    c.grid(row=1, column=2)
    assert c.winfo_manager() == "grid" and c.grid_info() == {"row": 1, "column": 2} and c not in f._packed
    with pytest.raises(ui.UIError):
        c.pack_info()
    assert str(a).startswith(str(f) + ".") and root.nametowidget(str(a)) is a
    f.destroy()
    assert not a.winfo_exists() and root.winfo_children() == []


def test_variables_and_controls():
    seen = []
    v = ui.StringVar(value="x")
    v.trace_add("write", lambda *a: seen.append(v.get()))
    lbl = ui.Label(ui.Root(), textvariable=v)
    v.set("y")
    assert lbl.cget("text") == "y" and seen == ["y"]
    on = ui.BooleanVar(value=False)
    calls = []
    chk = ui.Checkbutton(ui.Root(), text="An", variable=on, command=lambda: calls.append(on.get()))
    chk.invoke()
    assert on.get() and chk.instate(["selected"]) and calls == [True]
    chk.state(["disabled"])
    chk.invoke()
    assert on.get() and calls == [True] and chk.instate(["disabled"])        # disabled: no click
    chk.configure(state="normal")
    assert not chk.instate(["disabled"])
    mode = ui.StringVar(value="a")
    r = ui.Radiobutton(ui.Root(), variable=mode, value="b")
    assert not r.instate(["selected"])
    r.invoke()
    assert mode.get() == "b" and r.instate(["selected"])
    picked = []
    cb = ui.Combobox(ui.Root(), values=["eins", "zwei"], state="readonly")
    cb.bind("<<ComboboxSelected>>", lambda e: picked.append(cb.get()))
    cb.set("zwei")
    cb.event_generate("<<ComboboxSelected>>")
    assert picked == ["zwei"] and not cb.editable() and cb["values"] == ["eins", "zwei"]
    e = ui.Entry(ui.Root())
    e.insert(0, "Name")
    e.delete(0, "end")
    e.insert(0, "Neu")
    assert e.get() == "Neu"
    got = []
    s = ui.Scale(ui.Root(), from_=10, to=50, variable=ui.DoubleVar(value=20), command=lambda v: got.append(v))
    s.set(80)
    assert s.get() == 50 and got == ["80"]                       # clamped, the command runs like a drag
    assert ui.Button(ui.Root(), command=lambda: "ok").invoke() == "ok"


def test_notebook_and_table():
    nb = ui.Notebook(ui.Root())
    a, b = ui.Frame(nb), ui.Frame(nb)
    nb.add(a, text="A")
    nb.add(b, text="B")
    changed = []
    nb.bind("<<NotebookTabChanged>>", lambda e: changed.append(nb.select()))
    assert nb.select() == str(a) and nb.index("current") == 0
    nb.select(b)
    nb.select(b)                                                 # no event without a change
    assert changed == [str(b)] and nb.index("current") == 1
    nb.tab(b, text="B ⚠")
    assert nb.tab(b, "text") == "B ⚠" and nb.tabs() == [str(a), str(b)]
    t = ui.Treeview(ui.Root(), columns=("n", "ping"), show="headings")
    g = t.insert("", "end", text="Europa", open=True)
    r1 = t.insert(g, "end", iid="fra", values=("1", "31 ms"), tags=("good",))
    t.insert("", 0, iid="first", values=("0", ""))
    assert t.get_children() == ("first", g) and t.get_children(g) == (r1,)
    assert t.item("fra", "values") == ("1", "31 ms") and t.set("fra", "ping") == "31 ms"
    t.set("fra", "ping", "28 ms")
    t.item("fra", tags="bad")
    assert t.item("fra")["values"] == ("1", "28 ms") and t.item("fra", "tags") == ("bad",)
    t.selection_set("fra")
    assert t.selection() == ("fra",)
    assert [r[:3] for r in t.rows()] == [("first", 0, ""), (g, 0, "Europa"), ("fra", 1, "")]
    t.delete(g)
    assert not t.exists("fra") and t.selection() == () and t.get_children() == ("first",)
    with pytest.raises(ui.UIError):
        t.insert("", "end", iid="first")


# ------------------------------------------------------------------ what the window reads and does
def test_tab_structure_state_and_clicks():
    pytest.importorskip("PySide6")
    from dbdmapscout.app_qt import ui_act, ui_layout, ui_shown, ui_state
    root = ui.Root()
    nb = ui.Notebook(root)
    tab = ui.Frame(nb)
    nb.add(tab, text="Statistik")
    card = ui.LabelFrame(tab, text="Regionen")
    card.pack(fill="x")
    clicked, sorted_by = [], []
    row = ui.Frame(card)
    row.pack(fill="x")
    btn = ui.Button(row, text="Ping messen", command=lambda: clicked.append("ping"))
    btn.pack(side="left")
    btn._dbdms_tip = lambda: "misst den Ping"
    ui.Label(row, text="rechts", style="Dim.TLabel").pack(side="right")
    t = ui.Treeview(card, columns=("ping",), show="tree headings", selectmode="browse")
    t.heading("ping", text="Ping", anchor="e", command=lambda: sorted_by.append("ping"))
    t.insert("", "end", iid="g:eu", text="Europa")
    t.insert("g:eu", "end", iid="r:fra", text="Frankfurt", values=("31 ms",), tags=("p_good",))
    t.tag_configure("p_good", foreground="#7cc47f")
    t.pack()
    hidden = ui.Label(card, text="erst später")              # not packed: in the layout, but not shown
    reg = {}
    node = ui_layout(tab, reg)
    assert node["kind"] == "box" and node["children"][0]["kind"] == "card"
    rowdesc = node["children"][0]["children"][0]
    assert rowdesc["row"] and [c["side"] for c in rowdesc["children"]] == ["left", "right"]
    assert str(hidden) in reg and not ui_shown(hidden) and ui_shown(t)
    st = ui_state(t)
    assert st["rows"][1][:4] == ("r:fra", 1, "Frankfurt", ["31 ms"]) and st["colours"] == {"p_good": "#7cc47f"}
    assert st["columns"] == [("#0", "", "w"), ("ping", "Ping", "e")] and st["selectable"]
    assert ui_state(btn) == {"visible": True, "text": "Ping messen", "enabled": True, "tip": "misst den Ping"}
    ui_act(t, ("click", "r:fra"))
    assert t.selection() == ("r:fra",)
    ui_act(t, ("sort", "ping"))
    ui_act(btn, None)
    assert sorted_by == ["ping"] and clicked == ["ping"]
    assert ui_state(nb) == {"visible": True, "tabs": ["Statistik"], "index": 0}


def test_how_tables_and_notebooks_are_packed_reaches_the_window():
    """A notebook packed to fill (statistics) takes the page's height; a table packed without expand (server
    regions) is as tall as its rows; the stretching column is the model's, not always the first."""
    pytest.importorskip("PySide6")
    from dbdmapscout.app_qt import ui_layout, ui_state
    root = ui.Root()
    tab = ui.Frame(root)
    nb = ui.Notebook(tab)
    nb.pack(fill="both", expand=True)
    page = ui.Frame(nb)
    nb.add(page, text="Letzte Runden")
    t = ui.Treeview(page, columns=("when", "map"), show="headings")
    t.column("when", width=120)
    t.column("map", width=130, stretch=True)
    t.pack(fill="both", expand=True)
    fit = ui.Treeview(tab, columns=("ping",), show="tree headings")
    fit.pack(fill="x")
    fit.insert("", "end", iid="r:fra", text="Frankfurt", tags=("p_good", ui.CHECK_ON))
    node = ui_layout(tab, {})
    tabs, small = node["children"]
    assert tabs["kind"] == "tabs" and tabs["fill"]
    assert tabs["children"][0]["children"][0]["fit"] is False and small["fit"] is True
    st = ui_state(t)
    assert st["stretch"] == 1 and st["widths"] == [120, 130]
    assert list(ui_state(fit)["rows"][0][4]) == ["p_good", ui.CHECK_ON]


def test_dialog_structure():
    pytest.importorskip("PySide6")
    from dbdmapscout.app_qt import ui_act, ui_layout, ui_shown, ui_state
    dlg = ui.Toplevel(ui.Root())
    body = ui.Frame(dlg)
    body.pack()
    mode = ui.StringVar(value="replace")
    r = ui.Radiobutton(body, text="Neue Map", variable=mode, value="new")
    r.pack()
    name = ui.StringVar(value="")
    e = ui.Entry(body, textvariable=name)
    e.pack()
    pic = ui.Label(body, text="Ergebnis")
    pic._dbdms_pil = None
    pic.pack()
    grid = ui.Frame(body)
    grid.pack()
    ui.Checkbutton(grid, text="EN").grid(row=0, column=0)
    ui.Checkbutton(grid, text="DE").grid(row=0, column=1)
    node = ui_layout(body, {})
    assert [c["kind"] for c in node["children"]] == ["radio", "entry", "image", "box"]
    assert node["children"][3]["grid"] and [c["cell"] for c in node["children"][3]["children"]] == [(0, 0), (0, 1)]
    assert ui_shown(r)                                        # inside a dialog: visible up to the dialog
    ui_act(r)
    ui_act(e, "Shattered Square")
    assert mode.get() == "new" and name.get() == "Shattered Square" and ui_state(r)["value"]
    cb = ui.Combobox(body, values=["A"], state="readonly")
    cb.pack()
    ui_act(cb, "frei getippt")                                # not a value, not editable: ignored
    assert cb.get() == ""
    cb.configure(state="normal")
    ui_act(cb, "frei getippt")
    assert cb.get() == "frei getippt"


# ------------------------------------------------------------------ the Qt overlay (fallback / not Windows)
def test_qt_overlay_shows_the_map_and_reports_a_drag():
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from dbdmapscout import qt_window
    from dbdmapscout.mainloop import MainLoop
    from dbdmapscout.overlay_qt import QtOverlay
    loop = MainLoop(qt_window.application())
    ov = QtOverlay(loop)
    ov.set_map(os.path.join(ROOT, "maps", "McMillan", "Coal Tower.webp"), "Coal Tower")
    ov.set_timer("01:23")
    w, h = ov.render(300)
    assert w > 0 and h > 300                                  # map + timer below it
    ov.show_at(40, 50)
    assert ov.shown and ov.is_visible() and ov.win.image.width() == w
    ov.set_fade(0.5)                                          # fading (1.2.9): a share of the opacity
    assert abs(ov.win.windowOpacity() - ov.opacity * 0.5) < 0.01
    ov.set_fade(1.0)
    moved = []
    ov.on_moved = lambda x, y: moved.append((x, y))
    ov.set_editing(True)
    assert ov.editing and ov.win.isVisible()
    ov._dropped()
    assert moved and not ov.dragging
    ov.set_editing(False)
    ov.hide()
    assert not ov.shown
    ov.destroy()


# ------------------------------------------------------------------ the whole program
@pytest.fixture
def app_root(tmp_path):
    if sys.platform == "win32":
        pytest.skip("Linux: the Windows job tests the native parts; the app would touch the system there")
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    for name in ("maps", "models", "maps.json"):
        os.symlink(os.path.join(ROOT, name), tmp_path / name)
    (tmp_path / "sim").mkdir()
    return tmp_path


def test_the_program_starts_shows_every_page_and_quits(app_root):
    """Smoke test of the whole program (Qt offscreen): every page and both dialogs are drawn from the model,
    clicks go through the event queue, nothing reports an error, quitting ends the loop."""
    from dbdmapscout import qt_window, tooltip
    from dbdmapscout.app import App
    app = App(str(app_root), simulate=str(app_root / "sim"))
    errors = []
    app._report_once = lambda key, text: errors.append((key, text))
    assert not (qt_window.page_keys() - set(app._qt_reg)), "a hand-made page names a widget the App never made"
    assert tooltip.missing(app.ui_root) == []                 # every button/checkbox has its info text
    keys = [k for k, _l in qt_window.PAGES]
    assert app.qt.current_key() == "setup"                    # first start: the setup assistant
    steps = []
    failed = []

    def step(i=0):
        try:
            _step(i)
        except BaseException as e:                   # a failed check ends the program (else the loop runs on)
            failed.append(e)
            app.quit()

    def _step(i=0):
        steps.append(i)
        if i < len(keys):
            app.qt.show_page(keys[i])
            assert app.qt.current_key() == keys[i]
        elif i == len(keys):
            app.show_map(next(iter(app.catalog.maps)), 1, "manual")
            app._unknown = ("SHATTERED SQUARE", "")
            app._qt_post("assign")                            # dialog "Map zuordnen"
            app._qt_post("add_picture")                       # dialog "Kartenbild hinzufügen"
            app._qt_post("act", ("ov.caption", False))        # a click on the overlay page
            app._qt_post("search_open")                       # the search fills every page
            app._qt_post("act", ("ov.edit", None))                   # "Mit der Maus verschieben" (also without a map)
            app._qt_post("act", ("ov.preview", ("move", 300, 300)))   # a click on the overlay preview
            app._qt_post("act", ("ov.preview", ("place", "music", 0, 0)))     # the music card dragged there
            app._qt_post("act", ("ov.preview", ("place", "hud", 0, 0)))       # the system values too
            app._qt_post("act", ("ov.preview", ("select", "hud")))            # picked (1.64.9) …
            app._qt_post("act", ("ov.sel_size", 150))                         # … and sized by the one slider
            app._qt_post("act", ("ov.preview", ("resize", "music", 10 ** 6)))  # corner/wheel: as big as it goes
            app._qt_post("act", ("ov.sel", "Karte"))                          # the map from the list
            app._qt_post("act", ("ov.sel_size", 50))
            app._qt_post("act", ("ov.edit", None))                   # "Fertig"
            app._qt_post("setup_done")
            app._qt_post("act", ("st.swatches", "#E0508F"))   # a square of the colour palette
            settings = app.qt.forms["settings"].columns[0]
            app._qt_post("card_order", ("settings", 0, list(reversed(settings.ids()))))   # a card dragged
        elif i == len(keys) + 1:
            assert len(app.qt.dialogs) == 2
            assert app.settings["welcome_seen"] and any("Overlay" in e for e in app.qt._found)
            assert app.settings["overlay"]["anchor"] == "custom"
            assert app.settings["overlay"]["media_pos"] == "custom"       # dropped at (0, 0): its centre (1.2.5)
            music = next(lay for lay in app._preview_data()["layers"] if lay[0] == "music")
            assert music[1:3] == (0, 0)
            assert (app.settings["sysinfo"], app.settings["sysinfo_pos"]) == ("custom", [0.0, 0.0])
            o = app.settings["overlay"]
            assert (o["hud_scale"], o["media_scale"], o["height"]) == (1.5, 2.0, 0.36)
            assert o["map_heights"][app.current[0]] == 0.5          # a map on display: its own size (1.65.5)
            assert app._sel == "map" and app.sel_scale.cget("to") == 90 and app.media_size_var.get() == 200
            assert (app.settings["color_theme"], app.settings["accent_custom"]) == ("custom", "#e0508f")
            assert app.swatches.current == "#e0508f" and app.theme_var.get() == "Eigene Farbe"
            order = app.settings["card_order"]["settings"]["0"]
            assert order[0] == "st.updates"
            app._card_order_reset()                            # "Anordnung zurücksetzen"
            assert app.settings["card_order"] == {} and app.qt.forms["settings"].columns[0].ids()[0] == "st.look"
            for key in list(app.qt.dialogs):
                app._qt_post("dlg_close", key)
            assert app.settings["overlay"]["show_caption"] is False
        else:
            assert not app.qt.dialogs and not app._qt_dialogs
            app.quit()
            return
        app.root.after(300, lambda: step(i + 1))
    app.root.after(300, step)
    t0 = time.monotonic()
    app.run()
    if failed:
        raise failed[0]
    assert time.monotonic() - t0 < 60
    assert steps[-1] == len(keys) + 2 and app._quitting
    assert not errors, errors
    assert not [e for e in app._log_entries if e[1] == "Fehler"], list(app._log_entries)


def test_events_reach_the_app_in_order():
    """Clicks from the window are queued like the detection's events (one place handles both)."""
    q = queue.Queue()
    from dbdmapscout.app_qt import QtShell

    class Shell(QtShell):
        events = q
    Shell()._qt_post("scan")
    Shell()._qt_post("act", ("ov.caption", True))
    assert [q.get_nowait(), q.get_nowait()] == [("ui", "scan", None), ("ui", "act", ("ov.caption", True))]


def test_quitting_ends_the_loop_although_the_window_refuses_to_close():
    """QApplication.quit() would ask the windows first – the control window says no (its X = quit through the App)."""
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from dbdmapscout import qt_window
    from dbdmapscout.mainloop import MainLoop
    loop = MainLoop(qt_window.application())
    win = qt_window.MainWindow(lambda a, arg=None: None)
    win.show()
    ended = []
    loop.after(50, loop.quit)
    loop.after(5000, lambda: (ended.append("watchdog"), loop.qapp.exit(1)))
    t0 = time.monotonic()
    loop.mainloop()
    assert not ended and time.monotonic() - t0 < 4
    win.allow_close = True
    win.close()
    import shiboken6
    shiboken6.delete(win)


def test_slow_callbacks_are_noted_for_the_diagnosis():
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from dbdmapscout import diagnose, qt_window
    from dbdmapscout.mainloop import MainLoop
    loop = MainLoop(qt_window.application())

    def slow():
        time.sleep(0.05)

    loop.after(0, slow)
    loop.after(0, lambda: None)                               # fast: not noted
    loop.after(120, loop.quit)
    loop.mainloop()
    assert [s[1] for s in loop.slow] == ["test_slow_callbacks_are_noted_for_the_diagnosis.<locals>.slow"]
    assert loop.slow[0][2] >= 45
    text = "\n".join(diagnose.lag_lines(loop.slow))
    assert "Fenster-Hänger" in text and "slow" in text and " ms" in text
    assert diagnose.lag_lines([]) == ["Fenster-Hänger (≥ 30 ms): keine"]


def test_moving_without_a_map_shows_a_test_map(app_root):
    """1.64.3 (user: "die Map wird beim Verschieben nicht angezeigt"): "Mit der Maus verschieben" without a map
    shows a test map to grab – in the game too; "Fertig" hides it again, a map chosen meanwhile stays."""
    from dbdmapscout.app import App
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        assert not app.overlay.has_map()
        app.toggle_edit()
        assert app.overlay.editing and app.overlay.has_map() and app._test_map
        assert app.edit_btn.cget("text") == "Fertig"
        app.toggle_edit()
        assert not app.overlay.editing and not app._test_map
        # 1.65.2 (user: after the test "Warte auf Map" never came again): the test map is gone completely
        assert not app.overlay.has_map() and app.current is None and not app.worker.map_on_screen
        assert app.worker.watch_gen is None and app.round.start_t is None
        assert app._waiting_lines() == ["Warte auf Map"]
        app.test_overlay()                                    # "Overlay testen" without a map: the same after it
        assert app.overlay.has_map() and app._test_map
        app._force_until = 0
        app._tick_overlay(reschedule=False)
        assert not app.overlay.has_map() and app._waiting_lines() == ["Warte auf Map"]
        app.toggle_edit()                                     # again: a test map to grab
        mid = list(app.catalog.maps)[3]
        app.show_map(mid, 1, "manual")                        # a real choice while moving …
        app.toggle_edit()
        assert app.current[0] == mid and app.user_visible     # … stays after "Fertig"
    finally:
        app.quit()


def test_undo_arrow_keys_and_a_layout_per_window_size(app_root, monkeypatch):
    """1.65 (user: fine-tune, undo, one layout per window size)."""
    from types import SimpleNamespace
    from dbdmapscout import app_layout, layoutmem
    from dbdmapscout.app import App
    app = App(str(app_root), simulate=str(app_root / "sim"))
    clock = [100.0]
    monkeypatch.setattr(app_layout.time, "monotonic", lambda: clock[0])
    try:
        o = app.settings["overlay"]
        app._select("map")
        app._set_size("map", 50)                              # one step …
        clock[0] += 5
        app.toggle_edit()
        app._preview_pick(("place", "map", 0, 0))             # … and another one
        assert o["anchor"] == "custom" and o["height"] == 0.5 and app.undo_btn.instate(["!disabled"])
        x0 = o["pos_x"]
        clock[0] += 5
        app._preview_pick(("nudge", 10, 0))                   # arrow key with Shift: 10 px to the right
        assert o["pos_x"] > x0
        app.undo_layout()                                     # back before the arrow key
        assert o["pos_x"] == x0
        app.undo_layout()
        app.undo_layout()                                     # back to the start
        assert o["anchor"] == "auto" and o["height"] == 0.36 and app.size_var.get() == 36
        assert app.undo_btn.instate(["disabled"])
        app.toggle_edit()

        # one layout per DBD window size: the first size takes the layout in use
        app.game = SimpleNamespace(width=3440, height=1440, minimized=False, rect=(0, 0, 3440, 1440), monitor=None, hwnd=0)
        app._layout_size_tick()                               # a new size must settle first …
        clock[0] += app_layout.SIZE_SETTLE + 0.1
        app._layout_size_tick()
        assert app.settings["layout_key"] == "3440x1440"
        app._set_size("map", 60)
        app._layout_size_tick()                               # changes go to that size
        assert app.settings["layouts"]["3440x1440"]["overlay"]["height"] == 0.6
        app.game = SimpleNamespace(width=1920, height=1080, minimized=False, rect=(0, 0, 1920, 1080), monitor=None, hwnd=0)
        app._layout_size_tick()
        clock[0] += app_layout.SIZE_SETTLE + 0.1
        app._layout_size_tick()                               # a new size: starts with the layout in use
        app._set_size("map", 30)
        app._layout_size_tick()
        app.game = SimpleNamespace(width=3440, height=1440, minimized=False, rect=(0, 0, 3440, 1440), monitor=None, hwnd=0)
        app._layout_size_tick()
        clock[0] += app_layout.SIZE_SETTLE + 0.1
        app._layout_size_tick()                               # back: its own layout again
        assert o["height"] == 0.6 and app.size_var.get() == 60
        assert app.settings["layouts"]["1920x1080"]["overlay"]["height"] == 0.3
        assert "3440×1440" in app.per_size_text.get()
        assert layoutmem.snapshot(app.settings.data) == app.settings["layouts"]["3440x1440"]
        app._select("map")
        app._size_cap_tick()                                  # 60 % in the 440-px bar: the bar holds it back
        assert "Balken" in app.size_cap_var.get()
        app._set_size("map", 20)
        app._size_cap_tick()
        assert app.size_cap_var.get() == ""
    finally:
        app.quit()


def test_size_changes_with_a_map_on_display_are_for_that_map(app_root):
    """1.65.5 (user: "sobald ich eine Map in der Runde bearbeite, zählt dies nur für die Map")."""
    from dbdmapscout.app import App
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        o = app.settings["overlay"]
        app._select("map")
        assert app._size_scope_text().startswith("Gilt für: alle Maps")
        app._select("hud")                                # 1.2.17: every element says what it applies to
        assert app._size_scope_text() == "Gilt für: alle Fenstergrössen"
        app._select("map")
        app._set_size("map", 40)                              # no map on display: all maps
        assert o["height"] == 0.4 and not o.get("map_heights")
        mid = list(app.catalog.maps)[2]
        app.show_map(mid, 1, "manual")
        assert app._size_scope_text().startswith(f"Gilt für: nur {app.catalog.maps[mid].name}")
        app._set_size("map", 55)                              # a map on display: only this one
        assert o["height"] == 0.4 and o["map_heights"][mid] == 0.55 and app._map_height() == 0.55
        app._resize(0.05)                                     # hotkeys: the same map
        assert o["map_heights"][mid] == 0.6
        app._unload_test_map()
        app.toggle_edit()                                     # the test map: all maps again
        assert app._test_map and app._own_size_map() is None
        app._set_size("map", 30)
        assert o["height"] == 0.3 and len(o["map_heights"]) == 1
        app.toggle_edit()
    finally:
        app.quit()


def test_position_sliders_only_for_an_own_position_and_folded_cards_are_gone(app_root):
    """1.66.3 (user: "GUI user friendly"): the sliders "Horizontal/Vertikal" stood there at 1 % with "automatisch";
    the cards under "Mehr" showed as empty headings while folded."""
    from dbdmapscout import uimodel as ui
    from dbdmapscout.app import App, anchor_label
    from dbdmapscout.app_qt import ui_shown, ui_state
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        x, y = (app._qt_reg[k] for k in ("ov.posx", "ov.posy"))
        app.anchor_var.set(anchor_label("auto"))
        app._anchor_changed()
        assert not ui_shown(x) and not ui_shown(y) and "Mit der Maus verschieben" in app.pos_hint_var.get()
        app.anchor_var.set(anchor_label("custom"))
        app._anchor_changed()
        assert ui_shown(x) and ui_shown(y)
        rows = [w.master for w in (x, y)]                     # back in their place: above the buttons
        kids = [k for k in rows[0].master.winfo_children() if k.winfo_manager()]
        assert kids.index(rows[1]) == kids.index(rows[0]) + 1 and kids.index(app.edit_btn.master) > kids.index(rows[1])
        app.anchor_var.set(anchor_label("top-left"))
        app._anchor_changed()
        assert not ui_shown(x)
        app._overlay_dragged(500, 300)                        # dragged in the game: own position, sliders there
        assert ui_shown(x) and app.settings["overlay"]["anchor"] == "custom"
        card = app._qt_reg["st.more.backup"]
        assert isinstance(card, ui.LabelFrame) and not ui_state(card)["visible"]
        app._toggle_more()
        assert ui_state(card)["visible"]
    finally:
        app.quit()


_KEEP = []


def test_a_card_is_hidden_with_its_frame():
    """The window hides a card whose model frame is folded away (its title says so) and shows it again."""
    pytest.importorskip("PySide6")
    from dbdmapscout import qt_window
    qt_window.application()
    page = qt_window.FormPage(lambda *a: None, "T", (("card", "c1", (("hint", "h"),)),))
    _KEEP.append(page)                         # a page without a parent freed by Python mid-run crashes Qt later
    kind, head, extra = page.controls["c1"]
    card = head.parentWidget()
    qt_window.show_control(kind, head, extra, {"visible": False, "text": "Karte"})
    assert card.isHidden()
    qt_window.show_control(kind, head, extra, {"visible": True, "text": "Karte"})
    assert not card.isHidden()


def test_a_slider_rows_labels_are_not_drawn_twice():
    """1.2.15 (Erkennung → Erweitert showed "Scans/Sek. Scans/Sek." and the value twice): the name and value
    labels of App._slider belong to the slider control – ui_layout leaves them out."""
    from dbdmapscout import uimodel as ui
    from dbdmapscout.app_qt import ui_layout
    root = ui.Frame(None)
    row = ui.Frame(root)
    row.pack(fill="x")
    name = ui.Label(row, text="Scans/Sek.")
    name.pack(side="left")
    val = ui.Label(row, text="5")
    val.pack(side="right")
    name._dbdms_slider_part = val._dbdms_slider_part = True
    ui.Scale(row, from_=2, to=10, variable=ui.DoubleVar(value=5)).pack(side="left", fill="x", expand=True)
    node = ui_layout(root, {})
    kinds = [c["kind"] for c in node["children"][0]["children"]]
    assert kinds == ["slider"]
