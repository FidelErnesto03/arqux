"""REQ-10: enforce levels for learn-policies.cortex rules.

Every rule entry (``RUL`` executable hooks, ``GTE`` gates, ``POL`` entries
carrying an ``action``) MUST declare ``enforce:CODE|PROMPT|HUMAN``:

- ``CODE`` — executed automatically by the runtime as pre/post hooks; the
  LLM is never trusted to apply them.
- ``PROMPT`` — rendered into agent context (AGENTS.md / wake payload); the
  agent is expected to follow them but the runtime does not execute them.
- ``HUMAN`` — require an explicit human gate; the runtime surfaces them and
  blocks automatic application.

``evaluate_hooks(operation, content, project_root)`` runs the ``CODE`` rules
whose ``on`` glob matches *operation* and returns the violations found —
callers (the governed write path, cycle/task mutations) block on them.

Fail-closed on malformed rules: a rule entry without ``enforce`` produces
``ERR_MISSING_ENFORCE_LEVEL`` from ``validate_policy_file`` and makes the
file fail ``cortex_verify`` — the schema rejects it, exactly like an
undeclared sigil.
"""
from __future__ import annotations

import fnmatch
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..constants import ARQUX_DIR
from .learning._common import POLICY_FILENAME

logger = logging.getLogger(__name__)

ENFORCE_LEVELS = ("CODE", "PROMPT", "HUMAN")
ERR_MISSING_ENFORCE = "ERR_MISSING_ENFORCE_LEVEL"
ERR_INVALID_ENFORCE = "ERR_INVALID_ENFORCE_LEVEL"

# Rule sigils: entries that must carry an enforce level. THR/KNW/PRT/IDN are
# configuration, not rules.
RULE_SIGILS = ("RUL", "GTE")


# --- built-in CODE checks ---------------------------------------------------

_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"api[_-]?key\s*[:=]\s*['\"][A-Za-z0-9_-]{16,}", re.IGNORECASE),
)


def _check_secret_pattern(text: str) -> list[str]:
    """Return one finding per secret-looking match (kind + position)."""
    findings: list[str] = []
    for rx in _SECRET_PATTERNS:
        for m in rx.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            findings.append(f"secret-pattern '{rx.pattern[:24]}…' at line {line}")
    return findings


CODE_CHECKS = {"secret_pattern": _check_secret_pattern}


# --- rule model -------------------------------------------------------------


@dataclass
class EnforceRule:
    sigil: str
    name: str
    enforce: str
    on: str = "*"
    check: str = ""
    pattern: str = ""
    when: str = "pre"
    attrs: dict[str, Any] = field(default_factory=dict)

    def matches(self, operation: str, when: str) -> bool:
        if self.when not in (when, "both"):
            return False
        return any(
            fnmatch.fnmatch(operation, tok.strip())
            for tok in self.on.split("|")
            if tok.strip()
        )


def _rule_entries(doc: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """(sigil, name, attrs) for every rule entry in the parsed document."""
    out: list[tuple[str, str, dict[str, Any]]] = []
    for section in doc.get("sections", []):
        for entry in section.get("entries", []):
            sigil = str(entry.get("sigil", "")).upper()
            attrs = entry.get("attrs") if isinstance(entry.get("attrs"), dict) else {}
            name = str(entry.get("name", ""))
            if sigil in RULE_SIGILS and attrs and not name.endswith("_contract") or sigil == "POL" and attrs.get("action"):
                out.append((sigil, name, attrs))
    return out


def validate_policy_text(text: str) -> list[str]:
    """ERR_MISSING_ENFORCE_LEVEL / ERR_INVALID_ENFORCE_LEVEL diagnostics."""
    from ..cortex.reader import cortex_to_dict

    try:
        doc = cortex_to_dict(text)
    except Exception as exc:  # noqa: BLE001
        return [f"[PARSE] policy file is not readable CORTEX ({exc})"]
    errors: list[str] = []
    for sigil, name, attrs in _rule_entries(doc):
        level = str(attrs.get("enforce", "")).upper()
        ref = f"{sigil}:{name}"
        if not level:
            errors.append(f"[{ERR_MISSING_ENFORCE}] {ref} — rule must declare enforce:{'|'.join(ENFORCE_LEVELS)}")
        elif level not in ENFORCE_LEVELS:
            errors.append(f"[{ERR_INVALID_ENFORCE}] {ref} — enforce '{level}' not in {'|'.join(ENFORCE_LEVELS)}")
    return errors


def validate_policy_file(path: str | Path) -> list[str]:
    return validate_policy_text(Path(path).read_text(encoding="utf-8"))


def load_rules(project_root: Path) -> list[EnforceRule]:
    """Executable rules from the project's learn-policies.cortex.

    Entries missing/invalid enforce are skipped here — schema validation
    already flags them (ERR_MISSING_ENFORCE_LEVEL); the engine only runs
    well-formed CODE rules.
    """
    from ..cortex.reader import cortex_to_dict
    from .learning._common import _resolve_policy_path

    policy_path = _resolve_policy_path(project_root)
    if not policy_path.exists():
        return []
    try:
        doc = cortex_to_dict(policy_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        logger.warning("policy_engine: cannot parse %s", policy_path)
        return []
    rules: list[EnforceRule] = []
    for sigil, name, attrs in _rule_entries(doc):
        level = str(attrs.get("enforce", "")).upper()
        if level not in ENFORCE_LEVELS:
            continue
        rules.append(
            EnforceRule(
                sigil=sigil,
                name=name,
                enforce=level,
                on=str(attrs.get("on", "*")),
                check=str(attrs.get("check", "")),
                pattern=str(attrs.get("pattern", "")),
                when=str(attrs.get("when", "pre")).lower(),
                attrs=dict(attrs),
            )
        )
    return rules


def evaluate_hooks(
    operation: str,
    content: str,
    project_root: Path,
    *,
    when: str = "pre",
) -> list[str]:
    """Run CODE rules matching *operation*; return human-readable violations."""
    violations: list[str] = []
    for rule in load_rules(project_root):
        if rule.enforce != "CODE" or not rule.matches(operation, when):
            continue
        checker = CODE_CHECKS.get(rule.check)
        if checker is None:
            if rule.check:
                violations.append(
                    f"[POLICY_UNKNOWN_CHECK] {rule.sigil}:{rule.name} — no CODE check '{rule.check}'"
                )
            continue
        for finding in checker(content):
            violations.append(
                f"[POLICY_BLOCK] {rule.sigil}:{rule.name} on {operation}: {finding}"
            )
    return violations


def _project_root_for(path: Path) -> Path | None:
    """Project root owning a governed path (``<root>/.arqux/...``), else None."""
    if path.parent.name == ARQUX_DIR:
        return path.parent.parent
    for parent in path.parents:
        if parent.name == ARQUX_DIR:
            return parent.parent
    return None


__all__ = [
    "CODE_CHECKS",
    "ENFORCE_LEVELS",
    "ERR_INVALID_ENFORCE",
    "ERR_MISSING_ENFORCE",
    "EnforceRule",
    "evaluate_hooks",
    "load_rules",
    "validate_policy_file",
    "validate_policy_text",
    "POLICY_FILENAME",
]
