"""Overlay styles (skin.py, 1.3): the cards of system values / today / music as glass cards, chips & icons or
minimal line art – pure Pillow."""
import importlib.util
import os
import sys

if "tkinter" not in sys.modules and importlib.util.find_spec("tkinter") is None:   # headless CI (like test_sysinfo)
    from unittest import mock
    sys.modules["tkinter"] = mock.MagicMock()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from PIL import Image  # noqa: E402

from dbdmapscout import skin, sysinfo  # noqa: E402
from dbdmapscout.preview import sample_cover  # noqa: E402

HUD = sysinfo.hud_rows(sysinfo.Snapshot(t=0, cpu_load=38, cpu_temp=64, gpu_temp=71, gpu_load=92, vram_used=7.9,
                                        vram_total=12, ram_used=18.2, ram_total=32, gpu_hot=88))
TODAY = [[("HEUTE ", sysinfo.DIM), ("4 RUNDEN · 1:12 h", sysinfo.WHITE)],
         [("Ø KILLS ", sysinfo.DIM), ("2.5", sysinfo.WHITE), (" · ", sysinfo.DIM), ("ENTKOMMEN ", sysinfo.DIM),
          ("75%", sysinfo.WHITE)]]
MUSIC = [[("Blinding Lights", sysinfo.WHITE)], [("The Weeknd", sysinfo.DIM)]]
MODERN = [s for s in skin.STYLES if s != "classic"]


def test_fonts_are_bundled_and_load():
    for weight in skin.WEIGHTS:
        assert os.path.exists(os.path.join(skin.FONT_DIR, f"Inter-{weight}.otf")), weight
        assert skin.inter(weight, 20).getname()[0].startswith("Inter")
    assert os.path.exists(os.path.join(skin.FONT_DIR, "OFL-Inter.txt"))


def test_rows_become_labelled_pairs_and_bars():
    title, lines = skin.card_model(HUD, sysinfo.DIM, "SYSTEM")
    assert title == "SYSTEM" and [ln[0] for ln in lines] == ["CPU", "GPU", "HOTSPOT", "VRAM", "RAM"]
    assert lines[0][1][0][0] == "64°C" and lines[0][2] == pytest.approx(0.38)     # "38 %" -> the bar
    assert lines[3][2] == pytest.approx(7.9 / 12) and lines[2][2] is None          # "7.9 / 12 GB"; no share
    title, lines = skin.card_model(TODAY, sysinfo.DIM)
    assert title == "HEUTE" and lines[0][0] == "" and lines[0][1][0][0] == "4 RUNDEN · 1:12 h"
    assert [ln[0] for ln in lines[1:]] == ["Ø KILLS", "ENTKOMMEN"]
    assert skin.nice("4 RUNDEN · 1:12 h") == "4 Runden · 1:12 h" and skin.nice("CPU") == "CPU"
    assert skin.accent_rgba("#c9a227") == (201, 162, 39, 255) and skin.accent_rgba(None) == skin.GOLD


@pytest.mark.parametrize("style", MODERN)
def test_every_style_draws_the_three_cards_and_scales(style):
    hud = skin.card(HUD, 1440, style, "#c9a227", "SYSTEM")
    today = skin.card(TODAY, 1440, style, "#c9a227")
    music = skin.music(MUSIC, sample_cover(), 1440, style, (70, 200), ("accent", "remaining"))
    bare = skin.music([[("Song", sysinfo.WHITE)]], None, 1440, style, None, ())
    for pic in (hud, today, music, bare):
        assert isinstance(pic, Image.Image) and pic.mode == "RGBA"
        assert 60 < pic.width <= 470 and 40 < pic.height < 400       # fits the user's 440-px bar
        assert pic.getchannel("A").getbbox() is not None
    small = skin.card(HUD, 720, style, None, "SYSTEM")
    assert 0.4 < small.width / hud.width < 0.6 and 0.4 < small.height / hud.height < 0.6
    assert skin.card([], 1440, style).size == (1, 1)


def test_a_long_title_is_set_smaller_then_cut():
    long = [[("A" * 80, sysinfo.WHITE)], [("Artist", sysinfo.DIM)]]
    for style in MODERN:
        pic = skin.music(long, sample_cover(), 1440, style, None, ())
        assert pic.width <= skin.WRAP_SHARE * 1440 + 40, style


