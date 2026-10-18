"""1.8.24 (user: "die Map mit der Scrollbar grösser – ändert sich nicht in der Vorschau", "Zeit etc. nicht mehr mit
der Map verbunden, eigene Elemente – ich will ab und zu nur die eigentliche Map-Grösse ändern")."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402

from dbdmapscout import layout, preview  # noqa: E402
from dbdmapscout import overlay_win32 as ow  # noqa: E402
from dbdmapscout.config import DEFAULTS  # noqa: E402
from dbdmapscout.mapimage import title_split  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COAL = os.path.join(ROOT, "maps", "McMillan", "Coal Tower.webp")
W, H = 3440, 1440
INFO = {"timer": "3:27", "server": "Frankfurt", "ping": 31.0, "record": "Bilanz: Ø 2,8 Kills · 12 Runden",
        "name": "Coal Tower", "realm": "MacMillan Estate"}


def _o(**kw):
    o = dict(DEFAULTS["overlay"])
    o.update(kw)
    return o


class _Root:
    def after(self, *a):
        return None

    def after_cancel(self, *a):
        pass


class _Overlay(ow.PictureOverlay):
    def _push(self, *a):
        pass


def test_the_map_is_cut_to_what_is_drawn_so_it_can_grow_in_the_bar():
    """Coal Tower's map took 270 of the 406-px picture: the transparent strips beside it filled the bar."""
    pic = Image.open(COAL).convert("RGBA")
    split = title_split(pic)[2]
    cols = ow.body_cols(pic, split)
    assert cols and cols[1] - cols[0] < pic.width * 0.8
    whole = ow.compose(pic, 500, "", True, False, 300, split)
    cut = ow.compose(pic, 500, "", True, False, 300, split, cols)
    assert cut.height == whole.height and cut.width < whole.width
    ov = _Overlay(_Root())
    ov.set_map(COAL, "")
    iw, ih = ov.map_extent()
    assert iw == cols[1] - cols[0] and ih == pic.height
    for o in (_o(info_pos="below"), _o(info_pos="inside")):
        sizes = {}
        for v in (0.30, 0.40):
            fits = {}
            layers, rect = preview.layers(W, H, o, "", [], None, pic, "", INFO, v, fits=fits)
            sizes[v] = rect[3]
            assert rect[2] <= layout.bar_width(W, H)                   # still inside the bar
        assert sizes[0.40] > sizes[0.30]                               # 1.8.23: stopped at ~31 %


def test_the_lines_are_their_own_element_and_keep_their_size_when_the_map_changes():
    pic = Image.open(COAL).convert("RGBA")
    texts, maps = set(), set()
    for v in (0.2, 0.25, 0.3):
        layers, rect = preview.layers(W, H, _o(info_pos="below"), "", [], None, pic, "", INFO, v)
        by = {n: (img, x, y) for n, img, x, y in layers}
        img, x, y = by["text"]
        texts.add(img.size)
        maps.add(rect[3])
        assert y >= rect[1] + rect[3]                                 # right below the map
        assert x >= 0 and x + img.width <= layout.bar_width(W, H)     # in its bar
    assert len(texts) == 1 and len(maps) == 3                         # only the map changed
    layers, rect = preview.layers(W, H, _o(info_pos="above"), "", [], None, pic, "", INFO, 0.3)
    by = {n: (img, x, y) for n, img, x, y in layers}
    assert by["text"][2] + by["text"][0].height <= rect[1]           # above
    layers, rect = preview.layers(W, H, _o(info_pos="custom", info_xy=[0.5, 0.1]), "", [], None, pic, "", INFO, 0.3)
    by = {n: (img, x, y) for n, img, x, y in layers}
    img, x, y = by["text"]
    assert abs(x + img.width / 2 - W / 2) <= 1                        # its centre where it was dropped
    layers, rect = preview.layers(W, H, _o(info_pos="inside"), "", [], None, pic, "", INFO, 0.3)
    assert [n for n, *_r in layers] == ["map"]                        # as before: drawn with the map


