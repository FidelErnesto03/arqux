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
from .execution import (
    authoritative_execution_key,
    bind_execution_key,
    mint_execution_key,
)
from .handlers import REGISTRY
from .permissions import (
    PermissionContext,
    PermissionDenied,
    apply_active_identity_role,
)


def _safe_name(name: str) -> str:
    """Convert a dotted handler name to an MCP-safe tool name."""
    return name.replace(".", "_")


_SESSION_PARAM_KEYS = ("session_ref", "session_id", "ses_ref", "session")
_PATH_PARAM_KEYS = ("project_dir", "project_root", "root", "project_path")


def _resolve_kwargs(handler: Any, kwargs: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Normalise alias params onto the names *handler* declares (E-2077).

    Session-family spellings (``session``, ``session_ref``, ``session_id``,
    ``ses_ref``), ``blueprint_id`` for ``bp_id`` and the path-family
    spellings map onto whichever name the signature accepts. Params that
    match nothing are returned as *unknown* so the caller gets
    INVALID_ARGS naming the expected signature instead of a cryptic
    TypeError or, worse, a silently ignored argument.
    """
    import inspect

    try:
        params = inspect.signature(handler).parameters
    except (TypeError, ValueError):
        return dict(kwargs), []
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return dict(kwargs), []

    declared = set(params) - {"ctx"}
    resolved = dict(kwargs)
    unknown: list[str] = []

    def _declared_of(family: tuple[str, ...]) -> str | None:
        return next((k for k in family if k in declared), None)

    for key in list(resolved):
        if key in declared:
            continue
        target: str | None = None
        if key in _SESSION_PARAM_KEYS:
            target = _declared_of(_SESSION_PARAM_KEYS[:-1])
        elif key == "blueprint_id":
            target = _declared_of(("bp_id",))
        elif key in _PATH_PARAM_KEYS:
            target = _declared_of(("path",))
        if target and target not in resolved:
            resolved[target] = resolved.pop(key)
        else:
            unknown.append(key)
    return resolved, unknown


def _wrap_handler(name: str, handler: Any) -> Any:
    """Wrap a handler with permission checks and CORTEX-OUT formatting."""

    async def wrapped(**kwargs: Any) -> str:
        ctx = PermissionContext.from_env()
        # E-2077: alias normalisation + loud unknown-param reporting.
        kwargs, unknown = _resolve_kwargs(handler, kwargs)
        if unknown:
            import inspect as _i

            expected = [
                p for p in _i.signature(handler).parameters if p != "ctx"
            ]
            return CortexOUT.profile(
                OUT_ERROR,
                f"ERROR code=INVALID_ARGS handler={name} "
                f"unknown={unknown} expected={expected}",
            ).to_text()
        # F6: the effective role follows the ACTIVE identity (context pointer),
        # not the static transport default. Without it a server started as
        # governor lets a switched-to auditor mutate state.
        apply_active_identity_role(ctx, handler=name)
        try:
            # T-020: forward the call args — ctx.check resolves signature
            # defaults for CONDITIONAL_MUTATING evaluation (e.g.
            # cortex.gc(force=True) still previews: dry_run defaults True).
            ctx.check(name, **kwargs)
        except PermissionDenied as exc:
            return CortexOUT.profile(
                OUT_ERROR,
                f"ERROR code={PERMISSION_DENIED} handler={name} reason={exc.reason}",
            ).to_text()

        try:
            try:
                result = await handler(**kwargs, ctx=ctx) if _is_coro(handler) else handler(**kwargs, ctx=ctx)
            except TypeError as exc:
                # Signature mismatch the alias pass could not resolve —
                # report the expected contract, not an internal error.
                import inspect as _i

                expected = [
                    p for p in _i.signature(handler).parameters if p != "ctx"
                ]
                return CortexOUT.profile(
                    OUT_ERROR,
                    f"ERROR code=INVALID_ARGS handler={name} "
                    f"reason={exc} expected={expected}",
                ).to_text()
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


def _schema_invalid_args(handler: str, exc: Any) -> str:
    """Compact INVALID_ARGS for a jsonschema.ValidationError.

    The SDK's own rejection (``validate_input=True``) returns an ``isError``
    result that leads MCP clients to dump the whole tool catalog — thousands
    of tokens per schema mistake, critical at tier LITE. Validating here and
    answering with a plain-text ``OUT-ERROR`` keeps the contract: code +
    field + expected value (valid enum or type) + example.
    """
    field = ".".join(str(p) for p in exc.absolute_path) or "(root)"
    if exc.validator == "enum":
        valid = list(exc.validator_value or [])
        example = f"{field}={valid[0]}" if valid else ""
        return (
            f"ERROR code=INVALID_ARGS handler={handler} field={field} "
            f"value={exc.instance!r} valid={valid} example={example}"
        )
    if exc.validator == "type":
        return (
            f"ERROR code=INVALID_ARGS handler={handler} field={field} "
            f"value={exc.instance!r} expected={exc.validator_value}"
        )
    return (
        f"ERROR code=INVALID_ARGS handler={handler} field={field} "
        f"reason={exc.message}"
    )


def _validate_arguments(handler: str, schema: dict[str, Any], arguments: dict[str, Any]) -> str | None:
    """Validate *arguments* against the handler's inputSchema.

    Returns a compact INVALID_ARGS string on failure, ``None`` when valid.
    """
    import jsonschema

    try:
        jsonschema.validate(instance=arguments, schema=schema)
    except jsonschema.ValidationError as exc:
        return _schema_invalid_args(handler, exc)
    return None


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
    # CYCLE-14 / BLP-001: the transport supplies the execution key. One MCP
    # server process is one execution; a host bridge may rebind it explicitly
    # for a different logical execution. Never derived from the agent identity.
    #
    # The guard must test the *authoritative* key, not `current_execution_key()`:
    # the latter falls back to a lazily-minted process key, so it is never None
    # and the transport would never actually bind one — every session mutation
    # then failed with SESSION_BINDING_REQUIRED.
    if authoritative_execution_key() is None:
        bind_execution_key(mint_execution_key())
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

    @server.call_tool(validate_input=False)
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        resolved = name
        if resolved not in handlers:
            # Some MCP clients forward the namespaced tool name
            # ("arqux_blueprint_update"). Normalize before lookup.
            stripped = name.removeprefix(f"{PRODUCT_NAME}_").removeprefix(
                f"{PRODUCT_NAME}."
            )
            if stripped in handlers:
                resolved = stripped
        if resolved not in handlers:
            return [
                TextContent(
                    type="text",
                    text=CortexOUT.profile(
                        OUT_ERROR, f"ERROR code=NOT_FOUND handler={name}"
                    ).to_text(),
                )
            ]
        # Schema validation lives here (not in the SDK) so a bad call gets a
        # compact INVALID_ARGS text instead of an isError that makes clients
        # re-dump the full tool catalog (issue 2026-11-02).
        dotted = safe_to_dotted.get(resolved, resolved)
        spec = REGISTRY.get(dotted)
        if spec is not None and spec.input_schema:
            invalid = _validate_arguments(
                dotted, spec.input_schema, arguments or {}
            )
            if invalid is not None:
                return [TextContent(type="text", text=invalid)]
        text = await handlers[resolved](**arguments)
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