def test_chips_wrap_into_rows():
    chips = [skin.chip(f"Chip {i}", 1.0) for i in range(6)]
    one = skin.chip_rows(chips, 10000, 8)
    many = skin.chip_rows(chips, 250, 8)
    assert one.height < many.height and many.width <= 250


def test_the_preview_draws_the_cards_in_the_chosen_style():
    from dbdmapscout import preview
    from dbdmapscout.config import DEFAULTS
    import copy
    o = copy.deepcopy(DEFAULTS["overlay"])
    pic = Image.new("RGBA", (300, 400), (120, 120, 200, 255))
    pics = {}
    for style in skin.STYLES:
        o["style"] = style
        layers, _rect = preview.layers(3440, 1440, o, "right", HUD, None, pic, "", {"timer": "1:00"}, 0.36,
                                       (MUSIC, sample_cover(), (10, 100)), TODAY, accent="#c9a227")
        pics[style] = {name: img for name, img, _x, _y in layers}
        assert {"hud", "today", "music", "map"} <= set(pics[style])
    for a in MODERN:
        assert pics[a]["hud"].tobytes() != pics["classic"]["hud"].tobytes()
        assert pics[a]["music"].tobytes() != pics["classic"]["music"].tobytes()


# ------------------------------------------------------------------ the map card (1.3.1)
def _coal_body():
    from dbdmapscout import mapimage
    from dbdmapscout.overlay_win32 import map_body
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pic = Image.open(os.path.join(root, "maps", "McMillan", "Coal Tower II.webp")).convert("RGBA")
    return pic, map_body(pic, 440, mapimage.title_split(pic)[2])


@pytest.mark.parametrize("style", MODERN)
def test_the_map_card_carries_map_timer_and_lines(style):
    pic, body = _coal_body()
    assert body.height < pic.height * 440 / pic.height and body.width < pic.width     # name and margins cut
    card = skin.map_card(body, "Coal Tower II", "MacMillan Estate", "12:34", "", "Ø 2.8 Kills · 12 Runden",
                         "Frankfurt", 28, (), 518, style, "#c9a227")
    assert card.width >= body.width and card.height > body.height + 60
    plain = skin.map_card(body, "Coal Tower II", "MacMillan Estate", "", "", "", "", None, (), 518, style)
    assert plain.height < card.height                                                 # no lines: shorter
    warn = skin.map_card(body, "Coal Tower II", "", "0:05", "Unsicher", "", "", None, (), 518, style)
    assert warn.height > plain.height
    waiting = skin.map_card(None, "", "", "", "", "", "Frankfurt", 28, ("Warte auf Map", "Suche läuft: 1:23"), 518,
                            style, None)
    assert 100 < waiting.width < 400 and 60 < waiting.height < 300
    assert skin.frame_pad(style, 518) > 0 and skin.frame_pad("classic", 518) == 0   # 1.8.27: every style frames the map


@pytest.mark.parametrize("style", MODERN)
def test_the_maps_name_and_realm_stand_centred_over_it(style, monkeypatch):
    """1.8.40 (user: "über der Map der name soll mittig sein"): name and realm centred like the timer below."""
    pic, body = _coal_body()
    drawn = []
    real = skin._text

    def spy(im, x, y, text, font, fill, track=0):
        drawn.append((text, x, skin._width(font, text, track)))
        return real(im, x, y, text, font, fill, track)

    monkeypatch.setattr(skin, "_text", spy)
    card = skin.map_card(body, "Mount Ormond Resort I", "Ormond", "00:32", "", "", "Global", None, (), 518, style)
    name = next(d for d in drawn if d[0] == "Mount Ormond Resort I")
    realm = next(d for d in drawn if d[0] == "ORMOND")
    timer = next(d for d in drawn if d[0] == "00:32")
    mid = timer[1] + timer[2] / 2                                            # the timer was centred already
    assert abs(name[1] + name[2] / 2 - mid) <= 2
    assert abs(realm[1] + realm[2] / 2 - mid) <= 8       # the header centred – its text sits 5u right of the mark
    assert card.width > body.width


