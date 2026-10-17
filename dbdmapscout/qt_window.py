"""The control window (Qt): navigation on the left, one page per area.

The window only shows and reports: every button calls ``post`` (→ App.events, handled in App._poll, in order
with the detection's events), and the App pushes its state from its own ticks (``show_model``, ``show_states``).
The pages draw the App's UI model (uimodel.py; app_qt.ui_state). No modal dialogs: ``exec()`` would run a second
event loop inside a click.
"""
from __future__ import annotations

import base64
import html
import sys

from PySide6.QtCore import QByteArray, QEvent, QObject, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFontDatabase, QIcon, QPalette, QPixmap
from PySide6.QtWidgets import (QAbstractScrollArea, QAbstractSlider, QAbstractSpinBox, QApplication, QComboBox,
                               QFrame, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QPushButton,
                               QScrollArea, QStackedWidget, QTabWidget, QVBoxLayout, QWidget)

from . import qt_theme
from .i18n import N_, _
from .mapimage import FONT as FIRA
from .qt_common import (SLIDER_MAX, pixmap_from_pil, _label, _tip, _card, _set, _scroll_page)
from .qt_views import (FactBox, CHECKS, _check, Table, LogView, HotkeyButton, Chart, HEAT_RAMP, BAR_NEUTRAL,
                       heat_colour, ink_on, MapBars, Heatmap, SwatchView, TilesView, DashboardView)
from .qt_preview import (PREVIEW_NAMES, PreviewView)
from .qt_maps import (TILE_W, TILE_H, TILE_PIC, ALL_MAPS, RECENT, MapTile, RealmDelegate, MapsPage)
from .qt_pages import (THUMB_H, SETUP_W, GAME_LANGS, SETUP_HOTKEYS, SETUP, OverviewPage, make_control, show_control,
                       Grip, CardColumn, _card_head, _Arranged, FitTabs, FormPage, FLOW_KINDS, _grows, _fills,
                       AutoPage, DialogWindow, SetupPage)


# The classes and helpers moved to qt_common / qt_views / qt_preview / qt_maps / qt_pages (1.2.14, analysis point 2)
# stay reachable here (the App, the tests)
__all__ = (
    'SLIDER_MAX',
    'pixmap_from_pil',
    '_label',
    '_tip',
    '_card',
    '_set',
    '_scroll_page',
    'FactBox',
    'CHECKS',
    '_check',
    'Table',
    'LogView',
    'HotkeyButton',
    'Chart',
    'HEAT_RAMP',
    'BAR_NEUTRAL',
    'heat_colour',
    'ink_on',
    'MapBars',
    'Heatmap',
    'SwatchView',
    'TilesView',
    'DashboardView',
    'PREVIEW_NAMES',
    'PreviewView',
    'TILE_W',
    'TILE_H',
    'TILE_PIC',
    'ALL_MAPS',
    'RECENT',
    'MapTile',
    'RealmDelegate',
    'MapsPage',
    'THUMB_H',
    'SETUP_W',
    'GAME_LANGS',
    'SETUP_HOTKEYS',
    'SETUP',
    'OverviewPage',
    'make_control',
    'show_control',
    'Grip',
    'CardColumn',
    '_card_head',
    '_Arranged',
    'FitTabs',
    'FormPage',
    'FLOW_KINDS',
    '_grows',
    '_fills',
    'AutoPage',
    'DialogWindow',
    'SetupPage',
)

# key, label (the navigation's icons are drawn by nav_icon: same size and place for all)
PAGES = (("overview", N_("Übersicht")), ("maps", "Maps"), ("overlay", N_("Overlay")), ("stats", N_("Statistik")),
         ("server", N_("Server")), ("settings", N_("Einstellungen")), ("detect", N_("Erkennung")), ("log", "Log"))


NAV_ICON = 18                     # px (logical): every icon of the navigation in the same box


NAV_W, NAV_COMPACT_W = 190, 62    # px (logical): navigation with names / only icons


NAV_COMPACT_BELOW = 960           # px (logical) window width from which the navigation shows only icons


AUTO_PAGES = ("stats", "server", "detect", "log")   # built from the tab's structure (app_qt.ui_layout)


FOUND_MS = 1800                   # ms a search hit's card stays lit
STYLE_IDLE_MS = 120               # ms between restyling two hidden pages after a theme/zoom change (1.3.4)


