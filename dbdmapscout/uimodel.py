"""UI model of the control window (since 1.57, replaces the Tk widgets).

The tabs and dialogs are built from these plain Python objects; the Qt window (qt_window.py) draws them and hands
clicks back (app_qt.ui_act). The API is a small, Tk-like subset on purpose: the tab code reads as it did with
tkinter (``Label(parent, textvariable=…).pack(side="left")``), and pack order/``pack_forget`` still decide what
is shown where. Nothing here draws, measures or waits – sizes, fonts, scrolling and wrapping are Qt's job, so
options like ``width``/``padding``/``wraplength`` are accepted and ignored.
"""
from __future__ import annotations

import itertools
from types import SimpleNamespace

_ids = itertools.count(1)


class UIError(Exception):
    """A widget that is gone (like tkinter's TclError for destroyed widgets)."""


# ------------------------------------------------------------------ variables
class Var:
    default = None

    def __init__(self, master=None, value=None):
        self._value = self.default if value is None else value
        self._traces = []

    def get(self):
        return self._value

    def set(self, value):
        self._value = value
        for cb in list(self._traces):
            cb(str(id(self)), "", "write")

    def trace_add(self, mode, callback):
        self._traces.append(callback)


class StringVar(Var):
    default = ""

    def get(self):
        return "" if self._value is None else str(self._value)


class BooleanVar(Var):
    default = False

    def get(self):
        return bool(self._value)


class DoubleVar(Var):
    default = 0.0

    def get(self):
        return float(self._value)


class IntVar(Var):
    default = 0

    def get(self):
        return int(self._value)


# ------------------------------------------------------------------ widgets
class Widget:
    """Base of all widgets: options, pack/grid placement (order kept), states, bindings."""
    IGNORED = {"width", "height", "padding", "wraplength", "justify", "anchor", "compound", "font", "relief",
               "borderwidth", "highlightthickness", "padx", "pady", "cursor", "takefocus", "underline"}

    def __init__(self, master=None, **kw):
        self.master = master
        self._children = []
        self._packed = []                       # children placed with pack(), in pack order
        self._manager = ""                      # "pack" | "grid" | "notebook" | ""
        self._pack = {}
        self._grid = {}
        self._opts = {}
        self._binds = {}
        self._disabled = False
        self._alive = True
        name = kw.pop("name", None) or f"{type(self).__name__.lower()}{next(_ids)}"
        parent = "" if master is None or str(master) == "." else str(master)
        self._path = f"{parent}.{name}"
        if master is not None:
            master._children.append(self)
        self.configure(**kw)

    def __str__(self):
        return self._path

    def __repr__(self):
        return f"<{type(self).__name__} {self._path}>"

    # -- options
    def configure(self, **kw):
        for key, value in kw.items():
            if key == "state":
                self._set_state(value)
            elif key not in self.IGNORED:
                self._opts[key] = value

    config = configure

    def _set_state(self, value):
        self._disabled = str(value) == "disabled"
        self._opts["state"] = str(value)

    def cget(self, key):
        if key == "text":
            var = self._opts.get("textvariable")
            return var.get() if var is not None else str(self._opts.get("text", ""))
        if key == "state":
            return self._opts.get("state", "normal")
        return self._opts.get(key, "")

    def __getitem__(self, key):
        return self.cget(key)

    def state(self, spec=None):
        for s in spec or ():
            if s == "disabled":
                self._disabled = True
            elif s == "!disabled":
                self._disabled = False
        return ("disabled",) if self._disabled else ()

    def instate(self, spec):
        for s in spec:
            if s == "disabled" and not self._disabled:
                return False
            if s == "!disabled" and self._disabled:
                return False
            if s == "selected" and not self._selected():
                return False
        return True

    def _selected(self) -> bool:
        return False

    # -- placement
    def pack(self, **kw):
        m = self.master
        if m is None:
            return
        if self in m._packed:
            m._packed.remove(self)
        self._manager, self._grid = "pack", {}
        self._pack = {k: v for k, v in kw.items() if k in ("side", "fill", "expand", "anchor")}
        ref = kw.get("before") or kw.get("after")
        if ref is not None and ref in m._packed:
            i = m._packed.index(ref) + (1 if "after" in kw else 0)
            m._packed.insert(i, self)
        else:
            m._packed.append(self)

    def pack_forget(self):
        if self.master is not None and self in self.master._packed:
            self.master._packed.remove(self)
        if self._manager == "pack":
            self._manager = ""

    def grid(self, row=0, column=0, **_kw):
        self.pack_forget()
        self._manager, self._grid = "grid", {"row": int(row), "column": int(column)}

    def grid_forget(self):
        if self._manager == "grid":
            self._manager, self._grid = "", {}

    def pack_info(self) -> dict:
        if self._manager != "pack":
            raise UIError(f"{self} is not packed")
        return {"side": "top", **self._pack}

    def grid_info(self) -> dict:
        return dict(self._grid)

    def winfo_manager(self) -> str:
        return self._manager

    def winfo_children(self) -> list:
        return [c for c in self._children if c._alive]

    def placed_children(self) -> list:
        """Children as they are shown: packed ones in pack order, then gridded ones in creation order."""
        return [c for c in self._packed if c._alive] + [c for c in self._children
                                                        if c._alive and c._manager == "grid"]

    def winfo_exists(self) -> bool:
        return self._alive

    def nametowidget(self, path):
        stack = [self]
        while stack:
            w = stack.pop()
            if str(w) == str(path):
                return w
            stack.extend(w._children)
        raise UIError(f"no widget {path}")

    # -- events
    def bind(self, sequence, callback=None, add=None):
        if callback is None:
            return None
        if add:
            self._binds.setdefault(sequence, []).append(callback)
        else:
            self._binds[sequence] = [callback]
        return sequence

    def unbind(self, sequence, _funcid=None):
        self._binds.pop(sequence, None)

    def event_generate(self, sequence, **_kw):
        event = SimpleNamespace(widget=self, x=0, y=0, x_root=0, y_root=0, delta=0, num=0, keysym="", char="",
                                state=0, keycode=0)
        for cb in list(self._binds.get(sequence, ())):
            cb(event)

    def destroy(self):
        if not self._alive:
            return
        for c in list(self._children):
            c.destroy()
        self._alive = False
        self.pack_forget()
        if self.master is not None and self in self.master._children:
            self.master._children.remove(self)
        for cb in list(self._binds.get("<Destroy>", ())):
            cb(SimpleNamespace(widget=self))

    # -- no-ops of the old window (focus, scrolling): kept so callers need no special cases
    def focus_set(self):
        pass

    focus_force = focus_set

    def update_idletasks(self):
        pass


