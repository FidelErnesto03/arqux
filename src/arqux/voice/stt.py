"""Speech-to-text engines.

* ``Transcriber`` — faster-whisper (CTranslate2 int8, CPU)
* ``ParakeetTranscriber`` — NVIDIA Parakeet TDT 0.6B v3 int8 via onnx-asr.
  Measured on this machine (Spanish voice-domain corpus): WER 13.2% vs
  whisper-small 26.1%, RTF 0.09 vs 0.43.

``make_transcriber`` picks Parakeet when its model dir exists, else whisper.
"""

from __future__ import annotations

import threading
from pathlib import Path

import numpy as np

from .config import DEFAULT_LANG, DEFAULT_WHISPER_MODEL, models_dir


class Transcriber:
    """Lazy faster-whisper wrapper. Thread-safe single instance."""

    def __init__(self, model: str = DEFAULT_WHISPER_MODEL,
                 lang: str = DEFAULT_LANG, threads: int = 8):
        self.model_name = model
        self.lang = lang
        self.threads = threads
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self.model_name, device="cpu", compute_type="int8",
                cpu_threads=self.threads, num_workers=1)
        return self._model

    def prewarm(self) -> dict:
        """Load the model eagerly (call from a background thread)."""
        import time as _t
        t0 = _t.monotonic()
        self._load()
        return {"model": self.model_name,
                "ms": round((_t.monotonic() - t0) * 1000)}

    def transcribe(self, samples: np.ndarray,
                   lang: str | None = None) -> dict:
        """samples: float32 @16kHz mono → {text, duration, confidence}."""
        model = self._load()
        dur = len(samples) / 16000.0
        with self._lock:
            segs, info = model.transcribe(
                samples, language=lang or self.lang, beam_size=3,
                vad_filter=True, without_timestamps=True)
            segs = list(segs)
            text = " ".join(s.text.strip() for s in segs).strip()
        conf = (sum(s.avg_logprob for s in segs) / len(segs)
                if segs else 0.0)
        return {
            "text": text,
            "duration": round(dur, 2),
            "confidence": round(float(conf), 3),
            "lang": getattr(info, "language", lang or self.lang),
        }


class ParakeetTranscriber:
    """Parakeet TDT v3 int8 (onnx-asr) — faster and more accurate than
    whisper-small on Spanish, measured locally."""

    model_name = "parakeet-tdt-0.6b-v3"

    def __init__(self, path: Path | None = None, lang: str = DEFAULT_LANG,
                 threads: int = 8):
        self.path = path or models_dir() / "parakeet_asr"
        self.lang = lang
        self.threads = threads
        self._model = None
        self._lock = threading.Lock()

    @staticmethod
    def available(path: Path | None = None) -> bool:
        d = path or models_dir() / "parakeet_asr"
        return (d / "encoder-model.int8.onnx").exists() and \
               (d / "decoder_joint-model.int8.onnx").exists()

    def _load(self):
        if self._model is None:
            import onnx_asr
            import onnxruntime as ort

            so = ort.SessionOptions()
            so.intra_op_num_threads = self.threads
            self._model = onnx_asr.load_model(
                "nemo-parakeet-tdt-0.6b-v3", path=str(self.path),
                quantization="int8", sess_options=so)
        return self._model

    def prewarm(self) -> dict:
        import time as _t
        t0 = _t.monotonic()
        self._load()
        return {"model": self.model_name,
                "ms": round((_t.monotonic() - t0) * 1000)}

    def transcribe(self, samples: np.ndarray,
                   lang: str | None = None) -> dict:
        """samples: float32 @16kHz mono → {text, duration, confidence}."""
        model = self._load()
        dur = len(samples) / 16000.0
        with self._lock:
            text = model.recognize(samples, sample_rate=16000).strip()
        return {
            "text": text,
            "duration": round(dur, 2),
            "confidence": 0.0,  # onnx-asr exposes no logprob
            "lang": lang or self.lang,
        }


def make_transcriber(model: str = "auto", lang: str = DEFAULT_LANG):
    """'auto' → Parakeet when installed, else whisper-small; a whisper
    model name (small/medium/…) → whisper explicitly; 'parakeet' → Parakeet
    (falls back to whisper when absent)."""
    if model in ("auto", "parakeet") and ParakeetTranscriber.available():
        return ParakeetTranscriber(lang=lang)
    return Transcriber(
        model="small" if model in ("auto", "parakeet") else model, lang=lang)
