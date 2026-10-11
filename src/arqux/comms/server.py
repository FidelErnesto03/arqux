"""MCP stdio server: arqux-comms (Telegram-only).

Extensión harness-agnóstica: cualquier agente compatible con MCP obtiene
tools de comunicación por Telegram sobre un canal local-first.

Montaje (cualquier harness):
    {"mcpServers": {"arqux-comms": {
        "command": "arqux", "args": ["comms-serve"]}}}
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

from .bridge import Bridge
from .config import EGRESS_ENV, allowlist, egress_enabled, telegram_token
from .inbox import Inbox
from .telegram import TelegramChannel

_NAME = "arqux-comms"

_channel: TelegramChannel | None = None
_inbox: Inbox | None = None
_bridge: Bridge | None = None
_initialized = False


def _ensure() -> tuple[TelegramChannel | None, Inbox, Bridge]:
    global _channel, _inbox, _bridge, _initialized
    if not _initialized:
        _inbox = Inbox()
        _bridge = Bridge(enabled=False)
        tok = telegram_token()
        if tok:
            _channel = TelegramChannel(tok, _inbox, allowlist())
            _channel.start()
        _initialized = True
    assert _inbox is not None and _bridge is not None
    return _channel, _inbox, _bridge


_TOOL_SCHEMAS: list[tuple[str, str, dict]] = [
    ("comms.send", "Send a Telegram message. Requires egress ON and the "
     "destination chat_id in the allowlist.",
     {"type": "object",
      "properties": {"to": {"type": "string"},
                     "text": {"type": "string"},
                     "channel": {"type": "string", "default": "telegram"}},
      "required": ["to", "text"]}),
    ("comms.inbox", "List unread incoming messages.",
     {"type": "object", "properties": {}, "required": []}),
    ("comms.listen", "Long-poll the next incoming message.",
     {"type": "object",
      "properties": {"timeout_s": {"type": "number", "default": 20}},
      "required": []}),
    ("comms.status", "Channel status: token, egress, allowlist, listener, "
     "counters.",
     {"type": "object", "properties": {}, "required": []}),
    ("comms.configure", "Toggle egress and/or update the allowlist at "
     "runtime.",
     {"type": "object",
      "properties": {"enable": {"type": "boolean"},
                     "allowlist": {"type": "array",
                                   "items": {"type": "string"}}},
      "required": []}),
]


async def _dispatch(name: str, args: dict) -> str:
    channel, inbox, bridge = _ensure()
    if name == "comms.send":
        if channel is None:
            return json.dumps({"error": "no_token",
                               "hint": "set ARQUX_COMMS_TELEGRAM_TOKEN"})
        out = await asyncio.to_thread(channel.send, args["to"], args["text"])
        return json.dumps(out, default=str)
    if name == "comms.inbox":
        return json.dumps({"unread": inbox.unread()}, default=str)
    if name == "comms.listen":
        item = await asyncio.to_thread(inbox.listen, args.get("timeout_s", 20))
        return json.dumps(item if item else {"timeout": True}, default=str)
    if name == "comms.status":
        return json.dumps({
            "channel": "telegram",
            "token": bool(channel),
            "egress": egress_enabled(),
            "allowlist": sorted(allowlist()),
            "alive": bool(channel and channel.alive()),
            "sent": channel.sent if channel else 0,
            "received": channel.received if channel else 0,
            "unread": len(inbox.unread()),
            "last_error": channel.last_error if channel else None,
        }, default=str)
    if name == "comms.configure":
        if isinstance(args.get("allowlist"), list) and channel is not None:
            channel.allowlist = {str(x) for x in args["allowlist"]}
        if "enable" in args:
            os.environ[EGRESS_ENV] = "on" if args["enable"] else "off"
        return json.dumps({"egress": egress_enabled(),
                           "allowlist": sorted(allowlist())}, default=str)
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
        print("ERROR: mcp package required — pip install 'arqux[comms]'",
              file=sys.stderr)
        sys.exit(1)

    server = build_server()

    async def _main() -> None:
        async with stdio_server() as (rs, ws):
            await server.run(rs, ws, server.create_initialization_options())

    asyncio.run(_main())


if __name__ == "__main__":
    run()
