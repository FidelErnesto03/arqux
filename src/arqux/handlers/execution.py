"""Execution mechanism (BLP-005).

The minimum real executor that lets a governance handler perform work and
report a verifiable outcome. Before this module, no handler could launch
anything: ``blueprint.execute`` and ``task.run`` marked their items
``executed`` using a string literal, which certified work that never ran.

Design constraints (BLP-005 §7):

* **Deny by default.** Only actions declared in ``ALLOWED_ACTIONS`` may run.
  An undeclared action fails explicitly and never degrades to a simulation.
* **Evidence is the outcome.** A successful execution returns a real
  artifact reference. Without one, the caller has nothing to certify.
* **The actor is carried through.** Result and evidence record both the
  ``agent_id`` and the ``role``, so a verifier can refuse to certify work
  produced by an executor.
* **No shell.** This is not a general command runner. Each action is a
  small, named, auditable operation.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..permissions import PermissionContext

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ExecutionError(Exception):
    """Raised when an action cannot be executed.

    ``code`` is a stable, machine-readable reason:

    ``not_declared``     the action is not in the allow list
    ``bad_params``       the action was declared but parameters are invalid
    ``outside_root``     the target escapes the permitted root
    ``failed``           the action ran and failed
    ``forbidden_role``   the calling role may not perform this action
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class ExecutionResult:
    """Outcome of one executed action.

    ``ok`` reflects reality, not intent. There is no ``simulated`` field:
    a caller that wants a dry run must ask for one and get ``dry_run=True``,
    never a fabricated success.
    """

    action: str
    ok: bool
    reason: str = ""
    artifact_path: str = ""
    artifact_sha256: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    actor: str = ""
    role: str = ""

    @property
    def evidence_ref(self) -> str:
        """Stable reference to the produced artifact, or empty if none."""
        if not self.artifact_path:
            return ""
        return f"{self.artifact_path}#sha256:{self.artifact_sha256}"

    def as_evidence(self) -> dict[str, Any]:
        """Render as an evidence record suitable for the evidence store."""
        return {
            "action": self.action,
            "ok": self.ok,
            "reason": self.reason,
            "artifact": self.artifact_path,
            "sha256": self.artifact_sha256,
            "actor": self.actor,
            "role": self.role,
            **({"detail": self.detail} if self.detail else {}),
        }


# ---------------------------------------------------------------------------
# Actions — deny by default
# ---------------------------------------------------------------------------

Action = Callable[[dict[str, Any]], tuple[str, str, dict[str, Any]]]
# action -> fn(params) -> (artifact_path, detail) ; raises on failure


def _resolve_within(path: str, root: Path | None) -> Path:
    """Resolve ``path`` and guarantee it stays inside ``root``.

    The allow list controls *what* can be done; this controls *where*.
    Without it, a declared ``write_file`` could target any absolute path
    on the host (BLP-005 HD-02, R-01).

    The comparison happens after ``resolve()`` so that ``..`` traversal and
    symlinks are collapsed first — a prefix check on the raw string would
    be trivially bypassed by ``../../etc/passwd``.

    Args:
        path: Requested path, absolute or relative to ``root``.
        root: Confining root. When ``None`` the path must already be inside
            the current working directory.

    Returns:
        The resolved, contained path.

    Raises:
        ExecutionError: ``outside_root`` when the target escapes.
    """
    base = (root or Path.cwd()).resolve()
    candidate = Path(path)
    target = (candidate if candidate.is_absolute() else base / candidate).resolve()
    if target != base and not target.is_relative_to(base):
        raise ExecutionError(
            "outside_root",
            f"ruta fuera de la raíz permitida {base}: {path}",
        )
    return target


def _write_file(params: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    path = params.get("path")
    content = params.get("content")
    if not isinstance(path, str) or not isinstance(content, str):
        raise ExecutionError("bad_params", "write_file requiere path y content str")
    target = _resolve_within(path, params.get("root"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return str(target), {"bytes": len(content.encode("utf-8"))}


def _append_file(params: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    path = params.get("path")
    content = params.get("content")
    if not isinstance(path, str) or not isinstance(content, str):
        raise ExecutionError("bad_params", "append_file requiere path y content str")
    target = _resolve_within(path, params.get("root"))
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(content)
    return str(target), {"bytes": len(content.encode("utf-8"))}


def _read_file(params: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    path = params.get("path")
    if not isinstance(path, str):
        raise ExecutionError("bad_params", "read_file requiere path str")
    target = _resolve_within(path, params.get("root"))
    if not target.exists():
        raise ExecutionError("failed", f"no existe: {target}")
    return str(target), {"bytes": target.stat().st_size}


#: The only actions this executor will perform. Anything absent from this
#: mapping is refused. This list is the whole security boundary (BLP-005 R-01).
ALLOWED_ACTIONS: dict[str, Action] = {
    "write_file": _write_file,
    "append_file": _append_file,
    "read_file": _read_file,
}

#: Roles permitted to invoke the executor at all.
EXECUTION_ROLES: frozenset[str] = frozenset({"governor", "executor"})


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def execute_action(
    action: str,
    params: dict[str, Any] | None = None,
    *,
    ctx: PermissionContext | None = None,
    root: Path | str | None = None,
) -> ExecutionResult:
    """Execute one declared action and return a verifiable result.

    Args:
        action: Name of the action. Must be in ``ALLOWED_ACTIONS``.
        params: Action parameters. A ``root`` key inside params sets the
            confining root; the explicit ``root`` argument overrides it.
        ctx: Calling context. Its ``agent_id`` and ``role`` are recorded
            in the result so a verifier can refuse to certify it.
        root: Directory the action may not escape. Defaults to the
            working directory. Callers should pass the project root.

    Returns:
        ``ExecutionResult`` with ``ok`` reflecting what actually happened.

    Raises:
        ExecutionError: the action is not declared, the parameters are
            invalid, the role may not execute, the target escapes ``root``,
            or the action failed. An undeclared action never falls back to
            a simulated success.
    """
    params = dict(params or {})
    actor = getattr(ctx, "agent_id", "") if ctx else ""
    role = getattr(ctx, "role", "") if ctx else ""

    # The explicit argument wins over a ``root`` inside params.
    effective_root = Path(root) if root is not None else params.pop("root", None)
    if effective_root is not None:
        params["root"] = Path(effective_root)

    if action not in ALLOWED_ACTIONS:
        raise ExecutionError(
            "not_declared",
            f"acción no declarada: {action!r}; permitidas: {sorted(ALLOWED_ACTIONS)}",
        )

    if role and role not in EXECUTION_ROLES:
        raise ExecutionError(
            "forbidden_role",
            f"rol {role!r} no puede ejecutar; permitidos: {sorted(EXECUTION_ROLES)}",
        )

    handler = ALLOWED_ACTIONS[action]
    artifact, detail = handler(params)

    digest = ""
    target = Path(artifact) if artifact else None
    if target and target.exists():
        digest = hashlib.sha256(target.read_bytes()).hexdigest()

    return ExecutionResult(
        action=action,
        ok=True,
        artifact_path=artifact,
        artifact_sha256=digest,
        detail=detail,
        actor=actor,
        role=role,
    )


def declared_actions() -> tuple[str, ...]:
    """Names of every action this executor will accept."""
    return tuple(sorted(ALLOWED_ACTIONS))