# Hand-made pages: every key names a widget of the UI model registered with App._reg; texts, values,
# enabled/shown come from it (App._qt_refresh → show_states), a click is done on it (post("act", (key, value))).
# ("card", frame key, rows) – a row is one control or ("row", [controls]); controls: ("check"|"button"|"combo"|
# "slider"|"label"|"hint", key), ("stretch",). ("panel", rows) = a card without title; ("tabs", [(frame key, tab
# label, rows)]) = one tab per frame (hidden with the frame).
SPECS = {
    "overlay": (
        # 1.66.4 (user: "6 passt"): the preview stays on top; 1.2.12 (analysis point 9): below it the tools for the
        # element picked (list, size, opacity, move/test/undo – on every tab), then one tab per element and
        # "Allgemein"; a click on an element in the preview opens its tab (MainWindow.open_tab)
        ("panel", (("preview", "ov.preview"),)),
        ("panel", (
            ("row", (("label", "ov.sel.label"), ("combo", "ov.sel"), ("stretch",))), ("slider", "ov.sel_size"),
            ("slider", "ov.opacity"), ("hint", "ov.size_scope"), ("hint", "ov.size_cap"),
            ("row", (("button", "ov.edit"), ("button", "ov.test"), ("button", "ov.undo"), ("stretch",))))),
        ("tabs", (
            ("ov.look", N_("Karte"), (
                ("row", (("label", "ov.anchor.label"), ("combo", "ov.anchor"), ("stretch",), ("button", "ov.reset"))),
                ("slider", "ov.posx"), ("slider", "ov.posy"), ("hint", "ov.pos_hint"),
                ("row", (("hint", "ov.map_size"), ("stretch",), ("button", "ov.map_size_reset"))),
                ("row", (("label", "ov.map_style.label"), ("combo", "ov.map_style"), ("stretch",))),
                ("sub", N_("Darstellung")), ("check", "ov.show_map"), ("check", "ov.caption"), ("check", "ov.floors"),
                ("check", "ov.transparent"), ("check", "ov.map_backdrop"), ("check", "ov.keep_bar"), ("check", "ov.grow"),
                ("sub", N_("Unter der Karte")), ("check", "ov.timer"), ("check", "ov.server"), ("check", "ov.record"),
                ("sub", N_("Wann zeigen")), ("check", "ov.focus"), ("check", "ov.waiting"))),
            ("ov.sys", N_("Systemwerte"), (
                ("row", (("label", "ov.sysinfo.label"), ("combo", "ov.sysinfo"), ("stretch",))),
                ("hint", "ov.sys_text"), ("hint", "ov.sys_hint"), ("check", "ov.hud_backdrop"),
                ("check", "ov.hud_row_cpu"), ("check", "ov.hud_row_gpu"), ("check", "ov.hud_row_spot"),
                ("check", "ov.hud_row_vram"), ("check", "ov.hud_row_ram"))),
            ("ov.today_f", N_("Heute"), (
                ("check", "ov.today"),
                ("row", (("label", "ov.today_pos.label"), ("combo", "ov.today_pos"), ("stretch",))),
                ("check", "ov.today_backdrop"))),
            ("ov.music_f", N_("Musik"), (
                ("check", "ov.media"), ("row", (("label", "ov.media_pos.label"), ("combo", "ov.media_pos"), ("stretch",))),
                ("row", (("label", "ov.media_style.label"), ("combo", "ov.media_style"), ("stretch",))),
                ("check", "ov.media_cover"), ("check", "ov.media_progress"), ("check", "ov.media_accent"),
                ("check", "ov.media_remaining"), ("check", "ov.media_backdrop"), ("check", "ov.media_fade"))),
            ("ov.pos", N_("Allgemein"), (
                ("row", (("label", "ov.style.label"), ("combo", "ov.style"), ("stretch",))),     # 1.3
                ("slider", "ov.gap"),
                ("row", (("label", "ov.bar_align.label"), ("combo", "ov.bar_align"), ("stretch",))),
                ("row", (("label", "ov.preset.label"), ("combo", "ov.preset"), ("button", "ov.preset_apply"),
                         ("stretch",))),
                ("check", "ov.fade"), ("check", "ov.per_size"), ("hint", "ov.per_size_hint"))))),
    ),
    "settings": (
        ("card", "st.look", (
            ("row", (("label", "st.lang.label"), ("combo", "st.lang"), ("stretch",))), ("hint", "st.lang_note"),
            ("check", "st.dark"),
            ("row", (("label", "st.theme.label"), ("combo", "st.theme"), ("stretch",))), ("swatches", "st.swatches"),
            ("check", "st.oled"),
            ("row", (("label", "st.zoom.label"), ("combo", "st.zoom"), ("stretch",))),
            ("row", (("button", "st.card_reset"), ("hint", "st.card_hint"))))),
        ("card", "st.notify", (
            ("check", "st.lobby_notify"), ("check", "st.lobby_remind"), ("check", "st.notify_background_only"),
            ("hint", "st.notify_text"), ("row", (("button", "st.notify_test"), ("stretch",))))),
        ("card", "st.start", (("check", "st.tray"), ("check", "st.autostart"), ("hint", "st.autostart_info"),
                              ("row", (("button", "st.setup_again"), ("stretch",))))),
        ("card", "st.hotkeys", (
            ("grid", 2, tuple(("row", (("label", f"st.hk.{k}.label"), ("stretch",), ("hotkey", f"st.hk.{k}")))
                              for k in ("toggle_overlay", "next_variant", "scan_now", "prev_map", "next_map",
                                        "bigger", "smaller", "edit_position", "rotate_map", "next_floor",
                                        "reject_map", "mark_clip"))),
            ("row", (("button", "st.hk_defaults"), ("hint", "st.hk_status"))))),
        ("card", "st.updates", (
            ("check", "st.update"), ("hint", "st.update_note"),
            ("row", (("button", "st.upd_btn"), ("button", "st.upd_apply"), ("stretch",))), ("hint", "st.upd_status"),
            ("hint", "st.version"))),                 # 1.2.19: the version where the updates are
        ("row", (("button", "st.more_btn"), ("stretch",))),
        ("card", "st.more.own", (("row", (("hint", "st.more.aliases"), ("button", "st.more.aliases_clear"))),)),
        ("card", "st.more.official", (("check", "st.more.off_open"), ("check", "st.more.off_notify"),
                                      ("row", (("button", "st.more.script"), ("stretch",))), ("hint", "st.more.off_text"))),
        ("card", "st.more.farming", (("check", "st.more.farm_cross"),                       # 1.2.20
                                     ("row", (("label", "st.more.farm_region.label"), ("combo", "st.more.farm_region"),
                                              ("stretch",))),
                                     ("hint", "st.more.farm_text"))),
        ("card", "st.more.rec", (("check", "st.more.rec_on"),                              # 1.4: OBS recordings
                                 ("row", (("label", "st.more.rec_port.label"), ("entry", "st.more.rec_port"),
                                          ("label", "st.more.rec_pw.label"), ("entry", "st.more.rec_pw"),
                                          ("button", "st.more.rec_test"), ("stretch",))),
                                 ("row", (("button", "st.more.rec_dir"), ("hint", "st.more.rec_folder"))),
                                 ("row", (("label", "st.more.rec_limit.label"), ("combo", "st.more.rec_limit"),
                                          ("stretch",))),
                                 ("check", "st.more.rec_pre"), ("check", "st.more.rec_buffer"),
                                 ("check", "st.more.rec_merge"), ("hint", "st.more.rec_ffmpeg"),
                                 ("row", (("label", "st.more.rec_tail.label"), ("combo", "st.more.rec_tail"),
                                          ("stretch",))),
                                 ("hint", "st.more.rec_status"),
                                 ("hint", "st.more.rec_text"))),
        ("card", "st.more.backup", (("row", (("button", "st.more.export"), ("button", "st.more.import"), ("stretch",),
                                             ("button", "st.more.clear_hist"), ("button", "st.more.reset_all"))),)),
        ("card", "st.more.folders", (("row", (("button", "st.more.dir"), ("button", "st.more.maps_dir"), ("stretch",))),)),
    ),
}


