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


def test_the_dark_picture_is_made_once_and_then_taken_from_the_cache(tmp_path, map_cache, dark_maps):
    path = os.path.join(MAPS, "McMillan", "Coal Tower.webp")
    assert mapstyle.styled_path(path, str(tmp_path), make=False) == path       # tiles of the maps page: no waiting
    assert not any(tmp_path.rglob("*.webp"))
    first = mapstyle.styled_path(path, str(tmp_path))
    assert mapstyle.styled_path(path, str(tmp_path), make=False) == first
    assert first != path and first.startswith(str(tmp_path)) and f"-v{mapstyle.STYLE_VERSION}." in first
    stamp = os.stat(first).st_mtime_ns
    assert mapstyle.styled_path(path, str(tmp_path)) == first and os.stat(first).st_mtime_ns == stamp
    assert not list(tmp_path.rglob("*.tmp"))
    # (warm counts the pictures ready in the dark style – made or found; Midwich from the shared cache, 1.8.31)
    assert mapstyle.warm([path, os.path.join(MAPS, "Other", "Midwich.gif")], map_cache) == 2


def _fake_app(appmod, cat, tmp_path, style):
    import queue
    fake = types.SimpleNamespace(catalog=cat, root_dir=str(tmp_path), settings={"overlay": {"map_style": style}},
                                 events=queue.Queue())
    fake._style_request = lambda path, st: appmod.App._style_request(fake, path, st)
    fake._style_ready = types.SimpleNamespace(__name__="_style_ready")            # only posted, never called here
    return fake


def _styled_in_the_background(appmod, fake):
    """1.8.21: the window thread never makes the picture – first the original, then the event, then the styled."""
    path = fake.catalog.image_path("coal", 1)[0]
    assert appmod.App._map_file(fake, "coal", 1) == (path, 1)                 # at once, no waiting
    kind, fn, (made,) = fake.events.get(timeout=60)
    assert kind == "call" and fn is fake._style_ready and made == path
    styled, _v = appmod.App._map_file(fake, "coal", 1)
    assert styled != path
    return styled


def test_app_takes_the_dark_picture_only_when_chosen_and_never_for_own_pictures(tmp_path):
    from dbdmapscout import app as appmod
    path = os.path.join(MAPS, "McMillan", "Coal Tower.webp")
    own = {"x": False}
    cat = types.SimpleNamespace(image_path=lambda mid, v=1: (path, v), is_own=lambda mid, v=1: own["x"])
    fake = _fake_app(appmod, cat, tmp_path, "classic")
    assert appmod.App._map_file(fake, "coal", 1) == (path, 1)
    fake.settings["overlay"]["map_style"] = "dark"
    dark = _styled_in_the_background(appmod, fake)
    assert dark.startswith(os.path.join(str(tmp_path), appmod.STYLE_CACHE))
    own["x"] = True
    assert appmod.App._map_file(fake, "coal", 1) == (path, 1)


WORKERS = max(1, min(4, os.cpu_count() or 1))   # 1.8.31: numpy/OpenCV let threads run side by side (74 → 23 s)


@pytest.fixture(scope="module")
def map_cache(tmp_path_factory):
    return str(tmp_path_factory.mktemp("maps_dark"))


@pytest.fixture(scope="module")
def dark_maps(map_cache):
    """Every supplied map converted once (≈ 0.7 s each, in WORKERS threads) – the tests below share them."""
    from concurrent.futures import ThreadPoolExecutor
    paths = _supplied()
    with ThreadPoolExecutor(WORKERS) as ex:
        return dict(zip(paths, ex.map(lambda p: mapstyle.styled_path(p, map_cache), paths)))


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

    def check(item):                                   # one map; run in WORKERS threads (1.8.31: 38 → ~12 s)
        path, out = item
        name = os.path.basename(path)
        if name in other:
            assert out == path, name
            return 0
        assert out != path, name + ": not converted"
        if name == "Midwich.gif":
            return 0                                       # its own kind: test_midwich_keeps_its_floors
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
        return 1

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(WORKERS) as ex:
        styled = sum(ex.map(check, dark_maps.items()))
    assert styled == 52


