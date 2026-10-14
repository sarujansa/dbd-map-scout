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
    sep = find_separator(img, *FRAME)
    assert sep is not None and 0.2 < sep.frac < 0.35 and sep.thickness <= 2
    monkeypatch.setattr(detector, "SMALL_PICTURE_H", 0)        # 1440p and bigger: first pass only, as before
    assert find_separator(img, *FRAME) is None


def test_letterboxed_banner_is_read():
    pytest.importorskip("onnxruntime")
    from dbdmapscout.catalog import Catalog
    from dbdmapscout.ocr import Recognizer
    reader = BannerReader(Recognizer(os.path.join(ROOT, "models", "ch_PP-OCRv4_rec_infer.onnx")), Catalog(ROOT))
    sep, res = reader.read(cv2.imread(CROP), *FRAME)
    assert sep is not None and res is not None
    assert res.best == ("badham-preschool", 1) and res.name_fit > -1
