"""Runtime configuration for arqux-voice.

Model lookup order (first hit wins):
  1. $ARQUX_VOICE_MODELS
  2. <repo-root>/.voice/models   (dev layout)
  3. ~/.local/share/arqux/voice/models   (installed layout)
"""

from __future__ import annotations

import os
from pathlib import Path

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_FMT = "s16"

DEFAULT_WHISPER_MODEL = "small"
DEFAULT_LANG = "es"
DEFAULT_VOICE = "es_MX-claude-high"
DEFAULT_MENTION_PATTERNS = [r"\balfred\b"]
MEETINGS_DIR_ENV = "ARQUX_VOICE_MEETINGS"
# Input device selector. Empty/unset → follow the WirePlumber default
# source. Accepts a PipeWire node.name, node id, or a case-insensitive
# substring of the node description. A machine may expose several input
# devices (internal, DMIC, jack, Bluetooth); choosing one is a one-line
# config change, not a code change.
MIC_ENV = "ARQUX_VOICE_MIC"
SINK_ENV = "ARQUX_VOICE_SINK"
CAPTURE_CHUNK_ENV = "ARQUX_VOICE_CHUNK_MS"
ENDPOINT_ENV = "ARQUX_VOICE_ENDPOINT"
RSS_BUDGET_ENV = "ARQUX_VOICE_RSS_BUDGET_MB"
BARGE_GRACE_ENV = "ARQUX_VOICE_BARGE_GRACE_MS"
BARGE_FRAMES_ENV = "ARQUX_VOICE_BARGE_MIN_FRAMES"
BARGE_RMS_ENV = "ARQUX_VOICE_BARGE_MIN_RMS"


ENDPOINT_PROFILES: dict[str, dict[str, int]] = {
    "responsive": {"start_ms": 160, "end_ms": 450},
    "balanced": {"start_ms": 200, "end_ms": 650},
    "patient": {"start_ms": 240, "end_ms": 800},
}


def capture_chunk_samples() -> int:
    """Return a bounded PipeWire read size; default is 64 ms."""
    raw = os.environ.get(CAPTURE_CHUNK_ENV, "64")
    try:
        millis = int(raw)
    except ValueError:
        millis = 64
    if millis not in (32, 64, 128):
        millis = 64
    return SAMPLE_RATE * millis // 1000


def endpoint_settings() -> dict[str, int]:
    """Return a bounded endpointing profile; balanced preserves baseline."""
    profile = (os.environ.get(ENDPOINT_ENV) or "balanced").strip().lower()
    return dict(ENDPOINT_PROFILES.get(profile, ENDPOINT_PROFILES["balanced"]))


def memory_budget_mb() -> int:
    """Bound the process RSS target used by voice validation."""
    try:
        value = int(os.environ.get(RSS_BUDGET_ENV, "256"))
    except ValueError:
        value = 256
    return min(1024, max(128, value))


def mic_target() -> str | None:
    """Configured input-device selector ($ARQUX_VOICE_MIC) or None."""
    val = os.environ.get(MIC_ENV)
    return val.strip() if val and val.strip() else None


def sink_target() -> str | None:
    """Configured PipeWire playback target, or ``None`` for the default."""
    val = os.environ.get(SINK_ENV)
    return val.strip() if val and val.strip() else None


def barge_in_settings() -> dict[str, float | int]:
    """Return conservative, bounded audio barge-in settings."""
    try:
        grace = int(os.environ.get(BARGE_GRACE_ENV, "450"))
    except ValueError:
        grace = 450
    try:
        frames = int(os.environ.get(BARGE_FRAMES_ENV, "3"))
    except ValueError:
        frames = 3
    try:
        rms = float(os.environ.get(BARGE_RMS_ENV, "0.003"))
    except ValueError:
        rms = 0.003
    return {
        "grace_ms": min(2000, max(0, grace)),
        "min_frames": min(12, max(1, frames)),
        "min_rms": min(0.2, max(0.0, rms)),
    }


# Opt-in system-level capture recovery. Default OFF: the agent never
# restarts system services on its own. Setting it to "wireplumber" IS the
# authorization — the watchdog may then restart the user WirePlumber
# service when the microphone is stuck, the only known cure for the
# intermittent DMIC ACP6x hang.
AUTO_RECOVER_ENV = "ARQUX_VOICE_AUTO_RECOVER"


def auto_recover() -> str | None:
    """System recovery policy ($ARQUX_VOICE_AUTO_RECOVER) or None."""
    val = (os.environ.get(AUTO_RECOVER_ENV) or "").strip().lower()
    return val or None

