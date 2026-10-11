"""Smoke tests for arqux.voice — no live microphone required.

TTS -> WAV -> VAD segmenter -> STT round-trip validates the whole
pipeline deterministically. Mic/monitor capture is covered by
voice-doctor's live probe instead.
"""

import wave
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("faster_whisper")
pytest.importorskip("onnxruntime")
pytest.importorskip("piper")

from arqux.voice.config import vad_model_path, voice_path  # noqa: E402
from arqux.voice.gate import MentionGate  # noqa: E402
from arqux.voice.stt import Transcriber  # noqa: E402
from arqux.voice.vad import segment_stream  # noqa: E402

PHRASE = "Alfred esto es una prueba de voz local"


def _synth_wav(tmp_path: Path) -> np.ndarray:
    """Synthesize PHRASE with Piper -> float32 @16k for STT/VAD."""
    from piper import PiperVoice
    voice = PiperVoice.load(str(voice_path()))
    chunks = list(voice.synthesize(PHRASE))
    pcm = np.frombuffer(
        b"".join(c.audio_int16_bytes for c in chunks), dtype=np.int16)
    rate = chunks[0].sample_rate
    wav = tmp_path / "utt.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.astype(np.int16).tobytes())
    # resample 22050 -> 16000 (linear, sufficient for test)
    audio = pcm.astype(np.float32) / 32768.0
    ratio = 16000 / rate
    idx = (np.arange(int(len(audio) * ratio)) / ratio).astype(int)
    return audio[idx]


@pytest.mark.skipif(not voice_path().exists(), reason="no piper voice")
def test_tts_synthesizes(tmp_path):
    audio = _synth_wav(tmp_path)
    assert len(audio) > 16000 * 0.5  # at least 0.5 s


@pytest.mark.skipif(not vad_model_path().exists(), reason="no silero model")
def test_vad_segments_speech(tmp_path):
    audio = _synth_wav(tmp_path)
    pad = np.zeros(16000, dtype=np.float32)  # 1 s silence each side
    stream = np.concatenate([pad, audio, pad])
    segs = list(segment_stream(iter([stream])))
    assert len(segs) >= 1
    assert segs[0][0].shape[0] > 16000 * 0.4


@pytest.mark.skipif(not voice_path().exists(), reason="no piper voice")
def test_stt_roundtrip(tmp_path):
    audio = _synth_wav(tmp_path)
    t = Transcriber(model="small", lang="es")
    res = t.transcribe(audio)
    assert "prueba" in res["text"].lower()
    assert res["duration"] > 0.3


def test_mention_gate():
    g = MentionGate(patterns=[r"\balfred\b"])
    assert g.check("Alfred qué opinas")["addressed"]
    assert g.check("esto no menciona a nadie")["addressed"] is False
    g.set_mode("always")
    assert g.check("cualquier cosa")["addressed"]


def test_voice_commands_routing(tmp_path, monkeypatch):
    """Pipeline voice commands: suspend, resume, redact, cancel, speed."""
    import arqux.voice.meeting as meeting_mod
    import arqux.voice.transcript as transcript_mod
    monkeypatch.setattr(transcript_mod, "meetings_dir", lambda: tmp_path)
    m = meeting_mod.Meeting(name="cmd-test", mode="solo")
    # suspend / resume
    assert m._route_command("Alfred, suspende la escucha") is True
    assert m.listening_state() == "wake"
    assert m._route_command("reanuda la escucha") is False  # wake path, not router
    m.resume_listening()
    assert m.listening_state() == "on"
    # speed
    assert m._route_command("Alfred, más despacio") is True
    assert m.speaker._length_scale > 1.0
    assert m._route_command("Alfred, más rápido") is True
    # cancel pending
    m._queue.put({"x": 1})
    assert m._route_command("cancela lo pendiente") is True
    assert m._queue.qsize() == 0
    # non-command text passes through
    assert m._route_command("hola buenos días qué tal") is False
    # redact
    m.tx.append("mic", "secreto uno")
    m.tx.append("agent", "respuesta secreta dos")
    n = m.tx.redact_last(2)
    assert n == 2
    content = m.tx.path.read_text(encoding="utf-8")
    assert "[redactado]" in content and "secreto" not in content.split("---")[-1]
    # hard off
    assert m._route_command("apaga el micrófono") is True
    assert m.listening_state() == "off"


