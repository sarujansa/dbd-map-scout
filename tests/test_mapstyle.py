"""1.66 map style "Dunkel" (user: "Stil von Fallen Refuge oder Freddy Fazbear Pizza", only as an option)."""
import os
import sys
import types

import numpy as np
import pytest
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dbdmapscout import mapimage, mapstyle  # noqa: E402

MAPS = os.path.join(ROOT, "maps")


def _pic(rel):
    with Image.open(os.path.join(MAPS, rel)) as im:
        return im.convert("RGBA")


def _near(a, colour, tol=30):
    return (np.abs(a[..., :3].astype(int) - np.array(colour)).sum(axis=2) < tol) & (a[..., 3] > 200)


def test_lilac_floor_goes_see_through_and_boxes_get_their_colours():
    src = _pic("McMillan/Coal Tower.webp")
    out = mapstyle.restyle(src)
    a, b = np.asarray(src), np.asarray(out)
    assert out.size == src.size
    assert _near(a, mapstyle.FILL).sum() > 100_000 and _near(b, mapstyle.FILL).sum() < 500   # no lilac floor left
    assert (b[..., 3] == 0).sum() > (a[..., 3] == 0).sum() + 100_000                         # it is see-through
    assert _near(b, mapstyle.M_COLOUR).sum() > 10_000          # the M box dark red
    assert _near(b, mapstyle.S_COLOUR).sum() > 5000    # the S box olive
    assert mapimage.title_split(out) == mapimage.title_split(src)   # name on top: rotating still keeps it upright


def test_other_labels_stay_and_rooms_are_not_tinted():
    """WT boxes are no M/S; the thin room frames of Hawkins are no boxes."""
    out = np.asarray(mapstyle.restyle(_pic("Other/Hawkins.webp")))
    assert _near(out, mapstyle.M_COLOUR).sum() == 0 and _near(out, mapstyle.S_COLOUR).sum() == 0


def test_pictures_of_another_style_and_animations_stay(tmp_path):
    for rel in ("Withered Isle/Fallen Refuge.webp", "Sleepless District/Trickster's Delusion.webp"):
        src = _pic(rel)
        assert mapstyle.restyle(src) is src
        path = os.path.join(MAPS, rel)
        assert mapstyle.styled_path(path, str(tmp_path)) == path
    plain = tmp_path / "plain.gif"                       # an animation of another kind: as it is
    frames = [Image.new("RGB", (40, 40), (200, 30 * i, 0)) for i in range(3)]
    frames[0].save(plain, save_all=True, append_images=frames[1:], duration=100)
    assert mapstyle.styled_path(str(plain), str(tmp_path / "cache")) == str(plain)
    assert mapstyle.styled_path(str(tmp_path / "missing.png"), str(tmp_path)) == str(tmp_path / "missing.png")
    assert not any(tmp_path.rglob("*.webp"))


def test_the_dark_picture_is_made_once_and_then_taken_from_the_cache(tmp_path):
    path = os.path.join(MAPS, "McMillan", "Coal Tower.webp")
    assert mapstyle.styled_path(path, str(tmp_path), make=False) == path       # tiles of the maps page: no waiting
    assert not any(tmp_path.rglob("*.webp"))
    first = mapstyle.styled_path(path, str(tmp_path))
    assert mapstyle.styled_path(path, str(tmp_path), make=False) == first
    assert first != path and first.startswith(str(tmp_path)) and f"-v{mapstyle.STYLE_VERSION}." in first
    stamp = os.stat(first).st_mtime_ns
    assert mapstyle.styled_path(path, str(tmp_path)) == first and os.stat(first).st_mtime_ns == stamp
    assert not list(tmp_path.rglob("*.tmp"))
    assert mapstyle.warm([path, os.path.join(MAPS, "Other", "Midwich.gif")], str(tmp_path)) == 2