class Root(Widget):
    """Top of the main window's model (the tabs hang below its notebook)."""

    def __init__(self):
        super().__init__(None, name="")
        self._path = "."


class Frame(Widget):
    pass


class LabelFrame(Widget):
    """A card with a title (``text``)."""


class Label(Widget):
    """Text (``text``/``textvariable``) or a picture (``image`` = PIL image). Kind from ``style``:
    "Big.TLabel" = big value, "Dim.TLabel" = grey hint."""


class Button(Widget):
    def invoke(self):
        cmd = self._opts.get("command")
        if cmd is not None and not self._disabled:
            return cmd()
        return None


class Checkbutton(Widget):
    def __init__(self, master=None, **kw):
        kw.setdefault("variable", BooleanVar())
        super().__init__(master, **kw)

    def _selected(self) -> bool:
        return bool(self._opts["variable"].get())

    def invoke(self):
        if self._disabled:
            return None
        var = self._opts["variable"]
        var.set(not var.get())
        cmd = self._opts.get("command")
        return cmd() if cmd is not None else None


class Radiobutton(Widget):
    def _selected(self) -> bool:
        var = self._opts.get("variable")
        return var is not None and var.get() == self._opts.get("value")

    def invoke(self):
        if self._disabled:
            return None
        var = self._opts.get("variable")
        if var is not None:
            var.set(self._opts.get("value"))
        cmd = self._opts.get("command")
        return cmd() if cmd is not None else None


class Combobox(Widget):
    """A choice; ``state`` "readonly" = only the values, "normal" = also typed text, "disabled"."""

    def __init__(self, master=None, **kw):
        kw.setdefault("textvariable", StringVar())
        kw.setdefault("state", "normal")
        super().__init__(master, **kw)

    def get(self) -> str:
        return self._opts["textvariable"].get()

    def set(self, value):
        self._opts["textvariable"].set(value)

    def editable(self) -> bool:
        return self.cget("state") == "normal"


class Entry(Widget):
    def __init__(self, master=None, **kw):
        kw.setdefault("textvariable", StringVar())
        super().__init__(master, **kw)

    def get(self) -> str:
        return self._opts["textvariable"].get()

    def delete(self, _first, _last=None):
        self._opts["textvariable"].set("")

    def insert(self, _index, text):
        var = self._opts["textvariable"]
        var.set(var.get() + str(text))


