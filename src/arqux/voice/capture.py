"""PCM capture sources via PipeWire tools.

``PcmSource`` streams raw s16 mono 16 kHz PCM from ``pw-cat --record``.
Target resolution:

* mic     -> default source (pw-cat auto follows WirePlumber default)
* monitor -> the monitor node of the default sink (found via ``pw-dump``)
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import threading
from collections.abc import Iterator

import numpy as np

from .config import CHANNELS, SAMPLE_FMT, SAMPLE_RATE, capture_chunk_samples

_BYTES_PER_SAMPLE = 2
_CHUNK = capture_chunk_samples()  # 64 ms by default; configurable 32/128 ms


def _pw_dump() -> list[dict]:
    out = subprocess.run(["pw-dump"], capture_output=True, timeout=10)
    return json.loads(out.stdout.decode())


def _default_node_name(kind: str) -> str | None:
    """Return node.name of the default sink/source via wpctl inspect."""
    import re
    try:
        out = subprocess.run(
            ["wpctl", "inspect", f"@DEFAULT_AUDIO_{kind.upper()}@"],
            capture_output=True, text=True, timeout=10)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    m = re.search(r'node\.name\s*=\s*"([^"]+)"', out.stdout)
    return m.group(1) if m else None


def default_sink_name() -> str | None:
    return _default_node_name("sink")


def default_source_name() -> str | None:
    return _default_node_name("source")


def monitor_source_name() -> str | None:
    """Name of the monitor node exposing the default sink's output."""
    sink = default_sink_name()
    if not sink:
        return None
    for obj in _pw_dump():
        if obj.get("type") != "PipeWire:Interface:Node":
            continue
        props = obj.get("info", {}).get("props", {})
        if (props.get("media.class") == "Audio/Source"
                and props.get("node.name") == sink):
            return props["node.name"]
    return sink  # PipeWire monitor shares the sink's node.name


def list_sources(probe_secs: float = 0.0) -> list[dict]:
    """Enumerate input (Audio/Source) nodes: id, name, description, default.

    With ``probe_secs > 0`` each node is briefly opened and measured, so a
    device can be chosen from live data instead of by guessing.
    """
    default = default_source_name()
    sources: list[dict] = []
    for obj in _pw_dump():
        if obj.get("type") != "PipeWire:Interface:Node":
            continue
        props = obj.get("info", {}).get("props", {})
        if props.get("media.class") != "Audio/Source":
            continue
        name = props.get("node.name")
        entry = {
            "id": obj.get("id"),
            "name": name,
            "description": props.get("node.description") or name,
            "default": name == default,
        }
        if probe_secs > 0 and name:
            entry["level"] = probe_level(name, probe_secs)
        sources.append(entry)
    return sources


def probe_level(target: str, secs: float = 0.5) -> dict:
    """Live RMS/peak of a source over ``secs`` seconds (post DC-block)."""
    src = PcmSource(target=target)
    src.start()
    frames = src.read(int(SAMPLE_RATE * secs), timeout=secs + 2.0)
    src.stop()
    if len(frames) == 0:
        return {"rms": 0.0, "peak": 0.0, "n": 0}
    return {"rms": round(float(np.sqrt((frames ** 2).mean())), 4),
            "peak": round(float(np.abs(frames).max()), 4),
            "n": int(len(frames))}


def resolve_source(selector: str | None) -> str | None:
    """Resolve a selector to a ``pw-cat --target`` value.

    Match order: exact node id, exact node.name, then a case-insensitive
    substring of node.name/description. Unmatched selectors pass through
    unchanged (assumed to already be a valid PipeWire target). ``None`` →
    ``None`` (follow the WirePlumber default source).
    """
    if not selector:
        return None
    sel = selector.strip()
    if not sel:
        return None
    sources = list_sources()
    for s in sources:
        if str(s["id"]) == sel or s["name"] == sel:
            return s["name"]
    low = sel.lower()
    for s in sources:
        if low in (s["name"] or "").lower() or low in (s["description"] or "").lower():
            return s["name"]
    return sel


