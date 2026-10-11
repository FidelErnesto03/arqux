"""MCP stdio server: arqux-voice.

Harness-agnostic voice participation: any MCP-compatible agent gets
listen/speak/notes tools over a fully local audio pipeline.

Mount example (any harness):
    {"mcpServers": {"arqux-voice": {
        "command": "arqux", "args": ["voice-serve"]}}}
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from .daemon_client import DaemonRequestError, DaemonUnavailable, VoiceDaemonClient, daemon_mode
from .meeting import Meeting

_NAME = "arqux-voice"
_meeting: Meeting | None = None

_TOOL_SCHEMAS: list[tuple[str, str, dict]] = [
    ("voice_listen", "1:1 mode — long-poll the next utterance from the "
     "Architect's microphone. Auto-starts a solo session if none is "
     "active. Returns {speaker,text,ts,confidence,context_tail} or "
     "{timeout:true}.",
     {"type": "object",
      "properties": {"timeout_s": {"type": "number", "default": 20}},
      "required": []}),
    ("voice_say", "1:1 mode — speak text aloud through the default output "
     "(local Piper TTS). Auto-starts a solo session if none is active.",
     {"type": "object",
      "properties": {"text": {"type": "string"}},
      "required": ["text"]}),
    ("meeting_start", "Start a meeting session. mode='solo' (1:1 voice, "
     "mic only, TTS to speakers) or mode='meet' (join an ongoing call on "
     "this machine: captures mic+remote audio and provisions a VirtualMic "
     "so the agent's voice enters the call through the Architect's "
     "connection — no bot).",
     {"type": "object",
      "properties": {
          "name": {"type": "string"},
          "mode": {"type": "string", "enum": ["solo", "meet"],
                   "default": "solo"},
          "agent": {"type": "string", "default": "alfred"},
          "lang": {"type": "string", "default": "es"},
          "announce": {"type": "boolean",
                       "description": "Spoken transcription notice. "
                       "Omit for auto: ON in meet, OFF in solo."},
          "mention_patterns": {"type": "array",
                               "items": {"type": "string"}},
          "whisper_model": {"type": "string", "default": "auto",
                            "description": "auto=Parakeet si está instalado, si no whisper-small; o small/medium/parakeet"},
          "voice": {"type": "string"},
          "mic": {"type": "string",
                  "description": "Input device selector (node.name, id or "
                  "description substring). Overrides $ARQUX_VOICE_MIC for "
                  "this session. Use voice_devices to list options."}},
      "required": ["name"]}),
    ("meeting_listen", "Long-poll the next utterance addressed to the "
     "agent. In meet mode only utterances matching mention_patterns are "
     "returned (silence by default); everything is still transcribed. "
     "Returns {speaker,text,ts,confidence,match,context_tail} or "
     "{timeout:true,transcript_tail}.",
     {"type": "object",
      "properties": {"timeout_s": {"type": "number", "default": 20}},
      "required": []}),
    ("meeting_say", "Speak text into the meeting (VirtualMic in meet mode "
     "— remote participants hear it — or speakers in solo).",
     {"type": "object",
      "properties": {"text": {"type": "string"},
                     "interrupt": {"type": "boolean", "default": False},
                     "session_id": {"type": "string"},
                     "stream_id": {"type": "string"},
                     "sequence": {"type": "integer", "minimum": 1},
                     "final": {"type": "boolean", "default": False},
                     "blocking": {"type": "boolean", "default": False}},
      "required": ["text"]}),
    ("meeting_transcript", "Read transcript entries (incremental).",
     {"type": "object",
      "properties": {"tail_n": {"type": "integer", "default": 20},
                     "since_ts": {"type": "string"}},
      "required": []}),
    ("meeting_note", "Append a structured agent note to the transcript "
     "(decision|action|note).",
     {"type": "object",
      "properties": {"text": {"type": "string"},
                     "kind": {"type": "string",
                              "enum": ["decision", "action", "note"],
                              "default": "note"}},
      "required": ["text"]}),
    ("meeting_status", "Session status: uptime, entries, pending "
     "utterances, virtual mic state.",
     {"type": "object", "properties": {}, "required": []}),
    ("conversation_start", "Attach voice to the already active canonical "
     "ArqUX conversation. The host bridge owns the current agent and answer; "
     "the voice daemon remains transport-only and never creates a backend "
     "session. Activation fails closed when the host bridge is unavailable.",
     {"type": "object",
      "properties": {
          "conversation_session_id": {"type": "string",
                                      "description": "Current canonical ArqUX session ID."},
          "parent_arqx_session_id": {"type": "string",
                                      "description": "Current ArqUX host session reference."},
          "project": {"type": "string", "default": "ARQUX"},
          "scope": {"type": "string", "default": "CYCLE-12"},
          "blp": {"type": "string", "default": "BLP-019"},
          "bridge_socket": {"type": "string",
                             "description": "Unix socket exposed by the host session adapter."},
          "event_log": {"type": "string",
                         "description": "ArqUX-owned canonical event log path."},
          "owner_handler": {"type": "string", "default": "host-adapter"},
          "lease_ttl_s": {"type": "number", "default": 30},
          "timeout_s": {"type": "number", "default": 90}},
      "required": ["conversation_session_id", "parent_arqx_session_id",
                    "project", "scope", "bridge_socket"]}),
    ("conversation_stop", "Detach voice from the canonical session; the "
     "daemon and written ArqUX session remain active.",
     {"type": "object", "properties": {}, "required": []}),
    ("conversation_status", "Show canonical session, lease, host bridge, "
     "sequence, modality and voice transport state.",
     {"type": "object", "properties": {}, "required": []}),
    ("meeting_stop", "Stop the session: finalize transcript, release "
     "audio devices and the virtual mic.",
     {"type": "object", "properties": {}, "required": []}),
    ("voice_devices", "List available input (microphone) devices with id, "
     "name, description, default flag and a live input level — to choose "
     "the capture device for meeting_start(mic=...) / $ARQUX_VOICE_MIC.",
     {"type": "object",
      "properties": {"probe_secs": {"type": "number", "default": 1.0,
                                    "description": "Seconds of live level "
                                    "probe per device; 0 disables probing."}},
      "required": []}),
    ("voice_configure", "Tune the gate (mention_patterns, mode), the TTS "
     "voice, or switch the capture device at runtime.",
     {"type": "object",
      "properties": {
          "mention_patterns": {"type": "array",
                               "items": {"type": "string"}},
          "mode": {"type": "string", "enum": ["always", "mention"]},
          "mic": {"type": "string",
                  "description": "Switch the input device (node.name, id "
                  "or description substring); reopens the capture channel."}},
      "required": []}),
]


def _ensure_solo() -> Meeting:
    global _meeting
    if _meeting is None:
        _meeting = Meeting(name="voz-1a1", mode="solo")
        _meeting.start()
    return _meeting


def _persistent_client() -> VoiceDaemonClient | None:
    """Prefer the independent daemon when it is running.

    ``auto`` keeps the historical in-process fallback for development and
    tests.  The daemon itself remains the owner of audio capture once it has
    been started, so restarting this MCP stdio process does not stop listening.
    """
    if daemon_mode() == "off":
        return None
    client = VoiceDaemonClient()
    return client if client.available() else None


async def _dispatch(name: str, args: dict) -> str:
    global _meeting
    if name != "voice_devices":
        client = _persistent_client()
        if client is not None:
            try:
                return json.dumps(client.request(name, **args), default=str)
            except DaemonRequestError as exc:
                return f"ERROR: voice daemon request failed: {exc}"
            except DaemonUnavailable:
                # The daemon may have stopped between the status probe and
                # the request.  Auto mode falls back to the legacy runtime.
                if daemon_mode() == "required":
                    return "ERROR: voice daemon is required but unavailable"
    if name.startswith("conversation_"):
        return ("ERROR: conversation supervisor requires the persistent voice "
                "daemon; start it with `arqux voice-daemon start`")
    if name == "meeting_start":
        if _meeting is not None:
            return ("ERROR: meeting already active — call meeting_stop "
                    "first")
        _meeting = Meeting(
            name=args["name"], mode=args.get("mode", "solo"),
            agent=args.get("agent", "alfred"), lang=args.get("lang", "es"),
            announce=args.get("announce"),
            mention_patterns=args.get("mention_patterns"),
            whisper_model=args.get("whisper_model", "auto"),
            voice=args.get("voice"), mic=args.get("mic"))
        return json.dumps(_meeting.start(), default=str)
    if name == "voice_devices":
        from .capture import list_sources
        return json.dumps(list_sources(args.get("probe_secs", 1.0)),
                          default=str)
    if name in ("voice_listen", "voice_say"):
        m = _ensure_solo()
        if name == "voice_listen":
            out = await asyncio.to_thread(
                m.listen, args.get("timeout_s", 20))
        else:
            out = await asyncio.to_thread(m.say, args["text"])
        return json.dumps(out, default=str)
    if _meeting is None:
        return "ERROR: no active meeting — call meeting_start first"
    m = _meeting
    if name == "meeting_listen":
        return json.dumps(await asyncio.to_thread(
            m.listen, args.get("timeout_s", 20)), default=str)
    if name == "meeting_say":
        if args.get("session_id"):
            return json.dumps(await asyncio.to_thread(
                m.say_incremental, args), default=str)
        return json.dumps(await asyncio.to_thread(
            m.say, args["text"],
            interrupt=args.get("interrupt", False)), default=str)
    if name == "meeting_transcript":
        return json.dumps(m.transcript(args.get("tail_n", 20),
                                       args.get("since_ts")), default=str)
    if name == "meeting_note":
        return json.dumps(m.note(args["text"], args.get("kind", "note")),
                          default=str)
    if name == "meeting_status":
        return json.dumps(m.status(), default=str)
    if name == "meeting_stop":
        out = m.stop()
        _meeting = None
        return json.dumps(out, default=str)
    if name == "voice_configure":
        if args.get("mention_patterns"):
            m.gate.set_patterns(args["mention_patterns"])
        if args.get("mode"):
            m.gate.set_mode(args["mode"])
        out: dict = {"gate_mode": m.gate.mode}
        if args.get("mic"):
            out["mic_health"] = m.set_mic(args["mic"])
        return json.dumps(out, default=str)
    return f"ERROR: unknown tool {name}"


def build_server() -> Any:
    from mcp.server import Server
    from mcp.types import TextContent, Tool

    server = Server(_NAME)
    tools = [Tool(name=n, description=d, inputSchema=s)
             for n, d, s in _TOOL_SCHEMAS]

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        try:
            text = await _dispatch(name, arguments or {})
        except Exception as exc:  # noqa: BLE001
            text = f"ERROR code=INTERNAL tool={name} message={exc!r}"
        return [TextContent(type="text", text=text)]

    return server


def run() -> None:
    try:
        from mcp.server.stdio import stdio_server
    except ImportError:
        print("ERROR: mcp package required — pip install 'arqux[voice]'",
              file=sys.stderr)
        sys.exit(1)

    server = build_server()

    async def _main() -> None:
        async with stdio_server() as (rs, ws):
            await server.run(rs, ws,
                             server.create_initialization_options())

    asyncio.run(_main())


if __name__ == "__main__":
    run()