class Scale(Widget):
    """A slider: ``from_``/``to``, ``variable``; ``set()`` runs ``command`` (like a drag in Tk)."""

    def __init__(self, master=None, **kw):
        kw.setdefault("variable", DoubleVar())
        if "from_" in kw:
            kw["from"] = kw.pop("from_")
        super().__init__(master, **kw)

    def get(self) -> float:
        return float(self._opts["variable"].get())

    def set(self, value):
        lo, hi = float(self._opts.get("from", 0)), float(self._opts.get("to", 100))
        self._opts["variable"].set(min(max(float(value), min(lo, hi)), max(lo, hi)))
        cmd = self._opts.get("command")
        if cmd is not None:
            cmd(str(value))


class Notebook(Widget):
    """Pages with a title; ``select()`` without argument = path of the page on display."""

    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        self._tabs = []                         # [(page, title)]
        self._current = None

    def add(self, page, text=""):
        self._tabs.append([page, text])
        page._manager = "notebook"
        if self._current is None:
            self._current = page

    def tabs(self) -> list:
        return [str(p) for p, _t in self._tabs if p._alive]

    def _page(self, tab_id):
        if isinstance(tab_id, int):
            return self._tabs[tab_id][0]
        for p, _t in self._tabs:
            if p is tab_id or str(p) == str(tab_id):
                return p
        raise UIError(f"no tab {tab_id}")

    def select(self, tab_id=None):
        if tab_id is None:
            return str(self._current) if self._current is not None else ""
        page = self._page(tab_id)
        if page is not self._current:
            self._current = page
            self.event_generate("<<NotebookTabChanged>>")
        return None

    def index(self, tab_id):
        if tab_id == "current":
            return next((i for i, (p, _t) in enumerate(self._tabs) if p is self._current), 0)
        page = self._page(tab_id)
        return next(i for i, (p, _t) in enumerate(self._tabs) if p is page)

    def tab(self, tab_id, option=None, **kw):
        page = self._page(tab_id)
        entry = next(t for t in self._tabs if t[0] is page)
        if "text" in kw:
            entry[1] = kw["text"]
        if option == "text":
            return entry[1]
        return {"text": entry[1]}


# tags of a Treeview row that the window draws as a tick box in the first column (a click on the row goes to the
# model as usual, the model decides what it toggles) – the server tab's regions
CHECK_ON, CHECK_OFF, CHECK_PART = "check:on", "check:off", "check:part"


