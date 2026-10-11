"""Meeting orchestrator: audio threads -> transcript -> addressed queue.

Modes:
  * ``solo`` — 1:1 voice with the Architect: mic only, gate=always,
    TTS to default sink.
  * ``meet`` — inside a call on this machine: captures mic + monitor of the
    default sink, TTS to VirtualSpeaker (-> VirtualMic -> Meet) mirrored to
    the default sink, gate=mention.
"""

from __future__ import annotations

import collections
import contextlib
import queue
import re
import subprocess
import threading
import time
import unicodedata
import uuid

import numpy as np

from .capture import PcmSource, candidate_targets
from .config import barge_in_settings
from .gate import MentionGate
from .metrics import LatencyRecorder
from .mixer import VirtualMic
from .session import SpeechSession, StreamRejected
from .stt import Transcriber, make_transcriber
from .transcript import TranscriptWriter
from .turn import SmartTurn
from .vad import VadSegmenter

CHANNEL_MIC = "mic"
CHANNEL_MONITOR = "monitor"

# Capture health (T-1.22): the capture is a monitored resource — the session
# must never listen silently to a dead microphone.
_MIC_DEAD_AC = 0.0006      # near-digital-silence AC floor (DC-blocked)
_MIC_DEAD_CHECKS = 4       # ~8 s sustained below floor → treat as dead
_MIC_MAX_RECOVERIES = 3    # reopen/fallback attempts before giving up
_MIC_REFRESH_S = 90.0      # no voice for this long → preventive reopen
_MIC_ESCALATE_S = 180.0    # still no voice → opt-in system recovery
_SYSTEM_RECOVERY_COOLDOWN = 300.0  # min seconds between WirePlumber restarts

_WAKE_RE = re.compile(
    r"\b(alfred|alfredo)?\s*(re[ae]?nud\w*|continu\w*|sigue|sigamos)"
    r"(\s+(la\s+)?escucha)?\b")
_BARGE_RE = re.compile(
    r"\b(alfred|alfredo)\b.*\b(para|silencio|detente|alto)\b")
_SUSPEND_RE = re.compile(r"\b(susp\w*|paus\w*|pare\w*?\s+la)\s+(\w+\s+)?escucha\b")
_HARDOFF_RE = re.compile(r"\bapag\w*\s+(\w+\s+)?(microfono|micro|mic)\b")
_REDACT_RE = re.compile(r"\bborr\w*\s+(lo\s+)?ultimo\b")
_CANCEL_RE = re.compile(r"\bcancel\w*\s+(lo\s+)?pendiente\b")
_SILENT_ON_RE = re.compile(
    r"\b(escuch\w*|qued\w*te?)\s+(en\s+)?silencio\b"
    r"|\bmodo\s+silencio\b|\bsolo\s+escuch\w*\b")
_SILENT_OFF_RE = re.compile(
    r"\b(ya\s+)?(puedes|puede|podés)\s+responder\w*\b"
    r"|\bsal\w*\s+del\s+silencio\b|\bresponde\w*\s+(otra\s+vez|de\s+nuevo)\b")
_VOLUP_RE = re.compile(r"\b(alfred|alfredo)\b.*\b(sub[ei]|aumenta)\w*.*\bvolumen\b")
_VOLDN_RE = re.compile(r"\b(alfred|alfredo)\b.*\b(baja|reduce|disminui)\w*.*\bvolumen\b")
_SLOWER_RE = re.compile(r"\b(alfred|alfredo)\b.*\b(mas despacio|despacio|lento)\b")
_FASTER_RE = re.compile(r"\b(alfred|alfredo)\b.*\b(mas rapido|rapido|deprisa)\b")


def _norm(text: str) -> str:
    s = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


