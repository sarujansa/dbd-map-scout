"""The UI model (uimodel.py), how the window reads and operates it (app_qt.ui_layout/ui_state/ui_act), the Qt
overlay, and the whole program started without a screen (Qt offscreen; Linux – the Windows job has its own)."""
import os
import queue
import sys
import time

import pytest

from fogscout import uimodel as ui

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
    assert c.winfo_manager() == "grid" and c.grid_info() == {"row": 1, "column": 2, "columnspan": 1, "sticky": ""} and c not in f._packed
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
    from fogscout.app_qt import ui_act, ui_layout, ui_shown, ui_state
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
    from fogscout.app_qt import ui_layout, ui_state
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
    from fogscout.app_qt import ui_act, ui_layout, ui_shown, ui_state
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
    from fogscout import qt_window
    from fogscout.mainloop import MainLoop
    from fogscout.overlay_qt import QtOverlay
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
    from fogscout import qt_window, tooltip
    from fogscout.app import App
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
            lays = {lay[0]: lay[1:] for lay in app._preview_data()["layers"]}
            # 1.8.25: dropped on the system values (also at (0, 0)) – it moves next to them, never on top
            assert lays["music"][1] == 0 and lays["music"][0] >= lays["hud"][0] + lays["hud"][2]
            assert (app.settings["sysinfo"], app.settings["sysinfo_pos"]) == ("custom", [0.0, 0.0])
            o = app.settings["overlay"]
            assert (o["hud_scale"], o["media_scale"], o["height"]) == (1.5, 2.0, 0.36)
            assert o["map_heights"][app.current[0]] == 0.5          # a map on display: its own size (1.65.5)
            assert app._sel == "map" and app.sel_scale.cget("to") == 90 and app.media_size_var.get() == 200
            assert (app.settings["color_theme"], app.settings["accent_custom"]) == ("custom", "#e0508f")
            assert app.swatches.current == "#e0508f" and app.theme_var.get() == "Eigene Farbe"
            order = app.settings["card_order"]["settings"]["0"]
            assert order[0] == "st.more.folders"               # 1.8.90: the last card of the tab "Allgemein" first
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
    from fogscout.app_qt import QtShell

    class Shell(QtShell):
        events = q
    Shell()._qt_post("scan")
    Shell()._qt_post("act", ("ov.caption", True))
    assert [q.get_nowait(), q.get_nowait()] == [("ui", "scan", None), ("ui", "act", ("ov.caption", True))]


def test_quitting_ends_the_loop_although_the_window_refuses_to_close():
    """QApplication.quit() would ask the windows first – the control window says no (its X = quit through the App)."""
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from fogscout import qt_window
    from fogscout.mainloop import MainLoop
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
    from fogscout import diagnose, qt_window
    from fogscout.mainloop import MainLoop
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


def test_the_longest_hangs_survive_a_flood_of_short_ones():
    """1.8.69 (user: Bloodpoints takes 1–3 min, but the diagnosis copied in a match showed only the tick's 30–48 ms):
    the last 40 are gone after ~10 s of such ticks – the longest since the start stay in a list of their own."""
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from fogscout import diagnose, mainloop, qt_window
    loop = mainloop.MainLoop(qt_window.application())
    loop.note("Statistik-Reiter: Bloodpoints", 90000)
    for i in range(mainloop.SLOW_KEPT + 5):
        loop.note("Takt: layout", 40 + i % 5)
    loop.note("Ereignis spät", 10, late_ms=5000)
    assert all(e[1] != "Statistik-Reiter: Bloodpoints" for e in loop.slow)             # pushed out of the last 40
    assert [e[1] for e in loop.worst[:2]] == ["Statistik-Reiter: Bloodpoints", "Ereignis spät"]
    assert len(loop.worst) == mainloop.WORST_KEPT
    text = "\n".join(diagnose.lag_lines(loop.slow, loop.worst))
    assert "Längste Fenster-Hänger seit dem Start" in text and "Bloodpoints  90000 ms" in text


def test_slow_steps_of_the_tick_and_the_statistics_are_named_for_the_diagnosis(app_root, monkeypatch):
    """1.8.67 (user: "Statistik dauert ewig zum Laden, alle Felder darin"; not reproducible here – ~600 rounds and
    matches open the page in 60 ms, the slowest tab ~130 ms – and the diagnosis only said "App._tick_overlay
    6005 ms"): each step of the 250 ms tick and each part of the statistics that holds the window up gets a line of
    its own in "Fenster-Hänger"; quick ones do not."""
    from fogscout import diagnose
    from fogscout.app import App
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        app.root.slow.clear()
        monkeypatch.setattr(app, "_official_tick", lambda: time.sleep(0.05))
        app._tick_overlay(reschedule=False)
        names = [s[1] for s in app.root.slow]
        assert "Takt: offizielle Daten" in names and "Takt: hotkeys" not in names
        assert all(n.startswith("Takt: ") for n in names)                 # nothing else noted for this tick
        app.root.slow.clear()
        monkeypatch.setattr(app, "_stats_part_records", lambda c: time.sleep(0.05))
        app._stats_select(str(app.stats_records.master))
        app._stats_render()
        names = [s[1] for s in app.root.slow]
        assert "Statistik-Reiter: Rekorde" in names and "Statistik: Auswahl berechnen" in names
        assert "Takt: offizielle Daten" not in names
        assert any("Statistik-Reiter: Rekorde" in line for line in diagnose.lag_lines(app.root.slow))
    finally:
        app.quit()


def test_moving_without_a_map_shows_a_test_map(app_root):
    """1.64.3 (user: "die Map wird beim Verschieben nicht angezeigt"): "Mit der Maus verschieben" without a map
    shows a test map to grab – in the game too; "Fertig" hides it again, a map chosen meanwhile stays."""
    from fogscout.app import App
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


def test_limiter_lines_are_switched_on_dragged_alike_and_undone(app_root, monkeypatch):
    """1.8.14 (user: "Limiter … oben und unten, wo die GUI-Elemente nicht überschreiten dürfen"): the switch,
    dragging a line in the preview (both bars alike, or one alone), reset, undo, and the preview data."""
    from fogscout import app_layout
    from fogscout.app import App
    app = App(str(app_root), simulate=str(app_root / "sim"))
    clock = [100.0]
    monkeypatch.setattr(app_layout.time, "monotonic", lambda: clock[0])
    try:
        o = app.settings["overlay"]
        _gx, _gy, gw, gh = app._game_rect()
        app._preview_pick(("limit", "left", "top", gh * 0.2))               # not moving: nothing
        assert o["bar_limits"] == [0.08] * 4 and not o["bar_limits_on"]
        assert app._preview_data()["limits"] is None                         # off and not moving: no lines
        app.toggle_edit()
        data = app._preview_data()                                          # 1.8.15: moving – faint lines, off
        assert data["limits_on"] is False and (data["limits"] is not None or gw / gh < 2)
        app._preview_pick(("limit", "left", "top", gh * 0.2))               # dragging one switches it on
        assert o["bar_limits_on"] and app.limits_var.get() and app._preview_data()["limits_on"]
        assert o["bar_limits"] == [0.2, 0.08, 0.08, 0.08]                    # 1.8.17: only the left bar
        app._preview_pick(("limit", "right", "bottom", gh * 0.7))
        assert o["bar_limits"] == [0.2, 0.08, 0.08, 0.3]
        app._preview_pick(("limit", "right", "bottom", gh * 0.1))            # never further in than LIMIT_MAX
        assert o["bar_limits"][3] == 0.45
        app.limits_same_var.set(True)                                       # alike again: the right takes the left
        app._limits_changed()
        assert o["bar_limits"] == [0.2, 0.08, 0.2, 0.08]
        app._preview_pick(("limit", "left", "bottom", gh * 0.8))             # alike: both bars move
        assert o["bar_limits"] == [0.2, 0.2, 0.2, 0.2]
        app.limits_same_var.set(False)
        app._limits_changed()
        clock[0] += 5                                                       # a step of its own for "undo"
        app._limits_reset()
        assert o["bar_limits"] == [0.08] * 4
        app.undo_layout()
        assert o["bar_limits"] == [0.2, 0.2, 0.2, 0.2] and app.limits_var.get()
        app.toggle_edit()
    finally:
        app.quit()


def test_undo_arrow_keys_and_a_layout_per_window_size(app_root, monkeypatch):
    """1.65 (user: fine-tune, undo, one layout per window size)."""
    from types import SimpleNamespace
    from fogscout import app_layout, layoutmem
    from fogscout.app import App
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
        from fogscout import app_qt, qt_pages
        st = app_qt.ui_state(app.sel_scale)                   # 1.8.24: the slider marks where it stops growing
        assert 20 < st["cap"] < 60 and st["text"] == f"60 % → {st['cap']:.0f} %"
        w, extra = qt_pages.make_control("slider", "ov.sel_size", lambda *a: None)
        qt_pages.show_control("slider", w, extra, st)
        assert extra[1].cap == st["cap"]
        w.resize(400, 30)
        w.grab()                                              # paints the mark without an error
        app._set_size("map", 20)
        app._size_cap_tick()
        assert app.size_cap_var.get() == ""
        assert app_qt.ui_state(app.sel_scale)["cap"] is None
    finally:
        app.quit()


def test_size_changes_with_a_map_on_display_are_for_that_map(app_root):
    """1.65.5 (user: "sobald ich eine Map in der Runde bearbeite, zählt dies nur für die Map")."""
    from fogscout.app import App
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
    the cards under "Mehr" showed as empty headings while folded (the fold is gone since 1.8.90)."""
    from fogscout import uimodel as ui
    from fogscout.app import App, anchor_label
    from fogscout.app_qt import ui_shown, ui_state
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
        card = app._qt_reg["st.more.backup"]                 # 1.8.90: no fold any more – always there (tab Allgemein)
        assert isinstance(card, ui.LabelFrame) and ui_state(card)["visible"]
    finally:
        app.quit()


_KEEP = []


def test_a_card_is_hidden_with_its_frame():
    """The window hides a card whose model frame is folded away (its title says so) and shows it again."""
    pytest.importorskip("PySide6")
    from fogscout import qt_window
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
    from fogscout import uimodel as ui
    from fogscout.app_qt import ui_layout
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


def test_the_clips_sub_tab_lists_filters_and_deletes_the_programs_clips(app_root):
    """1.8.13 (user: clips list, "filtern nach Killer/Survivor"): the sub-tab "Clips" of the recordings tab –
    the program's clips with their round, filters for role / killer / kind, a right-click menu, deleting through
    the recorder; a clip the editor saves joins the list with the recording's round."""
    import json
    from fogscout import obsrec
    from fogscout.app import App
    folder = app_root / "rec"
    cdir = folder / obsrec.CLIPS_DIR
    cdir.mkdir(parents=True)
    t1 = time.time() - 3600
    (folder / "one.mkv").write_bytes(b"\0" * 2048)
    obsrec.save_index(str(folder), [obsrec.Recording(t=t1, file="one.mkv", label="Coal Tower", role="killer",
                                                     killer="Nurse", end=t1 + 600, size=2048)])
    (cdir / "nurse.mp4").write_bytes(b"x" * 4096)
    (cdir / "2026-10-18 20-05 Gas Heaven – Survivor (Sofort-Clip).mp4").write_bytes(b"x")
    (cdir / "holiday.mp4").write_bytes(b"x")                                        # not ours
    obsrec.save_clips(str(cdir), [obsrec.Clip(file="nurse.mp4", t=time.time() - 60, kind="clip", source=t1,
                                              label="Coal Tower", role="killer", killer="Nurse", seconds=28.0)])
    (app_root / "settings.json").write_text(json.dumps({"rec_on": True, "rec_folder": str(folder),
                                                        "welcome_seen": True}), encoding="utf-8")
    app = App(str(app_root), simulate=str(app_root / "sim"))
    shown = []
    app.qt.popup_menu = lambda items, pos: shown.append(items)
    try:
        assert [app.rec_nb.tab(i, "text") for i in app.rec_nb.tabs()] == ["Runden", "Clips"]
        app._rec_render()
        t = app.clip_table

        def rows():
            return [t.item(i, "values") for i in t.get_children()]
        assert [(r[1], r[2], r[3], r[4]) for r in rows()] == [("Gas Heaven", "Survivor", "Sofort-Clip", "–"),
                                                               ("Coal Tower", "Nurse", "Clip", "00:28")]
        assert "holiday.mp4" not in [r[6] for r in rows()] and "2 von 2 Clips" in app.clip_summary_var.get()
        assert [lbl for _k, lbl in app._clip_killers] == ["Alle Killer", "Nurse"]
        app.clip_role_var.set("Survivor")
        app._clips_render()
        assert [r[1] for r in rows()] == ["Gas Heaven"] and "1 von 2 Clips" in app.clip_summary_var.get()
        app.clip_role_var.set("Alle Rollen")
        app.clip_killer_var.set("Nurse")
        app._clips_render()
        assert [r[1] for r in rows()] == ["Coal Tower"]
        app.clip_killer_var.set("Alle Killer")
        app.clip_kind_var.set("Sofort-Clips (F8)")
        app._clips_render()
        assert [r[1] for r in rows()] == ["Gas Heaven"]
        app.clip_kind_var.set("Alle Arten")
        app._clips_render()
        assert app.clip_delete_btn.cget("state") == "disabled"
        t.selection_set("nurse.mp4")
        t.event_generate("<<TreeviewSelect>>")
        assert app.clip_delete_btn.cget("state") == "normal"
        ui_act = __import__("fogscout.app_qt", fromlist=["ui_act"]).ui_act
        ui_act(t, ("menu", (1, 2)))
        assert [i[0] for i in shown[-1] if i] == ["play", "edit", "explorer", "copy", "round", "youtube", "delete"]
        app._confirmed = True
        app._menu_act("delete")                                # → recorder thread
        deadline = time.time() + 5
        while time.time() < deadline and (cdir / "nurse.mp4").exists():
            time.sleep(0.05)
        assert not (cdir / "nurse.mp4").exists() and (cdir / "holiday.mp4").exists()
        assert obsrec.load_clips(str(cdir)) == []

        class Win:                                             # what the editor reports after saving
            saved_seconds = {str(cdir / "cut.mp4"): 14.2}
        (cdir / "cut.mp4").write_bytes(b"x" * 10)
        app._clip_saved(obsrec.load_index(str(folder))[0], str(cdir / "cut.mp4"), Win())
        deadline = time.time() + 5
        while time.time() < deadline and not obsrec.load_clips(str(cdir)):
            time.sleep(0.05)
        [c] = obsrec.load_clips(str(cdir))
        assert (c.file, c.kind, c.source, c.role, c.killer, c.seconds) == ("cut.mp4", "clip", t1, "killer", "Nurse",
                                                                           14.2)
    finally:
        app.quit()