def _spec_keys(items):
    for it in items:
        kind = it[0]
        if kind == "card":
            yield it[1]
            yield from _spec_keys(it[2])
        elif kind in ("row", "panel"):
            yield from _spec_keys(it[1])
        elif kind == "tabs":
            for frame, _label_, rows in it[1]:
                yield frame
                yield from _spec_keys(rows)
        elif kind == "grid":
            yield from _spec_keys(it[2])
        elif kind in ("check", "button", "combo", "slider", "label", "hint", "value", "plain", "hotkey", "preview", "entry",
                      "swatches"):
            yield it[1]


def page_keys(page: str | None = None) -> set:
    """Widget keys a hand-made page shows (all pages without ``page``) – also the whitelist for its clicks."""
    if page == "setup":
        return {k for _t, items in SETUP for k in _spec_keys(items)}
    pages = [page] if page else list(SPECS) + ["setup"]
    return {k for p in pages for k in (page_keys("setup") if p == "setup" else _spec_keys(SPECS.get(p, ())))}


def application() -> QApplication:
    """The one QApplication of the process (main thread, before any widget)."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
        app.setStyle("Fusion")
        app.setQuitOnLastWindowClosed(False)          # closing goes through the App (quit / tray)
        QFontDatabase.addApplicationFont(FIRA)         # map names like on the map pictures
    global _WHEEL_GUARD
    if _WHEEL_GUARD is None:
        _WHEEL_GUARD = WheelGuard(app)
        app.installEventFilter(_WHEEL_GUARD)
    return app


_WHEEL_GUARD = None                                    # kept here: Python would free the filter otherwise


class WheelGuard(QObject):
    """The mouse wheel scrolls the page, never a setting (1.64.8, user: scrolling the page changed some random
    field). Qt hands the wheel to the combo box or slider under the mouse; here it goes to the page's scroll bar."""

    def eventFilter(self, obj, event):
        if event.type() != QEvent.Wheel or not isinstance(obj, (QComboBox, QAbstractSlider, QAbstractSpinBox)):
            return False
        if isinstance(obj, QAbstractSlider) and obj.inherits("QScrollBar"):
            return False                               # the scroll bars themselves scroll as usual
        area = obj.parentWidget()
        while area is not None and not isinstance(area, QAbstractScrollArea):
            area = area.parentWidget()
        if area is not None:
            QApplication.sendEvent(area.verticalScrollBar(), event)
        return True                                    # the setting never changes