def test_app_takes_the_dark_picture_only_when_chosen_and_never_for_own_pictures(tmp_path):
    from dbdmapscout import app as appmod
    path = os.path.join(MAPS, "McMillan", "Coal Tower.webp")
    own = {"x": False}
    cat = types.SimpleNamespace(image_path=lambda mid, v=1: (path, v), is_own=lambda mid, v=1: own["x"])
    fake = types.SimpleNamespace(catalog=cat, root_dir=str(tmp_path), settings={"overlay": {"map_style": "classic"}})
    assert appmod.App._map_file(fake, "coal", 1) == (path, 1)
    fake.settings["overlay"]["map_style"] = "dark"
    dark, _v = appmod.App._map_file(fake, "coal", 1)
    assert dark.startswith(os.path.join(str(tmp_path), appmod.STYLE_CACHE))
    own["x"] = True
    assert appmod.App._map_file(fake, "coal", 1) == (path, 1)


@pytest.fixture(scope="module")
def dark_maps(tmp_path_factory):
    """Every supplied map converted once (≈ 0.7 s each) – the tests below share them."""
    cache = str(tmp_path_factory.mktemp("maps_dark"))
    return {path: mapstyle.styled_path(path, cache) for path in _supplied()}


def _supplied():
    return sorted(os.path.join(dp, f) for dp, _d, fs in os.walk(MAPS) for f in fs
                  if f.lower().endswith((".webp", ".png", ".jpg", ".gif")))


def test_every_map_stays_the_same_picture(dark_maps):
    """1.66.1 (user: "jede Map prüfen, ob sie korrekt angezeigt wird und identisch ist mit dem alten Bild"): for every
    supplied map – same size and name on top, nothing outside the map changed, no lilac left, clearly white text as
    white as before, and the dark picture laid over the lilac floor again = the original wherever no black backing
    was added (only the rounding of soft edges differs). Box colours never on what was floor."""
    other = {"Trickster's Delusion.webp", "Fallen Refuge.webp", "Freddy Fazbears Pizza.webp"}
    fill = mapstyle.FILL.astype(float)
    styled = 0
    for path, out in dark_maps.items():
        name = os.path.basename(path)
        if name in other:
            assert out == path, name
            continue
        assert out != path, name + ": not converted"
        if name == "Midwich.gif":
            continue                                       # its own kind: test_midwich_keeps_its_floors
        styled += 1
        oi, di = Image.open(path).convert("RGBA"), Image.open(out).convert("RGBA")
        assert oi.size == di.size, name
        split = mapimage.title_split(oi)
        assert split and mapimage.title_split(di) == split, name
        top = split[2]
        o, d = np.asarray(oi).astype(float), np.asarray(di).astype(float)
        assert np.array_equal(o[:top], d[:top]), name + ": the name on top changed"
        o, d = o[top:], d[top:]
        shape = mapstyle._outline(o[..., 3].astype(np.uint8))
        assert not (np.abs(o - d).max(axis=2) > 0)[~shape].any(), name + ": changed outside the map"
        assert not (_near(d, mapstyle.FILL) & shape).any(), name + ": lilac left"
        opaque = d[..., 3] == 255
        a = d[..., 3:4] / 255
        back = np.abs(d[..., :3] * a + fill * (1 - a) - o[..., :3]).max(axis=2)
        free = shape & ~opaque & (o[..., 3] == 255) & ~(d[..., :3] == mapstyle.WALL).all(axis=2)
        assert back[free].max() <= 20, f"{name}: over lilac it is not the original ({back[free].max():.0f})"
        white = shape & opaque & (o[..., 3] == 255) & (o[..., :3].min(axis=2) > 245)
        darker = (o[..., :3].mean(axis=2) - d[..., :3].mean(axis=2))[white]
        assert (darker > 15).sum() <= 0.002 * white.sum(), name + ": white text got darker"
        floor = _near(o, mapstyle.FILL) & (o[..., 3] == 255)
        box = _near(d, mapstyle.M_COLOUR) | _near(d, mapstyle.S_COLOUR) | _near(d, mapstyle.BOX_GREY)
        assert (box & floor).sum() <= 50, name + ": box colour on what was floor"
    assert styled == 52