@pytest.mark.parametrize("style", MODERN)
def test_every_up_next_row_has_the_same_size_and_a_long_one_is_cut(style):
    """1.8.40 (user's screenshot: "Creep On Me (feat. French Montana & DJ Snake) – DASH, …" tiny, the next rows
    normal): a long row was set smaller before it was cut – now all rows share one size, the long one ends in …"""
    items = [("Creep On Me (feat. French Montana & DJ Snake)", "GASHI, French Montana, DJ Snake"),
             ("Bad guy", "Duroc Creep"), ("BAD EYEZ", "Nimo, Luciano")]
    u = 1.0
    q = skin._upnext_fitted("UP NEXT", items, u, style, 300)
    sizes = {tf.size for _n, tf, _t, _k in q["rows"]}
    assert len(sizes) == 1
    assert q["rows"][0][2].endswith("…") and q["rows"][1][2] == "Bad guy – Duroc Creep"
    assert all(skin._width(tf, t) + q["num_w"] <= 300 for _n, tf, t, _k in q["rows"])


def test_the_overlay_draws_the_map_card_in_the_style_and_fits_the_bar():
    """PictureOverlay with skin glass / chips / line: the card stays inside the 440-px bar (its frame may use the
    margin like the dark area), the waiting card follows the style, and a style change re-renders."""
    from dbdmapscout import layout
    from dbdmapscout import overlay_win32 as ow

    class Root:
        def after(self, *a):
            return None

        def after_cancel(self, *a):
            pass

    class Overlay(ow.PictureOverlay):
        def _push(self, *a):
            pass

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    seen = {}
    for style in skin.STYLES:
        ov = Overlay(Root())
        ov.show_caption = False
        ov.set_skin(style, "#c9a227")
        ov.set_map(os.path.join(root, "maps", "McMillan", "Coal Tower II.webp"), "Coal Tower II", 0,
                   realm="MacMillan Estate")
        ov.set_timer("12:34")
        ov.set_server("Frankfurt", 28)
        ov.set_record("Bilanz: Ø 2,8 Kills · 12 Runden")
        edge = min(ov.backdrop_pad(518), 15)
        height = layout.fit_height(470, 406, *ov.map_size())
        h = ov.fit_width(height, 518, 406 + 2 * edge)
        w, hh = ov.render(h)
        assert w <= 406 + 2 * edge and hh > h, style
        seen[style] = ov._prepared[0][0]
        ov.set_waiting(("Warte auf Map", "Suche läuft: 1:23 · Killer"))
        ww, wh = ov.render(518)
        assert 120 < ww < 420 and 60 < wh < 320, style
    assert len({bytes(v) for v in seen.values()}) == len(skin.STYLES)          # four different pictures
    ov.set_skin("classic", None)                                                # a style change re-renders
    assert ov._key is None and ov._base_key is None and ov._fit is None


@pytest.mark.parametrize("style", MODERN)
def test_the_big_music_layout_puts_the_cover_on_top(style):
    """1.3.2 (user: "Groß – Cover oben" still showed the small card in the new styles)."""
    big = skin.music(MUSIC, sample_cover(), 1440, style, (70, 200), ("remaining",), None, "big")
    small = skin.music(MUSIC, sample_cover(), 1440, style, (70, 200), ("remaining",), None, "compact")
    assert big.height > small.height + 150 and big.height > big.width              # tall: cover above the text
    no_cover = skin.music(MUSIC, None, 1440, style, None, (), None, "big")
    assert no_cover.height < big.height                                            # without a cover: compact


def test_the_drop_shadow_looks_like_the_full_size_blur():
    """1.3.5: blurred on a smaller picture (it is drawn every second) – no visible difference."""
    import numpy as np
    from PIL import ImageFilter
    from dbdmapscout import skin
    card = skin._panel(420, 760, 20, (20, 20, 24, 200), (255, 255, 255, 40))
    for u in (0.6, 1.0, 2.0):
        blur, off = max(2, int(8 * u)), max(1, int(4 * u))
        ref = Image.new("RGBA", (card.width + 4 * blur, card.height + 4 * blur), (0, 0, 0, 0))
        sh = Image.new("RGBA", ref.size, (0, 0, 0, 0))
        sh.paste((0, 0, 0, 255), (2 * blur, 2 * blur + off), card.getchannel("A").point(lambda v: v * 120 // 255))
        ref.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))
        ref.alpha_composite(card, (2 * blur, 2 * blur))
        got = skin.shadowed(card, u)
        assert got.size == ref.size
        assert np.abs(np.asarray(got, int) - np.asarray(ref, int)).max() <= 8


