"""Regression test for issue 2026-10-01 (arqux serve / call_tool).

Two defects on the transport layer:

1. call_tool rejected tool names forwarded with the server prefix
   (e.g. ``arqux_project_status``) because handlers are registered under
   the safe dotted→underscore name only.
2. The NOT_FOUND branch built ``TextContent(text=CortexOUT(...))`` without
   ``.to_text()`` — the client received an illegible Pydantic error
   ("Input should be a valid string") instead of the real NOT_FOUND
   message.

Fix: call_tool normalizes the prefix before lookup and the NOT_FOUND
branch serializes via ``.to_text()``.
"""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("mcp")

import arqux.server as server_mod  # noqa: E402
from arqux.constants import OUT_ERROR, PRODUCT_NAME  # noqa: E402
from arqux.handlers import HandlerSpec  # noqa: E402
from arqux.server import build_server  # noqa: E402


def _extract_call_tool(server: Any) -> Any:
    from mcp.types import CallToolRequest

    handler = server.request_handlers[CallToolRequest]
    return handler


def _content(result: Any) -> list[Any]:
    """Unwrap the lowlevel ServerResult → CallToolResult → content blocks."""
    content = getattr(result, "content", None)
    if content is None and hasattr(result, "root"):
        content = result.root.content
    return content


def _make_request(name: str, arguments: dict[str, Any] | None = None) -> Any:
    from mcp.types import CallToolRequest, CallToolRequestParams

    return CallToolRequest(
        method="tools/call",
        params=CallToolRequestParams(name=name, arguments=arguments or {}),
    )


@pytest.fixture()
def fake_registry(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Single no-op handler registered as 'test.echo' (safe name: test_echo)."""

    def echo(ctx: Any = None, **kwargs: Any) -> str:
        return "OK test.echo"

    spec = HandlerSpec(
        name="test.echo",
        fn=echo,
        description="echo handler",
        input_schema={"type": "object", "properties": {}},
    )
    monkeypatch.setattr(server_mod, "REGISTRY", {"test.echo": spec})
    return server_mod.REGISTRY


@pytest.mark.asyncio()
async def test_call_tool_accepts_prefixed_name(fake_registry: dict[str, Any]) -> None:
    """A tool name with the server prefix ('arqux_test_echo') must resolve."""
    server = build_server()
    call_tool = _extract_call_tool(server)
    result = await call_tool(_make_request(f"{PRODUCT_NAME}_test_echo"))
    content = _content(result)
    assert content and len(content) == 1
    text = content[0].text
    assert isinstance(text, str)
    assert "OK test.echo" in text


@pytest.mark.asyncio()
async def test_call_tool_accepts_plain_name(fake_registry: dict[str, Any]) -> None:
    """The plain safe name still works (no normalization side effects)."""
    server = build_server()
    call_tool = _extract_call_tool(server)
    result = await call_tool(_make_request("test_echo"))
    assert "OK test.echo" in _content(result)[0].text


@pytest.mark.asyncio()
async def test_call_tool_not_found_is_plain_text(fake_registry: dict[str, Any]) -> None:
    """NOT_FOUND must return a readable string, not a Pydantic dump."""
    server = build_server()
    call_tool = _extract_call_tool(server)
    result = await call_tool(_make_request(f"{PRODUCT_NAME}_definitely_missing"))
    content = _content(result)
    assert content and len(content) == 1
    text = content[0].text
    assert isinstance(text, str)
    assert OUT_ERROR in text
    assert "NOT_FOUND" in text
    assert "definitely_missing" in text