def test_the_overlay_draws_the_map_alone_and_the_lines_as_a_card():
    ov = _Overlay(_Root())
    ov.set_map(COAL, "")
    ov.set_timer("3:27")
    ov.set_record("Ø 2.8 Kills · 12 Runden")
    ov.text_height = 300
    with_lines = ov.render(500, push=False)
    ov.set_info_apart(True)
    alone = ov.render(500, push=False)
    assert alone[1] < with_lines[1]                                   # the lines left the map window
    card = ov.info_picture(300)
    assert card is not None and card.height > 0
    assert ov.info_picture(300) is card                               # drawn once per content
    ov.set_timer("")
    ov.set_record("")
    assert ov.info_picture(300) is None and ov.info_picture(300, "0:00") is not None
    assert layout.info_reserve(_o(info_pos="below", anchor="auto"), (100, 50), 8) == (0, 58)
    assert layout.info_reserve(_o(info_pos="above", anchor="auto"), (100, 50), 8) == (58, 0)
    assert layout.info_reserve(_o(info_pos="inside"), (100, 50), 8) == (0, 0)
    assert not layout.info_apart(_o(info_pos="below", show_map=False))    # "nur Infos": the lines are all


def test_the_lines_below_a_map_at_the_bottom_go_above_it_and_stay_on_screen():
    game = (0, 0, W, H)
    x, y = layout.info_xy("below", (20, H - 300, 400, 290), (380, 90), game, 8, 17)
    assert y + 90 <= H and y < H - 300
    x, y = layout.info_xy("above", (20, 5, 400, 290), (380, 90), game, 8, 17)
    assert y >= 5 + 290
    assert layout.union((0, 0, 10, 10), (5, 20, 10, 10)) == (0, 0, 15, 30)
    assert layout.union(None, (1, 2, 3, 4)) == (1, 2, 3, 4)


def test_the_music_cover_can_be_round_or_square_in_every_style():
    """1.8.24 (user: "im Spotify-Overlay die Option zwischen runden und eckigen Bildern")."""
    from dbdmapscout import media, skin
    from dbdmapscout.sysinfo import DIM, WHITE
    cover = Image.new("RGB", (300, 300), (200, 40, 40))
    rows = [[("Blinding Lights", WHITE)], [("The Weeknd", DIM)]]
    assert media.look(_o(media_cover_shape="round"))[-1] == "cover_round"
    assert not any(k.startswith("cover_") for k in media.look(_o()))
    assert ow.cover_radius(("cover_round",), 100, 7) == 50 and ow.cover_radius(("cover_square",), 100, 7) == 0
    assert ow.cover_radius((), 100, 7) == 7

    def corner_alpha(pic):
        """Alpha in the top-left corner of the cover: find the first red pixel row, look at its far left."""
        px = pic.convert("RGBA").load()
        for y in range(pic.height):
            xs = [x for x in range(pic.width) if px[x, y][0] > 150 and px[x, y][1] < 90 and px[x, y][3] > 200]
            if xs:
                return len(xs)                                   # red pixels in the cover's first row
        return 0
    for style in ("classic",) + tuple(s for s in skin.STYLES if s != "classic"):
        for layout_ in ("big", "compact"):
            widths = {}
            for shape in ("round", "square"):
                look = ("cover_" + shape,)
                pic = ow.music_picture(rows, 800, cover, layout_, None, look, style, None)
                widths[shape] = corner_alpha(pic)
            assert widths["square"] > widths["round"], (style, layout_, widths)   # a circle starts narrow


