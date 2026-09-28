"""Own map pictures: background removal (mapimage.py) and user_maps/ in the catalog."""
import os
import shutil
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dbdmapscout import mapimage as mi  # noqa: E402
from dbdmapscout.catalog import Catalog  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DARK, GREY = (0x28, 0x2A, 0x42), (0x53, 0x57, 0x81)
FLOOR, WALL = (0x88, 0x90, 0xE8), (0, 0, 0)


def original(w=300, h=200):
    """Like the community originals: dark background, grey-violet surround, map in the middle."""
    img = Image.new("RGB", (w, h), DARK)
    a = np.array(img)
    a[40:160, 60:240] = GREY
    a[60:140, 90:210] = FLOOR
    a[60:140, 90:94] = WALL
    a[100, 150] = (0x2A, 0x2C, 0x46)              # close to the dark background -> removed too
    return Image.fromarray(a)


def test_background_becomes_transparent_map_stays():
    out = np.array(mi.remove_background(original()))
    assert out[5, 5, 3] == 0 and out[50, 70, 3] == 0 and out[100, 150, 3] == 0
    assert out[100, 120, 3] == 255 and tuple(out[100, 120, :3]) == FLOOR
    assert out[100, 91, 3] == 255                                  # black walls stay


def test_tolerance_is_ten_percent():
    near = tuple(c + 14 for c in DARK)                             # distance ~0.095
    far = tuple(c + 16 for c in DARK)                              # distance ~0.109
    img = Image.new("RGB", (2, 1))
    img.putpixel((0, 0), near)
    img.putpixel((1, 0), far)
    a = np.array(mi.remove_background(img))
    assert a[0, 0, 3] == 0 and a[0, 1, 3] == 255


def test_convert_trims_and_scales_to_1280():
    img = Image.new("RGB", (400, 300), (255, 255, 255))
    img.paste(original(), (50, 50))                                # white frame around the original
    out = mi.convert(img)
    assert out.height == 1280 and out.width == round(300 * 1280 / 200)   # frame trimmed away first
    small = mi.convert(original(), remove_bg=False, height=100)
    assert small.size == (150, 100) and np.array(small)[0, 0, 3] == 255


def test_safe_names():
    assert mi.safe_name('  Wreck: "Night"? / Harbor. ') == "Wreck Night Harbor"
    assert mi.safe_name("Garden of Joy") == "Garden of Joy"


def test_save_replaces_older_own_picture(tmp_path):
    src = tmp_path / "in.png"
    original().save(src)
    old = tmp_path / "user_maps" / "X" / "Map.gif"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"GIF89a")
    dest = mi.save(str(src), mi.target_path(str(tmp_path), "X/Map", False))
    assert dest.endswith("Map.webp") and os.path.exists(dest) and not old.exists()
    with Image.open(dest) as im:
        assert im.height == 1280 and im.mode == "RGBA"


def _repo(tmp_path):
    shutil.copy(os.path.join(ROOT, "maps.json"), tmp_path / "maps.json")
    (tmp_path / "maps" / "McMillan").mkdir(parents=True)
    for f in ("Coal Tower.webp", "Coal Tower II.webp"):
        shutil.copy(os.path.join(ROOT, "maps", "McMillan", f), tmp_path / "maps" / "McMillan" / f)
    return tmp_path


def test_own_picture_replaces_the_supplied_one(tmp_path):
    root = _repo(tmp_path)
    cat = Catalog(str(root))
    assert not cat.is_own("coal-tower", 2) and cat.own_stem("coal-tower", 2) == "McMillan/Coal Tower II"
    own = root / "user_maps" / "McMillan" / "Coal Tower II.webp"
    own.parent.mkdir(parents=True)
    original().save(own)
    cat = Catalog(str(root))
    path, v = cat.image_path("coal-tower", 2)
    assert v == 2 and os.path.samefile(path, own) and cat.is_own("coal-tower", 2)
    assert not cat.is_own("coal-tower", 1)                          # other layout keeps the supplied picture
    assert not [m for m in cat.maps.values() if m.custom]          # no duplicate map


def test_own_picture_of_a_new_map(tmp_path):
    root = _repo(tmp_path)
    new = root / "user_maps" / "The MacMillan Estate" / "Night Harbor.webp"
    new.parent.mkdir(parents=True)
    original().save(new)
    cat = Catalog(str(root))
    m = cat.maps["custom:The MacMillan Estate/Night Harbor.webp"]
    assert m.custom and m.name == "Night Harbor" and m.realm == "The MacMillan Estate"
    assert cat.is_own(m.id) and cat.own_stem(m.id) == "The MacMillan Estate/Night Harbor"
    h = [h for h in cat.hypotheses if h.map_id == m.id][0]
    assert h.name_key == "NIGHTHARBOR" and "THEMACMILLANESTATE" in h.realm_keys
