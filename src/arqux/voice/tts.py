"""Local TTS engines → PipeWire playback.

Two engines behind one interface:

* ``PiperSpeaker``  — Piper ONNX voices (fast: RTF ~0.07, accents: es_ES/
  es_MX/es_AR catalog)
* ``KokoroSpeaker`` — Kokoro-82M ONNX (neutral latino Spanish, RTF ~1.2;
  supports blended voices for extra identities)

Playback: persistent raw-PCM ``pw-cat`` workers — to the default sink (1:1)
or ``VirtualSpeaker`` (meet mode), optionally mirroring to the default sink.
Text is spoken sentence-by-sentence (first sentence sounds after a single
short synthesis) and playback is interruptible — ``interrupt()`` kills
the active ``pw-play`` processes so a new turn can start instantly.
"""

from __future__ import annotations

import contextlib
import os
import queue
import re
import subprocess
import threading
from collections.abc import Iterable

import numpy as np

from .config import models_dir, sink_target, voice_path
from .metrics import LatencyRecorder

_SENTENCE_RE = re.compile(r"(?<=[.!?…:])\s+")


def split_sentences(text: str, max_len: int = 220,
                    merge_to: int = 110) -> list[str]:
    """Chunk text for speech: sentences, clause-split when too long, and
    short sentences merged up to ``merge_to`` chars (fewer synthesis calls
    = less per-call overhead = better real-time factor)."""
    parts = [p.strip() for p in _SENTENCE_RE.split(text.strip()) if p.strip()]
    # merge short adjacent sentences
    merged: list[str] = []
    for p in parts:
        if merged and len(merged[-1]) + len(p) + 1 <= merge_to:
            merged[-1] = f"{merged[-1]} {p}"
        else:
            merged.append(p)
    chunks: list[str] = []
    for p in merged:
        while len(p) > max_len:
            # prefer a clause boundary (, ; :) near the limit
            cut = max(p.rfind(",", 0, max_len), p.rfind(";", 0, max_len),
                      p.rfind(":", 0, max_len), p.rfind(" ", 0, max_len))
            cut = cut if cut > 40 else max_len
            head = p[:cut].strip()
            chunks.append(head + ("," if not head.endswith((",", ";", ":"))
                                  else ""))
            p = p[cut:].lstrip(",;: ").strip()
        if p:
            chunks.append(p)
    return chunks


