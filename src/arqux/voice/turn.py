"""Smart end-of-turn detection via pipecat smart-turn v3 (ONNX, CPU).

Classifies a closed VAD segment as a complete or incomplete conversational
turn by listening to the raw waveform (whisper-tiny encoder backbone, 8M
params, int8 ONNX ~8 MB, ~12 ms inference on CPU). BSD-2-Clause model by
pipecat-ai; log-mel features vendored from the Apache-2.0 transformers
implementation (via pipecat's numpy port).

If the model file is missing the pipeline degrades to a fixed-silence EOT.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from .config import models_dir

_MODEL_FILE = "smart-turn-v3.2-cpu.onnx"
_WINDOW = 16000 * 8  # 8 s @ 16 kHz
_NORM_EPS = 1e-7

# --- vendored Whisper log-mel (Apache-2.0, via pipecat _whisper_features) ---

_N_FFT = 400
_HOP = 160
_N_MELS = 80
_SR = 16000
_MEL_FLOOR = 1e-10


def _hertz_to_mel_slaney(freq: np.ndarray) -> np.ndarray:
    min_log_hertz = 1000.0
    min_log_mel = 15.0
    logstep = 27.0 / np.log(6.4)
    freq = np.atleast_1d(np.asarray(freq, dtype=np.float64))
    mels = 3.0 * freq / 200.0
    log_region = freq >= min_log_hertz
    mels[log_region] = min_log_mel + np.log(freq[log_region] / min_log_hertz) * logstep
    return mels


def _mel_to_hertz_slaney(mels: np.ndarray) -> np.ndarray:
    min_log_hertz = 1000.0
    min_log_mel = 15.0
    logstep = np.log(6.4) / 27.0
    mels = np.atleast_1d(np.asarray(mels, dtype=np.float64))
    freq = 200.0 * mels / 3.0
    log_region = mels >= min_log_mel
    freq[log_region] = min_log_hertz * np.exp(logstep * (mels[log_region] - min_log_mel))
    return freq


def _mel_filterbank() -> np.ndarray:
    mel_min = float(_hertz_to_mel_slaney(np.array([0.0]))[0])
    mel_max = float(_hertz_to_mel_slaney(np.array([_SR / 2.0]))[0])
    mel_freqs = np.linspace(mel_min, mel_max, _N_MELS + 2)
    filter_freqs = _mel_to_hertz_slaney(mel_freqs)
    fft_freqs = np.linspace(0, _SR // 2, _N_FFT // 2 + 1)
    filter_diff = np.diff(filter_freqs)
    slopes = np.expand_dims(filter_freqs, 0) - np.expand_dims(fft_freqs, 1)
    down = -slopes[:, :-2] / filter_diff[:-1]
    up = slopes[:, 2:] / filter_diff[1:]
    fb = np.maximum(np.zeros(1), np.minimum(down, up))
    enorm = 2.0 / (filter_freqs[2:_N_MELS + 2] - filter_freqs[:_N_MELS])
    return fb * np.expand_dims(enorm, 0)


_HANN = np.hanning(_N_FFT + 1)[:-1]
_MELS = _mel_filterbank()


def whisper_log_mel(audio: np.ndarray) -> np.ndarray:
    """Whisper-style log-mel features, shape (80, 800), input padded to 8 s."""
    x = np.asarray(audio, dtype=np.float32)
    if x.size < _WINDOW:
        x = np.pad(x, (0, _WINDOW - x.size))
    elif x.size > _WINDOW:
        x = x[:_WINDOW]
    x = (x - x.mean()) / np.sqrt(x.var() + _NORM_EPS)
    pad = _N_FFT // 2
    padded = np.pad(x.astype(np.float64), (pad, pad), mode="reflect")
    windows = sliding_window_view(padded, _N_FFT)[::_HOP]
    spec = np.fft.rfft(windows * _HANN.astype(np.float64), axis=-1)
    mag = (np.abs(spec) ** 2).T
    mel = np.maximum(_MEL_FLOOR, _MELS.T @ mag)
    log_spec = np.log10(mel)[:, :-1]
    log_spec = np.maximum(log_spec, log_spec.max() - 8.0)
    return ((log_spec + 4.0) / 4.0).astype(np.float32)


# --- classifier ---


class SmartTurn:
    """Lazy ONNX end-of-turn classifier. Missing model → unavailable."""

    def __init__(self, model: Path | None = None, threads: int = 1):
        self.path = model or models_dir() / _MODEL_FILE
        self.threads = threads
        self._session = None
        self._lock = threading.Lock()

    def available(self) -> bool:
        return self.path.exists()

    def _load(self):
        if self._session is None:
            import onnxruntime as ort

            so = ort.SessionOptions()
            so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            so.inter_op_num_threads = 1
            so.intra_op_num_threads = self.threads
            so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self._session = ort.InferenceSession(
                str(self.path), sess_options=so)
        return self._session

    def prewarm(self) -> dict:
        """Load Smart Turn before the first completed utterance."""
        started = time.monotonic()
        if not self.available():
            return {"available": False, "ms": 0}
        with self._lock:
            self._load()
        return {"available": True,
                "ms": round((time.monotonic() - started) * 1000)}

    def predict(self, audio: np.ndarray) -> dict:
        """audio: float32 mono @16 kHz → {complete, prob}."""
        if len(audio) > _WINDOW:
            audio = audio[-_WINDOW:]
        elif len(audio) < _WINDOW:
            audio = np.pad(audio, (_WINDOW - len(audio), 0))
        feats = whisper_log_mel(audio)
        with self._lock:
            out = self._load().run(None, {"input_features": feats[None]})
        prob = float(np.asarray(out[0]).reshape(-1)[0])
        return {"complete": prob > 0.5, "prob": round(prob, 4)}