# Per-identity voices (neutral latino Spanish via Kokoro) + speech pace
# (length_scale: >1 slower/graver, <1 faster/agile). Kokoro es voices:
# em_alex, em_santa (male), ef_dora (female) + em_blend_jarvis (blend of
# alex+santa — a 4th distinct timbre). Piper latino voices (es_MX/es_AR)
# remain available as fallback engine.
IDENTITY_VOICES: dict[str, tuple[str, str]] = {
    "alfred": ("kokoro", "em_blend_alfred"),
    "heimdall": ("kokoro", "em_santa"),
    "jarvis": ("kokoro", "em_blend_jarvis"),
    "seshat": ("kokoro", "ef_dora"),
}
IDENTITY_SPEED: dict[str, float] = {
    "alfred": 1.10,
    "heimdall": 1.05,
    "jarvis": 0.92,
    "seshat": 1.0,
}

# TTS engine preference. "fast" (default) uses Piper voices — RTF ~0.28,
# first word ~0.5-1 s; "quality" uses the Kokoro neutral-latino identity
# voices — richer timbre but RTF ~1-2 (measured 2.27 under load). A
# per-session `meeting_start(voice="kokoro:em_alex"|"es_MX-claude-high")`
# still overrides. Set with $ARQUX_VOICE_ENGINE.
ENGINE_ENV = "ARQUX_VOICE_ENGINE"
DEFAULT_ENGINE = "fast"
# Measured median F0: davefx 131 Hz, ald 146 Hz (male); claude 181 Hz,
# daniela 179 Hz (female). Identities are male except seshat.
FAST_VOICES: dict[str, str] = {
    "alfred": "es_ES-davefx-medium",
    "heimdall": "es_MX-ald-medium",
    "jarvis": "es_MX-ald-medium",
    "seshat": "es_AR-daniela-high",
}


def tts_engine() -> str:
    """Preferred TTS engine: 'fast' (Piper) or 'quality' (Kokoro)."""
    val = (os.environ.get(ENGINE_ENV) or DEFAULT_ENGINE).strip().lower()
    return val if val in ("fast", "quality") else DEFAULT_ENGINE


def identity_voice(agent: str) -> tuple[str, str]:
    """(engine, voice) for an agent, honoring $ARQUX_VOICE_ENGINE."""
    if tts_engine() == "quality":
        return IDENTITY_VOICES.get(agent, ("piper", DEFAULT_VOICE))
    return ("piper", FAST_VOICES.get(agent, DEFAULT_VOICE))


def _repo_models() -> Path:
    # src/arqux/voice/config.py -> parents[3] = repo root
    return Path(__file__).resolve().parents[3] / ".voice" / "models"


def _user_models() -> Path:
    return Path.home() / ".local" / "share" / "arqux" / "voice" / "models"


def models_dir() -> Path:
    env = os.environ.get("ARQUX_VOICE_MODELS")
    if env:
        return Path(env)
    for cand in (_repo_models(), _user_models()):
        if cand.is_dir() and any(cand.glob("*.onnx")):
            return cand
    return _user_models()  # default location even if empty


def voice_path(voice: str | None = None) -> Path:
    name = voice or os.environ.get("ARQUX_VOICE_TTS", DEFAULT_VOICE)
    return models_dir() / f"{name}.onnx"


def vad_model_path() -> Path:
    return models_dir() / "silero_vad.onnx"


def meetings_dir() -> Path:
    """Per-meeting transcript directory.

    Lookup order: $ARQUX_VOICE_MEETINGS > ~/workspace/meetings (when the
    workspace exists) > XDG data dir — portable beyond this machine.
    """
    env = os.environ.get(MEETINGS_DIR_ENV)
    if env:
        return Path(env)
    ws = Path.home() / "workspace"
    if ws.is_dir():
        return ws / "meetings"
    return Path.home() / ".local" / "share" / "arqux" / "voice" / "meetings"


def whisper_cached(model: str = DEFAULT_WHISPER_MODEL) -> bool:
    """True if the faster-whisper model is already in the HF cache —
    guards against a runtime download (local-only rule)."""
    try:
        from huggingface_hub import scan_cache_dir
    except ImportError:
        return False
    needle = model.replace("/", "--")
    try:
        for repo in scan_cache_dir().repos:
            if needle in repo.repo_id or repo.repo_id.endswith(model):
                return True
    except Exception:
        return False
    return False