def nav_icon(key: str, colour: str, ratio: float = 1.0, alert: bool = False) -> QPixmap:
    """One icon of the navigation, drawn as lines (not a font character: symbols from different fonts came out
    in different sizes and places). All in a NAV_ICON box, 1.6 px lines; ``alert`` = amber dot (log)."""
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QPainter, QPen
    size = NAV_ICON
    pm = QPixmap(round(size * ratio), round(size * ratio))
    pm.setDevicePixelRatio(ratio)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    col = QColor(colour)
    pen = QPen(col, 1.6)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    m, c = 2.5, size / 2                       # margin, centre
    full = QRectF(m, m, size - 2 * m, size - 2 * m)
    if key == "overview":                      # target: ring + dot
        p.drawEllipse(QPointF(c, c), 6.5, 6.5)
        p.setBrush(col)
        p.drawEllipse(QPointF(c, c), 2.4, 2.4)
    elif key == "maps":                        # four tiles
        g = (size - 2 * m - 2) / 2
        for x in (m, m + g + 2):
            for y in (m, m + g + 2):
                p.drawRoundedRect(QRectF(x, y, g, g), 1.5, 1.5)
    elif key == "overlay":                     # a screen with a picture in its left part
        p.drawRoundedRect(full, 2, 2)
        p.setBrush(col)
        p.drawRoundedRect(QRectF(m + 2.5, m + 2.5, (size - 2 * m) * 0.4, size - 2 * m - 5), 1, 1)
    elif key == "stats":                       # three columns on a base line
        base = size - m
        for i, h in enumerate((5, 11, 8)):
            x = m + 1.5 + i * 4.6
            p.drawLine(QPointF(x, base - 1.5), QPointF(x, base - 1.5 - h))
        p.drawLine(QPointF(m, base), QPointF(size - m, base))
    elif key == "server":                      # globe
        p.drawEllipse(QPointF(c, c), 6.5, 6.5)
        p.drawEllipse(QPointF(c, c), 2.8, 6.5)
        p.drawLine(QPointF(c - 6.5, c), QPointF(c + 6.5, c))
    elif key == "settings":                    # gear: ring + eight teeth
        import math
        p.drawEllipse(QPointF(c, c), 4.6, 4.6)
        p.drawEllipse(QPointF(c, c), 1.7, 1.7)
        tooth = QPen(col, 2.6)
        tooth.setCapStyle(Qt.FlatCap)
        p.setPen(tooth)
        for i in range(8):
            a = i * math.pi / 4 + math.pi / 8
            p.drawLine(QPointF(c + 5.2 * math.cos(a), c + 5.2 * math.sin(a)),
                       QPointF(c + 7.4 * math.cos(a), c + 7.4 * math.sin(a)))
    elif key == "detect":                      # scan frame: four corners + a dot
        k = 4.0
        for (x, y, dx, dy) in ((m, m, 1, 1), (size - m, m, -1, 1), (m, size - m, 1, -1), (size - m, size - m, -1, -1)):
            p.drawLine(QPointF(x, y), QPointF(x + dx * k, y))
            p.drawLine(QPointF(x, y), QPointF(x, y + dy * k))
        p.setBrush(col)
        p.drawEllipse(QPointF(c, c), 2.2, 2.2)
    elif key == "search":                      # magnifier
        p.drawEllipse(QPointF(c - 1.5, c - 1.5), 5.0, 5.0)
        p.drawLine(QPointF(c + 2.2, c + 2.2), QPointF(size - m, size - m))
    elif key == "log":                         # lines of text
        for i, w in enumerate((1.0, 0.75, 0.9)):
            y = m + 2 + i * 5
            p.drawLine(QPointF(m, y), QPointF(m + (size - 2 * m) * w, y))
    if alert:
        from .theme import DOT
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(DOT["warn"]))
        p.drawEllipse(QPointF(size - 3.5, size - 3.5), 3.5, 3.5)
    p.end()
    return pm


SEARCH_KINDS = ("check", "radio", "button", "title", "label", "slider")   # what the search finds on a page


def _tab_of(w):
    """[(QTabWidget, its tab page holding w)] for every tab widget above w, innermost first."""
    out, child, p = [], w, w.parentWidget()
    while p is not None:
        if isinstance(p, QStackedWidget) and isinstance(p.parentWidget(), QTabWidget):
            out.append((p.parentWidget(), child))
        child, p = p, p.parentWidget()
    return out