def test_the_recordings_tab_lists_the_index_and_acts_on_the_marked_row(app_root):
    """1.5: the tab shows the OBS recording index with filters; play / Explorer / keep / delete work on the marked
    row through the recorder thread; the summary names room and folder."""
    import json
    from fogscout import obsrec
    from fogscout.app import App
    folder = app_root / "rec"
    folder.mkdir()
    for name in ("one.mkv", "two.mkv"):
        (folder / name).write_bytes(b"\0" * 2048)
    t1, t2 = time.time() - 3600, time.time() - 60
    obsrec.save_index(str(folder), [
        obsrec.Recording(t=t1, file="one.mkv", label="Coal Tower", role="killer", killer="Nurse", end=t1 + 600,
                         size=2048, marks=[12.0, 100.5]),
        obsrec.Recording(t=t2, file="two.mkv", label="Gas Heaven", role="survivor", end=t2 + 50, size=2048,
                         farming=True)])
    (app_root / "settings.json").write_text(json.dumps({"rec_on": True, "rec_folder": str(folder),
                                                        "welcome_seen": True}), encoding="utf-8")
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        app._rec_render()
        t = app.rec_table
        rows = [t.item(i, "values") for i in t.get_children()]                          # 1.11.5: farming counts
        assert [r[1] for r in rows] == ["Gas Heaven", "Coal Tower"]                     # newest first
        assert rows[1][2] == "Nurse" and rows[1][4] == "10:00" and rows[1][6] == "2" and rows[0][2].endswith("Farming")
        assert rows[0][5] == "2 KB"                                                        # size column
        assert "2 Aufnahmen" in app.rec_summary_var.get() and app.rec_hint_var.get() == str(folder)
        assert app.rec_play_btn.cget("state") == "disabled"
        t.selection_set(repr(t1))
        t.event_generate("<<TreeviewSelect>>")
        assert app.rec_play_btn.cget("state") == "normal" and "00:12" in app.rec_marks_var.get()
        assert [lbl for _m, lbl in app._rec_maps] == ["Alle Maps", "Coal Tower", "Gas Heaven"]
        app.rec_map_var.set("Coal Tower")
        app._rec_render(force=True)
        assert [t.item(i, "values")[1] for i in t.get_children()] == ["Coal Tower"]
        app.rec_map_var.set("Alle Maps")
        app.rec_role_var.set("Survivor")
        app._rec_render(force=True)
        assert [t.item(i, "values")[1] for i in t.get_children()] == ["Gas Heaven"]
        app.rec_role_var.set("Alle Rollen")
        app._farming_vars[0].set(True)                                             # "Farming ausblenden"
        app._farming_switch(app._farming_vars[0])
        assert [t.item(i, "values")[1] for i in t.get_children()] == ["Coal Tower"]
        app._farming_vars[0].set(False)
        app._farming_switch(app._farming_vars[0])
        t.selection_set(repr(t1))
        app._rec_keep()                                        # → recorder thread → "changed" event
        deadline = time.time() + 5
        while time.time() < deadline and not obsrec.load_index(str(folder))[0].keep:
            time.sleep(0.05)
        assert obsrec.load_index(str(folder))[0].keep
        app._rec_render()
        t.selection_set(repr(t1))
        app._rec_buttons()
        assert t.item(repr(t1), "values")[7] == "✓" and app.rec_keep_btn.cget("text") == "Nicht mehr behalten"
        app._confirmed = True                                  # the question bar answered with OK
        app._rec_delete()
        deadline = time.time() + 5
        while time.time() < deadline and (folder / "one.mkv").exists():
            time.sleep(0.05)
        assert not (folder / "one.mkv").exists() and [r.file for r in obsrec.load_index(str(folder))] == ["two.mkv"]
        assert (folder / "two.mkv").exists()
    finally:
        app.quit()


def test_farming_rounds_have_a_tab_of_their_own_whatever_the_role_filter(app_root):
    """1.8.64 (user: "ich finde es bei letzten Runden nicht" → "wir haben so viele Kategorien, warum keine für
    Farming"): the tab "Farming" lists the farming rounds with tiles, whatever the role filter; the other filters
    (map) still apply. 1.11.5 (user: "die Filterung von Farming find ich kacke"): "Alle Rollen" has the farming
    rounds in "Letzte Runden" too – the box "Farming ausblenden" (setting hide_farming) takes them out."""
    from fogscout import history
    from fogscout.app import App
    t1, t2, t3 = time.time() - 7200, time.time() - 3600, time.time() - 1800
    path = str(app_root / "rounds.jsonl")
    history.append(path, history.Round(t=t1, seconds=600, map_id="coal", map="Coal Tower", role="killer",
                                       killer="The Nurse", farming=True))
    history.append(path, history.Round(t=t2, seconds=500, map_id="mine", map="Ormond Lake Mine", role="survivor",
                                       farming=True))
    history.append(path, history.Round(t=t3, seconds=700, map_id="coal", map="Coal Tower", role="killer"))
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        app._stats_select(str(app.stats_last.master.master))
        app._stats_render()
        assert list(app.stats_last.get_children()) == [repr(t3), repr(t2), repr(t1)]   # 1.11.5: all of them
        assert len(app._farming_vars) == 3 and not any(v.get() for v in app._farming_vars)   # stats, recordings, clips
        app._farming_vars[0].set(True)
        app._farming_switch(app._farming_vars[0])
        assert app.settings.get("hide_farming") is True and all(v.get() for v in app._farming_vars)
        assert list(app.stats_last.get_children()) == [repr(t3)]      # hidden: the normal round only
        farm_tab = app.stats_farm.master.master
        assert app._stats_parts[str(farm_tab)][0] == "Farming"
        app._stats_select(str(farm_tab))
        app._stats_render()
        assert list(app.stats_farm.get_children()) == [repr(t2), repr(t1)]   # newest first
        row = app.stats_farm.item(repr(t1), "values")
        assert row[1] == "Coal Tower" and "Nurse" in row[4] and row[5] == "–"   # no official match: no BP
        # 1.8.85 (user: "Wartezeit, wenn's instant ist, kann man das hinschreiben"): a farming round without a
        # measured search time filled its lobby at once; a normal round without one stays unknown
        assert row[3] == "sofort" and row[6] == "–"
        assert app._wait_text(history.Round(0, 1, "coal", "Coal Tower", wait=12.0, farming=True)) == "00:12"
        assert app._wait_text(history.Round(0, 1, "coal", "Coal Tower", farming=True, custom=True)) == "–"
        assert app._wait_text(history.Round(0, 1, "coal", "Coal Tower")) == "–"
        tiles = {x.title: x for x in app.stats_farm_tiles.data}
        assert tiles["Farming-Runden"].value == "2" and "1 als Killer · 1 als Survivor" in tiles["Farming-Runden"].sub
        app.stats_map_var.set("Coal Tower")
        app._stats_render()
        assert list(app.stats_farm.get_children()) == [repr(t1)]
        app.stats_map_var.set("Ormond Lake Mine")
        app.stats_role_var.set("Killer")
        app._stats_render()
        assert list(app.stats_farm.get_children()) == [repr(t2)]       # the role filter does not hide them here
    finally:
        app.quit()


def test_several_rounds_can_be_marked_as_farming_at_once_and_the_recordings_follow(app_root):
    """1.5.4 (user: "mehrere Zeilen markieren und als Farming markieren", "in der Statistik markiert, bei den
    Aufnahmen nicht"): Ctrl-selection in "Letzte Runden", one click sets every marked round; the recorder moves
    the matching recordings into "Farming"."""
    import json
    from fogscout import history, obsrec
    from fogscout.app import App
    folder = app_root / "rec"
    folder.mkdir()
    t1, t2 = time.time() - 7200, time.time() - 3600
    for t, name in ((t1, "one.mkv"), (t2, "two.mkv")):
        (folder / name).write_bytes(b"\0" * 16)
        history.append(str(app_root / "rounds.jsonl"), history.Round(t=t, seconds=600, map_id="coal", map="Coal Tower",
                                                                     role="killer", killer="The Nurse"))
    obsrec.save_index(str(folder), [obsrec.Recording(t=t1, file="one.mkv", label="Coal Tower"),
                                    obsrec.Recording(t=t2, file="two.mkv", label="Coal Tower")])
    (app_root / "settings.json").write_text(json.dumps({"rec_on": True, "rec_folder": str(folder),
                                                        "welcome_seen": True}), encoding="utf-8")
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        t = app.stats_last
        app._stats_select(str(t.master.master))               # the sub-tab "Letzte Runden" (only it is drawn)
        app._stats_render()
        assert str(t.cget("selectmode")) == "extended" and len(t.get_children()) == 2
        t.selection_set(repr(t1), repr(t2))
        t.event_generate("<<TreeviewSelect>>")
        assert app.stats_delete_btn.cget("state") == "normal"
        app._stats_toggle_farming()
        rounds = history.load(str(app_root / "rounds.jsonl"))
        assert all(r.farming for r in rounds)
        deadline = time.time() + 5
        while time.time() < deadline and not all(x.farming for x in obsrec.load_index(str(folder))):
            time.sleep(0.05)
        recs = obsrec.load_index(str(folder))
        assert all(x.farming and x.file.startswith("Farming/") for x in recs)
        assert sorted(os.listdir(folder / "Farming")) == ["one.mkv", "two.mkv"]
        # 1.11.5: farming rounds stay listed (the box "Farming ausblenden" is off); the next click turns both back
        assert len(t.get_children()) == 2
        t.selection_set(repr(t1), repr(t2))
        app._stats_toggle_farming()
        assert not any(r.farming for r in history.load(str(app_root / "rounds.jsonl")))
        deadline = time.time() + 5
        while time.time() < deadline and any(x.farming for x in obsrec.load_index(str(folder))):
            time.sleep(0.05)
        assert sorted(os.listdir(folder)) == ["Farming", obsrec.INDEX, "one.mkv", "two.mkv"]
        app._stats_render()
        t.selection_set(repr(t1), repr(t2))
        app._stats_set_role("survivor")
        assert all(r.role == "survivor" for r in history.load(str(app_root / "rounds.jsonl")))
        assert set(t.selection()) == {repr(t1), repr(t2)}          # both stay marked after the re-render
    finally:
        app.quit()


def test_the_match_start_and_f8_reach_the_recorder(app_root):
    """1.6: the worker's match_start event starts the early recording (with the found lobby's role and farming),
    F8 asks for an instant clip even without a running recording; the new boxes are saved."""
    import json
    from fogscout.app import App
    from fogscout.lobby import Found
    from fogscout.worker import Event
    (app_root / "settings.json").write_text(json.dumps({"rec_on": True, "welcome_seen": True}), encoding="utf-8")
    app = App(str(app_root), simulate=str(app_root / "sim"))
    calls = []
    app.recorder.start_early = lambda **m: calls.append(("early", m))
    app.recorder.instant_clip = lambda **m: calls.append(("clip", m))
    app.recorder.apply_audio = lambda: calls.append(("audio", {}))
    try:
        app._queue = {"state": "lobby", "found": Found(time.time(), 12.0, "survivor", crossplay_off=True)}
        app._dispatch(Event("match_start", {"t": 123.0}))
        assert calls[0] == ("early", {"t": 123.0, "role": "survivor", "killer": "", "farming": True})
        toasts = []
        app.toast.show = lambda title, text, seconds=8.0: toasts.append((title, text, seconds))
        app._hist = {"t": 99.0, "map": "Coal Tower", "map_id": "coal", "role": "killer", "killer": "Nurse",
                     "farming": False}
        app.mark_clip()
        assert calls[1] == ("clip", {"label": "Coal Tower", "role": "killer", "killer": "Nurse", "map_id": "coal",
                                     "farming": False, "source": 99.0})
        # 1.8.13 (user: "eine kleine Benachrichtigung, wenn ich mit F8 einen Clip mache"): right away and after
        assert toasts == [("Clip wird gespeichert …", "Die letzten 30 s aus dem Puffer von OBS", 6)]
        app._rec_event("clip", {"ok": True, "file": "x.mp4", "seconds": 30})
        app._rec_event("clip", {"ok": False, "why": "Wiederholungspuffer in OBS läuft nicht"})
        assert toasts[1:] == [("Clip gespeichert ✓", "30 s · im Tab Aufnahmen → Clips", 3),
                              ("Kein Clip", "Wiederholungspuffer in OBS läuft nicht", 5)]
        app.rec_clip_notify_var.set(False)
        app._rec_setting()
        app.mark_clip()
        app._rec_event("clip", {"ok": True, "file": "y.mp4", "seconds": 30})
        assert len(toasts) == 3 and app.settings.get("rec_clip_notify") is False
        app._hist = None
        app.rec_audio_vars["mic"].set(True)
        app._rec_audio_changed()
        assert calls[-1][0] == "audio" and app.settings.get("rec_audio_mic") is True
        assert app._rec_cfg().audio_mic and app._rec_cfg().early and app._rec_cfg().clip_s == 30
        app.rec_early_var.set(False)
        app._rec_setting()
        app._dispatch(Event("match_start", {"t": 200.0}))
        assert len([c for c in calls if c[0] == "early"]) == 1
    finally:
        app.quit()


