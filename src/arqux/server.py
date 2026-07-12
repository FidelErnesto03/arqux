"""MCP server entry point.

Exposes governance handlers as MCP tools. The server is transport-agnostic
(stdio by default) — the `mcp` package handles the wire protocol.

This module is intentionally thin: it imports the handler registry, registers
each handler as an MCP tool, and starts the server. All logic lives in the
handler modules.

Tool names: dots (.) in handler names are converted to underscores (_)
because the MCP protocol requires tool names matching ``^[a-zA-Z0-9_-]+$``.
The internal registry preserves the dotted names for handler lookup.
"""

from __future__ import annotations

import sys
from typing import Any

from .constants import (
    INTERNAL_ERROR,
    OUT_ERROR,
    PERMISSION_DENIED,
    PRODUCT_NAME,
    PRODUCT_NAME_TITLE,
)
from .cortex_out import CortexOUT
from .handlers import REGISTRY
from .permissions import PermissionContext, PermissionDenied


def _safe_name(name: str) -> str:
    """Convert a dotted handler name to an MCP-safe tool name."""
    return name.replace(".", "_")


def _wrap_handler(name: str, handler: Any) -> Any:
    """Wrap a handler with permission checks and CORTEX-OUT formatting."""

    async def wrapped(**kwargs: Any) -> str:
        ctx = PermissionContext.from_env()
        try:
            ctx.check(name)
        except PermissionDenied as exc:
            return CortexOUT.profile(
                OUT_ERROR,
                f"ERROR code={PERMISSION_DENIED} handler={name} reason={exc.reason}",
            ).to_text()

        try:
            result = await handler(**kwargs, ctx=ctx) if _is_coro(handler) else handler(**kwargs, ctx=ctx)
            # Convert to plain string — MCP expects text output
            if hasattr(result, "to_text"):
                return str(result.to_text())
            elif hasattr(result, "message"):
                return str(result.message)
            return str(result)
        except Exception as exc:  # noqa: BLE001
            return CortexOUT.profile(
                OUT_ERROR,
                f"ERROR code={INTERNAL_ERROR} handler={name} message={exc!r}",
            ).to_text()

    wrapped.__name__ = name
    wrapped.__doc__ = handler.__doc__ or f"{name} handler"
    return wrapped


def _is_coro(fn: Any) -> bool:
    import inspect

    return inspect.iscoroutinefunction(fn)


def build_server() -> Any:
    """Build the MCP server with all handlers registered."""
    try:
        from mcp.server import Server
        from mcp.types import TextContent, Tool
    except ImportError as exc:
        raise RuntimeError(
            "mcp package is required. Install with: pip install mcp"
        ) from exc

    server = Server(PRODUCT_NAME)
    tools: list[Tool] = []
    handlers: dict[str, Any] = {}
    # Maps safe name (underscores) → real dotted handler name
    safe_to_dotted: dict[str, str] = {}

    for name, spec in REGISTRY.items():
        safe = _safe_name(name)
        safe_to_dotted[safe] = name

        tool = Tool(
            name=safe,
            description=spec.description,
            inputSchema=spec.input_schema,
        )
        tools.append(tool)
        # Register handler under BOTH names: safe (for call_tool) and dotted (for permissions)
        handlers[safe] = _wrap_handler(name, spec.fn)
        handlers[name] = handlers[safe]  # alias for direct calls

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        if name not in handlers:
            return [
                TextContent(
                    type="text",
                    text=CortexOUT.profile(
                        OUT_ERROR, f"ERROR code=NOT_FOUND handler={name}"
                    ),
                )
            ]
        text = await handlers[name](**arguments)
        return [TextContent(type="text", text=text)]

    return server


def run_server(verbose: bool = False) -> None:
    """Start the MCP server on stdio."""
    try:
        import asyncio

        from mcp.server.stdio import stdio_server

        server = build_server()

        async def _main() -> None:
            async with stdio_server() as (read_stream, write_stream):
                await server.run(read_stream, write_stream, server.create_initialization_options())

        if verbose:
            print(f"[{PRODUCT_NAME_TITLE}] MCP server starting on stdio", file=sys.stderr)

        asyncio.run(_main())
    except ImportError:
        print(
            "ERROR: mcp package not installed. Run: pip install mcp",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    run_server()
