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
