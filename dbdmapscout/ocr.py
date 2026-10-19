"""Text-line recognition (PP-OCRv4 via ONNX Runtime) and lexicon scoring.

Instead of turning the network output into a string and fuzzy-matching that
string afterwards, every known map / realm name is scored directly against the
network's per-frame character probabilities with the CTC forward algorithm.
The result is P(name | image) for each candidate, which

* uses all the evidence (a half-sure "I" still counts),
* cleanly separates "COAL TOWER" from "COAL TOWER II",
* is independent of case, accents, spaces and punctuation (these are folded
  into the CTC blank symbol).
"""
from __future__ import annotations

import math
import os
import threading
import unicodedata

import cv2
import numpy as np

from .textnorm import ALPHABET, fold

try:
    import onnxruntime as ort
    try:
        ort.disable_telemetry_events()      # no usage events (Windows ETW)
    except Exception:
        pass
except ImportError:  # pragma: no cover - reported to the user by the app
    ort = None

REC_HEIGHT = 48
N_GROUPS = len(ALPHABET) + 2          # 0 = blank/ignorable, 1..36 = A-Z0-9, 37 = other
JUNK = N_GROUPS - 1
_GROUP_OF = {c: i + 1 for i, c in enumerate(ALPHABET)}

# Characters the network likes to emit for strokes of an upper-case font.
_VISUAL = {"l": "I", "|": "I", "!": "I", "¡": "I", "0": "O", "1": "I", "5": "S"}


def _char_group(ch: str) -> int:
    if ch in ("<blank>", " "):
        return 0
    if ch in _VISUAL:
        return _GROUP_OF[_VISUAL[ch]]
    f = fold(ch)
    if len(f) == 1:
        return _GROUP_OF[f]
    if f == "":
        # punctuation, symbols, spaces of all kinds -> treat like blank
        cat = unicodedata.category(ch[0]) if ch else "Zs"
        if cat[0] in ("P", "Z", "S", "C"):
            return 0
    return JUNK


class Recognizer:
    """Thin wrapper around the PP-OCRv4 recognition model."""

    def __init__(self, model_path: str, threads: int = 2):
        if ort is None:
            raise RuntimeError("onnxruntime ist nicht installiert")
        so = ort.SessionOptions()
        so.intra_op_num_threads = max(1, int(threads))
        so.inter_op_num_threads = 1
        so.log_severity_level = 3
        so.add_session_config_entry("session.intra_op.allow_spinning", "0")   # 1.8.38: no busy wait after a run
        self.session = ort.InferenceSession(model_path, so, providers=["CPUExecutionProvider"])
        meta = self.session.get_modelmeta().custom_metadata_map
        chars = meta.get("character", "").splitlines()
        if not chars:
            keys = os.path.join(os.path.dirname(model_path), "ppocr_keys_v1.txt")
            with open(keys, encoding="utf-8") as fh:
                chars = [ln.rstrip("\r\n") for ln in fh]
        self.chars = ["<blank>"] + chars + [" "]
        self.input_name = self.session.get_inputs()[0].name
        groups = np.array([_char_group(c) for c in self.chars], dtype=np.int64)
        self.group_matrix = np.zeros((len(self.chars), N_GROUPS), dtype=np.float32)
        self.group_matrix[np.arange(len(self.chars)), groups] = 1.0
        self._lock = threading.Lock()

    @staticmethod
    def _prepare(bgr: np.ndarray) -> np.ndarray:
        h, w = bgr.shape[:2]
        new_w = max(16, int(math.ceil(REC_HEIGHT * w / max(1, h))))
        interp = cv2.INTER_AREA if h > REC_HEIGHT else cv2.INTER_CUBIC
        img = cv2.resize(bgr, (new_w, REC_HEIGHT), interpolation=interp).astype(np.float32)
        img = (img.transpose(2, 0, 1) / 255.0 - 0.5) / 0.5
        width = max(new_w, 320)
        out = np.zeros((3, REC_HEIGHT, width), np.float32)
        out[:, :, :new_w] = img
        return out

    def probs(self, bgr: np.ndarray) -> np.ndarray:
        """Per-frame class probabilities, shape (T, C)."""
        if bgr is None or bgr.size == 0:
            return np.zeros((0, len(self.chars)), np.float32)
        if bgr.ndim == 2:
            bgr = cv2.cvtColor(bgr, cv2.COLOR_GRAY2BGR)
        x = self._prepare(bgr)[None]
        with self._lock:
            out = self.session.run(None, {self.input_name: x})[0][0]
        return out

    def groups(self, probs: np.ndarray) -> np.ndarray:
        """Collapse the ~6600 classes into blank + A-Z0-9 + other. Shape (T, 38)."""
        g = probs @ self.group_matrix
        return np.clip(g, 1e-9, 1.0)

    def text(self, probs: np.ndarray) -> str:
        """Greedy decoding, only used for logs / the debug view."""
        if len(probs) == 0:
            return ""
        idx = probs.argmax(1)
        res, prev = [], -1
        for i in idx:
            if i != prev and i != 0:
                res.append(self.chars[i])
            prev = i
        return "".join(res).strip()


