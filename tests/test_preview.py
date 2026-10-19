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
    o = dict(DEFAULTS["overlay"], info_pos="inside", keep_out_on=False)  # lines with the map, no Discord areas (1.8.24/25)
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
    w.overlay_rect = w.hud_rect = w.media_rect = w.today_rect = w.info_rect = w.toast_rect = None
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


def test_numpy_does_one_thread_so_nothing_spins_between_the_looks():
    """1.8.38 (QA audit, measured): multithreaded OpenBLAS threads spun between the OCR looks – about half a core
    in the menus for one tiny matrix product (46 % → 4 % of a core with one thread). The package sets it before
    numpy loads; a value the user set stays, and the OCR session does not spin either."""
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    code = ("import os; os.environ.pop('OPENBLAS_NUM_THREADS', None); import dbdmapscout.ocr; "
            "print(os.environ.get('OPENBLAS_NUM_THREADS'))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=root)
    assert out.stdout.strip() == "1", out.stderr
    env = dict(os.environ, OPENBLAS_NUM_THREADS="3")
    out = subprocess.run([sys.executable, "-c", "import os, dbdmapscout; print(os.environ['OPENBLAS_NUM_THREADS'])"],
                         capture_output=True, text=True, cwd=root, env=env)
    assert out.stdout.strip() == "3", out.stderr
    from dbdmapscout.ocr import Recognizer
    rec = Recognizer(os.path.join(root, "models", "ch_PP-OCRv4_rec_infer.onnx"), threads=2)
    opts = rec.session.get_session_options()
    assert opts.get_session_config_entry("session.intra_op.allow_spinning") == "0"


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


def test_the_drawn_in_name_keeps_its_size_when_the_map_grows():
    """1.65.4 (user: the name above the map as a picture of its own, the map's size freely)."""
    import glob
    import os
    from PIL import Image
    from dbdmapscout.mapimage import title_split
    from dbdmapscout.overlay_win32 import compose
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = sorted(glob.glob(os.path.join(root, "maps", "**", "*.webp"), recursive=True))[0]
    img = Image.open(path).convert("RGBA")
    split = title_split(img)[2]
    small = compose(img, 500, "", True, False, 500, split)
    big = compose(img, 800, "", True, False, 500, split)
    name_h = round(split * 500 / img.height)
    assert small.height == 500                                     # same as before at the standard size
    assert big.height == name_h + round((img.height - split) * 800 / img.height)   # only the map grew
    assert compose(img, 800, "", True, False, 0, split).height == 800              # no own text size: as before


def test_a_map_wider_than_the_bar_stays_at_its_outer_edge():
    """1.65.4: "Karte darf grösser als der Balken werden" – at the bar's outer edge, never off the screen."""
    from dbdmapscout import layout
    assert layout.clamp_x("left", 100, 600, 0, 3440, 440, 17) == 17
    assert layout.clamp_x("right", 3000, 600, 0, 3440, 440, 17) == 3440 - 17 - 600
    assert layout.clamp_x("right", 3200, 300, 0, 3440, 440, 17) == 3440 - 17 - 300     # fits: as before
    x, _y, w, _h, _mh = layout.preview_rect(3440, 1440, "auto", 0, 0, 0.6, 0.012, True, 0.9, grow=True)
    assert w > 440 and x == 17                                     # bigger than the bar, from its outer edge
    assert layout.preview_rect(3440, 1440, "auto", 0, 0, 0.6, 0.012, True, 0.9)[2] <= 440 - 2 * 17


def test_today_is_a_card_of_its_own():
    """1.2.6 (user: rounds/kills under the GPU/CPU counter made no sense): "today" is its own layer – below the
    system values by default (the music "below" then hangs under it), in the bar or at an own place."""
    today = [[("HEUTE ", sysinfo.DIM), ("3 RUNDEN · 1:12", sysinfo.WHITE)], [("UHR ", sysinfo.DIM), ("15:54", sysinfo.WHITE)]]
    pic = Image.new("RGBA", (400, 500), (120, 120, 200, 255))
    m = preview.music_rows(media.NowPlaying(), 0.0)
    layers, _r = preview.layers(W, H, _o(media_pos="under_today"), "right", ROWS, None, pic, "", INFO, 0.36, m, today)
    by = {n: (x, y, im.width, im.height) for n, im, x, y in layers}
    assert set(by) == {"map", "hud", "today", "music"}
    hx, hy, hw, hh = by["hud"]
    tx, ty, tw, th = by["today"]
    mx, my, mw, mh = by["music"]
    assert ty > hy + hh and abs((tx + tw / 2) - (hx + hw / 2)) <= 1          # centred right under the system values
    assert my > ty + th                                                      # the music below "today"
    layers, _r = preview.layers(W, H, _o(today_pos="bottom_left", today_backdrop=True), "right", ROWS, None, pic,
                                "", INFO, 0.36, None, today)
    by = {n: (x, y, im.width, im.height) for n, im, x, y in layers}
    assert by["today"][0] + by["today"][2] < 440 and by["today"][1] + by["today"][3] <= H - 17   # bottom of the left bar
    layers, _r = preview.layers(W, H, _o(today_pos="custom", today_xy=[0.5, 0.5]), "", [], None, pic, "", INFO,
                                0.36, None, today)
    by = {n: (x, y, im.width, im.height) for n, im, x, y in layers}
    assert "hud" not in by and abs(by["today"][0] + by["today"][2] / 2 - W / 2) <= 1   # its centre where asked
    # at the top of the left bar the map moves below the system values and "today"
    layers, (mx, my, _w, _h) = preview.layers(W, H, _o(), "left", ROWS, None, pic, "", INFO, 0.36, None, today)
    by = {n: (x, y, im.width, im.height) for n, im, x, y in layers}
    assert my >= by["today"][1] + by["today"][3]


def test_cards_stack_in_any_order_and_a_loop_falls_back():
    """1.2.7 (user's pick: "Elemente stapeln"): each card may hang below another; the preview places them in
    dependency order, a loop goes below the system values."""
    assert layout.stack_order({"today": "below", "music": "under_today"}) == [("today", "hud"), ("music", "today")]
    assert layout.stack_order({"today": "under_music", "music": "below"}) == [("music", "hud"), ("today", "music")]
    assert layout.stack_order({"today": "under_music", "music": "under_today"}) == [("today", "hud"), ("music", "today")]
    assert layout.stack_order({"today": "bottom_left", "music": "custom"}) == [("today", None), ("music", None)]
    assert layout.stack_order({"music": "under_today"}) == [("music", "hud")]        # no "today" card: the system values
    today = [[("HEUTE ", sysinfo.DIM), ("3 RUNDEN", sysinfo.WHITE)]]
    pic = Image.new("RGBA", (400, 500), (120, 120, 200, 255))
    m = preview.music_rows(media.NowPlaying(), 0.0)
    layers, _r = preview.layers(W, H, _o(media_pos="below", today_pos="under_music"), "right", ROWS, None, pic, "",
                                INFO, 0.36, m, today)
    by = {n: (x, y, im.width, im.height) for n, im, x, y in layers}
    assert by["music"][1] > by["hud"][1] + by["hud"][3] and by["today"][1] > by["music"][1] + by["music"][3]
    # the map at the top of the left bar: below the whole stack
    layers, (mx, my, _w, _h) = preview.layers(W, H, _o(media_pos="below", today_pos="under_music"), "left", ROWS,
                                               None, pic, "", INFO, 0.36, m, today)
    by = {n: (x, y, im.width, im.height) for n, im, x, y in layers}
    assert my >= by["today"][1] + by["today"][3]


def test_the_name_strip_no_longer_widens_the_map():
    """1.2.7 (idea 1): the map's name scaled apart from the map took the whole strip's width – wider than the map,
    so the lines below were shrunk for nothing. Now only the name itself counts."""
    from dbdmapscout.overlay_win32 import compose
    pic = Image.new("RGBA", (1000, 1200), (0, 0, 0, 0))
    pic.paste((255, 255, 255, 255), (300, 20, 700, 120))                 # the name: 400 px of a 1000-px strip
    pic.paste((140, 147, 232, 255), (100, 200, 900, 1100))               # the map body
    out = compose(pic, 300, "", True, False, 600, 160)                   # body at 300 px, name at 600 px
    assert out.width == round(1000 * 300 / 1200) and out.height > 300    # the body's strip (250), not the name's (500)


def test_the_preview_draws_the_cards_of_one_bar_at_one_width():
    """1.8.29: like the App – system values, today and music standing in the same bar get the widest one's
    width (two passes over layout.column_widths); off, each keeps its own."""
    import copy
    from dbdmapscout import preview, sysinfo
    from dbdmapscout.config import DEFAULTS
    o = copy.deepcopy(DEFAULTS["overlay"])
    o.update(style="chips", today_pos="custom", today_xy=[0.94, 0.6], media_pos="custom", media_xy=[0.94, 0.87],
             media_style="big", bar_limits_on=False, keep_out_on=False)
    hud = sysinfo.hud_rows(sysinfo.Snapshot(t=0, cpu_load=38, cpu_temp=64, gpu_temp=71, gpu_load=92, vram_used=7.9,
                                            vram_total=12, ram_used=18.2, ram_total=32))
    today = [[("HEUTE ", sysinfo.DIM), ("4 RUNDEN · 1:12 h", sysinfo.WHITE)]]
    music = ([[("Blinding Lights", sysinfo.WHITE)], [("The Weeknd", sysinfo.DIM)]], preview.sample_cover(), (70, 176))
    pic = Image.new("RGBA", (300, 400), (120, 120, 200, 255))

    def widths(o):
        layers, _r = preview.layers(3440, 1440, o, "right", hud, None, pic, "", {"timer": "1:00"}, 0.36, music,
                                    today, accent="#c9a227")
        by = {n: (img.width, x) for n, img, x, y in layers}
        assert all(by[n][1] >= 3440 - layout.bar_width(3440, 1440) for n in ("hud", "today", "music"))  # right bar
        return {n: by[n][0] for n in ("hud", "today", "music")}
    same = widths(o)
    assert len(set(same.values())) == 1
    o["cards_same_width"] = False
    own = widths(o)
    assert len(set(own.values())) > 1 and max(own.values()) == same["hud"]
    assert layout.column_widths({"a": (3100, 100, 200, 50), "b": (3050, 400, 300, 50), "c": (100, 100, 150, 50),
                                 "d": (1700, 100, 500, 50)}, (0, 0, 3440, 1440)) == {"a": 300}
    # a long title makes the music card bar-wide, so every card of the column is – such a card reaches into
    # Discord's pinned-chat zone at the bar's edge: the zone yields (soft), the cards never lie on each other
    o["cards_same_width"], o["keep_out_on"] = True, True
    o.update(bar_limits_on=True, bar_limits=[0.1521, 0.2381, 0.3014, 0.0], bar_limits_same=False)
    long = ([[("Beneath Your Beautiful (feat. Emeli Sandé)", sysinfo.WHITE)], [("Labrinth", sysinfo.DIM)]],
            preview.sample_cover(), (70, 196))
    for merged in (False, True):
        if merged:
            o.update(today_pos="below", media_pos="under_today")
        layers, _r = preview.layers(3440, 1440, o, "custom", hud, (0.984, 0.383), pic, "", {"timer": "1:00"}, 0.36,
                                    long, today, accent="#c9a227")
        boxes = {n: (x, y, img.width, img.height) for n, img, x, y in layers}
        assert len({boxes[n][2] for n in ("hud", "today", "music")}) == 1
        names = list(boxes)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                assert not layout.boxes_overlap(boxes[a], boxes[b]), (merged, a, b, boxes[a], boxes[b])
    # the keep-out areas still count when there is room: a card dropped on one moves off it
    shift = layout.resolve([("today", (3000, 900, 200, 100))], [], (0, 0, 3440, 1440), None, 8,
                           soft=[(2800, 806, 241, 339)])
    assert shift == {"today": (0, 698 - 900)}                      # the nearest free place: right above it
