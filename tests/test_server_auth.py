"""Regression test: MCP server initialize response MUST NOT expose auth capability.

Per MCP spec 2025-06-18 §Authorization, stdio transport should NOT advertise
OAuth or custom auth capabilities. Credentials come from environment variables.
"""

from __future__ import annotations


def test_server_initialize_has_no_auth_capability() -> None:
    """Verify the MCP server initialization options do not advertise auth."""
    from arqux.server import build_server

    server = build_server()
    init_opts = server.create_initialization_options()

    caps = init_opts.capabilities
    # Top-level auth must not exist
    assert not hasattr(caps, "auth") or caps.auth is None
    # experimental must not contain auth
    experimental = getattr(caps, "experimental", None) or {}
    assert "auth" not in experimental, (
        "MCP server MUST NOT advertise auth capability in initialize response"
    )
