"""Execution identity for ArqUX governance handlers (CYCLE-14 / BLP-001).

The agent identity (``ARQUX_AGENT_ID`` -> ``PermissionContext.agent_id``)
describes *who* is acting. It does not describe *which execution* is acting.
Two concurrent executions of the same agent in the same project share the
identity and would otherwise share the same session: ``session.resume``,
``session.status`` and ``session.close`` would pick the newest entry of a flat
list and one execution could close the other's session.

This module supplies the missing key. It is resolved, in order, from:

1. ``ARQUX_EXECUTION_KEY`` — set explicitly by the host/transport.
2. A ``contextvars.ContextVar`` bound by the transport (``server.py`` binds one
   key per server process; a host bridge may rebind it per logical execution).
3. A process-scoped default minted on first use, so a library/CLI call still
   has a stable key. Set ``ARQUX_STRICT_EXECUTION=1`` to disable this default:
   then a keyless caller is rejected with ``SESSION_BINDING_REQUIRED`` instead
   of silently sharing the process key.

The default is deliberately a *transport* concept, not an identity concept: it
never changes which agent is acting and it is never derived from the agent name.
"""

from __future__ import annotations

import os
import uuid
from contextvars import ContextVar, Token

ENV_EXECUTION_KEY = "ARQUX_EXECUTION_KEY"
ENV_STRICT_EXECUTION = "ARQUX_STRICT_EXECUTION"
ENV_ALLOW_IMPLICIT = "ARQUX_ALLOW_IMPLICIT_EXECUTION"

_EXECUTION_KEY: ContextVar[str | None] = ContextVar("arqux_execution_key", default=None)
_PROCESS_KEY: str | None = None

KEY_PREFIX = "exec"


def strict_execution_binding() -> bool:
    """True when a keyless caller must be rejected instead of using the default.

    ``ARQUX_STRICT_EXECUTION=1`` additionally refuses the implicit process key,
    so a handler that needs an authoritative execution binding rejects instead
    of minting one. The default is a real limitation, not an oversight: without
    this the fallback key is indistinguishable from a transport-provided one.
    """
    return os.environ.get(ENV_STRICT_EXECUTION, "0") == "1"


def implicit_execution_allowed() -> bool:
    """True when the implicit process key may back a mutating session call.

    Off by default. A process-scoped key cannot tell two executions apart, so
    ``session.context.set`` / ``session.close`` refuse it with
    ``SESSION_BINDING_REQUIRED`` unless the operator opts in explicitly.
    """
    return os.environ.get(ENV_ALLOW_IMPLICIT, "0") == "1"


def mint_execution_key(prefix: str = KEY_PREFIX) -> str:
    """Return a fresh, opaque execution key."""
    return f"{prefix}-{uuid.uuid4().hex}"


def bind_execution_key(key: str | None) -> Token:
    """Bind *key* as the execution key for the current context.

    Returns the ``contextvars`` token needed by :func:`reset_execution_key`.
    """
    global _PROCESS_KEY
    if key:
        _PROCESS_KEY = key
    return _EXECUTION_KEY.set(key)


def reset_execution_key(token: Token) -> None:
    """Undo a previous :func:`bind_execution_key`."""
    _EXECUTION_KEY.reset(token)


def set_process_execution_key(key: str | None) -> None:
    """Set the process-scoped fallback key without touching the context."""
    global _PROCESS_KEY
    _PROCESS_KEY = key


def current_execution_key() -> str | None:
    """Resolve the execution key for the caller, or ``None`` when unbound.

    ``None`` means *no unambiguous execution binding*; callers that mutate
    session state must reject with ``SESSION_BINDING_REQUIRED`` rather than
    fall back to a foreign session.
    """
    return authoritative_execution_key() or _process_key()


def authoritative_execution_key() -> str | None:
    """The execution key *only* when it was supplied by the transport.

    Environment or explicitly bound context. The implicit process key is
    excluded on purpose: it identifies the process, not the execution, so a
    mutation must not be attributed to it by default.
    """
    env_key = os.environ.get(ENV_EXECUTION_KEY)
    if env_key:
        return env_key

    ctx_key = _EXECUTION_KEY.get()
    if ctx_key:
        return ctx_key

    if strict_execution_binding() or not implicit_execution_allowed():
        return None

    return _PROCESS_KEY


def _process_key() -> str:
    global _PROCESS_KEY
    if _PROCESS_KEY is None:
        _PROCESS_KEY = mint_execution_key()
    return _PROCESS_KEY


def ensure_execution_key() -> str:
    """Bind and return a process execution key, minting one if needed."""
    key = current_execution_key()
    if key is None:
        key = mint_execution_key()
        bind_execution_key(key)
    return key
