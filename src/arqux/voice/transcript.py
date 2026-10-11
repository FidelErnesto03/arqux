"""Per-meeting markdown transcript writer."""

from __future__ import annotations

import re
import threading
from datetime import datetime

from .config import meetings_dir

CHANNEL_LABELS = {
    "mic": "arquitecto",
    "monitor": "remoto",
    "agent": "agente",
    "note": "agente·nota",
    "system": "sistema",
}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48] or "meet"


class TranscriptWriter:
    """Appends timestamped, channel-tagged entries to a .md file."""

    def __init__(self, name: str, mode: str, agent: str = "agent",
                 lang: str = "es", announce: bool = False,
                 session_id: str | None = None,
                 arqx_context: dict[str, str] | None = None):
        base = meetings_dir()
        base.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        session_suffix = f"-{_slug(session_id)}" if session_id else ""
        self.path = base / f"{now:%Y-%m-%d}_{_slug(name)}{session_suffix}.md"
        self._lock = threading.Lock()
        self.entries: list[dict] = []
        self.started = now
        # Sessions reopened the same day reuse the file — write the
        # header only once, else the transcript grows duplicate headers.
        if not self.path.exists() or self.path.stat().st_size == 0:
            self._write_header(name, mode, agent, lang, announce, now,
                               session_id, arqx_context)

    def _write_header(self, name, mode, agent, lang, announce, now,
                      session_id, arqx_context):
        notice = ("Esta conversación se transcribe localmente (arqux-voice)."
                  if announce else
                  "Transcripción local (arqux-voice).")
        with self._lock, open(self.path, "a", encoding="utf-8") as f:
            f.write(f"# Reunión: {name}\n\n")
            f.write(f"- Fecha: {now:%Y-%m-%d} | Inicio: {now:%H:%M}\n")
            f.write(f"- Modo: {mode} | Agente: {agent} | Idioma: {lang}\n")
            if session_id:
                f.write(f"- Sesión de voz: {session_id}\n")
            if arqx_context:
                context = " | ".join(
                    f"{key}={value}" for key, value in arqx_context.items()
                    if value)
                if context:
                    f.write(f"- Contexto ArqUX: {context}\n")
            f.write(f"- {notice}\n\n---\n")

    def append(self, channel: str, text: str,
               ts: datetime | None = None) -> dict:
        label = CHANNEL_LABELS.get(channel, channel)
        ts = ts or datetime.now()
        entry = {"ts": ts.isoformat(timespec="seconds"),
                 "channel": channel, "label": label, "text": text}
        with self._lock:
            self.entries.append(entry)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(f"\n## [{ts:%H:%M}] {label}\n\n{text}\n")
        return entry

    def tail(self, n: int = 20, since_ts: str | None = None) -> list[dict]:
        with self._lock:
            entries = self.entries
            if since_ts:
                entries = [e for e in entries if e["ts"] > since_ts]
            return entries[-n:]

    def redact_last(self, n: int = 2) -> int:
        """Replace the text of the last ``n`` non-system entries with
        ``[redactado]`` (timestamps kept for audit). Returns count."""
        with self._lock:
            targets = [e for e in self.entries
                       if e["channel"] != "system"][-n:]
            if not targets:
                return 0
            content = self.path.read_text(encoding="utf-8")
            redacted = 0
            for e in targets:
                old = f"\n## [{e['ts'][11:16]}] {e['label']}\n\n{e['text']}\n"
                new = (f"\n## [{e['ts'][11:16]}] {e['label']}\n\n"
                       f"[redactado]\n")
                idx = content.rfind(old)
                if idx >= 0:
                    content = content[:idx] + new + content[idx + len(old):]
                    e["text"] = "[redactado]"
                    redacted += 1
            self.path.write_text(content, encoding="utf-8")
            return redacted

    def footer(self, stats: dict) -> None:
        now = datetime.now()
        with self._lock, open(self.path, "a", encoding="utf-8") as f:
            f.write("\n---\n\n")
            f.write(f"Fin: {now:%H:%M} | "
                    f"Duración: {now - self.started} | "
                    f"Entradas: {stats.get('entries', len(self.entries))} | "
                    f"Intervenciones del agente: {stats.get('agent_turns', 0)}\n")