def test_values_never_change_the_size_of_a_card():
    """1.8.28 (user: "mir ist wichtig, dass sich die GUI-Elemente nicht verschieben, wenn ein Wert grösser oder
    kleiner wird"): the tile cards have one width, the timer field is at least five digits wide, the ping pill
    is sized for three digits, the progress time for the song's length – and ``min_w`` widens any card."""
    from dbdmapscout import overlay_win32 as ow

    def rows(cpu, gpu, vram, ram, throttle=None):
        return sysinfo.hud_rows(sysinfo.Snapshot(t=0, cpu_load=cpu, cpu_temp=64, gpu_temp=71, gpu_load=gpu,
                                                 vram_used=vram, vram_total=12, ram_used=ram, ram_total=32,
                                                 throttle=throttle))
    cover = sample_cover()
    for style in MODERN:
        sizes = {skin.card(rows(*v), 1440, style, None, "SYSTEM").size for v in ((3, 8, 0.9, 9.9), (100, 100, 11.9, 31.5))}
        assert len(sizes) == 1, style
        warn = skin.card(rows(38, 92, 7.9, 18.2, "thermal"), 1440, style, None, "SYSTEM")
        assert warn.width == next(iter(sizes))[0] and warn.height > next(iter(sizes))[1]   # a row more, no wider
        today = {skin.card([[("HEUTE ", sysinfo.DIM), (t, sysinfo.WHITE)]], 1440, style).size
                 for t in ("4 RUNDEN · 1:12 h", "12 RUNDEN · 10:12 h")}
        assert len(today) == 1, style
        info = {ow.info_card(t, "Frankfurt", p, "", "Ø 2.8 Kills", 518, style).size
                for t, p in (("0:05", 8), ("9:59", 128), ("10:00", 28))}
        assert len(info) == 1, style
        music = {skin.music(MUSIC, cover, 1440, style, prog, ("remaining",), None, "big").size
                 for prog in ((5, 1000), (900, 1000), (10, 100))}
        assert len(music) == 1, style
        assert skin.music(MUSIC, cover, 1440, style, (10, 100), (), None, "compact", min_w=420).width == 420
        up = ("ALS NÄCHSTES", (("Save Your Tears", "The Weeknd"),))
        beside = skin.music(MUSIC, cover, 1440, style, (10, 100), (), None, "big", up, "right").width
        assert skin.music(MUSIC, cover, 1440, style, (10, 100), (), None, "big", up, "right",
                          min_w=beside + 60).width == beside + 60                  # the list's panel takes it
        assert skin.card(rows(38, 92, 7.9, 18.2), 1440, style, None, "SYSTEM", min_w=440).width == 440
    classic = {ow.info_card(t, "Frankfurt", p, "", "", 518).size for t, p in (("0:05", 8), ("9:59", 128), ("10:00", 28))}
    assert len(classic) == 1
    assert len({ow.progress_strip(300, el, 1000, 1440, remaining=True).size for el in (5, 900, 995)}) == 1
    assert ow.music_picture(MUSIC, 1440, cover, "compact", (10, 100), (), min_w=420).width == 420
    assert ow.music_picture(MUSIC, 1440, cover, "big", (10, 100), ("backdrop",), min_w=420).width >= 420


