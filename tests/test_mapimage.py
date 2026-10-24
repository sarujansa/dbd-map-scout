"""Own map pictures: background removal (mapimage.py) and user_maps/ in the catalog."""
import os
import shutil
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fogscout import mapimage as mi  # noqa: E402
from fogscout.catalog import Catalog  # noqa: E402

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


def titled(w=120, name_h=20, gap=16, body_h=100):
    """Name on top, transparent gap, map below – like the supplied callout pictures."""
    img = Image.new("RGBA", (w, name_h + gap + body_h), (0, 0, 0, 0))
    a = np.array(img)
    a[:name_h, 30:90] = (255, 255, 255, 255)                     # the name
    a[name_h + gap:, :] = FLOOR + (255,)                         # the map
    a[name_h + gap:name_h + gap + 10, :10] = (255, 0, 0, 255)      # marker top left of the map
    return Image.fromarray(a)


def test_title_is_found_and_stays_upright():
    img = titled()
    assert mi.title_split(img) == (0, 20, 36, 136)
    out = mi.rotate(img, 90)
    a = np.asarray(out)
    assert out.size == (100, 20 + 16 + 120)                      # body 120x100 -> 100x120, name stays 60 wide
    assert (a[:20, 20:80, 3] == 255).all() and (a[:20, :20, 3] == 0).all()   # name upright, centred on top
    assert (a[36:, :, 3] == 255).all()                           # turned map below
    assert tuple(a[36, 99][:3]) == (255, 0, 0)                   # top-left marker now top right (clockwise)
    assert mi.rotate(img, 0) is img and mi.rotate(img, 360) is img


def test_picture_without_name_turns_as_a_whole():
    img = Image.new("RGBA", (40, 20), FLOOR + (255,))
    assert mi.title_split(img) is None
    assert mi.rotate(img, 90).size == (20, 40) and mi.rotate(img, 180).size == (40, 20)


def test_all_frames_use_the_same_split():
    a, b = titled(), titled()
    frames = mi.rotate_frames([(a, 50), (b, 60)], 270)
    assert [f[1] for f in frames] == [50, 60] and frames[0][0].size == frames[1][0].size
    assert mi.rotate_frames([(a, 0)], 0)[0][0] is a


def test_supplied_maps_keep_their_name_on_top():
    import glob
    from fogscout.overlay import load_frames
    split = [p for p in glob.glob(os.path.join(ROOT, "maps", "*", "*.webp"))
             if mi.title_split(load_frames(p)[0][0])]
    webp = glob.glob(os.path.join(ROOT, "maps", "*", "*.webp"))
    assert len(split) == len(webp) >= 55                         # every picture has its name above the map


def test_name_is_added_above_the_map():
    body = Image.new("RGBA", (600, 586), FLOOR + (255,))            # half the size of a supplied map
    out = mi.add_title(body, "Freddy Fazbear's Pizza")
    top, gap, body_top, bottom = mi.title_split(out)
    assert out.width == 600 and bottom == out.height and out.height - body_top == 586
    assert 30 <= gap - top <= 45 and body_top - gap >= mi.MIN_GAP  # ~half of the 75 px of the originals
    a = np.asarray(out)
    assert (a[:gap, ..., 3] > 0).any() and (a[:gap, :, :3].min(axis=2) > 250).any()   # white letters + shadow
    assert mi.title_text("Freddy Fazbear's Pizza") == "FREDDY FAZBEAR’S PIZZA"


def test_long_name_on_narrow_map_is_made_smaller():
    out = mi.add_title(Image.new("RGBA", (200, 586), FLOOR + (255,)), "Father Campbell's Chapel")
    assert out.width == 200 and mi.title_split(out) is not None


def test_convert_adds_a_name_only_when_missing(tmp_path):
    src = str(tmp_path / "karte.png")
    original().save(src)
    got = mi.convert(Image.open(src), title="Neue Map")
    assert mi.title_split(got) is not None and got.height == mi.HEIGHT
    again = mi.convert(got, remove_bg=False, title="Neue Map")    # already has one: no second name
    assert again.size == mi.convert(got, remove_bg=False).size
    plain = mi.convert(Image.open(src))
    assert mi.title_split(plain) is None


def test_oversized_pictures_shrink_on_load():
    from fogscout import overlay
    frames = overlay.load_frames(os.path.join(ROOT, "maps", "Other", "Midwich.gif"))
    assert len(frames) > 1 and all(img.height == overlay.MAX_LOAD_H for img, _d in frames)
    small = overlay.load_frames(os.path.join(ROOT, "maps", "McMillan", "Coal Tower.webp"))
    assert small[0][0].height == 1280                       # normal pictures stay as they are


def test_midwich_has_two_floors_between_the_fades():
    from fogscout import overlay
    frames = overlay.load_frames(os.path.join(ROOT, "maps", "Other", "Midwich.gif"))
    assert mi.floor_frames(frames) == [0, 3]                 # bottom, top – the 100 ms frames only fade over
    assert mi.floor_frames(mi.rotate_frames(frames, 90)) == [0, 3]
    still = overlay.load_frames(os.path.join(ROOT, "maps", "McMillan", "Coal Tower.webp"))
    assert mi.floor_frames(still) == []
    img = Image.new("RGBA", (4, 4))
    assert mi.floor_frames([(img, 100)] * 5) == []           # a plain animation is no map with floors
    assert mi.floor_frames([(img, 7000), (img, 100)]) == []


