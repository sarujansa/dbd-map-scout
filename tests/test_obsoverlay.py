"""1.8.89: the overlay in the OBS recording – composing the elements, the placement maths, the writer thread."""
import os
import sys
import time

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dbdmapscout import obsoverlay  # noqa: E402

S = 2560 / 3440     # a 3440×1440 window fitted into a 2560×1440 canvas (obsrec.Recorder._fit)
FIT = {"positionX": 0, "positionY": 0, "alignment": 5, "boundsType": "OBS_BOUNDS_SCALE_INNER", "boundsAlignment": 0,
       "boundsWidth": 2560, "boundsHeight": 1440, "sourceWidth": 3440, "sourceHeight": 1440}


def test_the_overlay_follows_the_window_item_fitted_into_the_canvas():
    """Our window item: top left, scaled into the canvas, centred in the bounds – the picture is 2560 wide and
    1071.6 high with 184.2 px above it; the overlay at (20, 300) of the window lands at (14.9, 407.4)."""
    tf = obsoverlay.overlay_transform(FIT, (20, 300, 400, 900))
    assert tf["boundsType"] == "OBS_BOUNDS_NONE" and tf["alignment"] == obsoverlay.TOP_LEFT
    assert abs(tf["scaleX"] - S) < 1e-5 and abs(tf["scaleY"] - S) < 1e-5
    assert abs(tf["positionX"] - 20 * S) < 0.01 and abs(tf["positionY"] - ((1440 - 1440 * S) / 2 + 300 * S)) < 0.01
    # a 3440×1440 canvas: 1:1
    big = dict(FIT, boundsWidth=3440, boundsHeight=1440)
    assert obsoverlay.overlay_transform(big, (20, 300, 400, 900)) == {
        "positionX": 20.0, "positionY": 300.0, "scaleX": 1.0, "scaleY": 1.0, "alignment": 5,
        "boundsType": "OBS_BOUNDS_NONE"}
    # no picture yet (OBS reports no source size): nothing to place
    assert obsoverlay.overlay_transform(dict(FIT, sourceWidth=0, sourceHeight=0), (20, 300, 400, 900)) is None
    assert obsoverlay.overlay_transform({}, (0, 0, 1, 1)) is None


def test_the_maths_covers_the_other_item_settings_a_user_may_pick():
    # no bounds, scaled by hand, the item's position is its centre (alignment 0)
    tf = obsoverlay.overlay_transform({"positionX": 1280, "positionY": 720, "alignment": 0, "scaleX": 0.5,
                                       "scaleY": 0.5, "boundsType": "OBS_BOUNDS_NONE", "sourceWidth": 3440,
                                       "sourceHeight": 1440}, (100, 40, 10, 10))
    assert tf["scaleX"] == 0.5 and tf["positionX"] == 1280 - 860 + 50 and tf["positionY"] == 720 - 360 + 20
    # the bars cropped away in OBS (440 px each side): the overlay sits 440 px further left
    tf = obsoverlay.overlay_transform(dict(FIT, cropLeft=440, cropRight=440, boundsWidth=2560, boundsHeight=1440),
                                      (500, 300, 10, 10))
    assert tf["scaleX"] == 1.0 and tf["positionX"] == 60.0 and tf["positionY"] == 300.0
    # bounds anchored bottom right, picture stretched
    tf = obsoverlay.overlay_transform({"positionX": 2560, "positionY": 1440, "alignment": 10,
                                       "boundsType": "OBS_BOUNDS_STRETCH", "boundsAlignment": 0, "boundsWidth": 1720,
                                       "boundsHeight": 1440, "sourceWidth": 3440, "sourceHeight": 1440}, (0, 0, 1, 1))
    assert (tf["positionX"], tf["positionY"], tf["scaleX"], tf["scaleY"]) == (840.0, 0.0, 0.5, 1.0)
    # the picture aligned to the right inside wider bounds
    tf = obsoverlay.overlay_transform(dict(FIT, boundsWidth=3000, boundsAlignment=obsoverlay.ALIGN_RIGHT), (0, 0, 1, 1))
    assert abs(tf["positionX"] - (3000 - 3440 * (1440 / 1440))) < 0.01 or abs(tf["positionX"] - 0) < 0.01
    outer = obsoverlay.picture_rect(dict(FIT, boundsType="OBS_BOUNDS_SCALE_OUTER"))
    assert abs(outer[2] - 1.0) < 1e-9 and abs(outer[0] - (2560 - 3440) / 2) < 0.01     # wider than the canvas


def test_compose_unites_the_elements_and_bakes_in_their_opacity():
    red = Image.new("RGBA", (4, 4), (255, 0, 0, 255))
    blue = Image.new("RGBA", (2, 2), (0, 0, 255, 255))
    pic, box = obsoverlay.compose([(red, (10, 10), 1.0), (blue, (20, 12), 0.5)])
    assert box == (10, 10, 12, 4) and pic.size == (12, 4)
    assert pic.getpixel((0, 0)) == (255, 0, 0, 255) and pic.getpixel((5, 0)) == (0, 0, 0, 0)
    assert pic.getpixel((10, 2))[2] == 255 and abs(pic.getpixel((10, 2))[3] - 128) <= 1
    assert blue.getpixel((0, 0))[3] == 255                                    # the element itself untouched
    assert obsoverlay.compose([]) is None
    assert obsoverlay.compose([(None, (0, 0), 1.0), (Image.new("RGBA", (0, 0)), (0, 0), 1.0), (red, (0, 0), 0)]) is None
    grey = Image.new("L", (2, 2), 200)                                        # other modes are converted
    pic, box = obsoverlay.compose([(grey, (-5, -5), 1.0)])
    assert box == (-5, -5, 2, 2) and pic.getpixel((0, 0)) == (200, 200, 200, 255)


def test_the_writer_writes_a_png_once_per_change_and_reports_the_box(tmp_path):
    boxes = []
    file = obsoverlay.path(str(tmp_path))
    w = obsoverlay.Writer(file, boxes.append)
    w.start()
    try:
        red = Image.new("RGBA", (4, 4), (255, 0, 0, 255))
        assert w.submit([(red, (120, 310), 0.85)], (100, 10), ("map", 120, 310, id(red)))
        end = time.time() + 5
        while w.writes < 1 and time.time() < end:
            time.sleep(0.02)
        assert w.writes == 1 and boxes == [(20, 300, 4, 4)] and not w.last_error
        with Image.open(file) as img:
            assert img.size == (4, 4) and img.getpixel((0, 0))[0] == 255 and abs(img.getpixel((0, 0))[3] - 217) <= 1
        assert not w.submit([(red, (120, 310), 0.85)], (100, 10), ("map", 120, 310, id(red)))   # unchanged
        time.sleep(0.1)
        assert w.writes == 1
        assert w.submit([], (0, 0), None)                                     # nothing shown: transparent, no box
        end = time.time() + 5
        while w.writes < 2 and time.time() < end:
            time.sleep(0.02)
        assert boxes[-1] is None
        with Image.open(file) as img:
            assert img.size == obsoverlay.EMPTY and img.getpixel((0, 0))[3] == 0
        assert not os.path.exists(file + ".tmp")
    finally:
        w.stop()
        w.join(timeout=5)
    assert not w.is_alive()
