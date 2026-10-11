"""Voice transport loop backed by the canonical ArqUX SessionBus."""

from __future__ import annotations

import threading
from typing import Any

from ..session_bus import SessionBus
from .session_bridge import VoiceSessionBridge


class VoiceSessionRuntime:
    """Consume STT turns and project current-agent output to TTS."""

    def __init__(self, meeting: Any, bus: SessionBus, bridge: VoiceSessionBridge):
        self.meeting = meeting
        self.bus = bus
        self.bridge = bridge
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._state = "stopped"
        self._turns = 0
        self._errors = 0
        self._last_error = ""

    def start(self) -> dict[str, Any]:
        if self._thread and self._thread.is_alive():
            return self.status()
        self._stop.clear()
        self._state = "running"
        self._thread = threading.Thread(
            target=self._run, name="arqux-voice-session-bridge", daemon=True)
        self._thread.start()
        return self.status()

    def stop(self) -> dict[str, Any]:
        self._state = "stopping"
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        self._thread = None
        self.bridge.detach()
        self._state = "stopped"
        return self.status()

    def status(self) -> dict[str, Any]:
        return {
            "state": self._state,
            "active": bool(self._thread and self._thread.is_alive()),
            "turns": self._turns,
            "errors": self._errors,
            "last_error": self._last_error or None,
            "bridge": self.bridge.status(),
        }

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                item = self.meeting.listen(timeout=1.0)
                if item.get("timeout"):
                    continue
                text = str(item.get("text", "")).strip()
                if not text:
                    continue
                self.bridge.submit_voice(text, metadata={
                    "stt_confidence": item.get("confidence"),
                    "speech_ts": item.get("ts"),
                })
                self._turns += 1
            except Exception as exc:  # noqa: BLE001
                self._errors += 1
                self._last_error = str(exc)
                self._stop.wait(0.25)
        if self._state == "running":
            self._state = "stopped"

    def speak_output(self, event: Any) -> None:
        if event.metadata.get("status") == "cancelled":
            self.meeting.say("", interrupt=True)
            return
        if event.text:
            self.meeting.say(event.text, interrupt=False)
            self.bus.latency.mark(event.turn_id, "tts_first_audio")
