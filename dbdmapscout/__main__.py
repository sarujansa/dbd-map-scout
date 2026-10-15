"""Start: python -m dbdmapscout [--simulate BILD|ORDNER] [--test BILD ...]"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import traceback

from . import i18n
from .i18n import _

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _setup_logging():
    logging.basicConfig(
        filename=os.path.join(ROOT, "dbdmapscout.log"), filemode="w", level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")


_mutex = None
ERROR_ACCESS_DENIED = 5
ERROR_ALREADY_EXISTS = 183


def _claim_mutex(name: str) -> bool:
    """True if no other copy holds the single-instance mutex. A copy running as administrator (autostart
    task, desktop shortcut) owns a mutex that a normal copy (start.bat double-clicked) may not open:
    CreateMutexW then fails with ERROR_ACCESS_DENIED instead of ERROR_ALREADY_EXISTS – another copy, too."""
    global _mutex
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    k32.CreateMutexW.restype = wintypes.HANDLE
    _mutex = k32.CreateMutexW(None, False, name)
    return ctypes.get_last_error() not in (ERROR_ALREADY_EXISTS, ERROR_ACCESS_DENIED)


def _message(text: str, error: bool = False):
    """A message box without a window of our own (Windows), else stderr."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, text, "DbD Map Scout", 0x10 if error else 0x40)
            return
        except Exception:
            pass
    print(text, file=sys.stderr)


def _single_instance() -> bool:
    """Only one running copy (a second one could not register the hotkeys)."""
    if sys.platform != "win32":
        return True
    from .restart import MUTEX_NAME
    if not _claim_mutex(MUTEX_NAME):
        _message(_("DbD Map Scout läuft bereits."))
        return False
    return True


def run_test(paths, languages):
    """Offline check: run the detector on screenshots and print what it reads."""
    import cv2
    import numpy as np
    from .catalog import Catalog
    from .detector import ROI, BannerReader
    from .ocr import Recognizer
    cat = Catalog(ROOT, languages)
    reader = BannerReader(Recognizer(os.path.join(ROOT, "models", "ch_PP-OCRv4_rec_infer.onnx")), cat)
    files = []
    for p in paths:
        if os.path.isdir(p):
            files += sorted(os.path.join(p, f) for f in os.listdir(p)
                            if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp")))
        else:
            files.append(p)
    for f in files:
        img = cv2.imdecode(np.fromfile(f, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            print(f"{f}: kann nicht gelesen werden")
            continue
        h, w = img.shape[:2]
        roi = img[int(ROI[1] * h):int(ROI[3] * h), int(ROI[0] * w):int(ROI[2] * w)]
        sep, res = reader.read(roi, w, h)
        if sep is None:
            print(f"{os.path.basename(f)}: kein Map-Banner gefunden")
        elif res is None:
            print(f"{os.path.basename(f)}: Banner gefunden, aber kein Text lesbar")
        else:
            m = cat.maps[res.best[0]]
            ok = "OK " if res.name_fit >= -9 else "?? "
            print(f"{os.path.basename(f)}: {ok}{m.label(res.best[1])}  (gelesen: '{res.name_text}' / "
                  f"'{res.realm_text}', Passung {res.name_fit:.1f}, {res.ms:.0f} ms)")


def main():
    ap = argparse.ArgumentParser(prog="dbdmapscout")
    ap.add_argument("--simulate", help="Screenshots statt Bildschirm verwenden (Datei oder Ordner)")
    ap.add_argument("--test", nargs="+", help="Nur testen: Screenshots auswerten und Ergebnis ausgeben")
    ap.add_argument("--lang", default="en,de", help="Sprachen für --test, z.B. en,de")
    ap.add_argument("--tray", action="store_true", help="im Infobereich starten (Autostart mit Windows)")
    ap.add_argument("--restart", action="store_true", help=argparse.SUPPRESS)   # helper of the update button
    ap.add_argument("--no-update", action="store_true", help=argparse.SUPPRESS)  # with --restart: plain restart
    args = ap.parse_args()

    if args.restart:
        from .restart import wait_and_start
        wait_and_start(ROOT, update=not args.no_update)
        return

    if args.test:
        run_test(args.test, [l.strip() for l in args.lang.split(",") if l.strip()])
        return

    from .appid import set_process_app_id
    set_process_app_id()                          # before the first window: own taskbar button and icon
    i18n.init_from_settings(os.path.join(ROOT, "settings.json"))
    if not _single_instance():
        return
    _setup_logging()
    from .capture import enable_dpi_awareness
    enable_dpi_awareness()
    try:
        from .app import App
        App(ROOT, simulate=args.simulate, start_in_tray=args.tray).run()
    except Exception:
        text = traceback.format_exc()
        logging.getLogger("dbdmapscout").error(text)
        _message(_("Start fehlgeschlagen:") + "\n\n" + text[-1500:], error=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