def test_custom_rounds_that_were_public_matches_are_offered_as_farming(app_root):
    """1.6.1: rounds saved as custom games, which the stats page lists as public matches (instant lobbies with
    cross-play off before 1.5.5), are shown with a button: all become farming rounds (custom dropped); "Ignorieren"
    hides them for good."""
    import json
    from fogscout import history, official
    from fogscout.app import App
    t0 = time.time() - 3 * 3600
    for i, (custom, page_custom) in enumerate([(True, False), (True, True), (False, False), (True, False)]):
        history.append(str(app_root / history.FILE), history.Round(t=t0 + i * 900, seconds=600, map_id="coal-tower",
                                                                   map="Coal Tower", role="survivor", custom=custom))
        with open(app_root / official.FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": t0 + i * 900 - 38, "map": "Coal Tower", "custom": page_custom,
                                "role": "survivor", "seconds": 600, "status": "ESCAPED"}) + "\n")
    (app_root / "settings.json").write_text(json.dumps({"welcome_seen": True}), encoding="utf-8")
    app = App(str(app_root), simulate=str(app_root / "sim"))
    moved = []
    app.recorder.set_farming = lambda t, on: moved.append((t, on))
    try:
        assert [r.t for r in app._stats_farm_candidates()] == [t0, t0 + 2700]
        app._stats_render()
        text = app.stats_farm_var.get()                       # 1.8.88: the hint names the reason
        assert "2 Runden sehen nach Farming aus: 2 als Custom Game gespeichert" in text and "kurze" not in text
        assert app.stats_farm_row.winfo_manager()
        app._confirmed = True
        app._stats_farm_found()
        saved = {r.t: r for r in history.load(str(app_root / history.FILE))}
        assert saved[t0].farming and not saved[t0].custom and saved[t0 + 900].custom and not saved[t0 + 900].farming
        assert sorted(moved) == [(t0, True), (t0 + 2700, True)] and not app._stats_farm_candidates()
        assert not app.stats_farm_row.winfo_manager()
        r = history.load(str(app_root / history.FILE))                          # a third one appears later
        r[2].custom = True
        history._rewrite(str(app_root / history.FILE), r, [])
        assert [x.t for x in app._stats_farm_candidates()] == [t0 + 1800]
        app._stats_farm_ignore()
        assert not app._stats_farm_candidates() and app.settings.get("farming_ignored") == [repr(t0 + 1800)]
    finally:
        app.quit()


def test_short_rounds_against_the_same_killer_are_offered_as_farming_and_the_overview_asks(app_root):
    """1.8.88 (user: farming rounds the lobby look missed had to be marked by hand): three short rounds in a row
    against the same killer (stats page) are offered with their reason – on the statistics' overview and as the
    tile "Farming?" of the overview page, whose button opens that overview; one answer marks them all, nothing
    is marked by itself."""
    import json
    from fogscout import history, official, overview
    from fogscout.app import App
    (app_root / "settings.json").write_text(json.dumps({"welcome_seen": True}), encoding="utf-8")
    t0 = time.time() - 7200
    ms = []
    for i, (seconds, killer) in enumerate([(120, "Slasher"), (120, "Slasher"), (150, "Slasher"), (600, "Nurse")]):
        history.append(str(app_root / history.FILE), history.Round(t0 + i * 300, seconds, "coal", "Coal Tower",
                                                                   role="survivor"))
        ms.append(official.Match(t=t0 + i * 300 - 38, map="Coal Tower", role="survivor", seconds=seconds,
                                 status="Escaped", opp=[official.Player(role="killer", character=killer)]))
    official.merge(str(app_root / official.FILE), ms)
    app = App(str(app_root), simulate=str(app_root / "sim"))
    moved = []
    app.recorder.set_farming = lambda t, on: moved.append((t, on))
    try:
        assert [r.t for r in app._stats_farm_candidates()] == [t0, t0 + 300, t0 + 600]
        assert [r.farming for r in app._joined().rounds] == [False] * 4           # a suggestion, no verdict
        app._stats_render()
        text = app.stats_farm_var.get()
        assert text.startswith("3 Runden sehen nach Farming aus: 3 kurze Runden (bis 3 min) hintereinander gegen "
                               "denselben Charakter. Zuletzt: Coal Tower")
        assert app.stats_farm_row.winfo_manager()
        facts, _note = overview.today(app, time.time())
        ask = [f for f in facts if f.title == "Farming?"]
        assert ask and ask[0].value == "3" and (ask[0].action, ask[0].action_label) == ("farm_suggest",
                                                                                           "Farming prüfen …")
        app._qt_event("farm_suggest")
        assert app.qt.current_key() == "stats" and app._stats_current_title() == "Übersicht"
        app._confirmed = True
        app._stats_farm_found()
        saved = {r.t: r for r in history.load(str(app_root / history.FILE))}
        assert [saved[t0 + i * 300].farming for i in range(4)] == [True, True, True, False]
        assert sorted(moved) == [(t0, True), (t0 + 300, True), (t0 + 600, True)]
        assert not app._stats_farm_candidates() and not [f for f in overview.today(app, time.time())[0]
                                                        if f.title == "Farming?"]
    finally:
        app.quit()


def test_the_visible_elements_go_to_obs_as_one_picture_over_the_dbd_window(app_root):
    """1.8.89 (user: "nur das DBD-Fenster aufnehmen und das Overlay im Spiel"): with recordings, the window capture
    and the tick on, every shown element (its picture at the worker's rect) goes to the writer as one picture; the
    recorder gets the picture's box relative to the DBD window; tick off → one transparent picture, no box."""
    import json
    from types import SimpleNamespace
    from PIL import Image
    from fogscout import obsoverlay
    from fogscout.app import App
    (app_root / "settings.json").write_text(json.dumps({"welcome_seen": True, "rec_on": True, "rec_window": True,
                                                        "rec_overlay": True}), encoding="utf-8")
    app = App(str(app_root), simulate=str(app_root / "sim"))
    boxes = []
    try:
        app.recorder.set_overlay = boxes.append
        app.game = SimpleNamespace(minimized=False, width=3440, rect=(100, 0, 3440, 1440))
        app._game_rect = lambda: (100, 0, 3440, 1440)
        card = Image.new("RGBA", (400, 900), (255, 0, 0, 255))
        app.overlay._shown, app.overlay.picture = True, lambda: card
        app.worker.overlay_rect = (120, 300, 400, 900)
        hud_pic = Image.new("RGBA", (300, 200), (0, 0, 255, 255))
        app.hud = SimpleNamespace(shown=True, opacity=0.5, fade=1.0, picture=lambda: hud_pic,
                                  destroy=lambda: None, hide=lambda: None)
        app.worker.hud_rect = (3100, 10, 300, 200)
        app.today_win = SimpleNamespace(shown=False, picture=lambda: card,        # hidden: not in the picture
                                        destroy=lambda: None, hide=lambda: None)
        app.worker.today_rect = None
        app._overlay_feed()
        w = app._overlay_writer
        end = time.time() + 5
        while w.writes < 1 and time.time() < end:
            time.sleep(0.02)
        assert boxes == [(20, 10, 3280, 1190)] and not w.last_error            # relative to the window at x=100
        with Image.open(obsoverlay.path(str(app_root))) as img:
            assert img.size == (3280, 1190) and img.getpixel((0, 290)) == (255, 0, 0, 217)   # opacity 0.85 baked in
            assert img.getpixel((3279, 0))[3] == 128                             # the HUD's 0.5 as well
        app._overlay_feed()                                                      # nothing changed: no new picture
        time.sleep(0.1)
        assert w.writes == 1
        app.rec_overlay_var.set(False)                                           # the tick off, as the user does
        app._rec_setting()
        app._overlay_feed()
        end = time.time() + 5
        while w.writes < 2 and time.time() < end:
            time.sleep(0.02)
        assert boxes[-1] is None
        assert app._rec_cfg().overlay is False and app._rec_cfg().overlay_file == obsoverlay.path(str(app_root))
    finally:
        app.quit()


def test_the_export_dialog_filters_rounds_and_writes_csv_or_a_text_list(app_root):
    """1.8.91 (user: "ein Fenster, wo ich alles auswählen kann, Killer, Zeit etc."): Statistik → "Exportieren …"
    opens the dialog with the statistics' filters preset; presets fill Von/Bis, typing there makes the range a
    custom one, columns and format are remembered, the list goes to the clipboard or into a file."""
    import json
    from fogscout import history, official, roundexport, tooltip
    from fogscout.app import App
    (app_root / "settings.json").write_text(json.dumps({"welcome_seen": True}), encoding="utf-8")
    day = history.period_start("day", time.time())
    t_old, t1, t2 = day - 7200, day + 10 * 3600, day + 11 * 3600          # yesterday evening, today 10:00, 11:00
    for t, kw in ((t_old, {"role": "killer", "killer": "The Trapper"}), (t1, {"role": "killer", "killer": "The Nurse"}),
                  (t2, {"role": "survivor", "farming": True})):
        history.append(str(app_root / history.FILE), history.Round(t, 600, "coal", "Coal Tower", **kw))
    official.merge(str(app_root / official.FILE), [official.Match(t=t1 - 38, map="Coal Tower", role="killer", bp=25000,
                                                                  opp=[official.Player(role="survivor", character="Meg Thomas",
                                                                                       status="Sacrificed")])])
    app = App(str(app_root), simulate=str(app_root / "sim"))
    copied = []
    app.root.clipboard_set = copied.append
    try:
        app._stats_render()
        app._export_open()
        assert app._export_dlg.winfo_exists() and str(app._export_dlg) in app._qt_dialogs
        assert tooltip.missing(app.ui_root) == []                           # every button/box of the dialog has a tip
        assert app.export_preset_var.get() == "Gesamter Zeitraum" or app.export_preset_var.get() == "Alles"
        assert app.export_count_var.get() == "3 Runden, 8 Spalten"
        app.export_preset_var.set("Heute")
        app._export_preset_changed()
        assert app.export_from_var.get() == roundexport.fmt_when(day) and app.export_to_var.get() == ""
        assert app.export_count_var.get() == "2 Runden, 8 Spalten"
        for key, var in app.export_col_vars.items():
            var.set(key in ("start", "map", "killer", "kills"))
        app.export_format_var.set("text")
        app._export_refresh()
        assert app.settings.get("export_columns") == ["start", "map", "killer", "kills"]
        assert app.settings.get("export_format") == "text"
        # the round with match data carries the page's layout ("Coal Tower I", official.correct_maps), as the tables do
        assert app.export_preview_var.get().splitlines() == [roundexport.fmt_when(t1) + " · Coal Tower I · Nurse · 1",
                                                             roundexport.fmt_when(t2) + " · Coal Tower"]
        app._export_copy()
        assert copied[-1].splitlines() == app.export_preview_var.get().splitlines()
        assert app.export_msg_var.get() == "2 Runden in die Zwischenablage kopiert."
        app.export_farming_var.set(False)                                    # the farming round out
        app._export_refresh()
        assert app.export_count_var.get() == "1 Runden, 4 Spalten"
        app.export_farming_var.set(True)
        app.export_from_var.set(time.strftime("%H:%M", time.localtime(t2 - 60)))   # typed: a time alone (today)
        assert app.export_preset_var.get() == "Eigener Zeitraum"
        assert app.export_count_var.get() == "1 Runden, 4 Spalten"
        app.export_from_var.set("irgendwann")
        assert app.export_count_var.get() == "" and "nicht lesbar" in app.export_msg_var.get()
        app.export_from_var.set("")
        app.export_format_var.set("csv")
        app._export_refresh()
        app._export_save(str(app_root / "out.csv"))
        text = (app_root / "out.csv").read_text(encoding="utf-8-sig").splitlines()
        assert text[0] == "Start;Map;Killer;Kills" and len(text) == 4 and text[2].endswith(";Coal Tower I;Nurse;1")
        assert app.export_msg_var.get().startswith("3 Runden exportiert")
        app._qt_event("dlg_close", str(app._export_dlg))                  # X / Esc of the window
        assert not app._export_dlg.winfo_exists()
        app._export_open()                                                   # remembered: columns and format
        assert [k for k, v in app.export_col_vars.items() if v.get()] == ["start", "map", "killer", "kills"]
        assert app.export_format_var.get() == "csv"
    finally:
        app.quit()


