"""Map banner in a DBD window narrower than 16:9 (user screenshot 1718×1360, 1.44.0): the trial is letterboxed,
the picture only ~858 px high, the separator hairline comes out at grey ~55 – the first pass (> 105) misses it."""
import os

import cv2
import pytest

from dbdmapscout import detector
from dbdmapscout.detector import BannerReader, find_separator

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CROP = os.path.join(ROOT, "tests", "data", "banner", "letterbox_badham.jpg")   # ROI of the 1718×1359 frame
FRAME = (1718, 1359)


def test_dim_separator_found_only_by_the_second_pass(monkeypatch):
    img = cv2.imread(CROP)
    sep = find_separator(img, *FRAME, letterboxed=True)
    assert sep is not None and 0.2 < sep.frac < 0.35 and sep.thickness <= 2
    assert find_separator(img, *FRAME) is None                 # lobby/menus (no bars): first pass only
    monkeypatch.setattr(detector, "SMALL_PICTURE_H", 0)        # 1440p and bigger: first pass only, as before
    assert find_separator(img, *FRAME, letterboxed=True) is None


def test_letterboxed_banner_is_read():
    pytest.importorskip("onnxruntime")
    from dbdmapscout.catalog import Catalog
    from dbdmapscout.ocr import Recognizer
    reader = BannerReader(Recognizer(os.path.join(ROOT, "models", "ch_PP-OCRv4_rec_infer.onnx")), Catalog(ROOT))
    sep, res = reader.read(cv2.imread(CROP), *FRAME, letterboxed=True)
    assert sep is not None and res is not None
    assert res.best == ("badham-preschool", 1) and res.name_fit > -1


def test_letterbox_bars_measured_and_used_only_when_fresh():
    import numpy as np
    from dbdmapscout import layout
    frame = np.zeros((1359, 1718, 3), np.uint8)
    frame[251:1109] = 90                                      # intro picture, bars of 251/250 px
    frame[5:15, 0:40] = 255                                   # FPS counter in the bar does not end it
    assert detector.letterbox_rows(frame) == (251, 250)
    loading = np.zeros_like(frame)
    loading[194:1289] = 90                                    # uneven: no letterbox
    assert detector.letterbox_rows(loading) == (0, 0)
    assert detector.letterbox_rows(np.zeros_like(frame)) == (0, 0)
    m = (251, 250, 100.0, (1718, 1359))
    assert layout.vbars(m, 1718, 1359, 101.0) == (251, 250)
    assert layout.vbars(m, 1718, 1359, 100.0 + layout.VBAR_FRESH + 1) is None    # lobby: no new bars measured
    assert layout.vbars(m, 1720, 1359, 101.0) is None                          # other window size
    assert layout.vbars((251, 250, 100.0, (3440, 1440)), 3440, 1440, 101.0) is None   # ultrawide: side bars
    assert layout.vbars((60, 60, 100.0, (1718, 1359)), 1718, 1359, 101.0) is None    # too low for anything
    assert layout.fit_scale(400, 300, 800, 150) == 0.5 and layout.fit_scale(10, 10, 100, 100) == 1.0


def test_worker_keeps_the_smallest_bars_of_the_last_looks():
    import numpy as np
    from dbdmapscout.worker import DetectionWorker
    w = DetectionWorker.__new__(DetectionWorker)
    import collections
    from dbdmapscout import worker
    w._vbar_looks = collections.deque(maxlen=worker.VBAR_LOOKS)

    def look(bar):
        f = np.zeros((1359, 1718, 3), np.uint8)
        f[bar:1359 - bar] = 90
        return f
    w._note_vbars(look(251), 1718, 1359)
    assert w.vbars[:2] == (251, 251)
    w._note_vbars(look(198), 1718, 1359)                      # intro over: smaller bars apply at once
    assert w.vbars[:2] == (198, 198)
    dark = look(198)
    dark[198:320] = 0                                         # dark scene at the top edge for one look
    w._note_vbars(dark, 1718, 1359)
    assert w.vbars[0] == 198
    w._note_vbars(look(198), 1718, 1360)                      # resized window: start over
    assert len(w._vbar_looks) == 1


def test_empty_read_is_no_evidence():
    from dbdmapscout.detector import Accumulator, FrameResult
    acc = Accumulator()
    fr = FrameResult(scores={("the-game", 1): -10.0, ("coal-tower", 1): -60.0}, best=("the-game", 1),
                     name_text="", realm_text="", name_fit=-8.1, realm_fit=-20.0, ms=1.0)
    assert acc.add(fr) is None and acc.add(fr) is None and acc.good_frames == 0     # 1.45.0: "the-game" from nothing
    ok = FrameResult(scores={("the-game", 1): -1.0, ("coal-tower", 1): -60.0}, best=("the-game", 1),
                     name_text="THE GAME", realm_text="GIDEON MEAT PLANT", name_fit=-0.2, realm_fit=-0.5, ms=1.0)
    assert acc.add(ok) is not None
