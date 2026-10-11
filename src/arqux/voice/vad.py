"""Voice activity detection: Silero VAD (ONNX) with RMS fallback.

``VadSegmenter`` turns a PCM stream into utterance segments using a
speech/silence hysteresis. Silero runs at 16 kHz on 512-sample windows;
no torch required — plain onnxruntime.
"""

from __future__ import annotations

import collections
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import numpy as np

from .config import SAMPLE_RATE, endpoint_settings, vad_model_path

_FRAME = 512  # silero window @16kHz (32 ms)


class SileroVad:
    """Minimal ONNX wrapper for silero_vad.onnx (v5 layout)."""

    _sessions: dict[str, object] = {}
    _sessions_lock = threading.Lock()

    def __init__(self, model: Path | None = None):
        import onnxruntime as ort
        path = model or vad_model_path()
        cache_key = str(path.resolve())
        with self._sessions_lock:
            self._sess = self._sessions.get(cache_key)
            if self._sess is None:
                self._sess = ort.InferenceSession(
                    str(path), providers=["CPUExecutionProvider"])
                self._sessions[cache_key] = self._sess
        ins = {i.name: i for i in self._sess.get_inputs()}
        self._in_audio = "input" if "input" in ins else next(iter(ins))
        self._in_state = "state" if "state" in ins else None
        self._in_sr = "sr" if "sr" in ins else None
        outs = {o.name: o for o in self._sess.get_outputs()}
        self._out_prob = "output" if "output" in outs else next(iter(outs))
        self._out_state = "stateN" if "stateN" in outs else None
        self._state = np.zeros((2, 1, 128), dtype=np.float32)

    def reset(self) -> None:
        self._state = np.zeros((2, 1, 128), dtype=np.float32)

    def prob(self, frame: np.ndarray) -> float:
        feeds = {self._in_audio: frame[None, :].astype(np.float32)}
        if self._in_state:
            feeds[self._in_state] = self._state
        if self._in_sr:
            feeds[self._in_sr] = np.array(SAMPLE_RATE, dtype=np.int64)
        out = self._sess.run(None, feeds)
        prob = float(np.asarray(out[0]).ravel()[0])
        if self._out_state:
            idx = [o.name for o in self._sess.get_outputs()].index(self._out_state)
            self._state = out[idx]
        return prob


class VadSegmenter:
    """Stream → utterances. Emits (samples, t_start, t_end) on segment end."""

    def __init__(
        self,
        threshold: float = 0.35,
        start_ms: int | None = None,
        end_ms: int | None = None,
        min_seg_s: float = 0.4,
        max_seg_s: float = 90.0,
        pre_ms: int = 300,
        model: Path | None = None,
    ):
        settings = endpoint_settings()
        start_ms = settings["start_ms"] if start_ms is None else start_ms
        end_ms = settings["end_ms"] if end_ms is None else end_ms
        try:
            self._vad = SileroVad(model)
        except Exception:
            self._vad = None  # RMS fallback
        self.thr = threshold
        self.start_frames = max(1, start_ms // 32)
        self.end_frames = max(1, end_ms // 32)
        self.min_frames = int(min_seg_s * SAMPLE_RATE / _FRAME)
        self.max_frames = int(max_seg_s * SAMPLE_RATE / _FRAME)
        self._pre = collections.deque(
            maxlen=max(1, pre_ms // 32))
        self._reset()

    def _reset(self) -> None:
        self._speech = False
        self._hit = 0
        self._miss = 0
        self._seg: list[np.ndarray] = []
        self._t0 = 0.0

    @staticmethod
    def prewarm(model: Path | None = None) -> dict:
        """Load the shared Silero inference session before first capture."""
        started = time.monotonic()
        try:
            SileroVad(model)
            return {"available": True,
                    "ms": round((time.monotonic() - started) * 1000)}
        except Exception as exc:  # noqa: BLE001
            return {"available": False, "error": repr(exc),
                    "ms": round((time.monotonic() - started) * 1000)}

    def _score(self, frame: np.ndarray) -> float:
        if self._vad is not None:
            return self._vad.prob(frame)
        rms = float(np.sqrt(np.mean(frame ** 2))) if len(frame) else 0.0
        return min(1.0, rms * 40.0)  # rough RMS→prob mapping

    def feed(self, frames: np.ndarray) -> tuple[np.ndarray, float, float] | None:
        """Feed a 512-sample frame; returns utterance on segment end."""
        out = None
        if self._score(frames) > self.thr:
            self._hit += 1
            self._miss = 0
            if not self._speech and self._hit >= self.start_frames:
                self._speech = True
                self._t0 = time.monotonic()
                self._seg = list(self._pre) + self._seg
            if self._speech:
                self._seg.append(frames)
        else:
            self._miss += 1
            self._hit = 0
            if self._speech:
                self._seg.append(frames)
                if (self._miss >= self.end_frames
                        or len(self._seg) >= self.max_frames):
                    out = self._flush()
            else:
                self._pre.append(frames)
        return out

    def _flush(self) -> tuple[np.ndarray, float, float] | None:
        if len(self._seg) < self.min_frames:
            self._reset()
            return None
        audio = np.concatenate(self._seg)
        dur = len(audio) / SAMPLE_RATE
        t0, t1 = self._t0, time.monotonic()
        self._reset()
        if self._vad is not None:
            self._vad.reset()
        return audio, t0, t1 if dur else time.monotonic()

    def flush(self) -> tuple[np.ndarray, float, float] | None:
        """Force-close an open segment (on shutdown)."""
        if self._speech:
            return self._flush()
        return None

    # -- accessors for speculative transcription --------------------

    @property
    def speech_active(self) -> bool:
        return self._speech

    @property
    def silence_frames(self) -> int:
        return self._miss

    def current_audio(self) -> np.ndarray | None:
        """Audio accumulated for the open segment (None if none)."""
        return np.concatenate(self._seg) if self._seg else None


def segment_stream(
    frames_iter: Iterator[np.ndarray],
    segmenter: VadSegmenter | None = None,
    on_frame: Callable | None = None,
) -> Iterator[tuple[np.ndarray, float, float]]:
    """Yield utterances from a PCM frame iterator."""
    seg = segmenter or VadSegmenter()
    for frames in frames_iter:
        # split arbitrary chunks into 512-sample frames
        for off in range(0, len(frames) - _FRAME + 1, _FRAME):
            f = frames[off:off + _FRAME]
            if on_frame:
                on_frame(f)
            out = seg.feed(f)
            if out:
                yield out
