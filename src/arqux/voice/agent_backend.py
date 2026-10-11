"""Agent backends for the autonomous voice conversation supervisor.

The audio daemon deliberately does not depend on an MCP client.  Once the
conversation loop is explicitly enabled, it resolves one of these backends
and keeps the voice path alive even when the MCP stdio process is restarted.

Backends are intentionally small and optional:

* ``codex`` runs the local Codex CLI in read-only, ephemeral mode;
* ``openai`` speaks the OpenAI-compatible ``/v1/chat/completions`` protocol;
* ``command`` delegates to a configured executable receiving a text prompt;
* ``echo`` is a deterministic test backend.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import urllib.error
import urllib.request
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any


class BackendError(RuntimeError):
    """The configured conversation backend could not answer."""


@dataclass(frozen=True)
class BackendConfig:
    name: str
    command: tuple[str, ...] = ()
    endpoint: str = ""
    model: str = ""
    api_key: str = ""
    timeout_s: float = 90.0
    system_prompt: str = ""


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def default_system_prompt(agent: str = "alfred", lang: str = "es") -> str:
    language = "español" if lang.lower().startswith("es") else lang
    return (
        f"Eres {agent.capitalize()}, asistente de voz de ArqUX. "
        f"Responde en {language}, de forma natural, breve y conversacional. "
        "No uses Markdown, listas ni encabezados salvo que sean necesarios. "
        "No describas tu proceso interno y no ejecutes acciones del sistema "
        "desde esta interfaz: informa y conversa con el Arquitecto."
    )


def _prompt(system: str, text: str, history: Sequence[dict[str, Any]]) -> str:
    lines = [f"SISTEMA: {system}", "CONVERSACIÓN RECIENTE:"]
    for item in history[-12:]:
        channel = str(item.get("channel", "")).lower()
        role = "Arquitecto" if channel in {"mic", "monitor"} else "Alfred"
        value = str(item.get("text", "")).strip()
        if value:
            lines.append(f"{role}: {value}")
    lines.extend(("", f"Arquitecto: {text}", "Alfred:"))
    return "\n".join(lines)


class AgentBackend:
    """Minimal streaming interface used by ``ConversationSupervisor``."""

    name = "backend"
    session_id: str | None = None

    def stream(self, text: str, history: Sequence[dict[str, Any]]) -> Iterator[str]:
        raise NotImplementedError


class EchoBackend(AgentBackend):
    name = "echo"

    def stream(self, text: str, history: Sequence[dict[str, Any]]) -> Iterator[str]:
        del history
        yield f"Te escuché decir: {text}"


class CommandBackend(AgentBackend):
    """Run one isolated command per turn and read its stdout as the reply."""

    def __init__(self, config: BackendConfig):
        if not config.command:
            raise BackendError(
                "backend command requiere ARQUX_VOICE_AGENT_COMMAND o command"
            )
        self.name = config.name
        self.command = config.command
        self.timeout_s = config.timeout_s
        self.system = config.system_prompt

    def stream(self, text: str, history: Sequence[dict[str, Any]]) -> Iterator[str]:
        prompt = _prompt(self.system, text, history)
        try:
            proc = subprocess.run(
                list(self.command), input=prompt, text=True,
                capture_output=True, timeout=self.timeout_s, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise BackendError(f"command backend falló: {exc}") from exc
        if proc.returncode != 0:
            detail = proc.stderr.strip()[-500:]
            raise BackendError(
                f"command backend exit={proc.returncode}: {detail or 'sin detalle'}"
            )
        answer = proc.stdout.strip()
        if not answer:
            raise BackendError("command backend devolvió una respuesta vacía")
        yield answer


class CodexBackend(AgentBackend):
    """Persistent Codex CLI conversation resumed by one thread ID."""

    name = "codex"

    def __init__(self, config: BackendConfig):
        executable = shutil.which("codex")
        if not executable:
            raise BackendError("backend codex requiere el ejecutable codex")
        self.executable = executable
        self.model = config.model
        self.timeout_s = config.timeout_s
        self.system = config.system_prompt
        self.session_id: str | None = None

    def stream(self, text: str, history: Sequence[dict[str, Any]]) -> Iterator[str]:
        prompt = _prompt(self.system, text, history)
        if self.session_id:
            command = [self.executable, "exec", "resume", self.session_id,
                       "--json", "--skip-git-repo-check", "-"]
        else:
            command = [self.executable, "exec", "--json", "--sandbox",
                       "read-only", "--color", "never",
                       "--skip-git-repo-check", "-"]
            if self.model:
                command.extend(("--model", self.model))
        try:
            proc = subprocess.run(
                command, input=prompt, text=True, capture_output=True,
                timeout=self.timeout_s, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise BackendError(f"backend codex falló: {exc}") from exc
        answer = ""
        for line in proc.stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "thread.started":
                thread_id = event.get("thread_id")
                if thread_id:
                    self.session_id = str(thread_id)
            item = event.get("item") or {}
            if item.get("type") == "agent_message" and item.get("text"):
                answer = str(item["text"]).strip()
        if proc.returncode != 0:
            detail = proc.stderr.strip()[-500:]
            raise BackendError(
                f"backend codex exit={proc.returncode}: "
                f"{detail or 'sin detalle'}"
            )
        if not answer:
            answer = proc.stdout.strip()
        if not answer:
            raise BackendError("backend codex devolvió una respuesta vacía")
        yield answer


class OpenAICompatibleBackend(AgentBackend):
    """Streaming client for local or remote OpenAI-compatible endpoints."""

    name = "openai"

    def __init__(self, config: BackendConfig):
        self.endpoint = config.endpoint.rstrip("/")
        if not self.endpoint.endswith("/chat/completions"):
            self.endpoint += "/v1/chat/completions"
        self.model = config.model
        self.api_key = config.api_key
        self.timeout_s = config.timeout_s
        self.system = config.system_prompt
        if not self.model:
            raise BackendError("backend openai requiere model")

    def stream(self, text: str, history: Sequence[dict[str, Any]]) -> Iterator[str]:
        messages = [{"role": "system", "content": self.system}]
        for item in history[-12:]:
            channel = str(item.get("channel", "")).lower()
            role = "user" if channel in {"mic", "monitor"} else "assistant"
            value = str(item.get("text", "")).strip()
            if value:
                messages.append({"role": role, "content": value})
        messages.append({"role": "user", "content": text})
        body = json.dumps({"model": self.model, "messages": messages,
                           "stream": True}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(self.endpoint, data=body,
                                         headers=headers, method="POST")
        try:
            response = urllib.request.urlopen(request, timeout=self.timeout_s)
        except (OSError, urllib.error.HTTPError, urllib.error.URLError) as exc:
            raise BackendError(f"openai backend no disponible: {exc}") from exc
        with response:
            for raw in response:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    event = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                choices = event.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if content:
                    yield str(content)


def _command_from_env() -> tuple[str, ...]:
    raw = _env("ARQUX_VOICE_AGENT_COMMAND")
    if not raw:
        return ()
    try:
        return tuple(shlex.split(raw))
    except ValueError as exc:
        raise BackendError(f"ARQUX_VOICE_AGENT_COMMAND inválido: {exc}") from exc


def build_backend(agent: str = "alfred", lang: str = "es",
                  **options: Any) -> AgentBackend:
    """Build the explicitly selected backend from MCP args or environment."""
    name = str(options.get("backend") or _env(
        "ARQUX_VOICE_AGENT_BACKEND", "codex" if shutil.which("codex") else "none"
    )).strip().lower()
    system = str(options.get("system_prompt") or _env(
        "ARQUX_VOICE_AGENT_SYSTEM", default_system_prompt(agent, lang)
    ))
    timeout = float(options.get("timeout_s") or _env(
        "ARQUX_VOICE_AGENT_TIMEOUT", "90"
    ))
    if name == "echo":
        return EchoBackend()
    if name == "none":
        raise BackendError(
            "no hay backend de agente; use backend=codex, openai, command o echo"
        )
    if name == "codex":
        model = str(options.get("model") or _env("ARQUX_VOICE_AGENT_MODEL"))
        return CodexBackend(BackendConfig(
            name=name, model=model, timeout_s=timeout, system_prompt=system))
    if name == "command":
        raw = options.get("command")
        command = tuple(shlex.split(str(raw))) if raw else _command_from_env()
        return CommandBackend(BackendConfig(
            name=name, command=command, timeout_s=timeout,
            system_prompt=system))
    if name in {"openai", "ollama"}:
        endpoint = str(options.get("endpoint") or _env(
            "ARQUX_VOICE_AGENT_ENDPOINT",
            "http://127.0.0.1:11434" if name == "ollama" else ""
        ))
        model = str(options.get("model") or _env(
            "ARQUX_VOICE_AGENT_MODEL", "llama3.2" if name == "ollama" else ""
        ))
        if not endpoint:
            raise BackendError("backend openai requiere endpoint")
        return OpenAICompatibleBackend(BackendConfig(
            name=name, endpoint=endpoint, model=model,
            api_key=str(options.get("api_key") or _env("ARQUX_VOICE_AGENT_API_KEY")),
            timeout_s=timeout, system_prompt=system))
    raise BackendError(f"backend de agente desconocido: {name}")