def test_the_discord_state_follows_round_and_lobby_and_the_records_tab_draws(app_root):
    """1.7: the game state for the Rich Presence comes from the open round (map, realm, role, killer, start),
    else from the lobby, else the menu; the Discord boxes are saved and passed to the thread; the statistics'
    sub-tab "Rekorde" renders from the same selection as the others."""
    import json
    from fogscout import discordrpc, history
    from fogscout.app import App
    from fogscout.lobby import Found
    t0 = time.time() - 3600
    history.append(str(app_root / history.FILE), history.Round(t=t0, seconds=600, map_id="coal-tower",
                                                               map="Coal Tower", role="killer", killer="The Nurse"))
    (app_root / "settings.json").write_text(json.dumps({"welcome_seen": True}), encoding="utf-8")
    app = App(str(app_root), simulate=str(app_root / "sim"))
    cfgs = []
    app.presence.configure = lambda *a: cfgs.append(a)
    try:
        app.simulate = None                                   # as with a real DBD window
        app.game = object()
        assert app._discord_state() == discordrpc.GameState(True, "menu")
        app._queue = {"state": "search", "since": 100.0, "role": "killer", "killer": "The Nurse"}
        st = app._discord_state()
        assert (st.phase, st.role, st.killer, st.since) == ("search", "killer", "Nurse", 100.0)
        f = Found(200.0, 12.0, "survivor")
        app._queue = {"state": "lobby", "role": "survivor", "found": f}
        assert app._discord_state().since == 200.0
        app._hist = {"t": 300.0, "map_id": "coal-tower", "map": "Coal Tower", "role": "killer", "killer": "The Nurse"}
        st = app._discord_state()
        assert (st.phase, st.map, st.realm, st.killer, st.since) == ("match", "Coal Tower", "The MacMillan Estate",
                                                                      "Nurse", 300.0)
        app.game = None
        assert not app._discord_state().running
        app.dc_on_var.set(True)
        app.dc_id_var.set(" 42 ")
        app.dc_lobby_var.set(False)
        app._discord_setting()
        assert cfgs[-1] == (True, "42", True, False)
        assert app.settings.get("discord_on") is True and app.settings.get("discord_client_id") == "42"
        app._discord_status("Discord: verbunden", True)
        assert app.dc_status_var.get() == "Discord: verbunden"
        app._stats_render()
        app._stats_select("Rekorde")
        app._stats_render_tab()
        titles = [t.title for t in app.stats_records.data]
        assert titles[:2] == ["4K-Serie", "Entkommen-Serie"] and "Längste Runde" in titles
    finally:
        app.quit()


def test_the_statistics_tabs_keep_their_meaning_when_moved(app_root):
    """1.7.6: a moved sub-tab of the statistics still selects its own model tab (the model index travels with the
    widget), the order is saved as a setting and restored on apply, "Anordnung zurücksetzen" clears it."""
    import json
    from fogscout.app import App
    (app_root / "settings.json").write_text(json.dumps({"welcome_seen": True}), encoding="utf-8")
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        app.qt.show_page("stats")                                   # the page gets its texts when shown
        app._qt_refresh(force=True)
        page = app.qt.forms["stats"]
        tabs_id, tw, ids = next(s for s in page._tabsets                 # 1.8.76: the group "Runden" holds "Rekorde"
                                if "Rekorde" in [s[1].tabText(i) for i in range(s[1].count())])
        names = [tw.tabText(i) for i in range(tw.count())]
        assert tw.tabBar().isMovable() and names == ["Übersicht", "Letzte Runden", "Rekorde", "Verlauf"]
        assert page._tab_ids(tw, ids) == [str(i) for i in range(tw.count())]
        tw.tabBar().moveTab(0, 2)                                   # "Übersicht" behind "Rekorde"
        ev = []
        while not app.events.empty():
            ev.append(app.events.get())
        assert ("ui", "tab_order", ("stats", tabs_id, page._tab_ids(tw, ids))) in ev
        app._qt_event("tab_order", ("stats", tabs_id, page._tab_ids(tw, ids)))
        assert app.settings.get("tab_order")["stats"][tabs_id][:3] == ["1", "2", "0"]
        tw.setCurrentIndex(1)
        tw.setCurrentIndex(0)                                        # a click on the first shown tab = model tab 1
        ev = []
        while not app.events.empty():
            ev.append(app.events.get())
        assert ("ui", "act", (tabs_id, 1)) in ev
        app._qt_event("act", (tabs_id, 1))
        assert app._stats_current_title() == "Letzte Runden"
        app._qt_refresh(force=True)
        assert [tw.tabText(i) for i in range(3)] == [names[1], names[2], names[0]] and tw.currentIndex() == 0
        tw.setCurrentIndex(2)                                        # a click on the moved "Übersicht"
        ev = []
        while not app.events.empty():
            ev.append(app.events.get())
        assert ("ui", "act", (tabs_id, 0)) in ev
        app._card_order_reset()
        assert page._tab_ids(tw, ids) == [str(i) for i in range(tw.count())] and app.settings.get("tab_order") == {}
        app.qt.set_nav_order(["stats"])
        assert app.qt.nav_keys()[0] == "stats"
        app._card_order_reset()
        assert app.qt.nav_keys()[0] == "overview" and app.settings.get("nav_order") == []
    finally:
        app.quit()


def test_the_statistics_tabs_are_short_and_the_last_rounds_come_second(app_root):
    """1.8.2: "Letzte Runden" is the second sub-tab (the most used after the overview), the tab names are short
    enough for all of them to fit side by side, and the second tab draws the rounds table (1.8.46: eleven, the new
    "Gegner" last – the saved order of moved tabs keeps its meaning; 1.8.48: twelve with "Builds"; 1.8.64: thirteen
    with "Farming")."""
    import json
    from fogscout import history
    from fogscout.app import App
    (app_root / "settings.json").write_text(json.dumps({"welcome_seen": True}), encoding="utf-8")
    history.append(str(app_root / "rounds.jsonl"), history.Round(time.time() - 900, 600, "coal", "Coal Tower"))
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        groups = [app.stats_nb.tab(t, "text") for t in app.stats_nb.tabs()]      # 1.8.76: four groups
        assert groups == ["Runden", "Gegner & Builds", "Maps & Server", "Sonstiges"]
        parts = {g: [nb.tab(t, "text") for t in nb.tabs()] for g, nb in zip(groups, app._stats_groups.values())}
        assert parts["Runden"] == ["Übersicht", "Letzte Runden", "Rekorde", "Verlauf"]
        assert parts["Gegner & Builds"] == ["Killer", "Gegner", "Builds"]
        assert parts["Maps & Server"] == ["Maps", "Regionen", "Wartezeit"]
        assert parts["Sonstiges"] == ["Bloodpoints", "System", "Farming"]
        assert sum(len(v) for v in parts.values()) == 13 and app._stats_current_title() == "Übersicht"
        app._stats_render()
        app._stats_select("Letzte Runden")
        app._stats_render_tab()
        assert len(app.stats_last.get_children()) == 1
        tabs = [c[1] for k, c in app.qt.forms["settings"].controls.items() if c[0] == "tab"]   # 1.8.90
        assert tabs and tabs[0].count() == 6 and not hasattr(app, "more_btn")
    finally:
        app.quit()


def test_the_builds_tab_lists_the_own_loadout_with_its_results(app_root):
    """1.8.48: sub-tab "Builds" – perks, add-ons, offering, power from the stats page (userscript 3)."""
    import json
    from fogscout import history, official
    from fogscout.app import App
    (app_root / "settings.json").write_text(json.dumps({"welcome_seen": True}), encoding="utf-8")
    perks = [["P1", "Lethal Pursuer"], ["P2", "Pop Goes the Weasel"], ["P3", "Grim Embrace"], ["P4", "Deadlock"]]
    sac = official.Player(role="survivor", character="Meg Thomas", status="SACRIFICED", img="VE_Sacrificed")
    esc = official.Player(role="survivor", character="Feng Min", status="ESCAPED", img="VE_Escaped")
    ms = []
    for i, kills in enumerate((4, 2)):
        t = time.time() - 7200 + i * 1800
        history.append(str(app_root / "rounds.jsonl"), history.Round(t, 600, "coal", "Coal Tower", role="killer"))
        ms.append(official.Match(t=t - 38, map="Coal Tower", role="killer", character="The Nurse", seconds=560,
                                 opp=[sac] * kills + [esc] * (4 - kills), perks=perks,
                                 power=["W1", "Spencer's Last Breath"]))
    official.merge(str(app_root / official.FILE), ms)
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        app._stats_render()
        app._stats_select("Builds")
        app._stats_render_tab()
        rows = {app.stats_items.item(c, "values")[0]: app.stats_items.item(c, "values")
                for c in app.stats_items.get_children()}
        assert rows["Lethal Pursuer"][1:6] == ("Perk", "Killer", 2, "100%", "Ø 3.00")
        assert rows["Spencer's Last Breath"][1] == "Kraft/Item"
        builds_rows = [app.stats_builds.item(c, "values") for c in app.stats_builds.get_children()]
        assert len(builds_rows) == 1 and builds_rows[0][1:] == ("Nurse", 2, "Ø 3.00")
        assert app.stats_build_var.get() == ""
    finally:
        app.quit()


def test_the_builds_hint_says_when_the_selection_leaves_the_loadouts_out(app_root):
    """1.8.68 (user: "Statistik → Perk funktioniert nicht", screenshot: Builds empty with the userscript-3 hint and
    "All roles"): the hint blamed the userscript even when the saved matches have loadouts and only the selection
    leaves them out (custom games count only with their role filter, farming rounds not with "Farming ausblenden"
    since 1.11.5). Now it says which; the diagnosis counts the userscript 3 fields of the saved matches."""
    import json
    from fogscout import history, official
    from fogscout.app import App
    (app_root / "settings.json").write_text(json.dumps({"welcome_seen": True}), encoding="utf-8")
    t = time.time() - 3600
    history.append(str(app_root / "rounds.jsonl"), history.Round(t, 600, "coal", "Coal Tower", role="killer",
                                                                 farming=True))
    official.merge(str(app_root / official.FILE), [official.Match(
        t=t - 38, map="Coal Tower", role="killer", character="The Nurse", seconds=560, mode=["Online", "Online"],
        perks=[["P1", "Lethal Pursuer"]])])
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        app._stats_select("Builds")
        app.settings.set("hide_farming", True)
        app._stats_render()
        assert app.stats_items.get_children() == ()
        hint = app.stats_build_var.get()
        assert hint.startswith("1 gespeicherte Matches haben ein Loadout") and "Farming ausblenden" in hint
        app.settings.set("hide_farming", False)
        app._stats_render()
        assert [app.stats_items.item(c, "values")[0] for c in app.stats_items.get_children()] == ["Lethal Pursuer"]
        assert app.stats_build_var.get() == ""
        lines = app._official_diag()
        assert any(x.strip().startswith("Felder ab Userscript 3: Modus 1, Loadout 1, Embleme 0, Punkte 0 von 1")
                   for x in lines)
        official.clear(str(app_root / official.FILE))                     # no loadout saved anywhere: as before
        official.merge(str(app_root / official.FILE), [official.Match(t=t - 38, map="Coal Tower", role="killer")])
        app._stats_render()
        assert "Userscript" in app.stats_build_var.get()
    finally:
        app.quit()


def test_the_mode_filter_appears_with_known_modes_and_filters_the_rounds(app_root):
    """1.8.49: the game mode of the stats page as a filter – hidden while no match names one, "Alle Modi" by default
    (nothing changes on its own), a picked mode keeps only its rounds."""
    import json
    from fogscout import history, official
    from fogscout.app import App
    (app_root / "settings.json").write_text(json.dumps({"welcome_seen": True}), encoding="utf-8")
    ms = []
    for i, mode in enumerate((["Online", "Public Match"], ["Online", "Public Match"], ["2v8", "2v8"], [])):
        t = time.time() - 9000 + i * 1800
        history.append(str(app_root / "rounds.jsonl"), history.Round(t, 600, "coal", "Coal Tower", role="killer"))
        ms.append(official.Match(t=t - 38, map="Coal Tower", role="killer", character="The Nurse", seconds=560,
                                 mode=mode))
    official.merge(str(app_root / official.FILE), ms)
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        assert not app.stats_mode_cb.winfo_manager()                 # before any rendering: not there
        app._stats_render()
        assert app.stats_mode_cb.winfo_manager() == "pack"
        assert app.stats_mode_var.get() == "Alle Modi" and len(app._stats_rounds_shown) == 4
        assert [lbl for _k, lbl in app._stats_modes] == ["Alle Modi", "Öffentlich", "2v8"]
        app.stats_mode_var.set("2v8")
        app._stats_render()
        assert len(app._stats_rounds_shown) == 1
        app.stats_mode_var.set("Öffentlich")                        # 1.8.51: known ids get a name of their own
        app._stats_render()
        assert len(app._stats_rounds_shown) == 2                     # the round without a mode is not counted in
        assert app.settings.get("stats_mode", "") == ""              # set by code, not picked: nothing saved
        app._stats_mode_pick()                                       # picked in the box: remembered
        assert app.settings.get("stats_mode") == "Online"
    finally:
        app.quit()
    # 1.8.51 (user: "Merken"): after a restart the saved mode applies again
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        app._stats_render()
        assert app.stats_mode_var.get() == "Öffentlich" and len(app._stats_rounds_shown) == 2
        app.stats_mode_var.set("Alle Modi")
        app._stats_mode_pick()
        assert app.settings.get("stats_mode") == "" and len(app._stats_rounds_shown) == 4
    finally:
        app.quit()