def test_a_page_never_changes_width_when_its_scroll_bar_comes_and_goes():
    """1.8.24 (user: "das GUI springt ab und zu kurz nach links und dann wieder zurück")."""
    from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
    from dbdmapscout import qt_window
    from dbdmapscout.qt_common import _scroll_page
    qt_window.application()
    page, lay = _scroll_page("Test")
    page.resize(600, 300)
    page.show()
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QScrollArea
    sa = page.findChild(QScrollArea)

    def settle(cond, ms=1000):                       # the layout runs on timers: wait for it, not a fixed time
        for _i in range(ms // 20):
            QTest.qWait(20)
            if cond():
                return True
        return cond()
    assert settle(lambda: sa.viewport().width() > 0)
    width = sa.viewport().width()
    bar = sa.verticalScrollBar()
    assert bar.property("idle") is True
    extra = QWidget()
    QVBoxLayout(extra).addWidget(QLabel("x\n" * 60))
    lay.addWidget(extra)
    assert settle(lambda: bar.maximum() > 0 and bar.property("idle") is False)
    assert sa.viewport().width() == width                              # the content did not move
    extra.hide()
    assert settle(lambda: bar.property("idle") is True)
    assert sa.viewport().width() == width
    page.close()


def test_the_queue_beside_the_card_fills_its_height():
    """1.8.24 (user: "wenn rechts angezeigt wird, was abgespielt wird, soll die Liste verlängert werden, bis sie
    da voll ist")."""
    from dbdmapscout import skin
    from dbdmapscout.app_spotify import SAMPLE_UPNEXT
    from dbdmapscout.sysinfo import DIM, WHITE
    cover = Image.new("RGB", (300, 300), (200, 40, 40))
    rows = [[("Blinding Lights", WHITE)], [("The Weeknd", DIM)]]
    up = ("ALS NÄCHSTES", SAMPLE_UPNEXT)
    for style in ("classic",) + tuple(s for s in skin.STYLES if s != "classic"):
        tall = ow.music_picture(rows, 1440, cover, "big", (30, 200), (), style, None, up, "right")
        alone = ow.music_picture(rows, 1440, cover, "big", (30, 200), (), style, None)
        assert tall.height <= alone.height + 2, style                   # the list never makes the card taller
        short = ow.music_picture(rows, 1440, cover, "compact", (30, 200), (), style, None, up, "right")
        assert short.width > 0
    n_big = ow.upnext_rows("X", SAMPLE_UPNEXT, 1440, 600)
    n_small = ow.upnext_rows("X", SAMPLE_UPNEXT, 1440, 150)
    assert n_big > n_small >= 1 and n_big <= len(SAMPLE_UPNEXT)
    assert skin.upnext_fit("X", 10, 1000, 1.0) == 10 and skin.upnext_fit("X", 10, 120, 1.0) == 4     # 24 + 16 + 4 · 20 − 4 = 116 px
    assert skin.upnext_fit("X", 10, 10, 1.0) == 1


def test_no_element_lies_on_another_on_the_map_or_on_discords_overlay():
    """1.8.25 (user: "alle UI-Elemente beachten, damit es immer sauber aussieht" + screenshots with Discord's
    overlay open): the areas of Discord's widgets keep the bars' lines away (voice bottom left, notifications top
    right), and every element that would lie on another, on the map or on such an area moves up or down."""
    from dbdmapscout import media, sysinfo
    game = (0, 0, W, H)
    o = _o(keep_out_on=True)
    bands = layout.bar_bands(o, game, 17)
    zones = layout.keep_out_boxes(o, game)
    voice, top = zones[0], zones[1]
    side = layout.resolve([("d", (3000, 900, 400, 1000))], [(2800, 800, 220, 400)], game, None, 8)   # no room above/below
    assert side == {"d": (3028 - 3000, 0)}                                                         # → sideways in its bar
    assert bands["left"][1] <= int(voice[1]) - 17 and bands["right"][0] >= int(top[1] + top[3]) + 17
    assert layout.bar_bands(o, game, 17, zones=False) is None                 # the limiter itself stays off
    assert layout.keep_out_boxes(_o(keep_out_on=False), game) == []
    # the resolver: a box on the map moves below it, one with no free place stays
    m = (17, 100, 400, 800)
    shift = layout.resolve([("a", (20, 300, 380, 100)), ("b", (20, 300, 380, 100))], [m], game, None, 8)
    assert shift["a"] == (0, 908 - 300) and shift["b"] == (0, 1016 - 300)
    assert layout.resolve([("c", (20, 0, 380, 1440))], [m], game, None, 8) == {}
    # the preview: every combination of places – nothing overlaps anything
    rows = [[("CPU ", sysinfo.DIM), ("64°C", sysinfo.WHITE)], [("GPU ", sysinfo.DIM), ("71°C", sysinfo.WHITE)]]
    today = [[("HEUTE ", sysinfo.DIM), ("3 RUNDEN · 1:12", sysinfo.WHITE)]]
    music = preview.music_rows(media.NowPlaying(), 0.0)
    pic = Image.open(COAL).convert("RGBA")
    bad = []
    for tpos in ("below", "bottom_left", "bottom_right", "under_music"):
        for mpos in ("below", "bottom_left", "bottom_right", "under_today"):
            for spot in ("below", "custom"):
                o2 = _o(keep_out_on=True, today_pos=tpos, media_pos=mpos, info_pos=spot, info_xy=[0.06, 0.4])
                layers, _r = preview.layers(W, H, o2, "right", rows, None, pic, "", INFO, 0.36, music, today)
                boxes = [(n, (x, y, img.width, img.height)) for n, img, x, y in layers]
                for i, (n, b) in enumerate(boxes):
                    for n2, b2 in boxes[:i]:
                        if layout.boxes_overlap(b, b2):
                            bad.append((tpos, mpos, spot, n, n2))
                    if n != "map" and any(layout.boxes_overlap(b, z) for z in zones):
                        free = [z for z in zones if layout.boxes_overlap(b, z)]
                        bad.append((tpos, mpos, spot, n, "zone", free))
    assert not bad, bad[:6]


def test_characters_a_font_lacks_come_from_a_fallback_font():
    """1.8.25 (user: "andere Sprachen werden bei ‚Als nächstes' nicht korrekt angezeigt (russisch)"): the Inter
    subset of the modern styles has no Cyrillic – those characters are drawn with a font that has them."""
    from dbdmapscout import skin
    inter = skin.inter("Medium", 40)
    assert ow._has_glyph(inter, "a") and not ow._has_glyph(inter, "Ж")
    fb = ow.font_for(inter, "Ж")
    assert fb is not inter and ow._has_glyph(fb, "Ж")
    assert ow.font_for(inter, "a") is inter
    pic = Image.new("RGBA", (400, 80), (0, 0, 0, 0))
    ow._draw_run(pic, 0, 0, "Кино", inter, (255, 255, 255, 255))
    notdef = Image.new("RGBA", (400, 80), (0, 0, 0, 0))
    ow._draw_run(notdef, 0, 0, "￿" * 4, inter, (255, 255, 255, 255))
    assert pic.tobytes() != notdef.tobytes() and pic.getbbox() is not None
    assert ow._run_len(inter, "Кино") == sum(fb.getlength(c) for c in "Кино")


class _SizedWin:
    """A HudWindow whose natural size the test sets; ``min_w`` widens it like the real one."""

    def __init__(self, w, h):
        self.size, self.shown, self.opacity, self.editing, self.fade, self.calls = (w, h), True, 0.85, False, 1.0, []

    def set_editing(self, on):
        self.editing = bool(on)

    def render(self, *a, **kw):
        self.calls.append(kw)
        self.size = (max(self.size[0], int(kw.get("min_w") or 0)), self.size[1])
        return self.size

    def render_blend(self, old, new, t):
        self.calls.append(new)
        return self.size

    def show_at(self, x, y):
        pass

    def set_fade(self, f):
        self.fade = f

    def hide(self):
        self.shown = False

    def destroy(self):
        self.shown = False


def test_a_card_keeps_its_widest_width_while_its_values_change(tmp_path):
    """1.8.28: "today" and the music card are drawn again at the widest width they had for the same layout
    (layout.steady_width) – a shorter title or value never moves the card; another layout starts anew."""
    import json
    import time
    from dbdmapscout import media
    from dbdmapscout.app import App
    (tmp_path / "settings.json").write_text(json.dumps({"welcome_seen": True}), encoding="utf-8")
    (tmp_path / "sim").mkdir()
    app = App(str(tmp_path), simulate=str(tmp_path / "sim"))
    try:
        app._media_ctx = (0, 0, 3440, 1440, True)
        app._forced = True
        app.settings["overlay"]["media_fade"] = False
        win = app.media_win = _SizedWin(300, 400)
        app.media.now = media.NowPlaying("Blinding Lights", "The Weeknd", True, time.time(), position=10.0,
                                         duration=176.0, at=time.time())
        assert app._media_card() == (300, 400) and "min_w" not in win.calls[-1]
        win.size = (260, 400)                                # a shorter title
        app.media.now = media.NowPlaying("Hi", "X", True, time.time(), position=1.0, duration=90.0, at=time.time())
        assert app._media_card() == (300, 400) and win.calls[-1]["min_w"] == 300
        app.settings["overlay"]["media_style"] = "compact"   # another layout: its own steady width
        win.size = (250, 120)
        assert app._media_card() == (250, 120) and not win.calls[-1].get("min_w")
        today = app.today_win = _SizedWin(280, 200)
        assert app._today_card() == (280, 200)
        today.size = (250, 200)
        assert app._today_card() == (280, 200) and today.calls[-1]["min_w"] == 280
    finally:
        app.quit()


class _DrawWin:
    """A HudWindow that really draws (like the Windows one) and only remembers where it was shown – the Linux
    tests had no such windows for "today", the music and the lines, so a placing error never surfaced (1.8.28)."""

    def __init__(self, label=""):
        self.shown, self.opacity, self.editing, self.fade = False, 0.85, False, 1.0
        self.size, self.edit_label, self.at, self._bodies = (0, 0), label, None, {}

    def set_editing(self, on):
        self.editing = bool(on)

    def render(self, rows, height, cover=None, style=None, progress=None, look=(), skin="classic", accent=None,
               title=None, upnext=None, upnext_pos="below", min_w=0):
        if not rows:
            self.size = (0, 0)
            return self.size
        if style is not None:
            pic = ow.music_picture(rows, height, cover, style, progress, look, skin, accent, upnext, upnext_pos,
                                   None, self._bodies, min_w)
        elif skin != "classic":
            from dbdmapscout import skin as skins
            pic = skins.card(rows, height, skin, accent, title, min_w=min_w)
        else:
            pic = ow.pad_to(ow.render_hud(rows, height), min_w)
        if self.editing:
            pic = ow.add_border(pic, self.edit_label)
        self.size = pic.size
        return self.size

    def render_blend(self, old, new, t):
        a = ow.music_picture(bodies=self._bodies, **old)
        b = ow.music_picture(bodies=self._bodies, **new)
        self.size = ow.blend_cards(a, b, t, True).size
        return self.size

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


USER_OVERLAY = {"anchor": "custom", "style": "chips", "pos_x": 0.011, "pos_y": 0.613, "height": 0.37,
                "show_caption": False, "info_pos": "custom", "info_xy": [0.064, 0.3093], "media_pos": "custom",
                "media_xy": [0.9376, 0.8674], "media_cover_shape": "square", "media_style": "big",
                "media_scale": 0.97, "media_next_pos": "below", "map_backdrop": True, "bar_limits_on": True,
                "bar_limits": [0.1521, 0.2381, 0.3014, 0.0], "bar_limits_same": False, "media_backdrop": True,
                "hud_scale": 1.05, "today_pos": "custom", "today_xy": [0.936, 0.5938]}


def test_every_element_is_placed_with_real_windows(tmp_path):
    """1.8.28 (user's diagnosis of 1.8.27: only the system values showed, "Fehler seit Start: ['overlay']"):
    _cards_place handed _el_show the cards' boxes as four values – a TypeError on every tick that had a card to
    place, so map, lines, "today" and music never appeared. The App with the user's settings and windows that
    draw for real: one _place_overlay without an exception, every element on screen, in its bar, none on another."""
    import json
    import time
    from dbdmapscout import media, sysinfo
    from dbdmapscout.app import App
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name in ("maps", "models", "maps.json"):
        os.symlink(os.path.join(root, name), tmp_path / name)
    (tmp_path / "sim").mkdir()
    (tmp_path / "settings.json").write_text(json.dumps({"welcome_seen": True, "sysinfo": "custom",
                                                        "sysinfo_pos": [0.984, 0.383],
                                                        "overlay": USER_OVERLAY}), encoding="utf-8")
    app = App(str(tmp_path), simulate=str(tmp_path / "sim"))
    try:
        app.info_win, app.hud = _DrawWin("INFOS"), _DrawWin("SYSTEM")
        app.today_win, app.media_win = _DrawWin("HEUTE"), _DrawWin("MUSIK")
        app._game_rect = lambda: (0, 0, 3440, 1440)
        app._force_until = time.time() + 30
        app._forced = True
        app.sysmon.snapshot = sysinfo.Snapshot(t=time.time(), cpu_load=63, cpu_temp=75, gpu_temp=77, gpu_load=89,
                                               vram_used=5.8, vram_total=12, ram_used=21.2, ram_total=32,
                                               gpu_hot=97.9, gpu_mem=78, hwinfo=True)
        app.media.now = media.NowPlaying("Blinding Lights", "The Weeknd", True, time.time(), position=70.0,
                                         duration=176.0, at=time.time())
        app.show_map("shattered-square", 1, "auto")
        app.overlay.set_server("?", None)
        for _ in range(3):
            app._place_overlay()                                     # raised the TypeError before
        boxes = {"map": app._last_place}
        for name, win in (("text", app.info_win), ("hud", app.hud), ("today", app.today_win), ("music", app.media_win)):
            assert win.shown and win.at is not None and win.size[0] > 0, name
            boxes[name] = (*win.at, *win.size)
        assert app.overlay.shown
        bar = layout.bar_width(3440, 1440)
        for name, (x, y, w, h) in boxes.items():
            assert x >= 0 and y >= 0 and x + w <= 3440 and y + h <= 1440, (name, boxes[name])
            assert x + w <= bar or x >= 3440 - bar, (name, boxes[name])             # in a black bar
        names = list(boxes)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                assert not layout.boxes_overlap(boxes[a], boxes[b]), (a, b, boxes[a], boxes[b])
    finally:
        app.quit()