class Meeting:
    """One active meeting/voice session."""

    def __init__(self, name: str, mode: str = "solo", agent: str = "alfred",
                 lang: str = "es", announce: bool | None = None,
                 mention_patterns: list[str] | None = None,
                 whisper_model: str = "auto", voice: str | None = None,
                 mic: str | None = None, session_id: str | None = None,
                 arqx_context: dict[str, str] | None = None):
        assert mode in ("solo", "meet")
        self.name = name
        self.mode = mode
        self.agent = agent
        self.session_id = session_id or f"voice-{uuid.uuid4().hex}"
        self.arqx_context = dict(arqx_context or {})
        # input device selector (node.name/id/description); None → default
        self.mic = mic
        # Transcription notice defaults to ON inside real calls (third
        # parties present); stays opt-in for the 1:1 mode.
        self.announce = announce if announce is not None else mode == "meet"
        self.tx = TranscriptWriter(
            name, mode, agent=agent, lang=lang, announce=self.announce,
            session_id=self.session_id, arqx_context=self.arqx_context)
        self.gate = MentionGate(
            patterns=mention_patterns,
            mode="always" if mode == "solo" else "mention")
        self.stt = make_transcriber(whisper_model, lang)
        # per-identity voice: agent drives the TTS engine+voice unless
        # overridden — voice accepts "engine:voice" (kokoro:em_alex) or a
        # bare piper voice name; None = identity mapping
        from .config import IDENTITY_SPEED, identity_voice
        from .tts import make_speaker
        if voice and ":" in voice:
            engine, vname = voice.split(":", 1)
        elif voice:
            engine, vname = "piper", voice
        else:
            engine, vname = identity_voice(agent)
        self.speaker = make_speaker(
            (engine, vname), IDENTITY_SPEED.get(agent, 1.0))
        self.mixer = VirtualMic() if mode == "meet" else None
        self.turn = SmartTurn()
        # A voice turn is only useful while it is fresh. Bound the handoff
        # queue so a slow MCP/agent caller cannot replay stale conversation.
        self._queue: queue.Queue = queue.Queue(maxsize=8)
        self._dropped_turns = 0
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._sources: list[PcmSource] = []
        self._agent_turns = 0
        self._prewarm: dict = {}
        self._suspended = False   # soft: wake-listen only, nothing stored
        self._hard_off = False    # real: capture processes killed
        self._silent = False      # passive: transcribe/notes, never reply
        self._wake_stt: Transcriber | None = None
        self._speech_sessions: dict[str, SpeechSession] = {}
        self._speech_sessions_lock = threading.Lock()
        self._recent_agent: collections.deque = collections.deque(maxlen=6)
        self.latency = LatencyRecorder(name)
        self._last_agent_say_ts = 0.0
        self._barge_in_active = False
        self._barge_in_events = 0
        self._barge_in_frames = 0
        barge = barge_in_settings()
        self._barge_in_grace_s = float(barge["grace_ms"]) / 1000.0
        self._barge_in_min_frames = int(barge["min_frames"])
        self._barge_in_min_rms = float(barge["min_rms"])
        self._started = time.monotonic()
        # capture health / resilience (T-1.22, T-1.23)
        self._mic_source: PcmSource | None = None
        self._mic_target: str | None = None
        self._mic_device: str | None = mic
        self._candidates: list[str | None] = []
        self._cand_idx = 0
        self._recoveries = 0
        self._mic_state = "ok"
        self._low_checks = 0
        self._last_refresh_ts = time.monotonic()
        self._last_system_recovery_ts = 0.0
        self._health_lock = threading.Lock()
        _now = time.monotonic()
        self._health: dict = {"ac_rms": 0.0, "dc": 0.0, "vad_fires": 0,
                              "last_frame_ts": _now, "last_voice_ts": _now}
        self._watchdog: threading.Thread | None = None

    # ---------- lifecycle ----------

    def start(self) -> dict:
        info = {"meeting": self.name, "mode": self.mode,
                "transcript": str(self.tx.path), "agent": self.agent}
        self._candidates = candidate_targets(self.mic)
        self._cand_idx = 0
        self._open_mic(self._candidates[0])
        info["mic"] = self._mic_device
        if self.mode == "meet":
            mon = PcmSource.monitor()
            self._sources.append(mon)
            self._spawn(mon, CHANNEL_MONITOR)
            if self.mixer:
                info["virtual_mic"] = self.mixer.provision()
        if self.announce:
            self.say("Esta reunión se está transcribiendo localmente.",
                     _transcribe=False)
        self.tx.append("system", f"Sesión iniciada — modo {self.mode}.")
        threading.Thread(target=self._prewarm_models, daemon=True).start()
        self._watchdog = threading.Thread(target=self._watchdog_loop,
                                          daemon=True)
        self._watchdog.start()
        info["mic_health"] = self.mic_health()
        return info

    # ---------- capture health & resilience (T-1.22 / T-1.23) ----------

    def _open_mic(self, target: str | None) -> None:
        """Open the mic on ``target`` and (re)spawn its channel thread."""
        mic = PcmSource.mic(target=target)
        self._mic_source = mic
        self._mic_target = mic.target
        self._mic_device = mic.target or "default"
        self._sources.append(mic)
        self._spawn(mic, CHANNEL_MIC)
        with self._health_lock:
            self._health["ac_rms"] = 0.0
            self._health["last_frame_ts"] = time.monotonic()
            self._health["vad_fires"] = 0
        self._low_checks = 0
        self._last_refresh_ts = time.monotonic()
        self._mic_state = "ok"

    def _update_mic_health(self, source: PcmSource,
                           seg: VadSegmenter) -> None:
        with self._health_lock:
            h = self._health
            h["ac_rms"] = 0.7 * h["ac_rms"] + 0.3 * source.last_ac_rms
            h["dc"] = source.last_dc
            h["last_frame_ts"] = time.monotonic()
            if seg.speech_active:
                h["vad_fires"] += 1
                h["last_voice_ts"] = time.monotonic()

    def _watchdog_loop(self) -> None:
        while not self._stop.wait(2.0):
            with contextlib.suppress(Exception):
                self._check_mic_health()

    def _check_mic_health(self) -> None:
        if self._hard_off or self._stop.is_set():
            return
        src = self._mic_source
        now = time.monotonic()
        with self._health_lock:
            ac = self._health["ac_rms"]
            since_frame = now - self._health["last_frame_ts"]
            voice_age = now - self._health["last_voice_ts"]
        if not (src and src.alive) and since_frame > 3.0:
            self._recover_mic("captura caída")
            return
        if ac < _MIC_DEAD_AC and since_frame < 3.0:
            self._low_checks += 1
            if self._low_checks >= _MIC_DEAD_CHECKS:
                self._recover_mic("silencio digital sostenido")
            return
        self._low_checks = 0
        if self.listening_state() != "on" or not (src and src.alive):
            return
        # Escalation ladder when no voice has been detected for a long time:
        # (1) preventive reopen; (2) opt-in system recovery (WirePlumber).
        from .config import auto_recover
        if (auto_recover() == "wireplumber" and voice_age > _MIC_ESCALATE_S
                and now - self._last_system_recovery_ts
                > _SYSTEM_RECOVERY_COOLDOWN):
            self._system_recover("sin voz detectada en el periodo")
            return
        if (voice_age > _MIC_REFRESH_S
                and now - self._last_refresh_ts > _MIC_REFRESH_S):
            self._refresh_mic()

    def _refresh_mic(self) -> None:
        old = self._mic_source
        if old:
            old.stop()
            self._sources = [s for s in self._sources if s is not old]
        self._open_mic(self._mic_target)
        self.tx.append("system",
                       "Micrófono refrescado preventivamente (sin voz "
                       "detectada en el periodo).")

    def _system_recover(self, reason: str) -> None:
        """Opt-in: restart the user WirePlumber service. Enabled only when
        $ARQUX_VOICE_AUTO_RECOVER=wireplumber (that IS the authorization);
        the only known cure for the intermittently stuck DMIC ACP6x."""
        self._last_system_recovery_ts = time.monotonic()
        try:
            subprocess.run(["systemctl", "--user", "restart", "wireplumber"],
                           capture_output=True, timeout=10, check=True)
        except Exception as exc:  # noqa: BLE001
            self.tx.append("system",
                           f"Auto-recuperación de audio falló: {exc!r}")
            return
        time.sleep(1.0)
        self._recoveries = 0
        self._open_mic(self._mic_target)
        with self._health_lock:
            self._health["last_voice_ts"] = time.monotonic()
        self.tx.append(
            "system",
            "Servicio de audio reiniciado automáticamente "
            "(ARQUX_VOICE_AUTO_RECOVER=wireplumber) — "
            f"{reason}.")

    def _recover_mic(self, reason: str) -> None:
        now = time.monotonic()
        if self._recoveries >= _MIC_MAX_RECOVERIES:
            from .config import auto_recover
            if (auto_recover() == "wireplumber"
                    and now - self._last_system_recovery_ts
                    > _SYSTEM_RECOVERY_COOLDOWN):
                self._system_recover(reason)
                return
            if self._mic_state != "dead":
                self._mic_state = "dead"
                self.tx.append(
                    "system",
                    f"Micrófono degradado, sin más recuperación automática "
                    f"({reason}). Opciones: meeting_stop+meeting_start, "
                    f"voice_configure(mic=...), o reiniciar WirePlumber "
                    f"(requiere autorización).")
            return
        self._recoveries += 1
        self._mic_state = "recovering"
        old = self._mic_source
        if old:
            old.stop()
            self._sources = [s for s in self._sources if s is not old]
        if self._candidates:
            self._cand_idx = (self._cand_idx + 1) % len(self._candidates)
            target = self._candidates[self._cand_idx]
        else:
            target = None
        self._open_mic(target)
        self.tx.append(
            "system",
            f"Micrófono reconectado automáticamente ({reason}) → "
            f"{self._mic_device} [intento {self._recoveries}].")

    def mic_health(self) -> dict:
        now = time.monotonic()
        with self._health_lock:
            h = dict(self._health)
        src = self._mic_source
        return {
            "device": self._mic_device,
            "alive": bool(src and src.alive),
            "state": self._mic_state,
            "ac_rms": round(h.get("ac_rms", 0.0), 4),
            "dc": round(h.get("dc", 0.0), 4),
            "vad_fires": h.get("vad_fires", 0),
            "last_voice_ago_s": round(now - h.get("last_voice_ts", now), 1),
            "recoveries": self._recoveries,
        }

    def set_mic(self, selector: str) -> dict:
        """Switch the capture device at runtime (reopens the mic channel)."""
        from .capture import resolve_source
        target = resolve_source(selector)
        self._candidates = candidate_targets(selector)
        self._cand_idx = 0
        old = self._mic_source
        if old:
            old.stop()
            self._sources = [s for s in self._sources if s is not old]
        self._recoveries = 0
        self._open_mic(target)
        self.tx.append("system", f"Micrófono cambiado a {self._mic_device}.")
        return self.mic_health()

    def _prewarm_models(self) -> None:
        """Load STT, TTS, VAD and Smart Turn before first utterance."""
        try:
            stt = self.stt.prewarm()
            tts = self.speaker.prewarm()
            vad = VadSegmenter.prewarm()
            turn = self.turn.prewarm()
            self._prewarm = {"stt": stt, "tts": tts,
                             "vad": vad, "turn": turn}
            self.tx.append("system",
                           "Modelos precalentados en "
                           f"{stt['ms'] + tts['ms'] + vad['ms'] + turn['ms']} ms.")
        except Exception as exc:  # noqa: BLE001
            self._prewarm = {"error": repr(exc)}

    def _spawn(self, source: PcmSource, channel: str) -> None:
        t = threading.Thread(target=self._channel_loop,
                             args=(source, channel), daemon=True)
        t.start()
        self._threads.append(t)

    def stop(self) -> dict:
        self._stop.set()
        for s in self._sources:
            s.stop()
        for t in self._threads:
            t.join(timeout=3)
        stats = {"entries": len(self.tx.entries),
                 "agent_turns": self._agent_turns}
        self.tx.footer(stats)
        if self.mixer:
            self.mixer.teardown()
        return {"transcript": str(self.tx.path), **stats}

    # ---------- audio pipeline ----------

    def _handle_audio_barge_in(self, channel: str,
                               seg: VadSegmenter,
                               source: PcmSource | None = None) -> bool:
        """Interrupt TTS from local VAD, before waiting for final STT."""
        if channel != CHANNEL_MIC or not self.speaker.tts_active.is_set():
            self._barge_in_active = False
            self._barge_in_frames = 0
            return False
        if not seg.speech_active:
            self._barge_in_active = False
            self._barge_in_frames = 0
            return False
        if (time.monotonic() - self._last_agent_say_ts
                < self._barge_in_grace_s):
            self._barge_in_frames = 0
            return False
        rms = getattr(source, "last_ac_rms", None)
        if rms is not None and rms < self._barge_in_min_rms:
            self._barge_in_frames = 0
            return False
        if self._barge_in_active:
            return False
        self._barge_in_frames += 1
        if self._barge_in_frames < self._barge_in_min_frames:
            return False
        self._barge_in_active = True
        self._barge_in_events += 1
        self.speaker.interrupt()
        return True

    def _channel_loop(self, source: PcmSource, channel: str) -> None:
        seg = VadSegmenter()
        pending: np.ndarray | None = None
        spec: dict = {}
        try:
            for chunk in source.stream():
                if self._stop.is_set() or self._hard_off:
                    break
                for off in range(0, len(chunk) - 512 + 1, 512):
                    frame = chunk[off:off + 512]
                    out = seg.feed(frame)
                    if channel == CHANNEL_MIC and source is self._mic_source:
                        self._update_mic_health(source, seg)
                    if self._handle_audio_barge_in(channel, seg, source):
                        spec.clear()
                    # speculative STT: as soon as ~200 ms of silence
                    # accumulate, transcribe the open segment in the
                    # background so the result is ready when EOT confirms.
                    # The monitor channel gets the same optimization when
                    # TTS is not active; its completed segments are still
                    # filtered below during local playback.
                    # Guard on "len" (in-flight), not "res": prevents a
                    # thread storm while a transcription is still running.
                    if (channel in (CHANNEL_MIC, CHANNEL_MONITOR)
                            and not self._suspended
                            and not (channel == CHANNEL_MONITOR
                                     and self.speaker.tts_active.is_set())
                            and seg.speech_active and seg.silence_frames >= 6
                            and "len" not in spec):
                        snap = seg.current_audio()
                        if snap is not None and len(snap) > 16000 * 0.3:
                            spec["len"] = len(snap)
                            frozen = snap.copy()

                            def _run(a=frozen):
                                try:
                                    spec["res"] = self.stt.transcribe(a)
                                except Exception:  # noqa: BLE001
                                    spec["res"] = None
                            threading.Thread(target=_run,
                                             daemon=True).start()
                    if out is None:
                        continue
                    audio, _t0, _t1 = out
                    if channel == CHANNEL_MIC and source is self._mic_source:
                        self.latency.mark("speech_end", _t1)
                    if channel == CHANNEL_MONITOR and (
                            self._suspended
                            or self.speaker.tts_active.is_set()):
                        spec.clear()
                        continue
                    if self._suspended:
                        if channel != CHANNEL_MIC:
                            spec.clear()
                            continue
                        if self._wake_stt is None:
                            from .config import whisper_cached
                            model = "tiny" if whisper_cached("tiny") \
                                else self.stt.model_name
                            self._wake_stt = Transcriber(
                                model=model, lang=self.stt.lang)
                        try:
                            wake = self._wake_stt.transcribe(audio)["text"]
                        except Exception:  # noqa: BLE001
                            spec.clear()
                            continue
                        if wake and _WAKE_RE.search(_norm(wake)):
                            self.resume_listening()
                        spec.clear()
                        continue
                    # smart EOT: merge segments the classifier reads as an
                    # unfinished turn (short pauses); cap at 30 s
                    if self.turn.available():
                        cand = (audio if pending is None
                                else np.concatenate([pending, audio]))
                        if (len(cand) < 16000 * 30
                                and not self.turn.predict(cand)["complete"]):
                            pending = cand
                            spec.clear()  # stale: audio will grow
                            continue
                        audio, pending = cand, None
                    res = spec.get("res")
                    if (res is not None and spec.get("len")
                            and spec["len"] >= len(audio) - 16000):
                        pass  # speculative hit — tail is trailing silence
                    else:
                        try:
                            res = self.stt.transcribe(audio)
                        except Exception as exc:  # noqa: BLE001
                            self.tx.append("system", f"STT error: {exc!r}")
                            spec.clear()
                            continue
                    spec.clear()
                    text = res["text"]
                    if not text:
                        continue
                    # echo guard: the mic hears our own TTS. While the TTS
                    # is playing, the only legitimate mic input is a barge-in
                    # command — anything else is our own voice bleeding in.
                    if channel == CHANNEL_MIC:
                        if (self.speaker.tts_active.is_set()
                                and not _BARGE_RE.search(_norm(text))):
                            self.tx.append(
                                "system",
                                f"eco durante TTS ignorado: {text[:40]}")
                            continue
                        if self._is_echo(text):
                            self.tx.append(
                                "system", f"eco ignorado: {text[:40]}")
                            continue
                    # pipeline voice commands run before transcript/gate
                    if channel == CHANNEL_MIC and self._route_command(text):
                        continue
                    self.tx.append(channel, text)
                    if self._silent:
                        continue  # passive mode: notes only, never queue
                    g = self.gate.check(text)
                    if g["addressed"]:
                        self._enqueue_turn({
                            "speaker": channel,
                            "text": text,
                            "ts": self.tx.entries[-1]["ts"],
                            "duration_s": res["duration"],
                            "confidence": res["confidence"],
                            "match": g["match"],
                        })
        except Exception as exc:  # noqa: BLE001
            self.tx.append("system", f"capture error ({channel}): {exc!r}")

    # ---------- voice commands & listening states ----------

    def _enqueue_turn(self, item: dict) -> None:
        """Enqueue a fresh turn, dropping the oldest stale turn if full."""
        try:
            self._queue.put_nowait(item)
            return
        except queue.Full:
            pass
        with contextlib.suppress(queue.Empty):
            self._queue.get_nowait()
            self._dropped_turns += 1
        with contextlib.suppress(queue.Full):
            self._queue.put_nowait(item)

    def _is_echo(self, text: str) -> bool:
        """True when a mic utterance closely matches our own recent TTS
        (the mic hears the speakers; without this, our voice would trigger
        barge-in and cut our own playback)."""
        from difflib import SequenceMatcher
        norm = _norm(text)
        if len(norm) < 6:
            return False
        toks = set(norm.split())
        for said in self._recent_agent:
            if len(said) < 6:
                continue
            if norm in said or said in norm:
                return True
            if SequenceMatcher(None, norm, said).ratio() > 0.62:
                return True
            stoks = set(said.split())
            if toks and stoks:
                jaccard = len(toks & stoks) / len(toks | stoks)
                if jaccard > 0.6:
                    return True
        return False

    def _route_command(self, text: str) -> bool:
        """Execute a pipeline voice command; True if ``text`` was one."""
        norm = _norm(text)
        if self.speaker.tts_active.is_set() and _BARGE_RE.search(norm):
            self.speaker.interrupt()
            self.tx.append("system", "TTS interrumpido por voz.")
            return True
        if _SUSPEND_RE.search(norm):
            self.suspend_listening()
            return True
        if _HARDOFF_RE.search(norm):
            self.hard_off()
            return True
        if _REDACT_RE.search(norm):
            n = self.tx.redact_last(2)
            self.tx.append("system",
                           f"{n} entradas redactadas a solicitud del "
                           "Arquitecto.")
            return True
        if _CANCEL_RE.search(norm):
            dropped = 0
            while True:
                try:
                    self._queue.get_nowait()
                    dropped += 1
                except queue.Empty:
                    break
            self.tx.append("system",
                           f"Cola vaciada a solicitud ({dropped} pendientes).")
            return True
        if _SILENT_ON_RE.search(norm):
            self.set_silent(True)
            return True
        if _SILENT_OFF_RE.search(norm):
            self.set_silent(False)
            return True
        if _VOLUP_RE.search(norm) or _VOLDN_RE.search(norm):
            step = "10%+" if _VOLUP_RE.search(norm) else "10%-"
            try:
                subprocess.run(["wpctl", "set-volume",
                                "@DEFAULT_AUDIO_SINK@", step],
                               capture_output=True, timeout=5, check=True)
                out = subprocess.run(
                    ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"],
                    capture_output=True, timeout=5).stdout.decode().strip()
                self.tx.append("system", f"Volumen ajustado — {out}.")
            except Exception as exc:  # noqa: BLE001
                self.tx.append("system", f"Error de volumen: {exc!r}")
            return True
        if _SLOWER_RE.search(norm) or _FASTER_RE.search(norm):
            factor = 1.25 if _SLOWER_RE.search(norm) else 0.8
            scale = self.speaker.set_speed(factor)
            self.tx.append("system",
                           f"Velocidad TTS ajustada (length_scale={scale:.2f}).")
            return True
        return False

    def suspend_listening(self) -> dict:
        """Soft suspension: wake-phrase listening only; nothing stored."""
        if self._suspended or self._hard_off:
            return {"listening": self.listening_state()}
        self._suspended = True
        self.tx.append("system",
                       "Escucha suspendida a solicitud — modo despertar "
                       "(sin transcripción ni almacenamiento). Diga "
                       "'reanuda' para volver.")
        return {"listening": "wake"}

    def resume_listening(self) -> dict:
        """Voice-reactivation from soft suspension."""
        if not self._suspended:
            return {"listening": self.listening_state()}
        self._suspended = False
        self.tx.append("system", "Escucha reanudada por voz.")
        return {"listening": "on"}

    def hard_off(self) -> dict:
        """Real mic off: capture processes killed. Reactivation requires
        meeting_stop + meeting_start (or keyboard)."""
        self._hard_off = True
        for s in self._sources:
            s.stop()
        self.tx.append("system",
                       "Micrófono APAGADO a solicitud — sin captura. "
                       "Reactivación: meeting_stop + meeting_start.")
        return {"listening": "off"}

    def set_silent(self, on: bool) -> dict:
        """Passive listening: transcribe + notes, but never reply/queue."""
        if self._silent == on:
            return {"silent": self._silent}
        self._silent = on
        self.tx.append("system",
                       "Modo silencio ACTIVADO — transcribo todo, no "
                       "respondo. Diga 'puedes responder' para volver."
                       if on else
                       "Modo silencio DESACTIVADO — vuelvo a responder.")
        return {"silent": on}

    def listening_state(self) -> str:
        if self._hard_off:
            return "off"
        if self._suspended:
            return "wake"
        return "silent" if self._silent else "on"

    # ---------- MCP-facing API ----------

    def listen(self, timeout: float = 20.0) -> dict:
        """Long-poll for the next addressed utterance."""
        try:
            item = self._queue.get(timeout=max(0.5, min(timeout, 120)))
        except queue.Empty:
            return {"timeout": True,
                    "mic_health": self.mic_health(),
                    "transcript_tail": self.tx.tail(3)}
        item["context_tail"] = self.tx.tail(6)
        return item

    def say(self, text: str, _transcribe: bool = True,
            interrupt: bool = False) -> dict:
        if interrupt:
            self.speaker.interrupt()
        self.latency.mark("first_token")
        self._last_agent_say_ts = time.monotonic()
        if self.mode == "meet":
            res = self.speaker.say(text, targets=["VirtualSpeaker"],
                                   mirror_default=True)
        else:
            res = self.speaker.say(text, targets=[None])
        self._merge_speaker_latency()
        if _transcribe:
            self._agent_turns += 1
            self._recent_agent.append(_norm(text))
            self.tx.append("agent", text)
        return res

    def record_agent_response(self, text: str) -> dict:
        """Record one logical agent turn after incremental playback."""
        self._agent_turns += 1
        self._recent_agent.append(_norm(text))
        return self.tx.append("agent", text)

    def bind_conversation_session(self, session_id: str,
                                  arqx_context: dict[str, str] | None = None
                                  ) -> dict[str, object]:
        """Bind the meeting to one ArqUX-controlled conversation identity."""
        if self.session_id != session_id:
            # The transport writes system lifecycle entries before the host
            # bridge is attached.  Those entries are not semantic turns and
            # must not prevent binding the one canonical conversation.
            if any(entry.get("channel") != "system" for entry in self.tx.entries) \
                    or self._agent_turns:
                raise ValueError(
                    "la sesión de voz ya está vinculada y no puede cambiarse"
                )
            self.session_id = session_id
        if arqx_context:
            self.arqx_context.update({k: str(v) for k, v in arqx_context.items()
                                      if v})
        return {"session_id": self.session_id,
                "arqx_context": dict(self.arqx_context)}

    def mark_latency(self, stage: str, at: float | None = None) -> float:
        """Allow an external harness to add LLM/E2E stage timestamps."""
        return self.latency.mark(stage, at)

    def _merge_speaker_latency(self) -> None:
        for name, timestamp in self.speaker.latency.snapshot().items():
            if name in {"first_tts", "first_audio", "interrupt"}:
                self.latency.mark(name, timestamp)

    def say_incremental(self, fragment: dict) -> dict:
        """Accept one authenticated text fragment and play it incrementally."""
        session_id = str(fragment.get("session_id", ""))
        if not session_id:
            raise StreamRejected("missing_session", "session_id is required")
        owner = self.agent  # resolved from the active MCP meeting context
        with self._speech_sessions_lock:
            session = self._speech_sessions.get(session_id)
            if session is None:
                session = SpeechSession(session_id, owner)
                self._speech_sessions[session_id] = session
        result = session.accept(fragment, owner=owner)
        if result.get("interrupted"):
            self.speaker.interrupt()
            with self._speech_sessions_lock:
                self._speech_sessions.pop(session_id, None)
            return result
        text = str(fragment.get("text", ""))
        record = bool(fragment.get("_record", True))
        if text:
            self.latency.mark("first_token")
            self._last_agent_say_ts = time.monotonic()
            targets = ["VirtualSpeaker"] if self.mode == "meet" else [None]
            try:
                res = self.speaker.say_stream(
                    [text], targets=targets, mirror_default=self.mode == "meet")
            except Exception as exc:  # noqa: BLE001
                # Streaming is opt-in: cancel the broken stream and keep the
                # proven legacy path available as the immediate rollback.
                self.speaker.interrupt()
                with self._speech_sessions_lock:
                    self._speech_sessions.pop(session_id, None)
                res = self.say(text, _transcribe=True, interrupt=False)
                res.update({"stream_fallback": "legacy",
                            "stream_error": repr(exc)})
                return res
            self._merge_speaker_latency()
            if record:
                self.record_agent_response(text)
        else:
            res = {"spoken": False, "mode": "incremental"}
        session.drain()
        if result.get("final"):
            with self._speech_sessions_lock:
                self._speech_sessions.pop(session_id, None)
        return {**result, **res}

    def note(self, text: str, kind: str = "note") -> dict:
        return self.tx.append("note", f"[{kind}] {text}")

    def transcript(self, tail_n: int = 20,
                   since_ts: str | None = None) -> list[dict]:
        return self.tx.tail(tail_n, since_ts)

    def status(self) -> dict:
        return {
            "meeting": self.name, "mode": self.mode,
            "session_id": self.session_id,
            "arqx_context": dict(self.arqx_context),
            "uptime_s": round(time.monotonic() - self._started, 1),
            "entries": len(self.tx.entries),
            "agent_turns": self._agent_turns,
            "pending": self._queue.qsize(),
            "dropped_turns": self._dropped_turns,
            "listening": self.listening_state(),
            "transcript": str(self.tx.path),
            "virtual_mic": self.mixer.status() if self.mixer else None,
            "mic_health": self.mic_health(),
            "prewarm": self._prewarm or "loading",
            "latency": self.latency.summary(),
        }