def test_a_saved_tab_order_survives_a_new_tab(app_root):
    """1.8.46: the statistics got an eleventh tab – an order saved with ten keeps it, the new tab goes to the end
    (before, any list that was not a full permutation fell back to the built-in order)."""
    import json
    from fogscout.app import App
    (app_root / "settings.json").write_text(json.dumps({"welcome_seen": True}), encoding="utf-8")
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        app.qt.show_page("stats")
        app._qt_refresh(force=True)
        page = app.qt.forms["stats"]
        tabs_id, tw, ids = next(s for s in page._tabsets                 # 1.8.76: the group "Runden" (four tabs)
                                if "Rekorde" in [s[1].tabText(i) for i in range(s[1].count())])
        old = ["1", "0", "2", "99"]                                          # three known ids and a vanished one
        page.apply_tab_order({tabs_id: old})
        assert page._tab_ids(tw, ids) == ["1", "0", "2", "3"]                # the new tab at the end
        assert tw.tabBar().property("dense") is not True                     # 1.8.76: no row has eleven tabs now
    finally:
        app.quit()


def test_the_opponents_tab_shows_how_the_survivors_matches_ended(app_root):
    """1.8.46: sub-tab "Gegner" – the characters met from the stats page, the fates as tiles, the clean kills."""
    import json
    from fogscout import history, official
    from fogscout.app import App
    (app_root / "settings.json").write_text(json.dumps({"welcome_seen": True}), encoding="utf-8")
    t = time.time() - 1800
    history.append(str(app_root / "rounds.jsonl"), history.Round(t, 600, "coal", "Coal Tower", role="killer"))
    meg = official.Player(role="survivor", character="Meg Thomas", status="SACRIFICED", img="VE_Sacrificed")
    feng = official.Player(role="survivor", character="Feng Min", status="ESCAPED", img="VE_Escaped")
    official.merge(str(app_root / official.FILE), [official.Match(t=t - 38, map="Coal Tower", role="killer",
                                                                 character="The Nurse", seconds=560,
                                                                 opp=[meg, meg, meg, feng])])
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        app._stats_render()
        app._stats_select("Gegner")
        app._stats_render_tab()
        rows = [app.stats_opp.item(c, "values") for c in app.stats_opp.get_children()]
        assert rows[0][:5] == ("Meg Thomas", "Survivor", 3, "0%", "100%") and rows[1][0] == "Feng Min"
        tiles = {x.title: x for x in app.stats_opp_tiles.data}
        assert tiles["Geopfert"].value == "75%" and tiles["Entkommen"].value == "25%"
        assert tiles["Ø Kills ohne Aufgaben"].value == "3.00" and app.stats_opp_var.get() == ""
    finally:
        app.quit()


def test_recording_and_clip_menus_copy_mark_farming_and_go_to_the_round(app_root):
    """1.8.60 (user: "Contextactions wären da auch noch praktisch bei Aufnahmen und Clips"): copy the file for
    Discord, a recording's round as farming (statistics and folder follow), from a clip to its round's recording."""
    import json
    from fogscout import history, obsrec
    from fogscout.app import App
    from PySide6.QtGui import QGuiApplication
    folder = app_root / "rec"
    (folder / "Clips").mkdir(parents=True)
    (folder / "one.mkv").write_bytes(b"\0" * 2048)
    t1 = time.time() - 3600
    obsrec.save_index(str(folder), [obsrec.Recording(t=t1, file="one.mkv", label="Coal Tower", end=t1 + 600,
                                                     size=2048)])
    (folder / "Clips" / "c.mp4").write_bytes(b"\0" * 512)
    obsrec.save_clips(str(folder / "Clips"), [obsrec.Clip(file="c.mp4", t=t1 + 700, kind="instant", source=t1,
                                                          label="Coal Tower")])
    history.append(str(app_root / "rounds.jsonl"), history.Round(t1, 600, "coal_tower", "Coal Tower", role="killer"))
    (app_root / "settings.json").write_text(json.dumps({"rec_on": True, "rec_folder": str(folder),
                                                        "welcome_seen": True}), encoding="utf-8")
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        app._rec_render()
        app.rec_table.selection_set(repr(t1))
        app.rec_table.event_generate("<<TreeviewSelect>>")
        app._rec_menu_act("copy")
        urls = QGuiApplication.clipboard().mimeData().urls()
        assert [u.toLocalFile() for u in urls] == [str(folder / "one.mkv")]
        app._rec_menu_act("farming")
        assert history.load(str(app_root / "rounds.jsonl"))[0].farming
        deadline = time.time() + 5
        while time.time() < deadline and not (folder / obsrec.FARMING_DIR / "one.mkv").exists():
            time.sleep(0.05)
        assert (folder / obsrec.FARMING_DIR / "one.mkv").exists()        # the recording followed

        app.rec_map_var.set("Coal Tower")
        app.rec_only_var.set(app._rec_onlys[1][1])                          # "Mit Marke" hides it
        app._rec_render()
        assert not app.rec_table.exists(repr(t1))
        assert app.clip_table.exists("c.mp4")                             # 1.11.5: its round is farming – still here
        app.settings.set("hide_farming", True)
        app._rec_render()
        assert not app.clip_table.exists("c.mp4")                         # … unless "Farming ausblenden" is on
        app.settings.set("hide_farming", False)
        app._rec_render()
        app.clip_table.selection_set("c.mp4")
        app.clip_table.event_generate("<<TreeviewSelect>>")
        items = app._clip_menu_items()
        assert dict((i[0], i[2]) for i in items if i)["round"] is True
        app._clip_menu_act("round")
        assert app.rec_nb.select() == str(app.rec_rounds_tab)
        assert list(app.rec_table.selection()) == [repr(t1)]
    finally:
        QGuiApplication.clipboard().clear()     # files left on Qt's clipboard crash the interpreter's exit (offscreen)
        app.quit()


def test_right_click_menus_of_recordings_last_rounds_and_the_overlay_preview(app_root):
    """1.8.10 (user: "context actions"): a right click on a recording / a last round / an element of the overlay
    preview opens a menu with the actions of the buttons nearby; a picked line does the same as the button."""
    import json
    from fogscout import history, obsrec
    from fogscout.app import App
    from fogscout.app_qt import ui_act
    folder = app_root / "rec"
    folder.mkdir()
    (folder / "one.mkv").write_bytes(b"\0" * 2048)
    t1 = time.time() - 3600
    obsrec.save_index(str(folder), [obsrec.Recording(t=t1, file="one.mkv", label="Coal Tower", end=t1 + 600,
                                                     size=2048)])
    t2 = time.time() - 7200
    history.append(str(app_root / "rounds.jsonl"), history.Round(t2, 600, "coal_tower", "Coal Tower", role="survivor"))
    (app_root / "settings.json").write_text(json.dumps({"rec_on": True, "rec_folder": str(folder),
                                                        "welcome_seen": True}), encoding="utf-8")
    app = App(str(app_root), simulate=str(app_root / "sim"))
    shown = []
    app.qt.popup_menu = lambda items, pos: shown.append((items, pos))
    try:
        app._rec_render()
        app.rec_table.selection_set(repr(t1))
        app.rec_table.event_generate("<<TreeviewSelect>>")
        ui_act(app.rec_table, ("menu", (5, 6)))
        items, pos = shown[-1]
        assert pos == (5, 6) and [i[0] for i in items if i] == ["play", "clip", "explorer", "copy", "keep", "farming",
                                                                  "youtube", "delete"]                   # 1.10
        assert dict((i[0], i) for i in items if i)["keep"][3] is False          # a tick: not kept yet
        app._menu_act("keep")                                                   # → recorder thread
        deadline = time.time() + 5
        while time.time() < deadline and not obsrec.load_index(str(folder))[0].keep:
            time.sleep(0.05)
        assert obsrec.load_index(str(folder))[0].keep

        app._stats_select(str(app.stats_last.master.master))     # the sub-tab "Letzte Runden" (only it is drawn)
        app._stats_render()
        app.stats_last.selection_set(repr(t2))
        app.stats_last.event_generate("<<TreeviewSelect>>")
        ui_act(app.stats_last, ("menu", (1, 2)))
        items, _pos = shown[-1]
        assert [i[0] for i in items if i] == ["killer", "survivor", "custom", "farming", "site", "delete"]
        app._menu_act("killer")
        assert history.load(str(app_root / "rounds.jsonl"))[0].role == "killer"
        # 1.8.12 (user: "rechtsklick auf eine zeile – kommt nichts"): a real right click on the drawn table
        from PySide6.QtGui import QContextMenuEvent
        from PySide6.QtWidgets import QApplication
        from fogscout import qt_views
        app.qt.show()
        app.qt.show_page("stats")
        QApplication.processEvents()
        app._qt_refresh()
        QApplication.processEvents()
        table = next(t for t in app.qt.findChildren(qt_views.Table) if t._key == str(app.stats_last))
        app.stats_last.selection_set([])
        app.stats_last.event_generate("<<TreeviewSelect>>")
        app._qt_refresh()
        vp = table.viewport()
        at = table.visualItemRect(table.topLevelItem(0)).center()
        n = len(shown)
        QApplication.sendEvent(vp, QContextMenuEvent(QContextMenuEvent.Mouse, at, vp.mapToGlobal(at)))
        while not app.events.empty():
            app._dispatch(app.events.get_nowait())
        assert len(shown) == n + 1 and app.stats_last.selection() == (repr(t2),)

        o = app.settings["overlay"]
        o["hud_scale"] = 1.4
        app._preview_pick(("menu", "hud", 3, 4))
        items, _pos = shown[-1]
        ids = [i[0] for i in items if i]
        assert ids == ["size", "dark"] and app._sel == "hud"
        app._menu_act("size")
        assert abs(app.settings["overlay"]["hud_scale"] - 1.0) < 0.01
        before = bool(o.get("hud_backdrop"))
        app._menu_act("dark")
        assert bool(app.settings["overlay"].get("hud_backdrop")) != before
        app._preview_pick(("menu", "music", 3, 4))
        assert [i[0] for i in shown[-1][0] if i] == ["size", "dark", "hide"]
    finally:
        app.quit()


def test_no_update_restart_while_a_round_runs(app_root, monkeypatch):
    """1.8.63 (user: "mach eine Sperre rein, dass wenn es in einer Runde ist, kein Update stattfinden kann"):
    "Aktualisieren und neu starten" restarts the program – not while a round is open or OBS records."""
    from fogscout import restart
    from fogscout.app import App
    spawned = []
    monkeypatch.setattr(restart, "spawn_helper", lambda root: spawned.append(root) or False)   # False: no quit
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        app._hist = {"t": time.time(), "map_id": "x", "map": "X"}
        app.apply_update()
        assert spawned == [] and "gesperrt" in app.upd_status.get()
        app._hist = None
        monkeypatch.setattr(type(app.recorder), "recording", property(lambda self: True))
        app.apply_update()
        assert spawned == []                                            # the recording runs on (Nachlauf)
        monkeypatch.setattr(type(app.recorder), "recording", property(lambda self: False))
        app.apply_update()
        assert spawned == [str(app_root)]                               # between rounds: as before
    finally:
        app.quit()


def test_a_small_dbd_window_hides_the_overlay_and_the_round_still_counts(app_root):
    """1.8.62 (user: "wenn das Fenster so klein ist, soll das Overlay automatisch aus sein, aber die Runden soll es
    zählen und aufnehmen"): DBD at 1714×1360 hides every overlay window like the master switch; the detected round
    is saved and OBS starts and stops; a big window or the box off shows it again; the change is logged once."""
    from fogscout import history
    from fogscout.app import App
    from fogscout.app_place import small_window
    from fogscout.capture import GameWindow
    from fogscout.worker import Event
    assert small_window(1714, 1360) and small_window(1600, 900) and not small_window(3440, 1440)
    assert not small_window(1920, 1080) and not small_window(2560, 1440)
    app = App(str(app_root), simulate=str(app_root / "sim"))
    calls = []
    app.recorder.start_round = lambda **k: calls.append("start")
    app.recorder.stop_round = lambda **k: calls.append("stop")
    logs = []
    log = app._log
    app._log = lambda text, *a, **k: (logs.append(text), log(text, *a, **k))
    try:
        app.settings["overlay"]["fade"] = False
        app.game = GameWindow(1, "DeadByDaylight", 0, 0, 1714, 1360, client=(0, 0, 1714, 1360))
        app._game_checked = time.time() + 3600                          # keep the fake window
        mid = list(app.catalog.maps)[2]
        app._dispatch(Event("detected", {"map_id": mid, "variant": 1, "probability": .9, "variant_probability": 1.0,
                                         "name_text": "x", "realm_text": "y"}))
        app._place_overlay()
        assert app._overlay_off() and not app.overlay.shown and app.worker.overlay_rect is None
        assert app.worker.map_on_screen and app._hist is not None and calls == ["start"]
        app._place_overlay()
        assert sum("Kleines DBD-Fenster" in t for t in logs) == 1           # once, not every tick
        app._hist["t"] -= 600
        app._dispatch(Event("match_end", {"reason": "x", "gen": app._watch_gen, "t": time.time()}))
        assert calls == ["start", "stop"] and len(history.load(str(app_root / "rounds.jsonl"))) == 1
        app.show_map(mid, 1, "manual")
        app.small_off_var.set(False)
        app._small_off_changed()                                            # the box on the overlay page
        assert app.settings["overlay_small_off"] is False and not app._overlay_off()
        app.small_off_var.set(True)
        app._small_off_changed()
        assert app._overlay_off()
        app.game = GameWindow(1, "DeadByDaylight", 0, 0, 3440, 1440, client=(0, 0, 3440, 1440))
        assert not app._overlay_off() and any("wieder gross genug" in t for t in logs)
    finally:
        app.quit()


