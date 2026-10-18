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
    QTest.qWait(30)
    width = sa.viewport().width()
    bar = sa.verticalScrollBar()
    assert bar.property("idle") is True
    extra = QWidget()
    QVBoxLayout(extra).addWidget(QLabel("x\n" * 60))
    lay.addWidget(extra)
    QTest.qWait(30)
    assert bar.maximum() > 0 and bar.property("idle") is False
    assert sa.viewport().width() == width                              # the content did not move
    extra.hide()
    QTest.qWait(30)
    assert sa.viewport().width() == width and bar.property("idle") is True
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
