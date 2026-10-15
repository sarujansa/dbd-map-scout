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
    keys = [k for k, _l, _s in qt_window.PAGES]
    steps = []

    def step(i=0):
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
        elif i == len(keys) + 1:
            assert len(app.qt.dialogs) == 2
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