def test_next_floor_cycles_through_both_and_each_floor():
    floors = [0, 3]
    assert mi.next_floor(floors, None) == 0                   # both -> bottom
    assert mi.next_floor(floors, 0) == 1                      # bottom -> top
    assert mi.next_floor(floors, 1) is None                   # top -> both again
    assert [mi.next_floor([0, 2, 4], p) for p in (None, 0, 1, 2)] == [0, 1, 2, None]


def test_midwich_floors_stack_top_above_bottom():
    from fogscout import overlay
    frames = overlay.load_frames(os.path.join(ROOT, "maps", "Other", "Midwich.gif"))
    side = frames[0][0].width
    view, n = mi.floor_view(frames, None, overlay.MAX_LOAD_H)
    assert n == 2 and len(view) == 1 and view[0][1] == 0       # one still picture, no animation
    pic = view[0][0]
    assert pic.height == overlay.MAX_LOAD_H                   # shrunk on load like any tall picture
    assert 1.9 < pic.height / pic.width < 2.2                  # two squares and a small gap
    full = mi.stack_floors(frames, [0, 3])
    gap = round(side * mi.FLOOR_GAP)
    assert full.size == (side, 2 * side + gap)
    top, bottom = np.asarray(frames[3][0]), np.asarray(frames[0][0])
    assert np.array_equal(np.asarray(full)[:side], top)          # top floor first
    assert np.array_equal(np.asarray(full)[side + gap:], bottom)
    assert not np.asarray(full)[side:side + gap, :, 3].any()     # transparent between them
    one, n = mi.floor_view(frames, 3)
    assert n == 1 and len(one) == 1 and one[0][0] is frames[3][0]
    assert mi.floor_view(frames, 1)[1] == 2                      # a fade frame is no floor: both again


def test_floor_view_leaves_other_maps_alone():
    img = Image.new("RGBA", (4, 4))
    anim = [(img, 100)] * 3
    assert mi.floor_view(anim, None) == (anim, 1)                # plain animations keep running
    still = [(img, 0)]
    assert mi.floor_view(still, 0) == (still, 1)
    rotated = mi.rotate_frames([(Image.new("RGBA", (4, 2)), 7000), (Image.new("RGBA", (4, 2)), 7000)], 90)
    view, n = mi.floor_view(rotated, None)
    assert n == 2 and view[0][0].size == (2, 8)                  # turned floors are stacked as turned


def test_names_with_an_apostrophe_show_it_in_the_picture():
    """1.8.31 (user: "beim Titel wird das Hochkomma nicht angezeigt"): Azarov's Resting Place, Wreckers' Yard and
    Mother's Dwelling came with their name drawn without it (the source pictures); the name strips were drawn
    anew. In every supplied picture whose English name has an apostrophe, the white name has a short mark in its
    upper part – letters reach from the top to the bottom of the line."""
    import json
    import cv2
    import numpy as np
    with open(os.path.join(ROOT, "maps.json"), encoding="utf-8") as f:
        maps = json.load(f)["maps"]
    seen = 0
    for m in maps:
        if not any(c in m["names"]["en"] for c in "'’"):
            continue
        for rel in m["variants"].values():
            if not rel.endswith(".webp"):
                continue
            im = Image.open(os.path.join(ROOT, "maps", rel)).convert("RGBA")
            sp = mi.title_split(im)
            a = np.asarray(im)[:sp[1]]
            white = ((a[..., :3].min(axis=2) > 200) & (a[..., 3] > 200)).astype(np.uint8)
            rows = np.flatnonzero(white.any(axis=1))
            top, height = rows[0], rows[-1] - rows[0] + 1
            n, _lab, stats, _c = cv2.connectedComponentsWithStats(white)
            marks = [s for s in stats[1:] if s[cv2.CC_STAT_TOP] <= top + 0.2 * height
                     and s[cv2.CC_STAT_HEIGHT] < 0.45 * height and s[cv2.CC_STAT_AREA] > 20]
            assert marks, f"{rel}: no apostrophe in the drawn name"
            seen += 1
    assert seen >= 6


def test_a_map_is_decoded_once_until_its_file_changes(tmp_path, monkeypatch):
    """1.8.84 (idea 8 of the UI review, measured: show_map + set_map decoded Midwich twice per call, 0.43 s each):
    load_frames keeps the last FRAMES_KEPT results by path, file time, size and rotation; a changed file or
    another rotation is decoded anew; callers get their own list."""
    from fogscout import overlay
    overlay.clear_frames()
    paths = []
    for i in range(3):
        p = tmp_path / f"m{i}.png"
        Image.new("RGBA", (40 + i, 30), (i, 0, 0, 255)).save(p)
        paths.append(str(p))
    decoded = []
    real = overlay._decode
    monkeypatch.setattr(overlay, "_decode", lambda path, rotation: decoded.append((path, rotation)) or real(path, rotation))
    a = overlay.load_frames(paths[0])
    b = overlay.load_frames(paths[0])
    assert len(decoded) == 1 and a == b and a is not b and a[0][0].size == (40, 30)
    overlay.load_frames(paths[0], 90)
    assert len(decoded) == 2                                            # another rotation: its own entry
    os.utime(paths[0], (1, 1))                                          # the file changed: read anew
    overlay.load_frames(paths[0])
    assert len(decoded) == 3
    overlay.load_frames(paths[1])
    overlay.load_frames(paths[2])                                       # only FRAMES_KEPT stay
    assert len(overlay._frames) == overlay.FRAMES_KEPT
    overlay.load_frames(paths[0])
    assert len(decoded) == 6
    try:
        overlay.load_frames(str(tmp_path / "missing.png"))
    except OSError:
        pass
    else:
        raise AssertionError("a missing file must raise")
    overlay.clear_frames()
    assert not overlay._frames