def test_the_master_switch_hides_every_overlay_window_and_detection_goes_on(app_root):
    """1.8.18 (user: "eine Einstellung, dass man das Overlay deaktiviert, evtl. im Overview"): a button on the
    overview and a box on the overlay page – off hides the map and every card, the detection keeps watching the
    map; "Overlay testen" shows it all the same; the switch is remembered."""
    from fogscout import overview
    from fogscout.app import App
    from fogscout.app_qt import ui_act
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        app.settings["overlay"]["fade"] = False
        app.show_map(list(app.catalog.maps)[2], 1, "manual")
        acts = overview.actions(app)
        assert acts["power"] == (True, "Overlay ausschalten") and acts["toggle"] is not None
        assert "Erkennung" in app._button_tip("power")
        app._qt_event("power")                                              # the overview's button
        assert app.settings["overlay_on"] is False and app.master_var.get() is False
        acts = overview.actions(app)
        assert acts["power"] == (True, "Overlay einschalten") and acts["toggle"] is None
        app._place_overlay()
        assert not app.overlay.shown and app.worker.overlay_rect is None and app.worker.map_on_screen
        app.test_overlay()                                                  # the test shows it all the same
        assert not app._overlay_off()
        app._force_until = 0
        assert app._overlay_off()
        ui_act(app._qt_reg["ov.master"], True)                              # the box on the overlay page
        assert app.settings["overlay_on"] is True and not app._overlay_off()
        app.toggle_overlay_master()
        app.settings.save()
        import json
        with open(app.settings.path, encoding="utf-8") as fh:
            assert json.load(fh)["overlay_on"] is False
    finally:
        app.quit()


def test_a_map_style_click_never_makes_a_picture_in_the_window_thread(app_root, monkeypatch):
    """1.8.21 (user: "im Maps ist alles sehr langsam beim Wechseln, wenn ich zwischen den Buttons klicke"): the
    overlay preview's sample and the maps page picture made the styled picture in the window thread – ~2 s per
    floor style. Now the original shows at once, a thread makes it, ``_style_ready`` takes it."""
    import threading
    from fogscout import mapstyle
    from fogscout.app import App
    calls = []
    real = mapstyle.styled_path

    def spy(path, cache_dir, make=True, style="dark"):
        calls.append((threading.current_thread() is threading.main_thread(), make))
        return real(path, cache_dir, make, style)
    monkeypatch.setattr(mapstyle, "styled_path", spy)
    monkeypatch.setattr(mapstyle, "warm", lambda *a, **k: 0)           # only the asked pictures, not all 52
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        app.qt.show()
        app.qt.show_page("maps")
        mid = list(app.catalog.maps)[0]
        app._qt_preview_sel = (mid, 1)
        app._set_map_style("grey")
        app._qt_refresh(force=True)
        app._preview_data()
        app.show_map(mid, 1, "manual")
        assert not [c for c in calls if c == (True, True)]                    # never made in the window thread
        original = app.catalog.image_path(mid, 1)[0]
        assert app._map_file(mid, 1, request=False)[0] == original
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and app._map_file(mid, 1, request=False)[0] == original:
            time.sleep(0.05)
        styled = app._map_file(mid, 1, request=False)[0]
        assert styled != original and "-grey-" in styled
        ev = app.events.get(timeout=10)
        while ev[0] != "call" or getattr(ev[1], "__name__", "") != "_style_ready":
            ev = app.events.get(timeout=10)
        reloads = []
        monkeypatch.setattr(app, "_reload_picture", lambda: reloads.append(1))
        app._dispatch(ev)                                                     # the map on display takes it
        assert reloads and app._qt_preview_cache is None
    finally:
        app.quit()


def test_both_midwich_floors_at_an_own_place_stay_between_the_limiter_lines(app_root):
    """1.8.22 (user: "Midwich ignoriert die Regel"): at an own place the map was only moved to the top line, not
    made smaller – both floors one below the other ran past the bottom line. The fixed positions already fitted."""
    from fogscout import layout
    from fogscout.app import App
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        app._game_rect = lambda: (0, 0, 3440, 1440)
        o = app.settings["overlay"]
        o.update(bar_limits_on=True, bar_limits=[0.35, 0.05, 0.08, 0.08], bar_limits_same=False, fade=False)
        mid = next(m for m in app.catalog.maps if "midwich" in m.lower())
        top, bottom = layout.bar_bands(o, (0, 0, 3440, 1440), int(1440 * o["margin"]))["left"]
        for anchor in ("custom", "auto", "top-left", "bottom-left"):
            o.update(anchor=anchor, pos_x=0.0, pos_y=0.6)
            app._force_until = time.time() + 30
            app.show_map(mid, 1, "manual")
            app._place_overlay()
            _x, y, _w, h = app._last_place
            assert app.overlay.stacked() == 2 and top <= y and y + h <= bottom, (anchor, app._last_place)
        # 1.8.23 (user, right after 1.8.22: "die Map wurde ständig grösser und kleiner"): every tick showed the full
        # size, then the smaller one – only the final size may reach the screen, and no tick shows another one
        o.update(anchor="custom")
        app.show_map(mid, 1, "manual")
        app._force_until = time.time() + 30
        app._place_overlay()
        pushed = []
        real_push = app.overlay._push
        app.overlay._push = lambda pos=None: (pushed.append(app.overlay._prepared[app.overlay._frame_i][1:3]),
                                              real_push(pos))[1]
        for _ in range(6):
            app._place_overlay()
        assert len(set(pushed)) <= 1 and app._last_place[1] + app._last_place[3] <= bottom, (set(pushed),)
        assert layout.own_room((17, 0, 300, 900), (0, 0, 3440, 1440), {"left": (504, 1368), "right": (0, 1)}) == 864
        assert layout.own_room((1500, 0, 300, 900), (0, 0, 3440, 1440), {"left": (504, 1368)}) == 1440   # over the game
        assert layout.own_room((17, 0, 300, 900), (0, 0, 3440, 1440), None) == 1440
    finally:
        app.quit()


class _InfoWin:
    """A HudWindow for the map's lines on Linux (1.8.24)."""

    def __init__(self):
        self.shown = False
        self.opacity = 0.85
        self.editing = False
        self.fade = 1.0
        self.size = (0, 0)
        self.edit_label = "INFOS"
        self.at = None

    def set_editing(self, on):
        self.editing = bool(on)

    def set_picture(self, pic, key):
        self.size = pic.size
        return self.size

    def show_at(self, x, y):
        self.shown, self.at = True, (int(x), int(y))

    def set_fade(self, f):
        self.fade = f

    def hide(self):
        self.shown = False

    def destroy(self):
        self.shown = False


def test_the_maps_lines_are_their_own_window_and_only_the_map_follows_its_size(app_root):
    """1.8.24 (user: "Zeit etc. nicht mehr mit der Map verbunden – ich will ab und zu nur die eigentliche Map-Grösse
    ändern"): timer and record in a window of their own right below the map, the map makes room for them."""
    from fogscout import layout
    from fogscout.app import App
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        app.info_win = _InfoWin()
        app._game_rect = lambda: (0, 0, 3440, 1440)
        o = app.settings["overlay"]
        o.update(anchor="auto", fade=False, info_pos="below")
        app._force_until = time.time() + 30
        app.show_map(next(iter(app.catalog.maps)), 1, "manual")
        app.overlay.set_record("Ø 2.8 Kills · 12 Runden")
        sizes = set()
        for v in (20, 25, 30):
            app._select("map")
            app._set_size("map", v)
            app._place_overlay()
            x, y, w, h = app._last_place
            ix, iy = app.info_win.at
            iw, ih = app.info_win.size
            assert app.info_win.shown and iy >= y + h and iy + ih <= 1440 - int(1440 * o["margin"]) + 1
            assert ix >= 0 and ix + iw <= layout.bar_width(3440, 1440)
            assert app.worker.info_rect == (ix, iy, iw, ih)
            sizes.add((iw, ih))
        assert len(sizes) == 1                                       # the lines keep their size
        assert app.overlay.info_apart
        o["info_pos"] = "inside"                                     # as before: drawn with the map
        app._place_overlay()
        assert not app.info_win.shown and not app.overlay.info_apart and app.worker.info_rect is None
        o["info_pos"] = "below"
        app._place_overlay()
        assert app.info_win.shown
        app._info_dragged(1700, 600)                                 # dropped over the game: its own place
        assert o["info_pos"] == "custom" and abs(app.info_win.at[0] - 1700) <= 1
        app.set_overlay_on(False)
        app._force_until = 0
        app._place_overlay()
        assert not app.info_win.shown and app.worker.info_rect is None
    finally:
        app.quit()


def test_the_maps_lines_never_sit_on_the_map_in_any_layout(app_root):
    """1.8.24 (user screenshot: the lines sat on Midwich's top floor): at an own place the vertical slider spread
    the map over the whole free height – a tall map left room neither below nor above for its lines. Map + lines
    now go as one block; checked in the App and the preview over the combinations that matter."""
    import itertools
    from fogscout import layout, preview
    from fogscout.app import App
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        app.info_win = _InfoWin()
        app._game_rect = lambda: (0, 0, 3440, 1440)
        o = app.settings["overlay"]
        mid = next(m for m in app.catalog.maps if "midwich" in m.lower())
        cases = itertools.product((("custom", 0.0), ("custom", 0.37), ("custom", 1.0), ("auto", 0.0),
                                   ("bottom-left", 0.0)), ("below", "above"), (0.3, 0.6), (False, True),
                                  (False, True))
        bad = []
        for (anchor, py), spot, height, limits, grow in cases:
            o.update(anchor=anchor, pos_x=0.0, pos_y=py, info_pos=spot, height=height, fade=False,
                     bar_limits_on=limits, bar_limits=[0.1, 0.05, 0.1, 0.05], grow_past_bar=grow)
            app._force_until = time.time() + 30
            app.show_map(mid, 1, "manual")
            app.overlay.set_record("33% escaped · 3 rounds")
            app._place_overlay()
            x, y, w, h = app._last_place
            ix, iy = app.info_win.at
            iw, ih = app.info_win.size
            if iy < y + h and iy + ih > y and ix < x + w and ix + iw > x:
                bad.append(("app", anchor, py, spot, height, limits, grow))
            layers, _r = preview.layers(3440, 1440, dict(o), "", [], None, app.overlay._frames[0][0], "",
                                        {"timer": "3:27", "record": "Bilanz"}, height)
            by = {n: (img.size, lx, ly) for n, img, lx, ly in layers}
            (mw, mh), mx, my = by["map"]
            (tw, th), tx, ty = by["text"]
            if ty < my + mh and ty + th > my and tx < mx + mw and tx + tw > mx:
                bad.append(("preview", anchor, py, spot, height, limits, grow))
        assert not bad, bad
        extra, shift = layout.own_block(dict(o, anchor="custom", info_pos="above"), (300, 90), 8)
        assert (extra, shift) == (98, 98)
        assert layout.own_block(dict(o, anchor="auto"), (300, 90), 8) == (0, 0)
    finally:
        app.quit()


def test_an_element_dropped_on_the_map_moves_off_it_and_keeps_out_of_discords_widgets(app_root):
    """1.8.25 (user screenshots: the lines dragged onto Midwich's top floor; Discord's overlay): an element at an
    own place that lies on the map moves to the nearest free place – shown there at once and in later ticks
    without going back and forth; the bars' lines keep out of Discord's voice widget / notifications."""
    from fogscout import layout
    from fogscout.app import App
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        app.info_win = _InfoWin()
        app._game_rect = lambda: (0, 0, 3440, 1440)
        o = app.settings["overlay"]
        o.update(anchor="auto", info_pos="custom", fade=False, keep_out_on=True, bar_limits_on=False)
        mid = next(m for m in app.catalog.maps if "midwich" in m.lower())
        app._force_until = time.time() + 30
        app.show_map(mid, 1, "manual")
        app.overlay.set_record("33% escaped · 3 rounds")
        app._place_overlay()
        x, y, w, h = app._last_place
        o["info_xy"] = [0.06, (y + h / 3) / 1440]                     # dropped onto the map's top floor
        seen = set()
        for _tick in range(4):
            app._place_overlay()
            ix, iy = app.info_win.at
            iw, ih = app.info_win.size
            seen.add((ix, iy))
            assert not layout.boxes_overlap((ix, iy, iw, ih), app._last_place)
            assert app.worker.info_rect == (ix, iy, iw, ih)
        assert len(seen) == 1                                         # no back and forth between ticks
        voice = layout.keep_out_boxes(o, (0, 0, 3440, 1440))[0]
        assert app._last_place[1] + app._last_place[3] <= voice[1]   # the map stays above Discord's voice widget
    finally:
        app.quit()


