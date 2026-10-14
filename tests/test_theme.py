"""Designs of the control window: the vendored Sun Valley theme under own names and its gold accent
(pure part; loading into Tk runs in tests/test_windows.py)."""
import importlib.util
import io
import sys
from unittest import mock

if "tkinter" not in sys.modules and importlib.util.find_spec("tkinter") is None:   # headless CI: Tk only imported
    sys.modules["tkinter"] = mock.MagicMock()
if isinstance(sys.modules.get("tkinter"), mock.MagicMock):
    sys.modules.setdefault("tkinter.font", mock.MagicMock())
    sys.modules.setdefault("tkinter.ttk", mock.MagicMock())

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from PIL import Image  # noqa: E402

from dbdmapscout import theme  # noqa: E402


@pytest.mark.parametrize("mode", ["dark", "light"])
@pytest.mark.parametrize("gold", [False, True])
def test_sun_valley_source_gets_own_names(mode, gold):
    name, src = theme.sv_source(mode, gold)
    assert name == f"dbdms-{'gold' if gold else 'blue'}-{mode}"
    assert f"theme create {name}" in src
    assert "sun-valley" not in src and "info script" not in src and "package provide" not in src
    assert "$::dbdms_sheet" in src
    assert ("#57c8ff" in src or "#005fb8" in src) != gold          # blue accent only in the blue design


def test_gold_sheet_turns_only_the_blue_accent_gold():
    im = Image.new("RGBA", (3, 1))
    im.putpixel((0, 0), (0x57, 0xc8, 0xff, 255))                   # accent blue
    im.putpixel((1, 0), (0x40, 0x40, 0x40, 200))                   # grey stays
    im.putpixel((2, 0), (0x2f, 0x60, 0xd8, 0))                     # transparent stays transparent
    buf = io.BytesIO()
    im.save(buf, "PNG")
    out = Image.open(io.BytesIO(theme.gold_sheet(buf.getvalue(), light=False))).convert("RGBA")
    r, g, b, a = out.getpixel((0, 0))
    assert r > g > b and a == 255                                   # gold: red > green > blue
    assert out.getpixel((1, 0)) == (0x40, 0x40, 0x40, 200)
    assert out.getpixel((2, 0))[3] == 0


def test_real_sprite_sheets_recolour():
    for mode in ("dark", "light"):
        with open(f"{theme.SV_DIR}/spritesheet_{mode}.png", "rb") as f:
            png = f.read()
        out = Image.open(io.BytesIO(theme.gold_sheet(png, light=mode == "light"))).convert("RGB")
        h, s, _v = (np.asarray(c) for c in out.convert("HSV").split())
        assert not ((h >= 128) & (h <= 179) & (s > 64)).any()
    assert theme.DEFAULT_STYLE in dict(theme.STYLES)
