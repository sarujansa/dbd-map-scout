"""Map banner in a DBD window narrower than 16:9 (user screenshot 1718×1360, 1.44.0): the trial is letterboxed,
the picture only ~858 px high, the separator hairline comes out at grey ~55 – the first pass (> 105) misses it."""
import os

import cv2
import pytest

from fogscout import detector
from fogscout.detector import BannerReader, find_separator

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
    from fogscout.catalog import Catalog
    from fogscout.ocr import Recognizer
    reader = BannerReader(Recognizer(os.path.join(ROOT, "models", "ch_PP-OCRv4_rec_infer.onnx")), Catalog(ROOT))
    sep, res = reader.read(cv2.imread(CROP), *FRAME, letterboxed=True)
    assert sep is not None and res is not None
    assert res.best == ("badham-preschool", 1) and res.name_fit > -1


def test_letterbox_bars_measured_and_used_only_when_fresh():
    import numpy as np
    from fogscout import layout
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
    from fogscout.worker import DetectionWorker
    w = DetectionWorker.__new__(DetectionWorker)
    import collections
    from fogscout import worker
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
    from fogscout.detector import Accumulator, FrameResult
    acc = Accumulator()
    fr = FrameResult(scores={("the-game", 1): -10.0, ("coal-tower", 1): -60.0}, best=("the-game", 1),
                     name_text="", realm_text="", name_fit=-8.1, realm_fit=-20.0, ms=1.0)
    assert acc.add(fr) is None and acc.add(fr) is None and acc.good_frames == 0     # 1.45.0: "the-game" from nothing
    ok = FrameResult(scores={("the-game", 1): -1.0, ("coal-tower", 1): -60.0}, best=("the-game", 1),
                     name_text="THE GAME", realm_text="GIDEON MEAT PLANT", name_fit=-0.2, realm_fit=-0.5, ms=1.0)
    assert acc.add(ok) is not None


RPD = os.path.join(ROOT, "tests", "data", "banner", "letterbox_rpd_east.jpg")   # ROI of the 1714×1360 frame
RPD_FRAME, RPD_BARS = (1714, 1360), (251, 250)


def test_banner_without_a_visible_line_is_read_where_it_sits():
    """1.8.62 (user screenshot 1714×1360, RPD East Wing over a tiled floor): the hairline is grey ~95 on a floor of
    ~97 – no pass finds it. In a letterboxed small picture the name is read where the banner sits; it counts only
    when it fits a known name cleanly, so a frame without a banner stays nothing."""
    pytest.importorskip("onnxruntime")
    from fogscout.catalog import Catalog
    from fogscout.ocr import Recognizer
    img = cv2.imread(RPD)
    assert find_separator(img, *RPD_FRAME, letterboxed=True) is None
    reader = BannerReader(Recognizer(os.path.join(ROOT, "models", "ch_PP-OCRv4_rec_infer.onnx")), Catalog(ROOT))
    sep, res = reader.read(img, *RPD_FRAME, letterboxed=True, bars=RPD_BARS)
    assert sep is not None and res.best == ("rpd-east", 1) and res.name_fit > detector.ANCHOR_FIT
    assert reader.read(img, *RPD_FRAME, letterboxed=True) == (None, None)           # mid-match: no bars given
    assert reader.read(img, *RPD_FRAME, bars=RPD_BARS) == (None, None)              # not letterboxed: never
    blurred = img.copy()
    blurred[250:360] = cv2.GaussianBlur(blurred[250:360], (0, 0), 25)               # the same frame, no banner
    assert reader.read(blurred, *RPD_FRAME, letterboxed=True, bars=RPD_BARS) == (None, None)
    # the anchor holds for the older Badham screenshot (1718×1359) too, and never for 1080p and bigger
    s = detector.anchored_separator(*FRAME, RPD_BARS)
    assert abs(s.y - find_separator(cv2.imread(CROP), *FRAME, letterboxed=True).y) <= 3
    assert reader.score_lines(detector.locate_text(cv2.imread(CROP), s)).best == ("badham-preschool", 1)
    assert detector.anchored_separator(2560, 1440, (100, 100)) is None
    assert detector.anchored_separator(1714, 1360, None) is None


def test_the_worker_reads_a_letterboxed_banner_with_no_map_on_display(tmp_path, monkeypatch):
    """1.8.65 (user's diagnosis 1718×1360, 1.8.62: "Letzte Banner: keine"): the bars above/below were measured only
    while a map was on display (round-end looks) – before a round's banner there is none, so the worker never took
    the picture for letterboxed and the banner's fixed spot never ran. The real worker loop, in simulation, with the
    RPD frame rebuilt around its ROI crop (bars 251/250 px) and no map on display."""
    pytest.importorskip("onnxruntime")
    import queue
    import time
    import numpy as np
    from fogscout import config, worker
    from fogscout.catalog import Catalog
    w, h = RPD_FRAME
    frame = np.zeros((h, w, 3), np.uint8)
    frame[RPD_BARS[0]:h - RPD_BARS[1]] = 60                       # the picture between the bars
    crop = cv2.imread(RPD)
    y0, x0 = int(detector.ROI[1] * h), int(detector.ROI[0] * w)
    frame[y0:y0 + crop.shape[0], x0:x0 + crop.shape[1]] = crop
    assert detector.letterbox_rows(frame) == RPD_BARS

    class Source:
        def __init__(self, *_a, **_k):
            pass

        def current(self):
            return frame

    monkeypatch.setattr(worker, "ImageSource", Source)
    events = queue.Queue()
    wk = worker.DetectionWorker(ROOT, config.Settings(str(tmp_path / "settings.json")), Catalog(ROOT, ["en"]),
                                events, simulate=str(tmp_path))
    assert not wk.map_on_screen
    wk.start()
    found = None
    try:
        deadline = time.time() + 60                                # generous: shared CI runners
        while found is None and time.time() < deadline:
            try:
                ev = events.get(timeout=0.5)
            except queue.Empty:
                continue
            if ev.kind == "detected":
                found = ev.data
    finally:
        wk.stop()
        wk.join(timeout=10)
    assert found is not None and found["map_id"] == "rpd-east"
    assert wk._letterboxed(w, h)
