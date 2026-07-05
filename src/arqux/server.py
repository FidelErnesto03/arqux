"""MCP server entry point.

Exposes the 24 governance handlers as MCP tools. The server is transport-agnostic
(stdio by default) — the `mcp` package handles the wire protocol.

This module is intentionally thin: it imports the handler registry, registers
each handler as an MCP tool, and starts the server. All logic lives in the
handler modules.
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
            )

        try:
            result = await handler(**kwargs) if _is_coro(handler) else handler(**kwargs)
        except Exception as exc:  # noqa: BLE001
            return CortexOUT.profile(
                OUT_ERROR,
                f"ERROR code={INTERNAL_ERROR} handler={name} message={exc!r}",
            )

        return result.to_text() if hasattr(result, "to_text") else str(result)

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
        from mcp.server.stdio import stdio_server
        from mcp.types import TextContent, Tool
    except ImportError as exc:
        raise RuntimeError(
            "mcp package is required. Install with: pip install mcp"
        ) from exc

    server = Server(PRODUCT_NAME)
    tools: list[Tool] = []
    handlers: dict[str, Any] = {}

    for name, spec in REGISTRY.items():
        tool = Tool(
            name=name,
            description=spec.description,
            inputSchema=spec.input_schema,
        )
        tools.append(tool)
        handlers[name] = _wrap_handler(name, spec.fn)

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
