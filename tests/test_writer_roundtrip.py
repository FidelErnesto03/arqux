"""Round-trip tests for the CORTEX writer (G-12 / T-006).

Regression guard: re-writing an already-serialized (or corrupted)
.task artifact must NOT duplicate serialized-attr prefixes such as
``text=`` / ``criterion=``. See .arqux/issues/2026-07-19-writer-cortex-duplica.issue.md
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from arqux.core.state._project import parse_cortex_file
from arqux.core.state._render import write_cortex_pair


def _write_task(body: str, fm: dict | None = None) -> str:
    d = Path(tempfile.mkdtemp())
    fm = fm or {
        "id": "T-999", "status": "done", "governor": "alfred",
        "assignee": "jarvis", "priority": "high", "complexity": "standard",
        "cycle": "CYCLE-07", "created": "2026-07-19", "updated": "2026-07-19",
    }
    p = write_cortex_pair(d, "T-999", fm, body)
    return p[0].read_text()


def test_clean_roundtrip_no_duplication() -> None:
    body = (
        "# OBJ\nCorregir el handler session.handoff.\n\n"
        "# PRE\n- CYCLE-07 abierto\n\n"
        "# AC\n- AC-1: handoff respeta agent_id\n"
    )
    text = _write_task(body)
    assert 'OBJ:objective{text:"Corregir el handler session.handoff."}' in text
    assert 'CLAIM:ac1{criterion:"AC-1: handoff respeta agent_id"}' in text
    # No duplicated prefixes
    assert "text=text=" not in text
    assert "criterion=criterion=" not in text


def test_corrupted_roundtrip_idempotent() -> None:
    """A previously-corrupted artifact must be healed on re-write."""
    corrupted = (
        "$0\n\n"
        "$1: TASK\n\n"
        'WRK:task{id:"T-999", status:"done", assignee:"jarvis"}\n\n'
        "$2: OBJECTIVE\n\n"
        'OBJ:objective{text:"- text=- text=- text=Corregir el handler"}\n\n'
        "$5: ACCEPTANCE\n\n"
        'CLAIM:ac1{criterion:"criterion=criterion=AC-1 handoff respeta agent_id"}\n'
    )
    d = Path(tempfile.mkdtemp())
    src = d / "T-999.cortex"
    src.write_text(corrupted)
    fm, body = parse_cortex_file(src)
    out = write_cortex_pair(d / "out", "T-999", fm, body)[0].read_text()

    # Healed: single prefix only
    assert 'OBJ:objective{text:"Corregir el handler"}' in out
    assert 'CLAIM:ac1{criterion:"AC-1 handoff respeta agent_id"}' in out
    assert "text=text=" not in out
    assert "criterion=criterion=" not in out


def test_repeated_prefix_stripped() -> None:
    """Even deeply nested repetition collapses to a single value."""
    body = "# OBJ\ntext=text=text=Corregir\n"
    text = _write_task(body)
    m = re.search(r"OBJ:objective\{([^}]*)\}", text)
    assert m is not None
    assert m.group(1) == 'text:"Corregir"'
