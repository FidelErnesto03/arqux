"""REQ-13: authoritative Journal for multi-workspace sync.

The journal (``<workspace>/.arqux/journal/journal.cortex``) is the single
ordered log that reconciles ``.cortex`` policy deltas pushed by multiple
workspaces:

- ``push_delta`` applies a delta only when the pusher's ``base_version``
  equals the journal's current version — optimistic locking. A stale base
  is rejected with ``ERR_CONFLICT_VERSION`` for human triage.
- ``pull_policy`` renders the journal's authoritative ``$3 POLICY`` section
  so a workspace can merge it into ``learn-policies.cortex``.

Resolution is deterministic: entries are applied in journal order; within
one version, same-named rule entries are replaced by the later delta.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from .constants import ARQUX_DIR

JOURNAL_REL = f"{ARQUX_DIR}/journal/journal.cortex"

_ENTRY_RX = re.compile(r"^([A-Z]{2,4}):(\w+)\{")
_RULE_SIGILS = ("RUL", "GTE", "POL", "THR", "PRT", "KNW")
_VERSION_RX = re.compile(r"JRN:journal\{[^}]*version:(\d+)")

_CONTRACTS = [
    'ARQX:arqx_contract{type:"attrs", weight:"M", focus:"value", fields:"value:any?", desc:"ArqUX artifact metadata", open:true}',
    'JRN:jrn_contract{type:"attrs", weight:"H", focus:"value", fields:"value:any?", desc:"Journal head", open:true}',
    'DLT:dlt_contract{type:"attrs", weight:"M", focus:"value", fields:"value:any?", desc:"Applied delta", open:true}',
    'RUL:rul_contract{type:"attrs", weight:"H", focus:"value", fields:"value:any?", desc:"Enforce rule", open:true}',
    'GTE:gel_contract{type:"attrs", weight:"H", focus:"value", fields:"value:any?", desc:"Mutation gate", open:true}',
    'POL:pol_contract{type:"attrs", weight:"M", focus:"value", fields:"value:any?", desc:"Policy rule", open:true}',
    'THR:thr_contract{type:"attrs", weight:"M", focus:"value", fields:"value:any?", desc:"Thresholds", open:true}',
    'PRT:prt_contract{type:"attrs", weight:"H", focus:"value", fields:"value:any?", desc:"Protected targets", open:true}',
    'KNW:knw_contract{type:"attrs", weight:"B", focus:"value", fields:"value:any?", desc:"Config entry", open:true}',
]

_HEAD = [
    "$0",
    "",
    "$0:format{cortex:1.0, encoding:UTF-8}",
    "",
    *_CONTRACTS,
    "",
    "$19: ARQUX METADATA",
    'ARQX:artifact{level:0, name:"journal", usage:"sync", kind:"native"}',
]


def _journal_path(workspace_root: Path) -> Path:
    return Path(workspace_root) / JOURNAL_REL


def _load(path: Path) -> tuple[int, list[str], list[str]]:
    """(version, delta_lines, policy_lines) from the journal."""
    if not path.exists():
        return 0, [], []
    version = 0
    deltas: list[str] = []
    policy: list[str] = []
    section = None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("$"):
            section = stripped
            continue
        vm = _VERSION_RX.search(stripped)
        if vm:
            version = int(vm.group(1))
        if section and section.startswith("$2") and _ENTRY_RX.match(stripped):
            deltas.append(stripped)
        elif section and section.startswith("$3") and _ENTRY_RX.match(stripped):
            policy.append(stripped)
    return version, deltas, policy


def _write(path: Path, version: int, deltas: list[str], policy: list[str]) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        *_HEAD,
        "",
        "$1: JOURNAL",
        f'JRN:journal{{version:{version}, deltas:{len(deltas)}, rules:{len(policy)}, updated:"{now}"}}',
        "",
        "$2: DELTAS",
        *deltas,
        "",
        "$3: POLICY",
        *policy,
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def journal_version(workspace_root: Path) -> int:
    return _load(_journal_path(workspace_root))[0]


def push_delta(
    workspace_root: Path,
    workspace_id: str,
    delta_text: str,
    base_version: int,
) -> dict:
    """Apply a policy delta if *base_version* is current (optimistic lock).

    Returns ``{"applied": True, "version": n}`` or
    ``{"applied": False, "error": "ERR_CONFLICT_VERSION", ...}``.
    """
    path = _journal_path(workspace_root)
    version, deltas, policy = _load(path)
    if base_version != version:
        return {
            "applied": False,
            "error": "ERR_CONFLICT_VERSION",
            "detail": f"journal is at version {version}, delta claims base {base_version} — human triage required",
            "current_version": version,
        }

    new_rules = [
        l.strip()
        for l in delta_text.splitlines()
        if (m := _ENTRY_RX.match(l.strip())) and m.group(1) in _RULE_SIGILS
    ]
    if not new_rules:
        return {"applied": False, "error": "ERR_EMPTY_DELTA",
                "detail": "delta contains no rule entries (RUL|GTE|POL|THR|PRT|KNW)"}

    # Deterministic merge: same-named rules are replaced by this delta.
    incoming = {_ENTRY_RX.match(l).group(2) for l in new_rules}
    policy = [l for l in policy if _ENTRY_RX.match(l).group(2) not in incoming]
    policy.extend(new_rules)

    seq = len(deltas) + 1
    digest = hashlib.sha256(delta_text.encode("utf-8")).hexdigest()[:16]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    deltas.append(
        f'DLT:{workspace_id.lower()}_{seq}{{workspace:"{workspace_id}", '
        f'base_version:{version}, new_version:{version + 1}, '
        f'rules:{len(new_rules)}, sha256:"{digest}", applied:"{now}"}}'
    )
    _write(path, version + 1, deltas, policy)
    return {"applied": True, "version": version + 1, "rules": len(new_rules)}


def pull_policy(workspace_root: Path) -> str:
    """The authoritative policy section, as mergeable cortex text."""
    version, _, policy = _load(_journal_path(workspace_root))
    return "\n".join(
        [
            f"# journal policy — version {version}",
            *policy,
            "",
        ]
    )


__all__ = ["journal_version", "pull_policy", "push_delta", "JOURNAL_REL"]
