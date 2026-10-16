"""DbD Map Scout – map overlay for Dead by Daylight with OCR map detection."""
import os as _os

__version__ = "1.66.1"

# 1.64.7: onnxruntime (OCR) has Microsoft telemetry built in – also on Linux it sent events to
# mobile.events.data.microsoft.com (measured: 4 tries in 40 s). The map detection must not connect to the
# internet (CLAUDE.md), so it is switched off before onnxruntime is ever loaded. ocr.py also calls
# onnxruntime.disable_telemetry_events() (on Windows: its ETW events).
_os.environ["ORT_DISABLE_TELEMETRY"] = "1"