def best_path_logp(groups: np.ndarray) -> float:
    """log-probability of the single most likely frame labelling (upper bound)."""
    if len(groups) == 0:
        return 0.0
    return float(np.log(groups.max(1)).sum())


class LexiconScorer:
    """Vectorised CTC forward pass for a fixed list of folded strings."""

    def __init__(self, strings):
        self.strings = list(dict.fromkeys(s for s in strings if s))
        self.index = {s: i for i, s in enumerate(self.strings)}
        n = len(self.strings)
        smax = 2 * max((len(s) for s in self.strings), default=1) + 1
        pad = N_GROUPS  # extra all-zero column
        z = np.full((n, smax), pad, dtype=np.int64)
        skip = np.zeros((n, smax), dtype=bool)
        self.last = np.zeros(n, dtype=np.int64)
        self.min_frames = np.zeros(n, dtype=np.int64)
        for i, s in enumerate(self.strings):
            lab = [_GROUP_OF[c] for c in s]
            ext = [0]
            for c in lab:
                ext += [c, 0]
            z[i, :len(ext)] = ext
            for k in range(2, len(ext)):
                if ext[k] != 0 and ext[k] != ext[k - 2]:
                    skip[i, k] = True
            self.last[i] = len(ext) - 1
            self.min_frames[i] = len(lab) + sum(1 for a, b in zip(lab, lab[1:]) if a == b)
        self.z = z
        self.skip = skip.astype(np.float64)
        self.smax = smax

    def score(self, groups: np.ndarray) -> np.ndarray:
        """log P(string | frames) for every string (−inf if impossible)."""
        n = len(self.strings)
        T = len(groups)
        out = np.full(n, -np.inf)
        if n == 0 or T == 0:
            return out
        g = np.concatenate([groups.astype(np.float64), np.zeros((T, 1))], axis=1)
        z = self.z
        e0 = g[0][z]
        alpha = np.zeros((n, self.smax))
        alpha[:, 0] = e0[:, 0]
        alpha[:, 1] = e0[:, 1]
        logscale = np.zeros(n)
        s = alpha.sum(1, keepdims=True)
        s[s <= 0] = 1e-300
        alpha /= s
        logscale += np.log(s[:, 0])
        for t in range(1, T):
            a1 = np.zeros_like(alpha)
            a1[:, 1:] = alpha[:, :-1]
            a2 = np.zeros_like(alpha)
            a2[:, 2:] = alpha[:, :-2]
            alpha = (alpha + a1 + a2 * self.skip) * g[t][z]
            s = alpha.sum(1, keepdims=True)
            s[s <= 0] = 1e-300
            alpha /= s
            logscale += np.log(s[:, 0])
        rows = np.arange(n)
        final = alpha[rows, self.last] + alpha[rows, self.last - 1]
        with np.errstate(divide="ignore"):
            out = logscale + np.log(final)
        out[self.min_frames > T] = -np.inf
        return out