def test_silent_mode_routing(tmp_path, monkeypatch):
    """Passive listen mode: notes only, never replies."""
    import arqux.voice.meeting as meeting_mod
    import arqux.voice.transcript as transcript_mod
    monkeypatch.setattr(transcript_mod, "meetings_dir", lambda: tmp_path)
    m = meeting_mod.Meeting(name="silent-test", mode="solo")
    assert m.listening_state() == "on"
    assert m._route_command("Alfred, escucha en silencio") is True
    assert m._silent is True
    assert m.listening_state() == "silent"
    assert m._route_command("ya puedes responder") is True
    assert m._silent is False
    assert m.listening_state() == "on"
    # no false positives on normal speech
    assert m._route_command("te escucho perfecto gracias") is False


def test_turn_queue_is_bounded_and_keeps_freshest(tmp_path, monkeypatch):
    import arqux.voice.meeting as meeting_mod
    import arqux.voice.transcript as transcript_mod

    monkeypatch.setattr(transcript_mod, "meetings_dir", lambda: tmp_path)
    m = meeting_mod.Meeting(name="queue-test", mode="solo")
    for index in range(10):
        m._enqueue_turn({"index": index})
    assert m._queue.qsize() == 8
    assert m._dropped_turns == 2
    assert m.listen(timeout=0.1)["index"] == 2


def test_speaker_prewarm_retains_model():
    """Prewarm must prevent a second model load on the next synthesis."""
    from arqux.voice.tts import BaseSpeaker

    class DummySpeaker(BaseSpeaker):
        engine = "dummy"

        def __init__(self):
            super().__init__("dummy")
            self.loads = 0

        def _load(self):
            with self._model_lock:
                if self._model is None:
                    self.loads += 1
                    self._model = object()
                return self._model

        def synthesize(self, text):
            self._load()
            return b"pcm", 16000

    speaker = DummySpeaker()
    speaker.prewarm()
    speaker.synthesize("hola")
    speaker.synthesize("otra frase")
    assert speaker.loads == 1


def test_latency_recorder_is_content_free():
    from arqux.voice.metrics import LatencyRecorder

    r = LatencyRecorder("session-1")
    r.mark("speech_end", 10.0)
    r.mark("first_audio", 10.25)
    r.mark("llm_start", 10.05)
    r.mark("first_token", 10.15)
    r.mark("first_tts", 10.20)
    result = r.summary()
    assert result["session_id"] == "session-1"
    assert result["durations"]["turn_to_first_audio_ms"] == 250.0
    assert result["durations"]["llm_ms"] == 100.0
    assert result["durations"]["tts_ms"] == 50.0
    assert "text" not in result and "audio" not in result


def test_capture_chunk_is_bounded(monkeypatch):
    from arqux.voice.config import capture_chunk_samples

    monkeypatch.setenv("ARQUX_VOICE_CHUNK_MS", "32")
    assert capture_chunk_samples() == 512
    monkeypatch.setenv("ARQUX_VOICE_CHUNK_MS", "999")
    assert capture_chunk_samples() == 1024


def test_endpoint_profiles_are_bounded(monkeypatch):
    from arqux.voice.config import endpoint_settings

    monkeypatch.setenv("ARQUX_VOICE_ENDPOINT", "responsive")
    assert endpoint_settings() == {"start_ms": 160, "end_ms": 450}
    monkeypatch.setenv("ARQUX_VOICE_ENDPOINT", "unknown")
    assert endpoint_settings() == {"start_ms": 200, "end_ms": 650}


def test_barge_in_settings_are_bounded(monkeypatch):
    from arqux.voice.config import barge_in_settings

    monkeypatch.setenv("ARQUX_VOICE_BARGE_GRACE_MS", "99999")
    monkeypatch.setenv("ARQUX_VOICE_BARGE_MIN_FRAMES", "0")
    monkeypatch.setenv("ARQUX_VOICE_BARGE_MIN_RMS", "-1")
    assert barge_in_settings() == {
        "grace_ms": 2000, "min_frames": 1, "min_rms": 0.0,
    }