class BaseSpeaker:
    """Sentence-streamed playback + interrupt machinery (engine-agnostic)."""

    engine = "base"

    def __init__(self, voice: str, length_scale: float = 1.0):
        self.voice_name = voice
        self._length_scale = length_scale  # >1 slower, <1 faster
        self._lock = threading.Lock()
        self._model_lock = threading.Lock()
        self._model = None
        self.latency = LatencyRecorder()
        self.tts_active = threading.Event()  # echo guard for monitor channel
        self._procs: set[subprocess.Popen] = set()
        self._procs_lock = threading.Lock()
        self._playback: dict[str, tuple[subprocess.Popen, int]] = {}
        self._playback_lock = threading.Lock()
        self._playback_errors: list[str] = []
        self._playback_started = False
        self._stream_stop = threading.Event()

    # -- engine API -------------------------------------------------

    def _load(self):
        raise NotImplementedError

    def synthesize(self, text: str) -> tuple[bytes, int]:
        """Return (s16 mono PCM bytes, sample_rate)."""
        raise NotImplementedError

    # -- shared behaviour -------------------------------------------

    def prewarm(self) -> dict:
        """Load the model eagerly (call from a background thread)."""
        import time
        t0 = time.monotonic()
        self._load()
        return {"engine": self.engine, "voice": self.voice_name,
                "ms": round((time.monotonic() - t0) * 1000)}

    def set_speed(self, factor: float) -> float:
        """Multiply speech length scale (>1 = slower). Clamped 0.6-2.0."""
        self._length_scale = min(2.0, max(0.6, self._length_scale * factor))
        return self._length_scale

    def interrupt(self) -> dict:
        """Kill any active playback immediately (barge-in support)."""
        self.latency.mark("interrupt")
        self.tts_active.clear()
        self._stream_stop.set()
        with self._playback_lock:
            self._playback.clear()
        with self._procs_lock:
            procs = list(self._procs)
            self._procs.clear()
        killed = 0
        for p in procs:
            with contextlib.suppress(Exception):
                p.kill()
            killed += 1
        return {"interrupted": killed}

    def say(self, text: str, targets: list[str | None] | None = None,
            mirror_default: bool = False) -> dict:
        """Speak text. Short replies are fully pre-synthesized before any
        sound (zero internal gaps — the "armed" mode); long replies stream
        with deep look-ahead so synthesis stays ahead of playback.
        ``targets`` are pw-play --target names; None = default sink.
        ``mirror_default`` also plays to the default sink."""
        sinks: list[str | None] = [
            target if target is not None else sink_target()
            for target in (targets or [None])
        ]
        if mirror_default and None not in sinks:
            sinks.append(None)
        chunks = split_sentences(text) or [text]
        self.latency.reset()
        self._playback_errors.clear()
        self._playback_started = False
        self.tts_active.set()
        self.latency.mark("tts_start")
        total = 0
        try:
            if self._is_short(text):
                prepared = []
                for chunk in chunks:
                    if not self.tts_active.is_set():
                        break
                    try:
                        prepared.append(self.synthesize(chunk))
                    except Exception:  # noqa: BLE001
                        continue
                for pcm, rate in prepared:
                    if not self.tts_active.is_set():
                        break
                    total += len(pcm)
                    self.latency.mark("first_tts")
                    self._play_all(pcm, rate, sinks)
            else:
                total = self._stream(chunks, sinks)
        finally:
            self._close_playback()
            self.latency.mark("tts_end")
            self.tts_active.clear()
        return {"spoken": total > 0 and self._playback_started
                and not self._playback_errors, "chars": len(text),
                "bytes": total, "targets": sinks, "chunks": len(chunks),
                "mode": "armed" if self._is_short(text) else "streamed",
                "playback_started": self._playback_started,
                "playback_errors": list(self._playback_errors)}

    def say_stream(self, fragments: Iterable[str],
                   targets: list[str | None] | None = None,
                   mirror_default: bool = False) -> dict:
        """Synthesize and play incremental text with bounded backpressure."""
        sinks: list[str | None] = [
            target if target is not None else sink_target()
            for target in (targets or [None])
        ]
        if mirror_default and None not in sinks:
            sinks.append(None)
        text_q: queue.Queue[str | None] = queue.Queue(maxsize=16)
        audio_q: queue.Queue[tuple[bytes, int] | None] = queue.Queue(maxsize=8)
        self.latency.reset()
        self._playback_errors.clear()
        self._playback_started = False
        self._stream_stop.clear()
        self.tts_active.set()
        self.latency.mark("tts_start")

        def put_bounded(q: queue.Queue, item: object) -> bool:
            while not self._stream_stop.is_set():
                try:
                    q.put(item, timeout=0.05)
                    return True
                except queue.Full:
                    continue
            return False

        def produce() -> None:
            try:
                for fragment in fragments:
                    if self._stream_stop.is_set():
                        break
                    for chunk in split_sentences(str(fragment)):
                        if not put_bounded(text_q, chunk):
                            return
            finally:
                put_bounded(text_q, None)

        def synthesize() -> None:
            while not self._stream_stop.is_set():
                try:
                    chunk = text_q.get(timeout=0.05)
                except queue.Empty:
                    continue
                if chunk is None:
                    put_bounded(audio_q, None)
                    return
                try:
                    item = self.synthesize(chunk)
                except Exception:  # noqa: BLE001
                    continue
                if not put_bounded(audio_q, item):
                    return

        producer = threading.Thread(target=produce, daemon=True)
        synthesizer = threading.Thread(target=synthesize, daemon=True)
        producer.start()
        synthesizer.start()
        total = 0
        try:
            while not self._stream_stop.is_set():
                try:
                    item = audio_q.get(timeout=0.05)
                except queue.Empty:
                    continue
                if item is None:
                    break
                pcm, rate = item
                total += len(pcm)
                self.latency.mark("first_tts")
                self._play_all(pcm, rate, sinks)
        finally:
            self._stream_stop.set()
            producer.join(timeout=0.5)
            synthesizer.join(timeout=0.5)
            self._close_playback()
            self.latency.mark("tts_end")
            self.tts_active.clear()
        return {"spoken": total > 0 and self._playback_started
                and not self._playback_errors, "bytes": total,
                "targets": sinks, "mode": "incremental",
                "playback_started": self._playback_started,
                "playback_errors": list(self._playback_errors)}

    # -- internals --------------------------------------------------

    @staticmethod
    def _is_short(text: str, max_chars: int = 150) -> bool:
        """Replies under ~10 s of speech are pre-synthesized fully."""
        return len(text) <= max_chars

    def _play_all(self, pcm: bytes, rate: int,
                  sinks: list[str | None]) -> None:
        threads = [threading.Thread(target=self._play,
                                    args=(pcm, rate, t), daemon=True)
                   for t in sinks]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    def _stream(self, chunks: list[str],
                sinks: list[str | None]) -> int:
        """Pre-arm a lead of chunks (no gaps while they play), then keep
        synthesizing the rest ahead of playback."""
        lead, rest, budget = [], [], 0
        for c in chunks:
            if budget < 110:
                lead.append(c)
                budget += len(c)
            else:
                rest.append(c)
        # short first chunk: a long opener is split so the first sound
        # comes fast (synthesis of the head only), remainder streams
        if lead and len(lead[0]) > 70:
            head = lead[0]
            cut = max(head.rfind(",", 0, 70), head.rfind(" ", 0, 70))
            cut = cut if cut > 30 else 70
            opener = head[:cut].strip()
            tail = head[cut:].lstrip(",;: ").strip()
            lead = [opener]
            if tail:
                rest.insert(0, tail)

        def synth_worker(queue_: queue.Queue) -> None:
            for chunk in rest:
                if not self.tts_active.is_set():
                    return
                try:
                    pcm, rate = self.synthesize(chunk)
                except Exception:  # noqa: BLE001
                    pcm, rate = b"", 22050
                queue_.put((chunk, pcm, rate))
            queue_.put(None)

        synth_q: queue.Queue = queue.Queue(maxsize=16)
        worker = threading.Thread(target=synth_worker, args=(synth_q,),
                                  daemon=True)
        total = 0
        # 1) arm the lead fully (zero gaps here)
        prepared = []
        for chunk in lead:
            if not self.tts_active.is_set():
                return total
            try:
                prepared.append(self.synthesize(chunk))
            except Exception:  # noqa: BLE001
                continue
        # 2) start the worker for the rest, play lead while it synthesizes
        worker.start()
        for pcm, rate in prepared:
            if not self.tts_active.is_set():
                return total
            total += len(pcm)
            self._play_all(pcm, rate, sinks)
        # 3) play the streamed remainder
        while True:
            item = synth_q.get()
            if item is None:
                break
            _chunk, pcm, rate = item
            if not pcm:
                continue
            total += len(pcm)
            self._play_all(pcm, rate, sinks)
            if not self.tts_active.is_set():
                break
        return total

    def _play(self, pcm: bytes, rate: int, target: str | None) -> None:
        self.latency.mark("first_audio")
        key = target or "__default__"
        with self._playback_lock:
            current = self._playback.get(key)
            if current is None or current[0].poll() is not None or current[1] != rate:
                if current is not None:
                    with contextlib.suppress(Exception):
                        current[0].kill()
                    with self._procs_lock:
                        self._procs.discard(current[0])
                cmd = ["pw-cat", "--playback", "--format", "s16",
                       "--rate", str(rate), "--channels", "1"]
                if target:
                    cmd += ["--target", target]
                cmd += ["-"]
                try:
                    proc = subprocess.Popen(
                        cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE, bufsize=0)
                except OSError as exc:
                    self._playback_errors.append(
                        f"pw-cat target={target or 'default'}: {exc!r}")
                    return
                self._playback[key] = (proc, rate)
                self._playback_started = True
                with self._procs_lock:
                    self._procs.add(proc)
            proc = self._playback[key][0]
        try:
            assert proc.stdin is not None
            proc.stdin.write(pcm)
            proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            self._playback_errors.append(
                f"pw-cat target={target or 'default'} write: {exc!r}")
            self._close_playback(key)

    def _close_playback(self, key: str | None = None) -> None:
        with self._playback_lock:
            if key is None:
                workers = list(self._playback.items())
                self._playback.clear()
            else:
                item = self._playback.pop(key, None)
                workers = [(key, item)] if item is not None else []
        for _name, item in workers:
            if item is None:
                continue
            proc, _rate = item
            with contextlib.suppress(Exception):
                if proc.stdin is not None:
                    proc.stdin.close()
            with contextlib.suppress(Exception):
                proc.wait(timeout=2)
            with contextlib.suppress(Exception):
                if proc.poll() is None:
                    proc.kill()
            with self._procs_lock:
                self._procs.discard(proc)