def test_a_music_card_keeps_a_given_height_and_steady_box_holds_a_size():
    """1.8.30: ``min_h`` makes the card (frame included) that tall in every style and in classic (the dark area
    round it too); layout.steady_box keeps the largest size for a key and follows a smaller one only after it
    lasted SHRINK_AFTER seconds."""
    from dbdmapscout import layout
    from dbdmapscout import overlay_win32 as ow
    up = ("ALS NÄCHSTES", (("Save Your Tears", "The Weeknd"), ("Levitating", "Dua Lipa")))
    for style in MODERN:
        full = skin.music(MUSIC, sample_cover(), 1440, style, (10, 100), (), None, "big", up, "below")
        bare = skin.music(MUSIC, None, 1440, style, (10, 100), (), None, "big", None, "below",
                          min_w=full.width, min_h=full.height)
        assert bare.size == full.size, style
        frame = bare.getchannel("A").getbbox()
        assert frame[3] - frame[1] > full.height * 0.8                      # the frame itself is that tall
    for look in ((), ("backdrop",)):
        full = ow.music_picture(MUSIC, 1440, sample_cover(), "big", (10, 100), look, upnext=up)
        bare = ow.music_picture(MUSIC, 1440, None, "big", (10, 100), look, min_w=full.width, min_h=full.height)
        assert bare.size == full.size, look
    st, w, h = layout.steady_box(None, "k", 300, 400, 0.0)
    st, w, h = layout.steady_box(st, "k", 260, 300, 1.0)
    assert (w, h) == (300, 400)                                              # a moment smaller: held
    st, w, h = layout.steady_box(st, "k", 300, 400, 2.0)
    st, w, h = layout.steady_box(st, "k", 260, 300, 3.0)
    st, w, h = layout.steady_box(st, "k", 260, 300, 3.0 + layout.SHRINK_AFTER - 0.1)
    assert (w, h) == (300, 400)                                              # the clock starts anew
    st, w, h = layout.steady_box(st, "k", 260, 300, 3.0 + layout.SHRINK_AFTER)
    assert (w, h) == (260, 300)                                              # lasted: followed
    assert layout.steady_box(st, "other", 200, 100, 99.0)[1:] == (200, 100)  # another key: anew


def test_a_cards_shadow_is_made_once_per_frame_and_looks_the_same():
    """1.8.31: the soft shadow depends only on the card's frame – kept per size and style, a second card of the
    same size reuses it; the result matches the shadow of the card itself (only under the text it may differ)."""
    import numpy as np
    skin._SHADOWS.clear()
    a = skin.card(HUD, 1440, "glass", "#c9a227", "SYSTEM")
    n = len(skin._SHADOWS)
    hot = sysinfo.hud_rows(sysinfo.Snapshot(t=0, cpu_load=99, cpu_temp=95, gpu_temp=88, gpu_load=12, vram_used=1.1,
                                            vram_total=12, ram_used=30.2, ram_total=32, gpu_hot=101))
    b = skin.card(hot, 1440, "glass", "#c9a227", "SYSTEM")
    assert a.size == b.size and len(skin._SHADOWS) == n == 1                 # the same frame: one shadow
    inner = skin._frame(a.width - 4 * 8, a.height - 4 * 8, "glass", 1.0)
    ref = skin.shadowed(inner, 1.0)                                           # without a key: as before
    got = skin.shadowed(inner, 1.0, ("frame", "glass"), lambda: inner.getchannel("A"))
    assert np.abs(np.asarray(got, int) - np.asarray(ref, int)).max() == 0
    assert skin.card(HUD, 1440, "line", None, "SYSTEM").size and len(skin._SHADOWS) == 1   # line: no shadow


def test_the_music_card_draws_only_its_progress_each_second():
    """1.8.31: cover, text and list are drawn once per song and size; each second only the bar and the time –
    the picture is exactly what drawing it whole gives."""
    import numpy as np
    up = ("ALS NÄCHSTES", (("Save Your Tears", "The Weeknd"), ("Levitating", "Dua Lipa")))
    cover = sample_cover()
    for style in MODERN:
        skin._BODIES.clear()
        first = skin.music(MUSIC, cover, 1440, style, (70, 200), ("accent", "remaining"), None, "big", up, "below")
        n = len(skin._BODIES)
        later = skin.music(MUSIC, cover, 1440, style, (71, 200), ("accent", "remaining"), None, "big", up, "below")
        assert len(skin._BODIES) == n == 1 and later.size == first.size, style      # the body was reused
        skin._BODIES.clear()
        whole = skin.music(MUSIC, cover, 1440, style, (71, 200), ("accent", "remaining"), None, "big", up, "below")
        assert np.array_equal(np.asarray(later), np.asarray(whole)), style         # the same picture
        assert not np.array_equal(np.asarray(first), np.asarray(later))            # the bar and time moved
