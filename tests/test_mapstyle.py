"""1.66 map style "Dunkel" (user: "Stil von Fallen Refuge oder Freddy Fazbear Pizza", only as an option)."""
import os
import sys
import types

import numpy as np
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
