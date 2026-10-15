"""1.64: the overlay tab's preview shows every element like the game (preview.layers)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402

from dbdmapscout import layout, media, preview, sysinfo  # noqa: E402
from dbdmapscout.config import DEFAULTS  # noqa: E402

W, H = 3440, 1440
ROWS = [[("CPU ", sysinfo.DIM), ("64°C", sysinfo.WHITE)], [("GPU ", sysinfo.DIM), ("71°C", sysinfo.WHITE)]]
INFO = {"timer": "3:27", "server": "", "ping": None, "record": "Bilanz: Ø 2,8 Kills · 12 Runden"}


def _o(**kw):
    o = dict(DEFAULTS["overlay"])
    o.update(kw)
    return o


def _layers(o, music=True):
    pic = Image.new("RGBA", (400, 500), (120, 120, 200, 255))
    m = preview.music_rows(media.NowPlaying(), 0.0) if music else None
    return preview.layers(W, H, o, "right", ROWS, None, pic, "", INFO, o["height"], m)


def test_every_element_is_a_layer_in_its_place():
    layers, (mx, my, mw, mh) = _layers(_o())
    names = [n for n, _img, _x, _y in layers]
    assert names == ["map", "hud", "music"]
    bar = layout.bar_width(W, H)
    assert mx >= 0 and mx + mw <= bar                              # automatic: the map in the left bar
    _n, hud, hx, hy = layers[1]
    assert hx + hud.width <= W and hx >= W - bar                   # system values at the top of the right bar
    _n, card, cx, cy = layers[2]
    assert cy >= hy + hud.height and cx >= W - bar                 # music below them, in the bar


def test_sliders_change_the_preview():
    small, _r = _layers(_o(height=0.2, media_scale=0.6))
    big, _r = _layers(_o(height=0.4, media_scale=1.4))
    assert big[0][1].height > small[0][1].height                   # map size
    assert big[2][1].height > small[2][1].height                   # music size
    bottom, _r = _layers(_o(media_pos="bottom_left"))
    _n, card, cx, cy = bottom[2]
    assert cx < 100 and cy + card.height > H - 60
    assert [n for n, *_x in _layers(_o(), music=False)[0]] == ["map", "hud"]


def test_same_inputs_reuse_the_pictures():
    a, _r = _layers(_o())
    b, _r = _layers(_o(height=0.3))                                # only the map changed
    assert a[1][1] is b[1][1] and a[2][1] is b[2][1] and a[0][1] is not b[0][1]


def test_centre_guides_are_thin_lines_and_blacked_out_for_the_detection():
    """1.64.5 (user: Mittellinie als Kreuz beim Ausrichten): 3-px lines with light dashes on a dark edge; the
    worker blacks them out like the overlay (a long light line would look like a banner's separator)."""
    import numpy as np
    from dbdmapscout.overlay_win32 import guide_line
    from dbdmapscout.worker import DetectionWorker
    v, h = guide_line(1440, True), guide_line(3440, False)
    assert v.size == (3, 1440) and h.size == (3440, 3)
    assert v.getpixel((1, 0))[:3] == (255, 255, 255) and v.getpixel((0, 0))[:3] == (0, 0, 0)
    w = DetectionWorker.__new__(DetectionWorker)
    w.overlay_rect = w.hud_rect = w.media_rect = None
    w.guide_rects = ((1719, 0, 3, 1440), (0, 719, 3440, 3))
    img = np.full((1440, 3440, 3), 200, np.uint8)
    w._mask_overlay(img, 0, 0)
    assert img[:, 1719:1722].max() == 0 and img[719:722].max() == 0 and img[100, 100].min() == 200


def test_onnxruntime_telemetry_is_off_before_it_is_loaded():
    """1.64.7: onnxruntime sends Microsoft telemetry (measured in the container: mobile.events.data.microsoft.com,
    4 tries in 40 s) unless ORT_DISABLE_TELEMETRY is set before it loads – the package sets it on import, so even
    a fresh interpreter that loads onnxruntime through dbdmapscout has it."""
    import subprocess
    code = ("import os; os.environ.pop('ORT_DISABLE_TELEMETRY', None); import dbdmapscout.ocr; "
            "print(os.environ.get('ORT_DISABLE_TELEMETRY'))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert out.stdout.strip() == "1", out.stderr


def test_system_values_keep_their_place_while_values_change_width():
    """1.64.7 (user: "bewegt sich immer leicht nach rechts und links"): placed by the widest width seen."""
    state, w = layout.steady_width(None, ("right", 1440, ("CPU ",)), 300)
    state, w2 = layout.steady_width(state, ("right", 1440, ("CPU ",)), 280)       # "100 %" → "38 %"
    assert w == w2 == 300
    state, w3 = layout.steady_width(state, ("right", 1440, ("CPU ", "GPU ")), 250)   # other rows: anew
    assert w3 == 250


def test_edit_frame_names_the_element_without_changing_its_size():
    from dbdmapscout.overlay_win32 import BORDER, add_border
    pic = add_border(Image.new("RGBA", (300, 200), (0, 0, 0, 0)), "MUSIK")
    assert pic.size == (300, 200)                              # no jump after "Fertig"
    assert pic.getpixel((2, 2)) == BORDER and pic.getpixel((150, 199)) == BORDER


def test_the_map_grows_but_its_text_keeps_its_size():
    """1.65 (user: "nur die Map grösser machen und die Schrift gleich behalten")."""
    from PIL import Image
    from dbdmapscout.preview import overlay_picture
    pic = Image.new("RGBA", (300, 400), (90, 90, 140, 255))
    small = overlay_picture(pic, 400, "", True, "3:27", "", None, "", text_h=500)
    big = overlay_picture(pic, 800, "", True, "3:27", "", None, "", text_h=500)
    assert big.height - 800 == small.height - 400          # the block below the map: the same height
