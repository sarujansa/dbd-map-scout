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
    gif = os.path.join(MAPS, "Other", "Midwich.gif")
    assert mapstyle.styled_path(gif, str(tmp_path)) == gif
    assert mapstyle.styled_path(str(tmp_path / "missing.png"), str(tmp_path)) == str(tmp_path / "missing.png")
    assert not any(tmp_path.rglob("*.webp"))


def test_the_dark_picture_is_made_once_and_then_taken_from_the_cache(tmp_path):
    path = os.path.join(MAPS, "McMillan", "Coal Tower.webp")
    first = mapstyle.styled_path(path, str(tmp_path))
    assert first != path and first.startswith(str(tmp_path)) and f"-v{mapstyle.STYLE_VERSION}." in first
    stamp = os.stat(first).st_mtime_ns
    assert mapstyle.styled_path(path, str(tmp_path)) == first and os.stat(first).st_mtime_ns == stamp
    assert not list(tmp_path.rglob("*.tmp"))
    assert mapstyle.warm([path, os.path.join(MAPS, "Other", "Midwich.gif")], str(tmp_path)) == 1


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
    other = {"Midwich.gif", "Trickster's Delusion.webp", "Fallen Refuge.webp", "Freddy Fazbears Pizza.webp"}
    fill = mapstyle.FILL.astype(float)
    styled = 0
    for path, out in dark_maps.items():
        name = os.path.basename(path)
        if name in other:
            assert out == path, name
            continue
        assert out != path, name + ": not converted"
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
    no_m = {"Wreckers.webp", "Rotten Fields.webp", "Dead Sands.webp", "Hawkins.webp", "Lerys.webp", "THE GAME.webp",
            "Rpd East Wing.webp", "Rpd West Wing.webp"}
    no_s = {"Nostromo Wreckage.webp", "Haddonfield.webp", "Hawkins.webp", "Lerys.webp", "THE GAME.webp",
            "Rpd East Wing.webp", "Rpd West Wing.webp"}
    for path, out in dark_maps.items():
        if out == path:
            continue
        name = os.path.basename(path)
        d = np.asarray(Image.open(out).convert("RGBA"))
        assert (_near(d, mapstyle.M_COLOUR).sum() > 3000) == (name not in no_m), name + ": M box"
        assert (_near(d, mapstyle.S_COLOUR).sum() > 3000) == (name not in no_s), name + ": S box"
