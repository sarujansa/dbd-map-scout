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
