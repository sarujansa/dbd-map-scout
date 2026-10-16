"""Timer/server block below the map in the native overlay picture."""
import importlib.util
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if importlib.util.find_spec("tkinter") is None:   # headless CI: overlay_win32 imports Tk only for its fallback
    from unittest import mock
    sys.modules["tkinter"] = mock.MagicMock()

from PIL import Image  # noqa: E402

from dbdmapscout import overlay_win32 as ow  # noqa: E402


def map_pic(w=300, h=400, empty_bottom=0):
    pic = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pic.paste((140, 147, 232, 255), (20, 20, w - 20, h - empty_bottom))
    return pic


def visible_rows(img, y0, y1):
    a = img.getchannel("A").crop((0, y0, img.width, y1))
    return a.getbbox() is not None


def test_nothing_to_show_keeps_picture():
    pic = map_pic()
    assert ow.add_info(pic, "", "", 400) is pic


def test_block_below_map_and_centred():
    pic = map_pic()
    out = ow.add_info(pic, "07:32", "Frankfurt", 400)
    assert out.width == pic.width and out.height > pic.height
    assert visible_rows(out, pic.height, out.height)                 # text below the map
    box = out.crop((0, pic.height, out.width, out.height)).getbbox()
    left, right = box[0], out.width - box[2]
    assert abs(left - right) <= 12                                    # centred


def test_uses_empty_margin_below_the_map():
    pic = map_pic(empty_bottom=150)                                   # map content ends 150 px above the edge
    out = ow.add_info(pic, "07:32", "", 400)
    assert out.height == pic.height                                   # fits into the empty margin
    assert visible_rows(out, 400 - 150, 400)


def test_backdrop_mode_extends_dark_rectangle():
    pic = map_pic()
    out = ow.add_info(pic, "07:32", "Irland", 400, backdrop=True)
    assert out.getpixel((2, out.height - 2)) == ow.BACKDROP + (255,)
    assert ow.add_info(pic, "07:32", "Irland", 400).getpixel((2, out.height - 2))[3] == 0


def test_ping_row_below_server_and_coloured():
    pic = map_pic()
    without = ow.add_info(pic, "07:32", "Frankfurt", 400)
    with_ping = ow.add_info(pic, "07:32", "Frankfurt", 400, ping=23)
    assert with_ping.height > without.height                         # extra row below the region
    assert ow.add_info(pic, "07:32", "", 400, ping=23).height == ow.add_info(pic, "07:32", "", 400).height
    assert ow.ping_colour(23) == ow.PING_COLOURS[0]
    assert ow.ping_colour(95) == ow.PING_COLOURS[1]
    assert ow.ping_colour(180) == ow.PING_COLOURS[2]
    green = ow.PING_COLOURS[0][:3]
    rows = with_ping.crop((0, without.height - 10, with_ping.width, with_ping.height)).convert("RGB")
    assert green in {c for _, c in rows.getcolors(1 << 20)}           # value drawn in its quality colour


def test_program_icon(tmp_path):
    from dbdmapscout.icon import SIZES, draw, save_ico
    path = tmp_path / "x.ico"
    save_ico(str(path))
    ico = Image.open(path)
    assert sorted(ico.info["sizes"]) == [(n, n) for n in SIZES]
    small = draw(16)
    assert small.size == (16, 16) and small.getpixel((8, 8))[3] == 255     # visible even at 16 px


def test_waiting_card_lines():
    """No map on screen: only the status lines, on an empty picture, wide enough to read."""
    empty = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    one = ow.add_info(empty, "", "", 500, status=["Warte auf Map"])
    two = ow.add_info(empty, "", "", 500, status=["Warte auf Map", "Suche läuft: 02:13 · Nurse"])
    assert one.width > 100 and two.height > one.height and two.width >= one.width
    assert two.getchannel("A").getextrema()[1] > 200                    # white text is drawn
    assert ow.add_info(empty, "", "", 500, status=()) is empty
    boxed = ow.add_info(empty, "", "", 500, status=["Warte auf Map"], backdrop=True)
    assert boxed.getpixel((1, 1))[3] == 255                             # dark box when the edge is not transparent


def test_waiting_card_shows_the_server_below_the_status():
    """In the lobby DBD already talks to the match server: region and ping go below "Warte auf Map"."""
    empty = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    status = ["Warte auf Map", "Rolle: Nurse · Wartezeit 03:10"]
    plain = ow.add_info(empty, "", "", 500, status=status)
    with_server = ow.add_info(empty, "", "Frankfurt", 500, ping=24, status=status)
    assert with_server.height > plain.height
    top = with_server.crop((0, 0, with_server.width, plain.height - 10))
    assert top.getchannel("A").getextrema()[1] > 200                   # status rows still at the top