class Treeview(Widget):
    """Table (``show`` "headings") or tree ("tree"/"tree headings") with rows by iid, tags with colours,
    selection and heading commands (sorting)."""

    def __init__(self, master=None, **kw):
        kw.setdefault("columns", ())
        kw.setdefault("show", "tree headings")
        kw.setdefault("selectmode", "browse")
        self._headings = {"#0": {"text": "", "anchor": "w", "command": None}}
        self._columns = {}
        self._items = {}                        # iid -> {"text", "values", "tags", "open", "parent"}
        self._kids = {"": []}
        self._sel = []
        self._focus = ""
        self._tags = {}
        self._auto = itertools.count(1)
        super().__init__(master, **kw)

    def configure(self, **kw):
        if "columns" in kw:
            kw["columns"] = tuple(kw["columns"])
            for c in kw["columns"]:
                self._headings.setdefault(c, {"text": "", "anchor": "w", "command": None})
        super().configure(**kw)

    def cget(self, key):
        if key == "columns":
            return tuple(self._opts.get("columns", ()))
        return super().cget(key)

    def heading(self, column, option=None, **kw):
        h = self._headings.setdefault(column, {"text": "", "anchor": "w", "command": None})
        h.update({k: v for k, v in kw.items() if k in ("text", "anchor", "command")})
        if option is not None:
            return h.get(option, "")
        return dict(h)

    def column(self, column, option=None, **kw):
        c = self._columns.setdefault(column, {})
        c.update(kw)
        return c.get(option) if option is not None else dict(c)

    def insert(self, parent, index, iid=None, **kw):
        iid = str(iid) if iid is not None else f"I{next(self._auto):03d}"
        if iid in self._items:
            raise UIError(f"item {iid} already exists")
        self._items[iid] = {"text": str(kw.get("text", "")), "values": tuple(kw.get("values", ()) or ()),
                            "tags": tuple([kw["tags"]] if isinstance(kw.get("tags"), str) else kw.get("tags", ()) or ()),
                            "open": bool(kw.get("open", False)), "parent": parent}
        kids = self._kids.setdefault(parent, [])
        if index == "end" or not isinstance(index, int):
            kids.append(iid)
        else:
            kids.insert(index, iid)
        self._kids[iid] = []
        return iid

    def delete(self, *iids):
        for iid in iids:
            if iid not in self._items:
                continue
            self.delete(*list(self._kids.get(iid, ())))
            parent = self._items.pop(iid)["parent"]
            self._kids.pop(iid, None)
            if iid in self._kids.get(parent, []):
                self._kids[parent].remove(iid)
            if iid in self._sel:
                self._sel.remove(iid)

    def get_children(self, item=""):
        return tuple(self._kids.get(item, ()))

    def exists(self, iid) -> bool:
        return str(iid) in self._items

    def item(self, iid, option=None, **kw):
        it = self._items[str(iid)]
        for k, v in kw.items():
            if k in ("values", "tags"):
                v = (v,) if isinstance(v, str) else tuple(v or ())
            it[k] = v
        if option is not None:
            return it.get(option, "")
        return dict(it)

    def set(self, iid, column=None, value=None):
        it = self._items[str(iid)]
        cols = list(self.cget("columns"))
        if column is None:
            return dict(zip(cols, it["values"]))
        i = cols.index(column)
        if value is None:
            return it["values"][i] if i < len(it["values"]) else ""
        vals = list(it["values"]) + [""] * max(0, i + 1 - len(it["values"]))
        vals[i] = value
        it["values"] = tuple(vals)
        return None

    def selection(self):
        return tuple(self._sel)

    def selection_set(self, *iids):
        if len(iids) == 1 and isinstance(iids[0], (list, tuple)):
            iids = tuple(iids[0])
        self._sel = [str(i) for i in iids if str(i) in self._items]

    def selection_remove(self, *iids):
        self._sel = [i for i in self._sel if i not in {str(x) for x in iids}]

    def focus(self, iid=None):
        if iid is None:
            return self._focus
        self._focus = str(iid)
        return None

    def see(self, _iid):
        pass

    def tag_configure(self, tag, option=None, **kw):
        t = self._tags.setdefault(tag, {})
        t.update(kw)
        return t.get(option, "") if option is not None else dict(t)

    def rows(self, parent="", depth=0):
        """[(iid, depth, text, values, tags, open)] in display order (for the Qt table)."""
        out = []
        for iid in self._kids.get(parent, ()):
            it = self._items[iid]
            out.append((iid, depth, it["text"], [str(v) for v in it["values"]], [str(t) for t in it["tags"]],
                        it["open"]))
            out += self.rows(iid, depth + 1)
        return out


class Log(Widget):
    """The log page: ``lines()`` -> (entries [(time, category, text)], dark mode)."""

    def __init__(self, master=None, lines=None, **kw):
        super().__init__(master, **kw)
        self._dbdms_lines = lines


class Chart(Widget):
    """A statistics chart; ``source`` = trendchart.TrendChart (data, dark, panels)."""

    def __init__(self, master=None, source=None, **kw):
        super().__init__(master, **kw)
        self._dbdms_chart = source


class Dashboard(Widget):
    """The statistics dashboard (dashboard.Dashboard in ``data``), drawn by qt_window.DashboardView."""

    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        self.data = None
        self.dark = True


class Tiles(Widget):
    """A row of key figure tiles (dashboard.Tile list in ``data``) – fewer columns in a narrow window."""

    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        self.data = []


class Preview(Widget):
    """A picture the window draws from ``source()`` (a dict, read on every refresh) – clicks and drags on it go
    to ``command(value)``. The overlay tab's screen with the map on it (since 1.61)."""

    def __init__(self, master=None, source=None, command=None, **kw):
        super().__init__(master, **kw)
        self.source = source or (lambda: {})
        self.command = command


class Toplevel(Widget):
    """A dialog: shown by the Qt window as a non-modal window built from its content (App._dialog)."""

    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        self._title = ""
        self._dbdms_qt = None              # set by App._dialog

    def title(self, text=None):
        if text is None:
            return self._title
        self._title = str(text)
        return None

    def transient(self, *_a):
        pass

    def resizable(self, *_a):
        pass

    def minsize(self, *_a):
        pass

    def withdraw(self):
        pass

    def protocol(self, *_a):
        pass
