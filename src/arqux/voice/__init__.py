"""ARQUX Voice — harness-agnostic local voice participation extension.

Pipeline: PipeWire/ALSA capture -> VAD -> faster-whisper STT -> mention gate
-> Piper TTS -> speaker or virtual microphone. Exposed as MCP stdio tools so
any agent harness (devin, claudecode, opencode, codex, cmd) can participate
in meetings: listen, speak when addressed, take notes to a per-meeting .md.

All local: no audio, transcript or model leaves the machine.
"""

__all__ = ["config", "capture", "vad", "stt", "gate", "tts", "mixer",
           "transcript", "meeting", "server", "daemon", "daemon_client",
           "host_adapter", "session_bridge", "session_runtime",
           "agent_backend", "supervisor", "doctor"]
