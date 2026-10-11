"""arqux voice-doctor — environment check for the voice extension."""

from __future__ import annotations

import shutil
import subprocess
import sys

from .config import DEFAULT_WHISPER_MODEL, models_dir, vad_model_path, voice_path, whisper_cached


def _check(name: str, ok: bool, detail: str) -> dict:
    return {"check": name, "ok": ok, "detail": detail}


def run_checks() -> list[dict]:
    checks = []
    # binaries
    for tool in ("pw-cat", "pw-play", "pw-cli", "pw-link", "pw-dump"):
        checks.append(_check(f"bin:{tool}",
                             shutil.which(tool) is not None,
                             shutil.which(tool) or "not found"))
    # pipewire service
    try:
        out = subprocess.run(
            ["systemctl", "--user", "is-active", "pipewire"],
            capture_output=True, timeout=5).stdout.decode().strip()
        checks.append(_check("service:pipewire", out == "active", out))
    except Exception as exc:  # noqa: BLE001
        checks.append(_check("service:pipewire", False, repr(exc)))
    # python deps
    for mod in ("faster_whisper", "onnxruntime", "piper"):
        try:
            __import__(mod)
            checks.append(_check(f"dep:{mod}", True, "import ok"))
        except ImportError as exc:
            checks.append(_check(f"dep:{mod}", False, str(exc)))
    # models
    checks.append(_check("model:vad", vad_model_path().exists(),
                         str(vad_model_path())))
    vp = voice_path()
    checks.append(_check("model:tts", vp.exists(), str(vp)))
    checks.append(_check("models_dir", models_dir().is_dir(),
                         str(models_dir())))
    # whisper cache — prevents a runtime download (local-only rule)
    checks.append(_check("model:whisper_cache",
                         whisper_cached(DEFAULT_WHISPER_MODEL),
                         f"faster-whisper '{DEFAULT_WHISPER_MODEL}' in HF cache"))
    # Parakeet STT (preferred engine when present)
    from .stt import ParakeetTranscriber
    checks.append(_check("model:parakeet", ParakeetTranscriber.available(),
                         "parakeet-tdt-0.6b-v3 int8 (WER 13.2% vs "
                         "whisper-small 26.1%, RTF 0.09)"
                         if ParakeetTranscriber.available()
                         else "missing — falling back to whisper"))
    # smart-turn EOT model (optional — degrades to fixed silence)
    from .turn import SmartTurn
    st = SmartTurn()
    checks.append(_check("model:smart_turn", st.available(),
                         str(st.path) if st.available()
                         else "missing — EOT falls back to fixed silence"))
    # audio probe: 0.5 s of mic audio
    try:
        import numpy as np

        from .capture import PcmSource
        src = PcmSource.mic()
        src.start()
        frames = src.read(8000, timeout=2.0)
        src.stop()
        ok = len(frames) > 0
        rms = float(np.sqrt(np.mean(frames ** 2))) if ok else 0.0
        checks.append(_check("probe:mic", ok,
                             f"{len(frames)} samples rms={rms:.4f}"))
    except Exception as exc:  # noqa: BLE001
        checks.append(_check("probe:mic", False, repr(exc)))
    # input devices — a machine may expose several (internal, DMIC, jack,
    # Bluetooth); enumeration makes the choice a simple config change.
    try:
        from .capture import list_sources
        srcs = list_sources()
        checks.append(_check("sources:count", len(srcs) > 0,
                             f"{len(srcs)} input device(s)"))
    except Exception as exc:  # noqa: BLE001
        checks.append(_check("sources:count", False, repr(exc)))
    return checks


def run() -> None:
    checks = run_checks()
    fails = 0
    for c in checks:
        mark = "PASS" if c["ok"] else "FAIL"
        if not c["ok"]:
            fails += 1
        print(f"[{mark}] {c['check']:22} {c['detail']}")
    try:
        from .capture import list_sources
        srcs = list_sources()
        if srcs:
            print("\nInput devices — choose with $ARQUX_VOICE_MIC or "
                  "meeting_start(mic=...):")
            for s in srcs:
                mark = "*" if s["default"] else " "
                print(f"  [{mark}] id={s['id']:<3} {s['name']}")
                print(f"        {s['description']}")
    except Exception as exc:  # noqa: BLE001
        print(f"\n(input devices unavailable: {exc!r})")
    print(f"\n{fails} failure(s)" if fails else "\nall checks PASS")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    run()
