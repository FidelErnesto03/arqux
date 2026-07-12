"""IdentityManager — central resolver for agent identities (BLP-039).

The IdentityManager is the SINGLE source of truth for resolving agent identity
files (``<agent>.cortex``) in a workspace. It:

1. Resolves identities by name (Alfred, Jarvis, Seshat, Heimdall, ...)
2. Binds the identity to the session context (``session.context.set``)
3. Serves as the destination of behavioral elevation (BLP-038): when the
   Governor approves an elevation, ``elevate_to_identity()`` injects an
   ``AXM`` or ``LIM`` sigil into the agent's identity file.
4. Is extensible by design: the ``IIdentityResolver`` interface allows
   future ``UserIdentityResolver`` implementations without modifying the
   base class.

Architectural blocking rules (BLP-039 §16):
    - No component may modify ``.arqux/identities/<agent>.cortex`` without
      passing through ``IdentityManager.elevate_to_identity()``.
    - No session may start without a resolved identity. If ``--agent`` is
      not specified, ``alfred`` is used by default.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .constants import (
    ARQUX_DIR,
    IDENTITIES_DIR,
    CortexLevel,
)
from .formats import (
    CortexArtifact,
    read_cortex_artifact,
)

logger = logging.getLogger(__name__)


# --- Exceptions (BLP-039 §10) ----------------------------------------------

class IdentityNotFoundError(Exception):
    """Raised when ``<name>.cortex`` does not exist in identities dir."""

class InvalidContractTypeError(Exception):
    """Raised when ``contract_type`` is not AXIOM or LIMIT."""


# --- SessionContext --------------------------------------------------------

@dataclass
class SessionContext:
    """The result of binding an identity to a session.

    Carries the agent name, the resolved CortexArtifact, and the parsed
    AXM/LIM contracts extracted from ``$1 IDENTITY`` / ``$2 AXIOMS`` /
    ``$3 LIMITS``.
    """
    agent: str
    identity: CortexArtifact
    contracts: list[dict[str, str]] = field(default_factory=list)

    def contracts_by_type(self, sigil: str) -> list[dict[str, str]]:
        """Return contracts of a specific sigil type (``AXM`` or ``LIM``)."""
        return [c for c in self.contracts if c.get("sigil") == sigil]


# --- IIdentityResolver interface -------------------------------------------

class IIdentityResolver(Protocol):
    """Interface for identity resolution (BLP-039 §8).

    Implementations include ``IdentityManager`` (agent identities) today
    and ``UserIdentityResolver`` (future) for user identities.
    """

    def resolve(self, name: str) -> CortexArtifact: ...
    def bind_to_session(self, name: str) -> SessionContext: ...


# --- AXM/LIM sigil parser --------------------------------------------------

_CONTRACT_RE = re.compile(
    r"(?P<sigil>AXM|LIM):(?P<name>[^\s{]+)\s*\{(?P<attrs>[^}]*)\}",
    re.DOTALL,
)


def _parse_contract_attrs(attrs_text: str) -> dict[str, str]:
    """Parse a sigil attrs body into a dict (key → original-case value)."""
    result: dict[str, str] = {}
    for m in re.finditer(
        r'(\w+)\s*:\s*("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|[^,}\s]+)',
        attrs_text,
    ):
        key = m.group(1)
        val = m.group(2)
        if (val.startswith('"') and val.endswith('"')) or (
            val.startswith("'") and val.endswith("'")
        ):
            val = val[1:-1]
        result[key] = val
    return result


def _extract_contracts(payload: str) -> list[dict[str, str]]:
    """Extract all AXM/LIM sigils from a <agent>.cortex payload.

    Searches the entire payload (ARQX:artifact in $0.1 is metadata, not content).
    Returns a list of dicts with keys: sigil, name, status, body, ...
    """
    body = payload
    contracts: list[dict[str, str]] = []
    for m in _CONTRACT_RE.finditer(body):
        attrs = _parse_contract_attrs(m.group("attrs"))
        attrs["sigil"] = m.group("sigil")
        attrs["name"] = m.group("name")
        contracts.append(attrs)
    return contracts


# --- IdentityManager -------------------------------------------------------

#: Default agent when no ``--agent`` is specified.
DEFAULT_AGENT: str = "alfred"

#: Known agent names (used for validation messages, not enforcement).
KNOWN_AGENTS: tuple[str, ...] = (
    "alfred", "jarvis", "seshat", "heimdall",
    "executor", "governor", "auditor",
)


class IdentityManager:
    """Central resolver for agent identities (BLP-039).

    Usage::

        from arqux.identity import IdentityManager

        im = IdentityManager()  # uses default identities dir
        ctx = im.bind_to_session("jarvis")
        for axm in ctx.contracts_by_type("AXM"):
            print(axm["name"], axm.get("body"))

    For elevation (Governor-only flow)::

        im.elevate_to_identity(
            agent="jarvis",
            lesson_id="lsn-042",
            contract_type="AXIOM",
            pattern="Always use exponential backoff",
            evidence_ref="T-037-04",
        )
    """

    def __init__(
        self,
        *,
        identities_dir: Path | str | None = None,
        project_root: Path | str | None = None,
    ) -> None:
        """Initialize the IdentityManager.

        ``identities_dir`` takes precedence. If not given, falls back to
        ``<project_root>/.arqux/identities/`` (if project_root is set),
        then to the packaged identities directory shipped with ArqUX.
        """
        if identities_dir is not None:
            self.identities_dir = Path(identities_dir)
        elif project_root is not None:
            self.identities_dir = Path(project_root) / ARQUX_DIR / "identities"
        else:
            self.identities_dir = IDENTITIES_DIR

    # --- IIdentityResolver implementation ---

    def resolve(self, name: str) -> CortexArtifact:
        """Resolve an identity by agent name (BLP-039 §8 / §10).

        Returns a CortexArtifact with metadata.level == BEHAVIORAL.
        Raises IdentityNotFoundError if ``<name>.cortex`` does not exist.
        """
        if not name:
            raise IdentityNotFoundError("agent name must be non-empty")
        path = self.identities_dir / f"{name}.cortex"
        if not path.exists():
            raise IdentityNotFoundError(
                f"Identity file not found: {path}. "
                f"Known agents: {', '.join(KNOWN_AGENTS)}."
            )
        artifact = read_cortex_artifact(path)
        # Sanity: identities should be level 1 (BEHAVIORAL). If not, log.
        if artifact.metadata.level is not CortexLevel.BEHAVIORAL:
            logger.warning(
                "Identity %s has unexpected level %s (expected BEHAVIORAL=1)",
                name, artifact.metadata.level,
            )
        return artifact

    def bind_to_session(self, name: str) -> SessionContext:
        """Resolve the identity and bind it to the session context.

        Returns a SessionContext carrying the agent name, the loaded
        CortexArtifact, and the AXM/LIM contracts extracted from the
        identity file.

        Side effect: writes the agent binding into the workspace
        ``.arqux/context.cortex`` (when a workspace is available) so that
        other handlers can discover the active identity.
        """
        identity = self.resolve(name)
        contracts = _extract_contracts(identity.payload)
        ctx = SessionContext(agent=name, identity=identity, contracts=contracts)

        # Best-effort session binding — if we're inside a workspace, write
        # the agent into the context.cortex pointer. We DO NOT use the
        # `session.context.set` handler directly to avoid the meta-brain
        # project lookup (which would fail outside a full project setup).
        # Instead, we update the context.cortex file if it exists.
        try:
            ws_context = self.identities_dir.parent / "context.cortex"
            if ws_context.exists():
                self._update_context_agent(ws_context, name)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Could not update session context: %s", exc)

        return ctx

    def list_identities(self) -> list[str]:
        """Return a sorted list of identity names (file stems)."""
        if not self.identities_dir.exists():
            return []
        return sorted(
            p.stem for p in self.identities_dir.glob("*.cortex")
            if not p.name.endswith(".lessons.cortex")
        )

    # --- Behavioral elevation (BLP-038 integration) ---

    def elevate_to_identity(
        self,
        agent: str,
        lesson_id: str,
        contract_type: str,
        *,
        pattern: str = "",
        evidence_ref: str = "",
        body: str | None = None,
    ) -> dict[str, Any]:
        """Inject an AXM or LIM sigil into ``<agent>.cortex`` (BLP-039 §10).

        This is the ONLY sanctioned way to mutate an identity file. It is
        called by the Governor (Alfred) after approving an elevation draft
        from BLP-038.

        Parameters
        ----------
        agent : str
            The agent whose identity will receive the new contract.
        lesson_id : str
            The sigil name to use (e.g. ``lsn-042``).
        contract_type : str
            ``"AXIOM"`` → writes ``AXM`` | ``"LIMIT"`` → writes ``LIM``.
        pattern : str
            The lesson pattern (becomes the ``body`` attribute).
        evidence_ref : str
            Optional reference to the originating evidence.

        Returns
        -------
        dict
            ``{agent, sigil, name, path, written: True}``
        """
        if not agent:
            raise IdentityNotFoundError("agent name must be non-empty")
        contract_norm = contract_type.upper().strip()
        if contract_norm == "AXIOM":
            sigil = "AXM"
        elif contract_norm == "LIMIT":
            sigil = "LIM"
        else:
            raise InvalidContractTypeError(
                f"contract_type must be 'AXIOM' or 'LIMIT'; got {contract_type!r}"
            )

        path = self.identities_dir / f"{agent}.cortex"
        if not path.exists():
            raise IdentityNotFoundError(
                f"Identity file not found: {path}. "
                f"Known agents: {', '.join(KNOWN_AGENTS)}."
            )

        # Build the sigil entry to inject.
        body_text = body if body is not None else pattern
        attrs_parts = [
            f'name:"{lesson_id}"',
            'status:"current"',
            f'body:"{body_text}"',
            f'source_lesson:"{lesson_id}"',
        ]
        if evidence_ref:
            attrs_parts.append(f'evidence_ref:"{evidence_ref}"')
        attrs_body = ", ".join(attrs_parts)
        new_entry = f"{sigil}:{lesson_id}{{{attrs_body}}}"

        # Find a home for it. Try $2: AXIOMS (for AXM) or $3: LIMITS (for LIM).
        # If the section doesn't exist, append to $1: IDENTITY as a fallback.
        content = path.read_text(encoding="utf-8")
        target_section = "$2" if sigil == "AXM" else "$3"

        new_content = self._inject_into_section(
            content, target_section, new_entry, fallback_section="$1",
        )
        path.write_text(new_content, encoding="utf-8")

        logger.info(
            "IdentityManager.elevate_to_identity: injected %s:%s into %s",
            sigil, lesson_id, path,
        )

        return {
            "agent": agent,
            "sigil": sigil,
            "name": lesson_id,
            "path": str(path),
            "written": True,
        }

    # --- Internals ---

    def _update_context_agent(self, context_path: Path, agent: str) -> None:
        """Update the ``agent=`` field in an existing context.cortex file."""
        text = context_path.read_text(encoding="utf-8")
        if re.search(r'\bagent="[^"]*"', text):
            new_text = re.sub(r'\bagent="[^"]*"', f'agent="{agent}"', text)
        else:
            # No agent field — append it to the CTX line.
            new_text = re.sub(
                r"(CTX:\S+ [^\n]+)",
                rf'\1 agent="{agent}"',
                text,
                count=1,
            )
        context_path.write_text(new_text, encoding="utf-8")

    def _inject_into_section(
        self,
        content: str,
        section_id: str,
        new_entry: str,
        *,
        fallback_section: str = "$1",
    ) -> str:
        """Inject ``new_entry`` as a new line in the ``section_id`` section.

        If the section doesn't exist, append it after ``fallback_section``
        (creating a new section block).
        """
        # Try to find the target section.
        # Pattern: $N[: TITLE]\n<body>
        pattern = re.compile(
            r"(^\s*\$" + section_id.lstrip("$") + r"(?:\s*:?\s*[A-Z_]*)?\s*\n)"
            r"((?:(?!\s*\$\d+\s*:?\s*[A-Z_]*\s*$).*\n)*)",
            re.MULTILINE,
        )
        m = pattern.search(content)
        if m:
            # Insert the new entry at the end of the section body.
            header = m.group(1)
            body = m.group(2)
            new_body = body.rstrip() + "\n" + new_entry + "\n"
            return content[:m.start()] + header + new_body + content[m.end():]

        # Section not found — create it after the fallback section.
        fallback_pattern = re.compile(
            r"(^\s*\$" + fallback_section.lstrip("$") + r"(?:\s*:?\s*[A-Z_]*)?\s*\n)"
            r"((?:(?!\s*\$\d+\s*:?\s*[A-Z_]*\s*$).*\n)*)",
            re.MULTILINE,
        )
        fm = fallback_pattern.search(content)
        if fm:
            section_title = "AXIOMS" if section_id == "$2" else "LIMITS"
            new_section = f"\n{section_id}: {section_title}\n{new_entry}\n"
            insert_pos = fm.end()
            return content[:insert_pos] + new_section + content[insert_pos:]

        # Last resort: append at the end.
        section_title = "AXIOMS" if section_id == "$2" else "LIMITS"
        return content.rstrip() + f"\n\n{section_id}: {section_title}\n{new_entry}\n"
