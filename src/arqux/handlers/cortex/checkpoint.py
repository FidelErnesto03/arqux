"""cortex.checkpoint handler (BLP-014 / CYCLE-05).

Persists the agent's working state (WRK:current) as a single CORTEX
line in brain.cortex $8.  session.bootstrap reads it back so the agent
can resume exactly where it left off between turns.

Format:  WRK:current{fcs:, obj:, tasks:, state:, last_turn:}
"""

from __future__ import annotations

import re
from pathlib import Path

from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ...pulse import append_pulse_to_brain, next_pulse_event_id
from ...state import crud_read, crud_update, find_project_root

_KEY_COLON_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\s*:")


def checkpoint_handler(
    content: str,
    *,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Persist WRK:current in brain.cortex $8.

    Accepts ``content`` as a CORTEX entry string:
        fcs:..., obj:..., tasks:..., state:..., last_turn:...
    or a raw CORTEX line:
        WRK:current{fcs:..., obj:..., tasks:..., state:..., last_turn:...}

    If the brain has an existing WRK:current entry it is replaced
    (cortex.patch semantics — single-line replacement).  If it does
    not exist a new entry is created.
    """
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    brain_path = root / "brain.cortex"
    if not brain_path.exists():
        return CortexOUT.error("brain.cortex not found", code="NOT_FOUND")

    agent = (ctx or PermissionContext.from_env()).agent_id

    # Normalise content — accept both raw WRK:current{...} and key:value
    body = content.strip()
    if body.startswith("WRK:current{"):
        body = body[len("WRK:current{"):]
        if body.endswith("}"):
            body = body[:-1]
    body = body.strip()

    # Parse key:value pairs — ',' or newline separators only, ignoring
    # separators inside [...] list values (a closing ']' also ends the
    # value: the next key: starts a new entry).
    # ';' is NOT a separator: values may legitimately contain it;
    # glued keys are caught by the hint below instead.
    parts: dict[str, str] = {}
    for pair in _split_entries(body):
        pair = pair.strip()
        if ":" not in pair:
            continue
        k, _, v = pair.partition(":")
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
            v = v[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        parts[k.strip()] = v.strip()

    # Detect glued known keys left inside values (e.g. wrong separator)
    glued = [
        k for k in ("fcs", "obj", "tasks", "state", "last_turn")
        if k not in parts and re.search(rf"\b{k}\s*:", body)
    ]

    now = _now_iso()
    value = {
        "fcs": parts.get("fcs", ""),
        "obj": parts.get("obj", ""),
        "tasks": parts.get("tasks", ""),
        "state": parts.get("state", "active"),
        "last_turn": now,
    }

    # Try crud_update first (if entry exists), fall back to crud_add-like write
    try:
        existing = crud_read(brain_path, "$8/WRK:current")
        if existing.get("entries"):
            crud_update(
                brain_path, "$8/WRK:current",
                set_={"fcs": value["fcs"], "obj": value["obj"], "tasks": value["tasks"], "state": value["state"], "last_turn": now},
                force=True,
            )
        else:
            # Write as raw CORTEX line
            _write_wrk_entry(brain_path, value)
    except Exception:
        _write_wrk_entry(brain_path, value)

    # Record meta-event
    try:
        event_id = next_pulse_event_id(root)
        append_pulse_to_brain(
            root, event_id=event_id, task_id="-",
            kind="checkpoint", agent=agent,
            payload=f"cortex.checkpoint ok fcs={value['fcs'][:40]} obj={value['obj'][:40]}",
        )
    except Exception:
        pass

    fields = {
        "fcs": value["fcs"][:60],
        "obj": value["obj"][:60],
        "tasks": value["tasks"][:60],
        "state": value["state"],
    }
    if glued:
        fields["hint"] = (
            f"unparsed key(s) {glued} — expected format "
            "fcs:...,obj:...,tasks:...,state:... (separators: ',' ';' newline)"
        )
    return CortexOUT.work("cortex.checkpoint ok", **fields)


def _split_entries(body: str) -> list[str]:
    """Split checkpoint body on top-level ','/'\n', respecting [...] depth.

    A comma inside an unclosed '[' does not split; a closing ']' returns
    to depth 0 and the next ``key:`` starts a new entry even without a
    separator.
    """
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    i = 0
    while i < len(body):
        c = body[i]
        if c == "[":
            depth += 1
            buf.append(c)
            i += 1
        elif c == "]" and depth:
            depth -= 1
            buf.append(c)
            i += 1
            if depth == 0:
                j = i
                while j < len(body) and body[j].isspace():
                    j += 1
                if _KEY_COLON_RE.match(body, j):
                    parts.append("".join(buf))
                    buf = []
                    i = j
        elif c in ",\n" and depth == 0:
            parts.append("".join(buf))
            buf = []
            i += 1
        else:
            buf.append(c)
            i += 1
    if buf:
        parts.append("".join(buf))
    return parts


def _write_wrk_entry(brain_path: Path, value: dict[str, str]) -> None:
    """Write WRK:current via cortex.patch (CODEC-CORTEX)."""
    from ...state import cortex_write

    def _q(v: str) -> str:
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'

    line = (
        f"WRK:current{{fcs:{_q(value['fcs'])},obj:{_q(value['obj'])},"
        f"tasks:{_q(value['tasks'])},state:{_q(value['state'])},"
        f"last_turn:{_q(value['last_turn'])}}}\n"
    )
    text = brain_path.read_text(encoding="utf-8")

    if "$8: ACTIVE_CONTEXT" in text:
        # Replace existing WRK:current line
        lines = text.splitlines()
        new_lines = []
        replaced = False
        for ln in lines:
            if ln.strip().startswith("WRK:current"):
                new_lines.append(line.rstrip())
                replaced = True
            else:
                new_lines.append(ln)
        if not replaced:
            new_lines.append(line.rstrip())
        cortex_write(path=str(brain_path), content="\n".join(new_lines) + "\n")
    else:
        cortex_write(path=str(brain_path), content=text.rstrip() + f"\n\n$8: ACTIVE_CONTEXT\n\n{line}")


def _now_iso() -> str:
    import time as _time
    return _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())


handler_schemas = [
    {
        "name": "cortex.checkpoint",
        "fn": checkpoint_handler,
        "description": (
            "Persist the agent's working state (WRK:current) as a single "
            "CORTEX line in brain.cortex §8. session.bootstrap reads it "
            "back so the agent can resume where it left off. "
            "Accepts content as key:value pairs (fcs:,obj:,tasks:,state:)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "CORTEX content: fcs:...,obj:...,tasks:...,state:... or WRK:current{...}",
                },
                "path": {"type": "string", "description": "Path to project root."},
            },
            "required": ["content"],
        },
    },
]
