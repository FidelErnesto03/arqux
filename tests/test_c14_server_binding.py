"""CYCLE-14 / BLP-001 — the transport must bind an authoritative execution key.

Without this, every session mutation over MCP (or the CLI) failed with
SESSION_BINDING_REQUIRED: the server's guard tested ``current_execution_key()``,
which lazily mints a process key and is therefore never ``None``, so the
authoritative key was never bound.
"""

from __future__ import annotations


def test_build_server_binds_the_authoritative_execution_key(arqux_env):
    from arqux import execution, server

    execution.set_process_execution_key(None)
    execution.bind_execution_key(None)
    assert execution.authoritative_execution_key() is None

    server.build_server()

    assert execution.authoritative_execution_key() is not None


def test_cli_call_binds_the_authoritative_execution_key(arqux_env):
    from arqux import cli, execution

    execution.set_process_execution_key(None)
    execution.bind_execution_key(None)
    assert execution.authoritative_execution_key() is None

    cli._call_handler("workspace.status", [f"path={arqux_env.ws_root}"])

    assert execution.authoritative_execution_key() is not None


def test_session_mutation_succeeds_once_the_transport_binds(arqux_env):
    """End-to-end: build_server then a session mutation is accepted."""
    from arqux import execution, server
    from arqux.handlers.session import context_set

    execution.set_process_execution_key(None)
    execution.bind_execution_key(None)
    server.build_server()

    out = context_set(project="test-proj", scope="CYCLE-TEST",
                      path=str(arqux_env.ws_root), ctx=None)
    assert out.profile != "OUT-ERROR", out.fields
    assert out.fields.get("session_ref")
