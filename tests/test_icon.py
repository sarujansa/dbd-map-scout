"""1.9.1 (user: "ändere ruhig auch das Logo"): the program icon – a compass star over fog – and its file."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fogscout import icon  # noqa: E402


def test_the_logo_is_a_gold_compass_star_over_fog():
    img = icon.draw(256)
    assert img.size == (256, 256) and img.mode == "RGBA"
    assert img.getpixel((2, 2))[3] == 0                                   # rounded corner: transparent
    r, g, b, a = img.getpixel((128, 40))                                  # the north needle: gold
    assert a == 255 and r > 170 and 130 < g < 190 and b < 80
    r, g, b, a = img.getpixel((92, 118))                                  # the west point: light
    assert a == 255 and min(r, g, b) > 200
    fog = img.getpixel((128, 236))                                        # fog at the bottom: pale lavender
    dark = img.getpixel((40, 60))                                         # beside the star: the dark ground
    assert fog[3] == 255 and fog[2] > fog[0] > 90 and sum(fog[:3]) > sum(dark[:3]) + 150
    assert dark[:3] == icon.BG[:3]
    assert icon.draw(16).size == (16, 16)
    for n in (16, 24, 32):                                                # the needle survives the small sizes
        r, g, b, _a = icon.draw(n).getpixel((n // 2, n // 3))
        assert r > 120 and r > b + 60


def test_the_icon_file_is_written_once_per_version(tmp_path, monkeypatch):
    path = icon.ensure_ico(str(tmp_path))
    assert os.path.basename(path) == icon.FILE == f"fogscout-{icon.ICON_VERSION}.ico"
    data = open(path, "rb").read()
    assert data[:4] == b"\x00\x00\x01\x00" and data == icon.ico_bytes()  # an .ico, this version's picture
    assert sorted(os.listdir(str(tmp_path))) == [icon.FILE]                 # no temporary file left
    os.utime(path, (time.time() - 100, time.time() - 100))
    stamped = os.stat(path).st_mtime_ns
    def no_draw():
        raise AssertionError("drawn again")
    monkeypatch.setattr(icon, "ico_bytes", no_draw)
    assert icon.ensure_ico(str(tmp_path)) == path and os.stat(path).st_mtime_ns == stamped   # left alone, not drawn
    monkeypatch.setattr(icon, "ico_bytes", lambda: data)
    open(path, "wb").close()                                                # an empty file: written again
    assert icon.ensure_ico(str(tmp_path)) == path and open(path, "rb").read() == data
    assert icon.FILE not in icon.OLD_FILES and "fogscout.ico" in icon.OLD_FILES