def test_a_farming_lobby_that_looked_custom_and_the_pages_role_and_killer_win(app_root):
    """1.8.36 (user's diagnosis: "Rolle/Killer nicht sauber", killer read as "Aeaiily"; "Farming-Runden rutschen
    immer noch als normale Runden in die Statistik"): cross-play off makes a farming round even when the lobby
    looked like a custom game (READY without countdown) – the stats page then shows it public: farming, never a
    normal round; a real custom game stays custom. The page's role and killer win over the lobby reading, also
    for a killer not on our list; the overlay's "Heute" leaves farming rounds out of Ø kills like the overview."""
    import json
    from fogscout import app_sysinfo, history, official
    from fogscout.app import App
    from fogscout.lobby import Found
    (app_root / "settings.json").write_text(json.dumps({"welcome_seen": True}), encoding="utf-8")
    app = App(str(app_root), simulate=str(app_root / "sim"))
    starts = []
    app.recorder.start_round = lambda **k: starts.append(k)
    try:
        def play(found, seconds=600):
            app._queue = {"state": "lobby", "found": found}
            app._hist_open("coal-tower", 1, "auto")
            t = app._hist["t"]
            app._hist_close(t + seconds)
            return t

        t1 = play(Found(time.time(), None, "killer", custom=True, killer="Aeaiily", crossplay_off=True))
        assert starts[-1]["farming"] is False                     # the recording waits for the page (custom?)
        t2 = play(Found(time.time(), None, "survivor", custom=True, crossplay_off=True))
        t3 = play(Found(time.time(), 30.0, "survivor", crossplay_off=False))
        saved = {r.t: r for r in history.load(str(app_root / history.FILE))}
        assert saved[t1].farming and saved[t1].custom and saved[t2].farming and not saved[t3].farming
        with open(app_root / official.FILE, "a", encoding="utf-8") as f:
            for t, custom, role, char, kills in ((t1, False, "killer", "The Newcomer", 4),
                                                 (t2, True, "survivor", "Meg Thomas", None),
                                                 (t3, False, "killer", "The Nurse", 2)):
                d = {"t": t - 38, "map": "Coal Tower", "custom": custom, "role": role, "character": char,
                     "seconds": 600, "status": "ESCAPED" if role == "survivor" else ""}
                if kills is not None:
                    d["opp"] = [{"role": "survivor", "status": "SACRIFICED" if i < kills else "ESCAPED"}
                                      for i in range(4)]
                f.write(json.dumps(d) + "\n")
        app._joined_cache = None
        j = app._joined()
        got = {r.t: r for r in j.rounds}
        assert got[t1].farming and not got[t1].custom and got[t1].killer == "The Newcomer"
        assert got[t2].custom                                     # a real custom game stays one
        assert (got[t3].role, got[t3].killer) == ("killer", "The Nurse")      # the page over the lobby's survivor
        assert [r.t for r in history.select(j.rounds)] == [t1, t2, t3]        # 1.11.5: "Alle Rollen" has farming in
        assert [r.t for r in history.select(j.rounds, farming=False)] == [t2, t3]   # "Farming ausblenden"
        assert [r.t for r in history.select(j.rounds, role="farming")] == [t1]
        assert not app._stats_farm_candidates()
        rows = app_sysinfo.today_rows(j, time.time())
        kills = [t for row in rows for t, _c in row if "." in t and t.replace(".", "").isdigit()]
        assert kills == ["2.0"]                                   # Ø kills of the normal killer round only
        heads = lambda: [row[0][0] for row in app._today_rows(time.time())]
        app._hist, app._queue = None, {"state": "idle"}
        assert heads() == ["HEUTE ", "NORMAL ", "UHR "]               # 1.8.57: the last round (t3) was normal
        app._hist = {"t": time.time(), "farming": True}
        assert heads() == ["HEUTE ", "FARMING ", "UHR "]              # a farming round is open: farming only
        app._hist = None
    finally:
        app.quit()


def test_a_dragged_statistics_tab_shows_its_content_at_once(app_root, monkeypatch):
    """1.8.70 (user: "wenn ich drauf bleibe, passiert nichts – ich muss immer verschiedene Fenster anklicken"; the
    diagnosis showed no hang): after the tabs were dragged into another order, AutoPage.visible_keys compared the
    model's tab index with the position in the row – the tab on display counted as hidden and was never filled; its
    content came only with the next page switch. A real click in the reordered row fills the table at once."""
    import json
    from fogscout import history
    from fogscout.app import App
    from fogscout.app_qt import QtShell
    from fogscout.qt_views import Table
    monkeypatch.setattr(QtShell, "_qt_warm", lambda self: None)       # it fills every page once – not the click
    now = time.time()
    for i in range(5):
        history.append(str(app_root / "rounds.jsonl"), history.Round(t=now - 3600 * (i + 1), seconds=600,
                                                                     map_id="coal", map="Coal Tower", role="killer",
                                                                     killer="The Trapper" if i < 2 else "The Nurse"))
    (app_root / "settings.json").write_text(json.dumps({"welcome_seen": True}), encoding="utf-8")
    app = App(str(app_root), simulate=str(app_root / "sim"))
    seen, failed = {}, []

    def start():
        try:
            app.qt.show_page("stats")
            app.qt.show()
            page = app.qt.forms["stats"]
            tabs_id, tw, ids = max(page._tabsets, key=lambda s: len(s[2]))
            order = list(reversed(sorted(ids, key=int)))              # every tab somewhere else
            app.qt.set_tab_order({"stats": {tabs_id: order}})
            seen["tw"], seen["want"] = tw, ids["1"]                    # model tab 1 = "Letzte Runden"
            app._stats_render()
            app.stats_killer_var.set(next(lbl for k, lbl in app._stats_killers if k == "The Trapper"))
            app._stats_render()                                        # the content changes after the build
            tw.setCurrentIndex(tw.indexOf(ids["1"]))                   # as a click on it
        except BaseException as e:
            failed.append(e)
            app.quit()

    def check():
        try:
            tw = seen["tw"]
            assert tw.currentWidget() is seen["want"]
            assert app._stats_current_title() == "Letzte Runden" and len(app.stats_last.get_children()) == 2
            seen["rows"] = [t.topLevelItemCount() for t in tw.currentWidget().findChildren(Table)]
        except BaseException as e:
            failed.append(e)
        app.quit()

    app.root.after(300, start)
    app.root.after(1500, check)
    app.root.mainloop()
    assert not failed, failed
    assert seen["rows"] == [2]                                         # in the window, not only in the model


def test_a_round_from_a_briefly_seen_lobby_with_cross_play_off_is_a_farming_round(app_root):
    """1.8.71 (user log: farming rounds stored as normal rounds, "No lobby for this round (lobby not seen)"): the
    worker sends what it saw of the lobby with the banner; with no confirmed lobby here the round takes role and
    cross-play from it. A confirmed lobby still wins."""
    from fogscout.app import App
    from fogscout.lobby import Found
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        now = time.time()
        brief = Found(now - 20, None, "survivor", crossplay_off=True, cross_looks=(1, 0))
        app._hist_open("coal", 1, "auto", lobby=brief)
        assert app._hist["farming"] and app._hist["role"] == "survivor" and app._hist["wait"] is None
        app._hist = None
        confirmed = Found(now - 60, 30.0, "killer", killer="The Nurse", crossplay_off=False)
        app._queue = {"state": "lobby", "found": confirmed}
        app._hist_open("coal", 1, "auto", lobby=brief)
        assert not app._hist["farming"] and app._hist["role"] == "killer" and app._hist["wait"] == 30.0
        app._hist = None
        app._hist_open("coal", 1, "auto")                                # no lobby at all: as before
        assert not app._hist.get("farming") and "role" not in app._hist
    finally:
        app.quit()


def test_one_box_hides_farming_rounds_in_statistics_recordings_and_clips(app_root):
    """1.8.71 (user: "Farming und normale Runden sollen bei Aufnahmen separiert werden") gave the recordings
    "Farming" and "Alle inkl. Farming" as roles; 1.11.5 (user: "die Filterung von Farming find ich kacke" →
    "überall mitzählen, Schalter zum Ausblenden"): the roles are roles again, one box "Farming ausblenden" per
    filter row – statistics, recordings, clips – all on the setting hide_farming, a click on one sets the others,
    and the setting survives a restart."""
    import json
    from fogscout.app import App
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        assert [lbl for _k, lbl in app._rec_roles] == ["Alle Rollen", "Killer", "Survivor"]
        assert [lbl for _k, lbl in app._stats_roles] == ["Alle Rollen", "Killer", "Survivor", "Custom Games"]
        assert app.rec_role_var.get() == "Alle Rollen" and app._rec_filters()[2] is None
        app.rec_role_var.set("Killer")
        assert app._rec_filters()[2] == "killer" and app.clip_role_var.get() == "Alle Rollen"
        stats_box, rec_box, clip_box = app._farming_vars
        assert not app._farming_hidden()
        rec_box.set(True)
        app._farming_switch(rec_box)
        assert app._farming_hidden() and stats_box.get() and clip_box.get()
        app.settings.save()
        assert json.loads((app_root / "settings.json").read_text(encoding="utf-8"))["hide_farming"] is True
        clip_box.set(False)
        app._farming_switch(clip_box)
        assert not app._farming_hidden() and not stats_box.get() and not rec_box.get()
    finally:
        app.quit()


def test_the_overview_shows_the_programs_own_load(app_root):
    """1.11.3 (user: "wie viel Leistung braucht das Programm alleine?"): the system card's last row is the program's
    own CPU share and memory – with the system values off and without the game too; the tick samples once a second
    and the diagnosis names average and peak."""
    from fogscout import diagnose, overview
    from fogscout.app import App
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        app.settings.set("sysinfo", "off")
        assert overview.self_row(app) is None                                   # one sample: no span yet
        app.selfload.sample(100.0, 1.0, 150 << 20)
        app.selfload.sample(101.0, 1.0 + 0.1 * app.selfload.cores, 160 << 20)   # 10 % of the machine
        rows, note = overview.system(app, 101.0, False)
        assert len(rows) == 1 and "aus" in note
        name, text, frac, colour = rows[0]
        assert (name, text, colour) == ("Fog Scout", "10.0 % CPU · 160 MB", None) and frac == pytest.approx(0.1)
        assert any("Eigene Last (nur dieser Prozess" in line for line in diagnose.collect(app).split("\n"))
        before = app.selfload.current.t
        app._selfload_tick()                                                    # a real reading, a second later
        assert app.selfload.current.t > before and app.selfload.current.rss > 0
        app._selfload_tick()                                                    # within the second: nothing new
        assert len(app.selfload.samples) == 2
    finally:
        app.quit()


def test_a_map_is_decoded_once_and_the_preview_sample_loads_in_a_thread(app_root, monkeypatch):
    """1.11.1 (user diagnosis: "Takt: layout 74 ms" at the start, "Takt: overlay 84 ms"): show_map decoded every map
    picture twice (App and PictureOverlay.set_map, ~80 ms each time a banner was read) – now once; the preview's
    sample picture (WebP decode + thumbnail, 250 ms measured in the first layout tick) is loaded in a thread, the
    tick only starts it, and a picture of a dropped sample (map style changed meanwhile) is not taken."""
    from fogscout import app as app_mod, overlay_win32
    from fogscout.app import App
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        calls = []
        real = app_mod.load_frames

        def counted(*a, **k):
            calls.append(a[0])
            return real(*a, **k)
        monkeypatch.setattr(app_mod, "load_frames", counted)
        monkeypatch.setattr(overlay_win32, "load_frames", counted)
        mid = next(iter(app.catalog.maps))
        app.show_map(mid, 1, "manual")
        assert len(calls) == 1 and app.overlay._frames

        started = []
        monkeypatch.setattr(app_mod.threading, "Thread",
                            lambda target, args, **k: type("T", (), {"start": lambda s: started.append((target, args))})())
        app._preview_drop()
        assert app._preview_sample() is None and len(started) == 1        # the tick does not wait for the picture
        assert app._preview_sample() is None and len(started) == 1        # started once
        target, args = started[0]
        target(*args)                                                       # the thread's work
        assert app._preview_sample() is not None
        app._preview_drop()
        app._preview_sample()
        target, args = started[1]
        app._preview_drop()                                                # style changed while it loaded
        target(*args)
        assert getattr(app, "_preview_pic", None) is None                  # the old picture is not taken
    finally:
        app.quit()


def test_a_search_on_the_maps_page_filters_at_once_without_building_the_tiles_anew(app_root):
    """1.8.72: the page's search went into the event queue and showed its hits with the next overlay tick
    (≤ 250 ms later) by building every tile anew; now the App filters the one grid as soon as the event is in."""
    import json
    from fogscout.app import App
    (app_root / "settings.json").write_text(json.dumps({"welcome_seen": True}), encoding="utf-8")
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        app.qt.show_page("maps")
        app._qt_refresh(force=True)
        page = app.qt.maps
        tiles = dict(page._tiles)
        assert len(tiles) == len(app._qt_map_items(search=False)) and len(page.visible_tiles()) == len(tiles)
        app._qt_event("search", "coal")                      # what _poll does with the page's ("search", text)
        shown = [t.key for t in page.visible_tiles()]
        assert shown and all("coal" in app.catalog.maps[m].name.lower() for m, _v in shown)
        assert page._tiles == tiles                           # filtered, not rebuilt
        assert app._list_items[0] == shown[0]                 # the hotkeys walk the hits
        app._qt_event("search", "")
        assert len(page.visible_tiles()) == len(tiles) and page._tiles == tiles
    finally:
        app.quit()


