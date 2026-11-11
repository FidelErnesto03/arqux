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


# ---------------------------------------------------------------------------
# Compact INVALID_ARGS (issue 2026-11-02)
#
# The SDK's validate_input=True rejected schema violations with an isError
# result; MCP clients respond by re-dumping the entire tool catalog (thousands
# of tokens, critical at tier LITE). call_tool now validates itself and
# answers with a compact plain-text INVALID_ARGS naming field + expected.
# ---------------------------------------------------------------------------


@pytest.fixture()
def schema_registry(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Handler with an enum + a required param + a typed param."""

    def picky(
        ctx: Any = None,
        status: str = "open",
        limit: int = 10,
        mode: str = "a",
    ) -> str:
        return f"OK picky status={status} limit={limit} mode={mode}"

    spec = HandlerSpec(
        name="test.picky",
        fn=picky,
        description="picky handler",
        input_schema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["open", "closed"]},
                "limit": {"type": "integer"},
                "mode": {"type": "string"},
            },
            "required": ["status"],
        },
    )
    monkeypatch.setattr(server_mod, "REGISTRY", {"test.picky": spec})
    return server_mod.REGISTRY


@pytest.mark.asyncio()
async def test_schema_enum_error_is_compact(schema_registry: dict[str, Any]) -> None:
    """Bad enum value → compact INVALID_ARGS with valid values + example."""
    server = build_server()
    call_tool = _extract_call_tool(server)
    result = await call_tool(
        _make_request("test_picky", {"status": "bogus", "limit": 5})
    )
    content = _content(result)
    assert content and len(content) == 1
    text = content[0].text
    assert "INVALID_ARGS" in text
    assert "test.picky" in text
    assert "status" in text
    assert "open" in text and "closed" in text
    # No isError flag — plain text content only.
    assert getattr(result, "isError", False) in (False, None)


@pytest.mark.asyncio()
async def test_schema_type_error_is_compact(schema_registry: dict[str, Any]) -> None:
    """Wrong JSON type → compact INVALID_ARGS naming expected type."""
    server = build_server()
    call_tool = _extract_call_tool(server)
    result = await call_tool(
        _make_request("test_picky", {"status": "open", "limit": "five"})
    )
    text = _content(result)[0].text
    assert "INVALID_ARGS" in text
    assert "limit" in text
    assert "integer" in text


@pytest.mark.asyncio()
async def test_schema_missing_required_is_compact(schema_registry: dict[str, Any]) -> None:
    """Missing required param → compact INVALID_ARGS."""
    server = build_server()
    call_tool = _extract_call_tool(server)
    result = await call_tool(_make_request("test_picky", {"limit": 3}))
    text = _content(result)[0].text
    assert "INVALID_ARGS" in text
    assert "status" in text


@pytest.mark.asyncio()
async def test_valid_call_still_dispatches(schema_registry: dict[str, Any]) -> None:
    """A schema-valid call reaches the handler unchanged."""
    server = build_server()
    call_tool = _extract_call_tool(server)
    result = await call_tool(
        _make_request("test_picky", {"status": "closed", "limit": 2, "mode": "b"})
    )
    text = _content(result)[0].text
    assert "OK picky status=closed limit=2 mode=b" in text