class PiperSpeaker(BaseSpeaker):
    """Piper ONNX voice engine."""

    engine = "piper"

    def _load(self):
        from piper import PiperVoice
        path = voice_path(self.voice_name)
        if not path.exists():
            raise FileNotFoundError(f"Piper voice not found: {path}")
        with self._model_lock:
            if self._model is None:
                self._model = PiperVoice.load(str(path))
            return self._model

    def synthesize(self, text: str) -> tuple[bytes, int]:
        voice = self._load()
        with self._lock:
            if self._length_scale != 1.0:
                from piper.config import SynthesisConfig
                cfg = SynthesisConfig(length_scale=self._length_scale)
                chunks = list(voice.synthesize(text, syn_config=cfg))
            else:
                chunks = list(voice.synthesize(text))
        pcm = b"".join(c.audio_int16_bytes for c in chunks)
        rate = chunks[0].sample_rate if chunks else 22050
        return pcm, rate


class KokoroSpeaker(BaseSpeaker):
    """Kokoro-82M ONNX engine — neutral latino Spanish."""

    engine = "kokoro"
    MODEL_FILE = "kokoro-v1.0.int8.onnx"
    VOICES_FILE = "kokoro-voices-v1.0-4id.bin"  # incl. em_blend_jarvis

    def _load(self):
        with self._model_lock:
            if self._model is not None:
                return self._model
            data = models_dir() / self.VOICES_FILE
            espeak = models_dir() / "espeak-ng-data"
            if espeak.is_dir():
                os.environ.setdefault("ESPEAK_NG_DATA", str(espeak))
            import onnxruntime as ort
            from kokoro_onnx import Kokoro

            so = ort.SessionOptions()
            so.intra_op_num_threads = 8
            so.graph_optimization_level = (
                ort.GraphOptimizationLevel.ORT_ENABLE_ALL)
            sess = ort.InferenceSession(str(models_dir() / self.MODEL_FILE),
                                        sess_options=so)
            self._model = Kokoro.from_session(sess, str(data))
            return self._model

    def synthesize(self, text: str) -> tuple[bytes, int]:
        k = self._load()
        with self._lock:
            samples, rate = k.create(
                text, voice=self.voice_name,
                speed=1.0 / max(self._length_scale, 1e-3), lang="es",
                sentence_pause=0.12, clause_pause=0.05)
        pcm = (samples * 32767.0).astype(np.int16).tobytes()
        return pcm, rate


Speaker = PiperSpeaker  # backward-compatible default


def make_speaker(engine_voice: tuple[str, str] | str,
                 length_scale: float = 1.0) -> BaseSpeaker:
    """Factory: ('kokoro', 'em_alex') → KokoroSpeaker; 'es_MX-…' → Piper."""
    if isinstance(engine_voice, str):
        return PiperSpeaker(engine_voice, length_scale)
    engine, voice = engine_voice
    cls = KokoroSpeaker if engine == "kokoro" else PiperSpeaker
    return cls(voice, length_scale)