def test_warning_note_below_the_timer():
    pic = map_pic()
    plain = ow.add_info(pic, "07:32", "", 400)
    noted = ow.add_info(pic, "07:32", "", 400, note="? unsicher")
    assert noted.height > plain.height
    assert ow.add_info(pic, "", "", 400, note="? unsicher").height > pic.height     # a note alone is shown too


def test_a_map_in_the_bar_is_put_on_screen_once_per_change_at_its_final_size():
    """User (1.2.2): "die Map hat sich ständig vergrössert und verkleinert" – the timer line at full text size is
    wider than the 406-px bar; the App rendered it big, pushed it, then rendered smaller: two sizes on every tick."""
    pushes = []

    class Root:
        def after(self, *a):
            return None

        def after_cancel(self, *a):
            pass

    class Overlay(ow.PictureOverlay):
        def _push(self, *a):
            pushes.append(self._size)

    ov = Overlay(Root())
    ov._shown = True
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ov.set_map(os.path.join(root, "maps", "Forsaken Boneyard", "Eyrie of Crows.webp"), "")
    ov.set_server("Frankfurt", 28)
    ov.set_record("Ø 2.8 Kills · 12 Runden")
    widths = set()
    for s in range(55, 65):                       # "0:59" → "1:00": other digits, other widths
        ov.set_timer(f"{s // 60}:{s % 60:02d}")
        for _tick in range(4):                    # the App places the overlay 4× a second
            height = ov.fit_width(470, 518, 406)
            w, _h = ov.render(height)
            widths.add(w)
    assert widths == {406}                        # never wider than the bar
    assert len(pushes) == 10                      # once per timer text, never an in-between size
    assert {w for w, _h in pushes} == {406}


def test_dark_area_behind_the_map_fits_the_bar_and_keeps_every_frame_the_same_size():
    """1.2.4 (user: "einen Hintergrund dahinter, z. B. bei der Map – als Option für jedes UI-Element")."""
    class Root:
        def after(self, *a):
            return None

        def after_cancel(self, *a):
            pass

    class Overlay(ow.PictureOverlay):
        def _push(self, *a):
            pass

    ov = Overlay(Root())
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ov.set_map(os.path.join(root, "maps", "Forsaken Boneyard", "Eyrie of Crows.webp"), "")
    ov.set_timer("1:23")
    plain = ov.render(ov.fit_width(470, 518, 406))
    ov.set_backdrop(True)
    w, h = ov.render(ov.fit_width(470, 518, 406))
    assert w <= 406 and (w, h) != plain
    pic = ov._prepared[0]
    corner = pic[0][:4]                                  # BGRA of the top left pixel: rounded corner, see-through
    assert corner[3] == 0
    middle_left = (pic[2] // 2 * pic[1] + 2) * 4         # left edge, half way down: the dark area
    assert pic[0][middle_left + 3] == ow.CARD_BACKDROP[3]
    frames = [Image.new("RGBA", (100, 80), (0, 0, 0, 0)) for _i in range(2)]
    frames[0].paste((200, 200, 200, 255), (10, 10, 50, 50))
    frames[1].paste((200, 200, 200, 255), (40, 30, 90, 70))
    out = ow.map_backdrop(frames, 400)
    assert out[0].size == out[1].size == (80 + 2 * (400 // 45), 60 + 2 * (400 // 45))   # union of both, padded


def test_the_dark_area_does_not_make_the_map_smaller():
    """1.2.5 (user: "Warum wird die Map kleiner?"): the area's edge may use the margin around the map."""
    class Root:
        def after(self, *a):
            return None

        def after_cancel(self, *a):
            pass

    class Overlay(ow.PictureOverlay):
        def _push(self, *a):
            pass

    ov = Overlay(Root())
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ov.set_map(os.path.join(root, "maps", "Forsaken Boneyard", "Eyrie of Crows.webp"), "")
    ov.set_timer("1:23")
    from dbdmapscout import layout
    height = layout.fit_height(470, 406, *ov.map_size())           # the map alone fits the bar (as the App does)
    plain_h = ov.fit_width(height, 518, 406)
    ov.set_backdrop(True)
    edge = ov.backdrop_pad(518)
    assert 0 < edge < 17                                           # fits into the 17-px margin of 1440p
    boxed_h = ov.fit_width(height, 518, 406 + 2 * edge)
    assert boxed_h == plain_h and ov.render(boxed_h)[0] <= 406 + 2 * edge