def test_sink_target_is_explicit_when_configured(monkeypatch):
    from arqux.voice.config import sink_target

    monkeypatch.setenv(
        "ARQUX_VOICE_SINK",
        "alsa_output.pci-0000_04_00.6.HiFi__hw_Generic_1__sink",
    )
    assert sink_target().endswith("__sink")


def test_memory_budget_is_bounded(monkeypatch):
    from arqux.voice.config import memory_budget_mb

    monkeypatch.setenv("ARQUX_VOICE_RSS_BUDGET_MB", "256")
    assert memory_budget_mb() == 256
    monkeypatch.setenv("ARQUX_VOICE_RSS_BUDGET_MB", "1")
    assert memory_budget_mb() == 128


def test_audio_barge_in_interrupts_without_stt(monkeypatch, tmp_path):
    import time
    from types import SimpleNamespace

    import arqux.voice.meeting as meeting_mod
    import arqux.voice.transcript as transcript_mod

    monkeypatch.setattr(transcript_mod, "meetings_dir", lambda: tmp_path)
    m = meeting_mod.Meeting(name="barge-test", mode="solo")
    calls = []
    m.speaker.tts_active.set()
    m._last_agent_say_ts = time.monotonic() - m._barge_in_grace_s - 0.01
    monkeypatch.setattr(m.speaker, "interrupt",
                        lambda: calls.append("interrupt") or {})
    active = SimpleNamespace(speech_active=True)
    source = SimpleNamespace(last_ac_rms=0.02)
    assert m._handle_audio_barge_in(
        meeting_mod.CHANNEL_MIC, active, source) is False
    assert m._handle_audio_barge_in(
        meeting_mod.CHANNEL_MIC, active, source) is False
    assert m._handle_audio_barge_in(
        meeting_mod.CHANNEL_MIC, active, source) is True
    assert calls == ["interrupt"]
    assert m._barge_in_events == 1
    assert m._handle_audio_barge_in(meeting_mod.CHANNEL_MIC, active) is False


def test_audio_barge_in_waits_for_grace_and_consecutive_frames(
        monkeypatch, tmp_path):
    import time
    from types import SimpleNamespace

    import arqux.voice.meeting as meeting_mod
    import arqux.voice.transcript as transcript_mod

    monkeypatch.setattr(transcript_mod, "meetings_dir", lambda: tmp_path)
    m = meeting_mod.Meeting(name="barge-policy-test", mode="solo")
    m._last_agent_say_ts = time.monotonic()
    m.speaker.tts_active.set()
    active = SimpleNamespace(speech_active=True)
    source = SimpleNamespace(last_ac_rms=0.02)
    assert m._handle_audio_barge_in(
        meeting_mod.CHANNEL_MIC, active, source) is False
    m._last_agent_say_ts -= m._barge_in_grace_s + 0.01
    assert m._handle_audio_barge_in(
        meeting_mod.CHANNEL_MIC, active, source) is False
    assert m._handle_audio_barge_in(
        meeting_mod.CHANNEL_MIC, active, source) is False
    assert m._handle_audio_barge_in(
        meeting_mod.CHANNEL_MIC, active, source) is True


def test_speech_session_rejects_replay_reorder_and_foreign_owner():
    from arqux.voice.session import SpeechSession, StreamRejected

    s = SpeechSession("voice-1", "alfred", max_fragments=2)
    base = {"session_id": "voice-1", "stream_id": "reply-1",
            "sequence": 1, "text": "hola"}
    assert s.accept(base, owner="alfred")["accepted"] is True
    with pytest.raises(StreamRejected, match="expected sequence"):
        s.accept({**base, "sequence": 1}, owner="alfred")
    with pytest.raises(StreamRejected, match="owner"):
        s.accept({**base, "sequence": 2}, owner="other")
    assert s.drain() == "hola"


def test_speech_session_is_bounded_and_interruptible():
    from arqux.voice.session import SpeechSession, StreamRejected

    s = SpeechSession("voice-1", "alfred", max_fragments=1, max_bytes=4)
    s.accept({"session_id": "voice-1", "stream_id": "reply",
              "sequence": 1, "text": "hola"}, owner="alfred")
    with pytest.raises(StreamRejected, match="buffer limit"):
        s.accept({"session_id": "voice-1", "stream_id": "reply",
                  "sequence": 2, "text": "x"}, owner="alfred")
    s.cancel()
    assert s.status()["interrupted"] is True