def test_the_boxes_get_their_colours_on_every_map(dark_maps):
    """M dark red / S olive where the map has them; WT/H/P boxes grey, never red or olive (Hawkins, Léry's: none)."""
    no_m = {"Midwich.gif", "Wreckers.webp", "Rotten Fields.webp", "Dead Sands.webp", "Hawkins.webp", "Lerys.webp", "THE GAME.webp",
            "Rpd East Wing.webp", "Rpd West Wing.webp"}
    no_s = {"Midwich.gif", "Nostromo Wreckage.webp", "Haddonfield.webp", "Hawkins.webp", "Lerys.webp", "THE GAME.webp",
            "Rpd East Wing.webp", "Rpd West Wing.webp"}
    for path, out in dark_maps.items():
        if out == path:
            continue
        name = os.path.basename(path)
        d = np.asarray(Image.open(out).convert("RGBA"))
        assert (_near(d, mapstyle.M_COLOUR).sum() > 3000) == (name not in no_m), name + ": M box"
        assert (_near(d, mapstyle.S_COLOUR).sum() > 3000) == (name not in no_s), name + ": S box"


def test_midwich_keeps_its_floors(dark_maps):
    """1.66.2 (user: "Midwich kann ebenfalls geändert werden"): both floors converted, the same timing (floors
    7 s, fading frames between), the name on top like on every map (stays upright when turned), the holes of the
    top floor dark grey, nothing of the patterned background left, the digits as many and as white as before."""
    import cv2
    from dbdmapscout.mapimage import floor_frames, title_split
    from dbdmapscout.overlay import load_frames
    src = os.path.join(MAPS, "Other", "Midwich.gif")
    out = dark_maps[src]
    assert out != src and out.endswith(".webp")
    orig, dark = load_frames(src), load_frames(out)
    assert [d for _f, d in dark] == [d for _f, d in orig] and floor_frames(dark) == floor_frames(orig) == [0, 3]
    hole_px = []
    for i in (0, 3):
        pic = np.asarray(dark[i][0]).astype(int)
        split = title_split(dark[i][0])
        assert split, "the name on top"
        body = pic[split[2]:]
        for colour in ((45, 49, 84), (64, 68, 98), (102, 102, 153)):     # background, its "+", the floor
            assert _near(body, colour).sum() < 200, (i, colour)
        hole_px.append(int(_near(body, mapstyle.HOLE, 10).sum()))
        assert _near(body, mapstyle.BOX_GREY).sum() > (3000 if i == 0 else -1)          # CT box (bottom only)

        def digits(a):
            white = ((a[..., :3].min(axis=2) > 230) & (a[..., 3] > 200)).astype(np.uint8)
            n, _l, st, _c = cv2.connectedComponentsWithStats(white)
            return sum(1 for j in range(1, n)                # the white frame round the old map is no digit
                       if st[j, 4] > 0.001 * white.size and st[j, 2] < 0.5 * white.shape[1])
        o = np.asarray(orig[i][0].convert("RGBA")).astype(int)
        frame_top = int(np.flatnonzero((o[..., :3].min(axis=2) > 230).sum(axis=1) > 0.75 * o.shape[1])[0])
        assert digits(body) == digits(o[frame_top + 20:]), i       # every digit there (below the old name)
    assert hole_px[0] < 2000 and hole_px[1] > 100_000     # holes only on the top floor (bottom: a few soft edges)


def test_frame_durations_of_an_animated_webp_are_read_right(tmp_path):
    """An animated WebP knows a frame's duration only once the frame is loaded – read before, it was the one of
    the frame before (Midwich's floors would have been the fading frames)."""
    from dbdmapscout.overlay import load_frames
    path = tmp_path / "anim.webp"
    frames = [Image.new("RGBA", (20, 20), (i * 60, 0, 0, 255)) for i in range(3)]
    frames[0].save(path, "WEBP", lossless=True, save_all=True, append_images=frames[1:], duration=[7000, 100, 200])
    assert [d for _f, d in load_frames(str(path))] == [7000, 100, 200]