def _reachable(w, page) -> bool:
    """Shown on the page, or on a tab that is not open now (the search goes there)."""
    tabs = _tab_of(w)
    if not tabs:
        return w.isVisibleTo(page)
    return (w.isVisibleTo(tabs[0][1]) and all(tw.isTabVisible(tw.indexOf(body)) for tw, body in tabs)
            and tabs[-1][0].isVisibleTo(page))


def _open_tabs(w):
    for tw, body in reversed(_tab_of(w)):
        tw.setCurrentWidget(body)


class MainWindow(QMainWindow):
    def __init__(self, post, icon_path: str | None = None, layouts: dict | None = None):
        super().__init__()
        self._post = post
        self.allow_close = False          # closing = quitting the program, through the App
        self.geometry_changed = False     # read and reset by the App (it saves the geometry, debounced)
        self.minimised = False
        self.setWindowTitle("DbD Map Scout")
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        central = QWidget()
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(NAV_W)
        self._nav_compact = False
        self._nav_kept = False
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.stack = QStackedWidget()
        self.overview = OverviewPage(post)
        self.maps = MapsPage(post)
        self.forms = {key: FormPage(post, _(label), SPECS[key], key) for key, label in PAGES if key in SPECS}
        for key, label in PAGES:
            if key in AUTO_PAGES and (layouts or {}).get(key):
                self.forms[key] = AutoPage(post, _(label), layouts[key], key)
        self.nav.setIconSize(QSize(NAV_ICON, NAV_ICON))
        for key, label in PAGES:
            item = QListWidgetItem(_(label))
            item.setData(Qt.UserRole, key)
            self.nav.addItem(item)
            page = {"overview": self.overview, "maps": self.maps}.get(key) or self.forms.get(key) or QWidget()
            self.stack.addWidget(page)
        self.setup = SetupPage(post)
        self.stack.addWidget(self.setup)
        self._setup_on = False
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self._page_changed)
        # search over the settings of all pages (1.60): a field above the navigation, Ctrl+F
        side = QWidget()
        side.setObjectName("navside")
        self._side = side
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)
        self.search = QLineEdit()
        self.search.setObjectName("navsearch")
        self.search.setPlaceholderText(_("Einstellung suchen …"))
        self.search.setClearButtonEnabled(True)
        self.search.setFocusPolicy(Qt.ClickFocus)  # not the window's first focus: only by a click or Ctrl+F
        self.search_btn = QPushButton()
        self.search_btn.setObjectName("navsearchbtn")
        self.search_btn.setToolTip(_("Einstellung suchen (Strg+F)"))
        self.search_btn.clicked.connect(self.focus_search)
        self.search_btn.hide()
        sl.addWidget(self.search)
        sl.addWidget(self.search_btn)
        sl.addWidget(self.nav, 1)
        self._found = {}                  # completer text -> (page key, widget)
        from PySide6.QtCore import QStringListModel
        from PySide6.QtWidgets import QCompleter
        self._search_model = QStringListModel()
        self.completer = QCompleter(self._search_model, self)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)
        self.completer.setMaxVisibleItems(12)
        self.completer.activated.connect(self.go_to_found)
        self.search.setCompleter(self.completer)
        self.search.installEventFilter(self)
        self.search.returnPressed.connect(self._search_first)
        from PySide6.QtGui import QKeySequence, QShortcut
        QShortcut(QKeySequence.Find, self, activated=self.focus_search)
        # 1.65: undo of place/size on the overlay page (a text field keeps its own Ctrl+Z)
        QShortcut(QKeySequence.Undo, self, activated=lambda: self.current_key() == "overlay" and self._post("undo"))
        lay.addWidget(side)
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        # OK/Cancel or a note (App._ask/_inform) – a bar, not a modal dialog
        self.question = QFrame()
        self.question.setObjectName("question")
        ql = QHBoxLayout(self.question)
        ql.setContentsMargins(16, 10, 16, 10)
        self.question_text = _label(wrap=True)
        ql.addWidget(self.question_text, 1)
        self.question_ok = QPushButton(_("OK"))
        self.question_ok.setObjectName("primary")
        self.question_ok.clicked.connect(lambda: post("answer", True))
        self.question_cancel = QPushButton(_("Abbrechen"))
        self.question_cancel.clicked.connect(lambda: post("answer", False))
        ql.addWidget(self.question_ok, alignment=Qt.AlignVCenter)
        ql.addWidget(self.question_cancel, alignment=Qt.AlignVCenter)
        self.question.hide()
        self._question = None
        right.addWidget(self.question)
        right.addWidget(self.stack, 1)
        lay.addLayout(right, 1)
        self.setCentralWidget(central)
        self.resize(1100, 760)
        self.setMinimumSize(560, 480)            # narrower: the navigation shows only icons, the pages wrap
        self._log_alert = False
        self._dark = True
        self._nav_icons()
        self.dialogs = {}                 # dialog path (UI model) -> DialogWindow
        self._qss = ""                    # the style sheet, set per part (_style_lazily)
        self._stale = []                  # pages still waiting for it
        self._style_timer = QTimer(self)  # owned by the window: it dies with it (a test deletes windows)
        self._style_timer.setSingleShot(True)
        self._style_timer.setInterval(STYLE_IDLE_MS)
        self._style_timer.timeout.connect(self._style_next)

    def _page_changed(self, row):
        self._setup_on = False                                     # the navigation leaves the assistant
        if 0 <= row < self.stack.count():
            self._style_page(self.stack.widget(row))
        self.stack.setCurrentIndex(row)
        self._post("page", PAGES[row][0])                          # the App fills it now

    def current_key(self) -> str:
        return "setup" if self._setup_on else PAGES[max(0, self.nav.currentRow())][0]

    def show_setup(self, on: bool = True):
        """The setup assistant instead of a page (first start); the navigation still leads away from it."""
        self._setup_on = bool(on)
        if on:
            self.setup.go(0)
            self._style_page(self.setup)
            self.stack.setCurrentWidget(self.setup)
            self.nav.blockSignals(True)                # 1.2.19: no page is highlighted behind the assistant
            self.nav.setCurrentRow(-1)
            self.nav.blockSignals(False)
        else:
            if self.nav.currentRow() < 0:
                self.nav.setCurrentRow(0)              # posts "page" → the App fills the overview
            self._style_page(self.stack.widget(max(0, self.nav.currentRow())))
            self.stack.setCurrentIndex(max(0, self.nav.currentRow()))

    # ------------------------------------------------------------- search over the settings
    def search_index(self) -> dict:
        """{shown text: (page key, widget)} – every tick box, button, slider, card title and label the pages show
        now (folded parts like "Mehr" only once they are open)."""
        out = {}
        labels = dict(PAGES)
        for key, page in self.forms.items():
            for ckey, (kind, w, extra) in page.controls.items():
                if kind not in SEARCH_KINDS:
                    continue
                target = extra[0] if kind == "slider" else w
                text = " ".join(target.text().split())
                if len(text) < 3 or not _reachable(w, page) or text.startswith("▸"):
                    continue
                entry = f"{text}  ·  {_(labels[key])}"
                out.setdefault(entry, (key, w))
        return out

    def eventFilter(self, obj, e):
        if obj is self.search and e.type() == QEvent.FocusIn:
            self._post("search_open")             # the App fills every page once (texts come from the model)
        return super().eventFilter(obj, e)

    def update_search_index(self):
        """After the App filled the pages: what the search offers (open parts, the language now …)."""
        self._found = self.search_index()
        self._search_model.setStringList(sorted(self._found, key=str.lower))

    def focus_search(self):
        if self._nav_compact:
            self._compact_nav(False, keep=True)                    # room for the field while searching
        self.search.setFocus()
        self.search.selectAll()

    def _search_first(self):
        if self.completer.completionCount():
            self.go_to_found(self.completer.currentCompletion())

    def go_to_found(self, entry: str):
        """Open the page of a search hit, scroll to it and light up its card for a moment."""
        hit = self._found.get(entry)
        if hit is None:
            return
        key, w = hit
        self.show_page(key)
        self.search.clear()
        self.search.clearFocus()
        if self._nav_kept:
            self._nav_kept = False
            self._compact_nav(self.width() < NAV_COMPACT_BELOW)
        self._reveal_widget(w)

    def reveal(self, page: str, key: str):
        """1.2.15: open ``page``, scroll to the control ``key`` of a hand-made page and light up its card (the
        overview's "Match-Daten einrichten" leads to the card under "Mehr")."""
        form = self.forms.get(page)
        ctl = form.controls.get(key) if form is not None else None
        if ctl is None:
            return
        self.show_page(page)
        self._reveal_widget(ctl[1], delay=50)          # after the App's refresh has shown the card

    def _reveal_widget(self, w, delay: int = 0):
        def scroll():
            _open_tabs(w)
            sa = w.parentWidget()
            while sa is not None and not isinstance(sa, QScrollArea):
                sa = sa.parentWidget()
            if sa is not None:
                sa.ensureWidgetVisible(w, 0, 120)
            card = w
            while card is not None and card.property("class") != "card" and card.objectName() != "formtabs":
                card = card.parentWidget()
            target = card or w
            target.setProperty("found", True)
            target.style().unpolish(target)
            target.style().polish(target)

            def done():
                target.setProperty("found", False)
                target.style().unpolish(target)
                target.style().polish(target)
            QTimer.singleShot(FOUND_MS, done)
        QTimer.singleShot(delay, scroll)

    def show_states(self, page, states):
        if page == "setup":
            self.setup.show_states(states)
        elif page in self.forms:
            self.forms[page].show_states(states)

    def visible_keys(self, page) -> set:
        f = self.forms.get(page)
        return f.visible_keys() if isinstance(f, AutoPage) else set()

    def open_dialog(self, key, title, node):
        self.close_dialog(key)
        dlg = DialogWindow(self, self._post, key, title, node)
        dlg.setStyleSheet(self._qss)
        self.dialogs[key] = dlg
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def close_dialog(self, key):
        dlg = self.dialogs.pop(key, None)
        if dlg is not None:
            dlg.closing_from_app = True
            dlg.close()

    def show_dialog_states(self, key, states):
        dlg = self.dialogs.get(key)
        if dlg is not None:
            dlg.page.show_states(states)

    def choose_file(self, mode, title, initial, pattern="JSON (*.json)"):
        """Non-modal file dialog (Qt's own, not the system one: no second message loop); the result goes out as
        post("file", path or None)."""
        from PySide6.QtWidgets import QFileDialog
        dlg = QFileDialog(self, title, initial, "" if mode == "dir" else f"{pattern};;* (*.*)")
        dlg.setOption(QFileDialog.DontUseNativeDialog, True)
        dlg.setAcceptMode(QFileDialog.AcceptSave if mode == "save" else QFileDialog.AcceptOpen)
        if mode == "dir":                             # 1.4: a folder (the recordings)
            dlg.setFileMode(QFileDialog.Directory)
            dlg.setOption(QFileDialog.ShowDirsOnly, True)
        else:
            dlg.setFileMode(QFileDialog.AnyFile if mode == "save" else QFileDialog.ExistingFile)
        if mode == "save":
            dlg.setDefaultSuffix("json")
        dlg.fileSelected.connect(lambda path: self._post("file", path))
        dlg.rejected.connect(lambda: self._post("file", None))
        dlg.open()
        self._file_dialog = dlg                       # keep it alive while it is open

    def show_question(self, q):
        """q = (title, text, ask) or None; ask False = only a note with OK."""
        if q == self._question:
            return
        self._question = q
        self.question.setVisible(q is not None)
        if q is not None:
            self.question_text.setText(f"<b>{html.escape(q[0])}</b><br>" + html.escape(q[1]).replace("\n", "<br>"))
            self.question_cancel.setVisible(bool(q[2]))

    def set_hidden_columns(self, hidden: dict):
        """1.3.6: the columns the user hid, per table ({column ids joined by "|": [hidden ids]}, setting
        hidden_columns)."""
        from .qt_views import Table
        for t in self.findChildren(Table):
            t.set_hidden_map(hidden)

    def set_card_order(self, orders: dict):
        """The user's order of the cards ({page: {run: [ids]}}, setting card_order); {} = as built."""
        for key, page in self.forms.items():
            page.apply_order((orders or {}).get(key, {}))

    def show_maps(self, items, current, preview=None, thumbs=None, recent=None, marks=None, style=None):
        self.maps.show_maps(items, current, thumbs, recent, marks, style)
        self.maps.show_preview(preview)

    def warm_pages(self):
        """1.3.4 (user: the window should feel smoother): lay out every page once while the window is idle – the
        first visit of a page polished and laid out all its widgets (settings ~110 ms), later visits ~10 ms."""
        from PySide6.QtWidgets import QWidget
        for i in range(self.stack.count()):
            page = self.stack.widget(i)
            if page is self.stack.currentWidget():
                continue
            page.resize(self.stack.size())
            for w in [page] + page.findChildren(QWidget):
                w.ensurePolished()
            if page.layout() is not None:
                page.layout().activate()

    def show_page(self, key, search=None):
        """Go to a page (e.g. the maps with a search: a scan found only the realm)."""
        if self._setup_on:
            self.show_setup(False)
        if search is not None:
            self.maps.search.blockSignals(True)
            self.maps.search.setText(search)
            self.maps.search.blockSignals(False)
        keys = [k for k, _l in PAGES]
        if key in keys:
            self.nav.setCurrentRow(keys.index(key))

    def open_tab(self, page: str, frame: str):
        """1.2.12 (analysis point 10): open the tab of a hand-made page that holds ``frame`` (an element picked in
        the overlay preview opens its settings)."""
        form = self.forms.get(page)
        ctl = form.controls.get(frame) if form is not None else None
        if ctl is not None and ctl[0] == "tab" and ctl[1].currentIndex() != ctl[2]:
            ctl[1].setCurrentIndex(ctl[2])

    def apply_theme(self, dark: bool, zoom: float):
        pal = QPalette()
        for role, colour in qt_theme.palette_roles(dark).items():
            pal.setColor(getattr(QPalette.ColorRole, role), QColor(colour))
        pal.setColor(QPalette.Disabled, QPalette.Text, QColor(qt_theme.colours(dark)["fg_dis"]))
        pal.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(qt_theme.colours(dark)["fg_dis"]))
        QApplication.setPalette(pal)
        self._style_lazily(qt_theme.stylesheet(dark, zoom))
        self._dark = bool(dark)
        self._nav_icons()
        try:
            hints = QApplication.styleHints()
            hints.setColorScheme(Qt.ColorScheme.Dark if dark else Qt.ColorScheme.Light)   # title bar (Qt 6.8+)
        except AttributeError:
            pass

    def _style_lazily(self, qss: str):
        """1.3.4: the style sheet per part, not on the window – Qt repolishes every widget of a window whose sheet
        changes, hidden pages too (1236 widgets ≈ 250 ms for a theme/zoom click). Navigation, question bar and the
        page on display get it at once, the other pages one after another while idle or when they are opened."""
        if qss == self._qss:
            return
        self._qss = qss
        for w in (self._side, self.question, self.completer.popup()):
            w.setStyleSheet(qss)
        current = self.stack.currentWidget()
        self._stale = [self.stack.widget(i) for i in range(self.stack.count())]
        self._style_page(current)
        if self._stale and self.isVisible():        # a hidden window gets its pages styled when shown
            self._style_timer.start()

    def _style_page(self, page):
        if page in self._stale:
            self._stale.remove(page)
            page.setStyleSheet(self._qss)

    def _style_next(self):
        if self._stale:
            self._style_page(self._stale[0])
        if self._stale and self.isVisible():
            self._style_timer.start()

    def show_model(self, o, thumb=None, tips=None):
        self.overview.update_page(o, thumb, tips)
        self.show_log_alert(o.log_alert)

    def show_log_alert(self, on: bool):
        """An amber dot on the log's icon while there is an error the user has not looked at."""
        if on != self._log_alert:
            self._log_alert = on
            self._nav_icons()

    def _nav_icons(self):
        """The navigation's icons in the colours of the theme: grey, the page on display in the accent colour."""
        c = qt_theme.colours(self._dark)
        ratio = self.devicePixelRatioF() or 1.0
        for row, (key, _text) in enumerate(PAGES):
            alert = key == "log" and self._log_alert
            icon = QIcon()
            icon.addPixmap(nav_icon(key, c["dim"], ratio, alert), QIcon.Normal)
            icon.addPixmap(nav_icon(key, c["accent"], ratio, alert), QIcon.Selected)
            icon.addPixmap(nav_icon(key, c["fg"], ratio, alert), QIcon.Active)
            self.nav.item(row).setIcon(icon)

    def geometry_b64(self) -> str:
        return base64.b64encode(bytes(self.saveGeometry())).decode("ascii")

    def restore_b64(self, text: str) -> bool:
        try:
            return bool(text) and self.restoreGeometry(QByteArray(base64.b64decode(text)))
        except (ValueError, TypeError):
            return False

    def bring_to_front(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def hwnd(self) -> int:
        try:
            return int(self.winId())
        except (TypeError, ValueError, RuntimeError):
            return 0

    # events: only flags and post() – see the module docstring
    def showEvent(self, e):
        super().showEvent(e)
        if self._stale and not self._style_timer.isActive():
            self._style_timer.start()

    def closeEvent(self, e):
        if self.allow_close:
            e.accept()
        else:
            e.ignore()
            self._post("quit")

    def changeEvent(self, e):
        if e.type() == QEvent.WindowStateChange:
            minimised = bool(self.windowState() & Qt.WindowMinimized)
            if minimised and not self.minimised:
                self._post("minimised")
            self.minimised = minimised
        super().changeEvent(e)

    def moveEvent(self, e):
        self.geometry_changed = True
        super().moveEvent(e)

    def resizeEvent(self, e):
        self.geometry_changed = True
        super().resizeEvent(e)
        self._compact_nav(self.width() < NAV_COMPACT_BELOW)

    def _compact_nav(self, on: bool, keep: bool = False):
        """A narrow window: the navigation shows only its icons (names as hover text) – the page gets the room.
        ``keep``: opened for a search (Ctrl+F) – stays open until a hit is chosen."""
        if keep:
            self._nav_kept = True
        elif self._nav_kept:
            return
        if on == self._nav_compact:
            return
        self._nav_compact = on
        self.search.setVisible(not on)
        self.search_btn.setVisible(on)
        if on:
            self.search_btn.setIcon(QIcon(nav_icon("search", qt_theme.colours(self._dark)["dim"],
                                                   self.devicePixelRatioF() or 1.0)))
        self.nav.setFixedWidth(NAV_COMPACT_W if on else NAV_W)
        self.search.setFixedWidth(NAV_W)
        self.search_btn.setFixedWidth(NAV_COMPACT_W)
        for row, (_key, label) in enumerate(PAGES):
            item = self.nav.item(row)
            item.setText("" if on else _(label))
            item.setToolTip(_(label) if on else "")