def test_playback_reuses_one_pipewire_worker(monkeypatch):
    from io import BytesIO

    import arqux.voice.tts as tts_mod

    class FakeProc:
        def __init__(self, cmd):
            self.cmd = cmd
            self.stdin = BytesIO()
            self.killed = False

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

        def kill(self):
            self.killed = True

    procs = []

    def fake_popen(cmd, **kwargs):
        proc = FakeProc(cmd)
        procs.append(proc)
        return proc

    monkeypatch.setattr(tts_mod.subprocess, "Popen", fake_popen)
    speaker = tts_mod.BaseSpeaker("dummy")
    for _ in range(100):
        speaker._play(b"x", 16000, "VirtualSpeaker")
    assert len(procs) == 1
    assert procs[0].stdin.getvalue() == b"x" * 100
    speaker.interrupt()
    assert procs[0].killed is True


def test_incremental_tts_starts_before_stream_closes(monkeypatch):
    from arqux.voice.tts import BaseSpeaker

    class DummySpeaker(BaseSpeaker):
        def synthesize(self, text):
            return text.encode(), 16000

    speaker = DummySpeaker("dummy")
    played = []
    monkeypatch.setattr(speaker, "_play_all",
                        lambda pcm, rate, sinks: played.append(pcm))
    result = speaker.say_stream(iter(["uno", "dos", "tres"]))
    assert result["mode"] == "incremental"
    assert played == [b"uno", b"dos", b"tres"]


def test_meeting_incremental_api_preserves_legacy(monkeypatch, tmp_path):
    import arqux.voice.meeting as meeting_mod
    import arqux.voice.transcript as transcript_mod

    monkeypatch.setattr(transcript_mod, "meetings_dir", lambda: tmp_path)
    m = meeting_mod.Meeting(name="stream-test", mode="solo")
    monkeypatch.setattr(m.speaker, "say_stream",
                        lambda fragments, **kwargs: {
                            "spoken": True, "mode": "incremental",
                            "fragments": list(fragments)})
    out = m.say_incremental({"session_id": "s1", "stream_id": "r1",
                             "sequence": 1, "text": "hola", "final": True})
    assert out["spoken"] is True
    assert out["fragments"] == ["hola"]
    assert m._speech_sessions == {}


def test_meeting_incremental_rolls_back_to_legacy(monkeypatch, tmp_path):
    import arqux.voice.meeting as meeting_mod
    import arqux.voice.transcript as transcript_mod

    monkeypatch.setattr(transcript_mod, "meetings_dir", lambda: tmp_path)
    m = meeting_mod.Meeting(name="rollback-test", mode="solo")
    monkeypatch.setattr(m.speaker, "say_stream",
                        lambda *args, **kwargs: (_ for _ in ()).throw(
                            RuntimeError("stream failed")))
    monkeypatch.setattr(m.speaker, "say",
                        lambda *args, **kwargs: {"spoken": True,
                                                 "mode": "legacy"})
    out = m.say_incremental({"session_id": "s1", "stream_id": "r1",
                             "sequence": 1, "text": "fallback", "final": True})
    assert out["stream_fallback"] == "legacy"
    assert out["mode"] == "legacy"
    assert m._speech_sessions == {}


def test_meet_incremental_keeps_virtualspeaker_target(monkeypatch, tmp_path):
    import arqux.voice.meeting as meeting_mod
    import arqux.voice.transcript as transcript_mod

    monkeypatch.setattr(transcript_mod, "meetings_dir", lambda: tmp_path)
    m = meeting_mod.Meeting(name="meet-stream-test", mode="meet")
    seen = {}

    def fake_stream(fragments, **kwargs):
        seen.update(kwargs)
        return {"spoken": True, "mode": "incremental"}

    monkeypatch.setattr(m.speaker, "say_stream", fake_stream)
    out = m.say_incremental({"session_id": "s1", "stream_id": "r1",
                             "sequence": 1, "text": "hola", "final": True})
    assert out["spoken"] is True
    assert seen == {"targets": ["VirtualSpeaker"], "mirror_default": True}