def test_the_boxes_get_their_colours_on_every_map(dark_maps):
    """M dark red / S olive where the map has them; WT/H/P boxes grey, never red or olive (Hawkins, Léry's: none)."""
    no_m = {"Midwich.gif", "Wreckers.webp", "Rotten Fields.webp", "Dead Sands.webp", "Hawkins.webp", "Lerys.webp", "THE GAME.webp",
            "Rpd East Wing.webp", "Rpd West Wing.webp"}
    no_s = {"Midwich.gif", "Nostromo Wreckage.webp", "Haddonfield.webp", "Hawkins.webp", "Lerys.webp", "THE GAME.webp",
            "Rpd East Wing.webp", "Rpd West Wing.webp"}
    def check(item):
        path, out = item
        if out == path:
            return
        name = os.path.basename(path)
        d = np.asarray(Image.open(out).convert("RGBA"))
        assert (_near(d, mapstyle.M_COLOUR).sum() > 3000) == (name not in no_m), name + ": M box"
        assert (_near(d, mapstyle.S_COLOUR).sum() > 3000) == (name not in no_s), name + ": S box"

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(WORKERS) as ex:
        list(ex.map(check, dark_maps.items()))


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


@pytest.mark.parametrize("style", sorted(mapstyle.FLOORS))
def test_the_floor_styles_put_a_floor_under_the_dark_drawing(tmp_path, style):
    """1.8.16 (user picked them from sample pictures, "zusätzlich", plain names): the dark conversion with a
    floor under it – the drawing (digits, boxes) and the name stay as in "dark", the see-through floor of "dark"
    gets the style's colour, outside the map stays see-through; each style has its own cache file; Midwich keeps
    its floors."""
    from dbdmapscout.mapimage import title_split
    path = os.path.join(MAPS, "McMillan", "Coal Tower.webp")
    dark_path = mapstyle.styled_path(path, str(tmp_path))
    out_path = mapstyle.styled_path(path, str(tmp_path), style=style)
    assert out_path not in (path, dark_path) and f"-{style}-v{mapstyle.STYLE_VERSION}." in out_path
    assert mapstyle.styled_path(path, str(tmp_path), make=False, style=style) == out_path
    assert mapstyle.styled_path(path, str(tmp_path), style="nonsense") == path
    dark = np.asarray(Image.open(dark_path).convert("RGBA")).astype(int)
    out = np.asarray(Image.open(out_path).convert("RGBA")).astype(int)
    assert out.shape == dark.shape
    top = title_split(Image.open(dark_path))[2]
    assert np.array_equal(out[:top], dark[:top])                              # the name untouched
    fill, edge, _ew, alpha = mapstyle.FLOORS[style]
    shape = mapstyle._outline(dark[top:, :, 3].astype(np.uint8))
    body_d, body_o = dark[top:], out[top:]
    vis = ~shape & (body_d[..., 3] > 0)                                       # outside: as in "dark" (the colour of
    assert np.array_equal(body_o[~shape][:, 3], body_d[~shape][:, 3])         # invisible pixels does not count)
    assert np.array_equal(body_o[vis], body_d[vis])
    floor = shape & (body_d[..., 3] == 0)                                    # where "dark" was see-through …
    floor &= ~(cv2_erode_edge(shape, 20))                                     # (away from the edge, 14 px)
    assert floor.sum() > 50000
    got = body_o[floor]
    assert (np.abs(got[:, :3] - np.array(fill)).max(axis=1) <= 2).mean() > 0.99   # … the floor's colour now
    assert (np.abs(got[:, 3] - alpha) <= 2).mean() > 0.99
    # the opaque drawing stays – away from the outline: there "dark" has its black ring, a floor style not (1.8.35)
    solid = shape & (body_d[..., 3] == 255) & ~cv2_erode_edge(shape, 40)
    assert (np.abs(body_o[solid] - body_d[solid]).max(axis=1) <= 2).mean() > 0.99
    if edge is not None:                                                      # a light edge on the outline
        rim = shape & ~mapstyle.cv2.erode(shape.astype(np.uint8), mapstyle._disk(2)).astype(bool)
        assert (np.abs(body_o[rim][:, :3] - np.array(edge)).max(axis=1) <= 2).mean() > 0.9
        wide = shape & ~mapstyle.cv2.erode(shape.astype(np.uint8), mapstyle._disk(8)).astype(bool)   # 1.8.29: ≥ 8 px
        assert (np.abs(body_o[wide][:, :3] - np.array(edge)).max(axis=1) <= 2).mean() > 0.9
    if style == "grey":                                                       # Midwich: floors kept, in this style
        from dbdmapscout.overlay import load_frames
        gif = os.path.join(MAPS, "Other", "Midwich.gif")
        styled = mapstyle.styled_path(gif, str(tmp_path), style=style)
        assert styled != gif and [d for _f, d in load_frames(styled)] == [d for _f, d in load_frames(gif)]