def test_rounds_with_a_farming_partner_count_as_farming_by_a_right_click_on_the_opponent(app_root):
    """1.8.73 (user: the opponents tab showed "Slasher 38×" – "das kommt safe vom Farmen"): a character picked in
    "Gegner" as farming partner makes every match with that character a farming round (older ones too, display
    only like the farming region). 1.11.5: it stays in the main count until "Farming ausblenden" moves it into the
    column "Farming"."""
    import json
    from fogscout import history, official
    from fogscout.app import App
    (app_root / "settings.json").write_text(json.dumps({"welcome_seen": True}), encoding="utf-8")
    t = time.time() - 7200
    ms = []
    for i, killer in enumerate(("Slasher", "The Nurse")):
        history.append(str(app_root / "rounds.jsonl"), history.Round(t + i * 1800, 600, "coal", "Coal Tower",
                                                                     role="survivor"))
        ms.append(official.Match(t=t + i * 1800 - 38, map="Coal Tower", role="survivor", seconds=560,
                                 status="Escaped", opp=[official.Player(role="killer", character=killer,
                                                                        status="Escaped")]))
    official.merge(str(app_root / official.FILE), ms)
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        app._stats_select("Gegner")
        app._stats_render()
        rows = lambda: [app.stats_opp.item(c, "values")[0] for c in app.stats_opp.get_children()]   # noqa: E731
        assert rows() == ["Slasher", "Nurse"] and app.stats_opp.get_children()[0] == "killer\tSlasher"   # by name
        app.stats_opp.selection_set("killer\tSlasher")
        items = app._stats_opp_menu_items()
        assert [it[0] for it in items] == ["opp_on:Slasher"] and "Farming" in items[0][1]
        app._stats_opp_menu_act("opp_on:Slasher")
        assert app.settings.get("farming_opponents") == ["Slasher"]
        j = app._joined()
        assert [r.farming for r in j.rounds] == [True, False]
        # 1.8.81: the partner stays listed; 1.11.5: in "Begegnungen" as long as farming counts, with "Farming
        # ausblenden" its rounds move into the column "Farming"
        vals = lambda: {c.split("\t")[1]: app.stats_opp.item(c, "values") for c in app.stats_opp.get_children()}  # noqa: E731
        assert rows() == ["Slasher", "Nurse"] and vals()["Slasher"][2] == 1 and vals()["Slasher"][7] == "–"
        assert vals()["The Nurse"][2] == 1 and vals()["The Nurse"][7] == "–"
        assert any("„Slasher“ gilt jetzt als Farming-Gegner – 1 Runden" in e[2] for e in app._log_entries)
        assert "Slasher" in app.farm_opp_var.get()
        app.settings.set("hide_farming", True)
        app._stats_render()
        assert rows() == ["Slasher", "Nurse"] and vals()["Slasher"][2] == 0 and vals()["Slasher"][7] == 1   # not twice
        app.settings.set("hide_farming", False)
        app._stats_render()
        app.stats_opp.selection_set("killer\tThe Nurse")
        assert [it[0] for it in app._stats_opp_menu_items()] == ["opp_on:The Nurse"]
        app._stats_opp_menu_act("opp_off:Slasher")                        # not marked: taken off again
        assert app.settings.get("farming_opponents") == [] and [r.farming for r in app._joined().rounds] == [False, False]
        assert rows() == ["Slasher", "Nurse"] and "(keine)" in app.farm_opp_var.get()
    finally:
        app.quit()


def test_the_right_click_on_an_opponent_reaches_the_menu_through_the_qt_table(app_root):
    """1.8.74 (user: "das geht nicht"): the opponents table was not selectable, and the Qt table opens no row menu
    on a NoSelection table – the right click of 1.8.73 never reached the App. The whole chain: Qt row menu →
    events → the model's marking → the App's menu → the picked entry marks the farming partner."""
    import json
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QTreeWidget
    from fogscout import history, official
    from fogscout.app import App
    (app_root / "settings.json").write_text(json.dumps({"welcome_seen": True}), encoding="utf-8")
    t = time.time() - 7200
    history.append(str(app_root / "rounds.jsonl"), history.Round(t, 600, "coal", "Coal Tower", role="survivor"))
    official.merge(str(app_root / official.FILE), [official.Match(
        t=t - 38, map="Coal Tower", role="survivor", seconds=560, status="Escaped",
        opp=[official.Player(role="killer", character="Slasher", status="Escaped")])])
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        qapp = app.qapp
        app.qt.show_page("stats")
        app._stats_select("Gegner")
        app._stats_render()
        for _n in range(3):                       # the tab row follows the model, then the table gets its rows
            app._qt_refresh(force=True)
            qapp.processEvents()
        kind, table, _extra = app.qt.forms["stats"].controls[str(app.stats_opp)]
        assert kind == "table" and table.selectionMode() != QTreeWidget.NoSelection
        item = next(table.topLevelItem(k) for k in range(table.topLevelItemCount())
                    if table.topLevelItem(k).data(0, Qt.UserRole) == "killer\tSlasher")
        menus = []
        app.qt.popup_menu = lambda items, pos: menus.append(items)
        table._row_menu(table.visualItemRect(item).center())            # the right click on the row
        app._poll()                                                       # the events it posted
        assert menus and [it[0] for it in menus[-1]] == ["opp_on:Slasher"]
        app._menu_act("opp_on:Slasher")                                   # the entry picked in the menu
        assert app.settings.get("farming_opponents") == ["Slasher"]
        assert [r.farming for r in app._joined().rounds] == [True]
    finally:
        app.quit()


def test_the_detection_page_went_into_the_settings_and_the_log(app_root):
    """1.8.78 (UI review point 3: nine pages, "Erkennung" held three check boxes, the game languages and the
    technical part): the detection's cards are on the settings page, "Erweitert" at the foot of the log page
    (folded, as before), the stats check in the card "Offizielle Match-Daten" and filled when the settings open."""
    import json
    from fogscout import qt_window
    from fogscout.app import App
    from fogscout.app_qt import ui_layout, ui_shown
    (app_root / "settings.json").write_text(json.dumps({"welcome_seen": True}), encoding="utf-8")
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        assert not hasattr(app, "tab_detect") and "detect" not in dict(qt_window.PAGES)
        assert "detect" not in qt_window.AUTO_PAGES and len(app.nb.tabs()) == len(qt_window.PAGES) - 1   # no overview tab
        keys = qt_window.page_keys("settings")
        assert {"st.detect", "st.det_auto", "st.det_hide", "st.det_menu", "st.langs", "det.lang.en", "det.lang.tr",
                "st.more.off_check"} <= keys
        assert all(k in app._qt_reg for k in keys)                       # every key names a widget the App made
        # the technical options: in the log tab's model, hidden until "Erweitert" is unfolded
        reg = {}
        ui_layout(app.tab_log, reg)
        assert str(app.adv_frame) in reg and not ui_shown(app.adv_frame)
        app._toggle_advanced()
        assert ui_shown(app.adv_frame) and app.settings["show_advanced"] is True
        # opening the settings fills the stats check (no data: one line, no pointer to a page that is gone)
        assert app.off_check_var.get() == ""
        app.nb.select(app.tab_settings)
        app._tab_changed()
        assert app.off_check_var.get() == "Noch keine offiziellen Daten."
    finally:
        app.quit()


def test_an_update_shows_what_is_new_once(app_root):
    """1.8.79: the first start only remembers the version; a start with another version remembered lists the
    HISTORY.md rows after it on the overview until "Verstanden"."""
    import json
    from fogscout import __version__, overview
    from fogscout.app import App
    (app_root / "settings.json").write_text(json.dumps({"welcome_seen": True}), encoding="utf-8")
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        assert app.settings["seen_version"] == __version__ and app._news == []
    finally:
        app.quit()
    (app_root / "HISTORY.md").write_text("| A 1.0.1 (alt) | x |\n| B 1.0.2 (neu) | x |\n", encoding="utf-8")
    (app_root / "settings.json").write_text(json.dumps({"welcome_seen": True, "seen_version": "1.0.1"}),
                                            encoding="utf-8")
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        assert app._news == [("1.0.2", "B", "neu")] and app.settings["seen_version"] == "1.0.1"
        o = overview.overview_model(app, time.time(), is_win=False)
        assert o.news == [("1.0.2", "B", "neu")] and o.news_since == "Neu seit 1.0.1"
        app._qt_event("news_seen")
        assert app._news == [] and app.settings["seen_version"] == __version__
        assert overview.overview_model(app, time.time(), is_win=False).news == []
    finally:
        app.quit()


def test_the_history_is_copied_before_it_is_cleared(app_root):
    """1.8.80: the start copies rounds.jsonl/official.jsonl to backup/ (in a thread; here the worker is run in
    line), the settings' hint counts the copies, and "Verlauf löschen" takes one more copy first."""
    import json
    from fogscout import backups, history
    from fogscout.app import App
    (app_root / "settings.json").write_text(json.dumps({"welcome_seen": True}), encoding="utf-8")
    history.append(str(app_root / "rounds.jsonl"), history.Round(time.time() - 900, 600, "coal", "Coal Tower"))
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        end = time.time() + 10
        while time.time() < end and not os.path.isdir(app_root / "backup"):       # the start's thread
            time.sleep(0.05)
        app._backup_done(backups.snapshot(str(app_root)))                       # nothing new: only the hint
        names = sorted(os.listdir(app_root / "backup"))
        assert len(names) == 1 and names[0].startswith("rounds-") and "1 Dateien" in app.backup_var.get()
        app._ask = lambda *a, **k: True
        app._stats_clear()
        names = sorted(os.listdir(app_root / "backup"))
        assert len(names) == 2 and any(n.endswith("-vorher.jsonl") for n in names)
        assert not os.path.exists(app_root / "rounds.jsonl")
        assert "2 Dateien" in app.backup_var.get()
        assert any("Sicherung: rounds-" in e[2] and "-vorher.jsonl" in e[2] for e in app._log_entries)
    finally:
        app.quit()


def test_the_search_finds_statistics_tabs_and_log_categories(app_root):
    """1.8.82 (UI review idea 5): the search field (Ctrl+F) also lists the statistics' groups and parts and the
    log's categories; going to a statistics part opens its group and the part, and the model follows."""
    import json
    from fogscout.app import App
    (app_root / "settings.json").write_text(json.dumps({"welcome_seen": True}), encoding="utf-8")
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        app._qt_event("search_open")                                      # every page built and filled
        app.qapp.processEvents()
        app._qt_refresh(force=True)
        app.qt.update_search_index()
        found = app.qt._found
        assert "Gegner  ·  Statistik" in found and "Gegner & Builds  ·  Statistik" in found
        assert "Letzte Runden  ·  Statistik" in found and "Overlay  ·  Log" in found      # a log category
        assert app._stats_current_title() == "Übersicht"
        app.qt.go_to_found("Gegner  ·  Statistik")
        for _i in range(5):
            app.qapp.processEvents()
            app._poll()
        assert app.qt.current_key() == "stats" and app._stats_current_title() == "Gegner"
        assert app.stats_nb.tab(app.stats_nb.select(), "text") == "Gegner & Builds"
    finally:
        app.quit()


def test_a_round_without_hwinfo_is_said_once_per_dbd_start(app_root):
    """1.8.86 (user: empty CPU columns in the statistics): with the system values on and DBD running, the log says
    once per DBD start that HWiNFO is not running – after HWINFO_WAIT_S, not again until DBD was closed."""
    import json
    from fogscout import app_sysinfo
    from fogscout.app import App
    from fogscout.sysinfo import Snapshot
    (app_root / "settings.json").write_text(json.dumps({"welcome_seen": True}), encoding="utf-8")
    app = App(str(app_root), simulate=str(app_root / "sim"))
    try:
        told = lambda: sum(1 for e in app._log_entries if "HWiNFO läuft nicht" in e[2])   # noqa: E731
        now = time.time()
        app.game = object()
        app.sysmon.active = True
        app.sysmon.snapshot = Snapshot(cpu_load=10, t=now)
        app._hwinfo_check(now)
        app._hwinfo_check(now + app_sysinfo.HWINFO_WAIT_S - 1)
        assert told() == 0
        app.sysmon.snapshot = Snapshot(cpu_load=10, t=now + app_sysinfo.HWINFO_WAIT_S)
        app._hwinfo_check(now + app_sysinfo.HWINFO_WAIT_S)
        app._hwinfo_check(now + app_sysinfo.HWINFO_WAIT_S + 30)
        assert told() == 1                                               # once
        app.game = None
        app._hwinfo_check(now + 100)                                     # DBD gone: the next start may say it again
        app.game = object()
        app.sysmon.snapshot = Snapshot(cpu_load=10, t=now + 200)
        app._hwinfo_check(now + 200)
        app.sysmon.snapshot = Snapshot(cpu_load=10, t=now + 200 + app_sysinfo.HWINFO_WAIT_S)   # a fresh reading
        app._hwinfo_check(now + 200 + app_sysinfo.HWINFO_WAIT_S)
        assert told() == 2
        app.sysmon.snapshot = Snapshot(cpu_load=10, t=now + 300, hwinfo=True)       # HWiNFO there: never
        app.game = None
        app._hwinfo_check(now + 300)
        app.game = object()
        app._hwinfo_check(now + 300)
        app._hwinfo_check(now + 400)
        assert told() == 2
    finally:
        app.quit()