def candidate_targets(selector: str | None = None) -> list[str | None]:
    """Ordered capture targets for a fallback chain.

    Order: explicit ``selector`` → current WirePlumber default → every other
    available source. ``None`` means "follow the default source", used as the
    last-resort candidate. Duplicates are dropped.
    """
    order: list[str | None] = []
    chosen = resolve_source(selector) if selector else None
    default = default_source_name()
    for cand in (chosen, default):
        if cand and cand not in order:
            order.append(cand)
    for s in list_sources():
        name = s["name"]
        if name and name not in order:
            order.append(name)
    if not order:
        order.append(None)
    return order


class PcmSource:
    """Blocking PCM reader over a ``pw-cat --record`` subprocess."""

    def __init__(self, target: str | None = None, rate: int = SAMPLE_RATE):
        self.rate = rate
        self.target = target
        self._cmd = ["pw-cat", "--record", "--format", SAMPLE_FMT,
                     "--rate", str(rate), "--channels", str(CHANNELS)]
        if target:
            self._cmd += ["--target", target]
        self._cmd += ["-"]
        self._proc: subprocess.Popen | None = None
        self._buf = bytearray()
        self._lock = threading.Lock()
        self._eof = threading.Event()
        # last-chunk health metrics (for the capture watchdog)
        self.last_dc = 0.0
        self.last_ac_rms = 0.0
        self.last_ac_peak = 0.0

    @classmethod
    def mic(cls, target: str | None = None) -> PcmSource:
        """Mic capture. ``target`` overrides ``$ARQUX_VOICE_MIC``; both
        accept a node.name, node id or description substring. ``None`` →
        the WirePlumber default source."""
        from .config import mic_target
        selector = target or mic_target()
        return cls(target=resolve_source(selector) if selector else None)

    @classmethod
    def monitor(cls) -> PcmSource:
        return cls(target=monitor_source_name())

    def start(self) -> None:
        if self._proc:
            return
        self._proc = subprocess.Popen(
            self._cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            bufsize=0)
        self._eof.clear()
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        assert self._proc and self._proc.stdout
        while True:
            data = self._proc.stdout.read(_CHUNK * _BYTES_PER_SAMPLE)
            if not data:
                self._eof.set()
                return
            with self._lock:
                self._buf += data

    def read(self, n_samples: int, timeout: float = 2.0) -> np.ndarray:
        """Read exactly ``n_samples`` int16 → float32 [-1, 1]; [] on EOF."""
        need = n_samples * _BYTES_PER_SAMPLE
        import time
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                if len(self._buf) >= need:
                    raw = bytes(self._buf[:need])
                    del self._buf[:need]
                    i16 = np.frombuffer(raw, dtype=np.int16)
                    frames = i16.astype(np.float32) / 32768.0
                    # metric: raw DC bias (before removal) for the watchdog
                    self.last_dc = float(frames.mean())
                    # DC-block: some DMIC/ALSA paths (e.g. ASUS ACP6x) emit a
                    # constant DC bias that suppresses Silero VAD. Removing the
                    # per-chunk mean (~8 Hz high-pass) restores VAD + STT.
                    frames = frames - self.last_dc
                    self.last_ac_rms = float(np.sqrt((frames ** 2).mean()))
                    self.last_ac_peak = (float(np.abs(frames).max())
                                         if len(frames) else 0.0)
                    return frames
            if self._eof.is_set() or time.monotonic() > deadline:
                return np.empty(0, dtype=np.float32)
            time.sleep(0.005)

    def stream(self, chunk: int = _CHUNK) -> Iterator[np.ndarray]:
        self.start()
        while not self._eof.is_set():
            frames = self.read(chunk)
            if len(frames):
                yield frames

    @property
    def alive(self) -> bool:
        """True while the capture subprocess runs and has not hit EOF."""
        return (self._proc is not None and self._proc.poll() is None
                and not self._eof.is_set())

    def stop(self) -> None:
        """Deterministic teardown: terminate → wait → kill, then verify the
        process is gone and mark EOF so consumer threads exit promptly."""
        proc = self._proc
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                with contextlib.suppress(subprocess.TimeoutExpired):
                    proc.wait(timeout=2)  # unreapable: nothing more to do
            except Exception:  # noqa: BLE001
                pass
            self._proc = None
        self._eof.set()