def test_no_map_keeps_the_black_ring_in_a_floor_style(map_cache):
    """1.8.35 (user: "bei den Maps gibt es immer noch einen schwarzen Rand", "bitte bei jedem Map durchgehen"): the
    dark style lays the drawing over a black ring along the outline (24 px at 1280 px) – a floor style has its floor
    there. Every supplied map, the ones drawn dark already (Fallen Refuge, Freddy) too: in the band 16–24 px inside
    the outline hardly any black ("dark": 75–100 %, left now: the black edges of digits and walls, RPD ≤ 16 %);
    the light edge leaves light text on the outline readable (RPD West "BACK DOOR")."""
    import cv2
    from concurrent.futures import ThreadPoolExecutor
    from dbdmapscout.mapimage import title_split

    def check(path):
        name = os.path.basename(path)
        out = mapstyle.styled_path(path, map_cache, style="grey")
        if name in ("Trickster's Delusion.webp", "Midwich.gif"):     # its own kind / its own test
            return None
        assert out != path, name
        src = Image.open(path).convert("RGBA")
        top = title_split(src)[2]
        o = np.asarray(Image.open(out).convert("RGBA"))[top:]
        shape = mapstyle._outline(np.asarray(src)[top:, :, 3])
        k = o.shape[0] / 1280
        pad = cv2.copyMakeBorder(shape.astype(np.uint8), 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0)
        dist = cv2.distanceTransform(pad, cv2.DIST_L2, 3)[1:-1, 1:-1]
        band = shape & (dist >= 16 * k) & (dist <= 24 * k)
        black = (o[..., :3].max(axis=2) < 25) & (o[..., 3] > 200) & band
        share = black.sum() / band.sum()
        assert share < 0.25, f"{name}: {share:.0%} of the outline band black"
        return share

    with ThreadPoolExecutor(WORKERS) as ex:
        shares = [s for s in ex.map(check, _supplied()) if s is not None]
    assert len(shares) == 54 and sorted(shares)[len(shares) // 2] < 0.05
    src = _pic("Raccoon City/Rpd West Wing.webp")                  # the text on the outline stays white
    top = title_split(src)[2]
    rim = cv2_erode_edge(mapstyle._outline(np.asarray(src)[top:, :, 3]), 14)
    white = [((a[top:, :, :3].min(axis=2) > 230) & (a[top:, :, 3] > 200) & rim).sum()
             for a in (np.asarray(mapstyle.restyle(src, style=st)) for st in ("dark", "grey_edge"))]
    assert white[0] > 300 and white[1] >= 0.95 * white[0], white


def cv2_erode_edge(shape, px):
    """The band of ``px`` along the outline (True there)."""
    inner = mapstyle.cv2.erode(shape.astype(np.uint8), mapstyle._disk(px), borderType=mapstyle.cv2.BORDER_CONSTANT,
                               borderValue=0).astype(bool)
    return shape & ~inner


def test_the_app_takes_the_picture_of_a_floor_style(tmp_path):
    from dbdmapscout import app as appmod
    path = os.path.join(MAPS, "McMillan", "Coal Tower.webp")
    cat = types.SimpleNamespace(image_path=lambda mid, v=1: (path, v), is_own=lambda mid, v=1: False)
    fake = _fake_app(appmod, cat, tmp_path, "lilac")
    styled = _styled_in_the_background(appmod, fake)
    assert styled.startswith(os.path.join(str(tmp_path), appmod.STYLE_CACHE)) and "-lilac-" in styled
    from dbdmapscout.app_overlay import MAP_STYLES
    from dbdmapscout.qt_maps import STYLE_BUTTONS
    assert [k for k, _l in MAP_STYLES] == [k for k, _l, _t in STYLE_BUTTONS] == ["classic", *mapstyle.STYLES]


@pytest.mark.parametrize("style", sorted(mapstyle.FLOORS))
def test_maps_drawn_dark_already_get_the_floor_of_a_floor_style(tmp_path, style):
    """1.8.29 (user: "ich seh die Umrandung der Map nicht" – Fallen Refuge in "Grau mit Rand"): Fallen Refuge and
    Freddy Fazbear's Pizza come in the dark style (see-through floor, black ring), so the floor styles left them as
    they were – a black ring on the black bar. Now they get the style's floor and edge like every converted map;
    "dark" leaves them, Trickster's Delusion (opaque, its own kind) stays in every style."""
    from dbdmapscout.mapimage import title_split
    for rel in ("Withered Isle/Fallen Refuge.webp", "Withered Isle/Freddy Fazbears Pizza.webp"):
        path = os.path.join(MAPS, rel)
        assert mapstyle.styled_path(path, str(tmp_path)) == path                  # "dark": as it is
        out_path = mapstyle.styled_path(path, str(tmp_path), style=style)
        assert out_path != path, rel
        src = np.asarray(Image.open(path).convert("RGBA")).astype(int)
        out = np.asarray(Image.open(out_path).convert("RGBA")).astype(int)
        top = title_split(Image.open(path))[2]
        assert np.array_equal(out[:top], src[:top])                               # the name untouched
        shape = mapstyle._outline(src[top:, :, 3].astype(np.uint8))
        fill, edge, _ew, alpha = mapstyle.FLOORS[style]
        floor = shape & (src[top:, :, 3] == 0) & ~cv2_erode_edge(shape, 40)
        assert floor.sum() > 20000
        got = out[top:][floor]
        assert (np.abs(got[:, :3] - np.array(fill)).max(axis=1) <= 2).mean() > 0.99, rel
        assert (np.abs(got[:, 3] - alpha) <= 2).mean() > 0.99
        solid = shape & (src[top:, :, 3] == 255) & ~cv2_erode_edge(shape, 40)    # the drawing stays
        assert (np.abs(out[top:][solid] - src[top:][solid]).max(axis=1) <= 2).mean() > 0.99
        assert np.array_equal(out[top:][~shape][:, 3], src[top:][~shape][:, 3])  # outside: as it was
        if edge is not None:                                                      # the light edge, wide enough
            rim = shape & ~mapstyle.cv2.erode(shape.astype(np.uint8), mapstyle._disk(8)).astype(bool)
            assert (np.abs(out[top:][rim][:, :3] - np.array(edge)).max(axis=1) <= 2).mean() > 0.9, rel
    trick = os.path.join(MAPS, "Sleepless District", "Trickster's Delusion.webp")
    assert mapstyle.styled_path(trick, str(tmp_path), style=style) == trick
