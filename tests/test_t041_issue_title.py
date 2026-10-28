"""CYCLE-12 / BLP-026 — the issue header is readable.

Issue 2026-10-26: ``issue.create`` used ``desc`` both as the title and as the
body, collapsing its line breaks. Every ticket was born with a 3.000-character
``# ISSUE:`` line repeated under ``## PROBLEM``. These tests pin the mapping
between handler parameters and file sections.
"""

from __future__ import annotations

from pathlib import Path

from arqux.handlers.issue import TITLE_MAX, create_issue
from arqux.permissions import PermissionContext

GOV = PermissionContext(agent_id="alfred", role="governor")

LONG_DESC = (
    "TIMELOG: el bloque de sesion abierto no tiene duracion y total_seconds "
    "informa 0 — el registro autoritativo no puede responder cuanto llevamos "
    "sin salir del MCP.\n\n"
    "## Que paso\n"
    "El Arquitecto pidio el timelog de la sesion en curso.\n\n"
    "## Evidencia\n"
    "duration_seconds: None y total_seconds: 0.\n"
)


def _header(text: str) -> str:
    return next(line for line in text.splitlines() if line.startswith("# ISSUE:"))


def _problem(text: str) -> str:
    return text.split("## PROBLEM", 1)[1].split("## CONTEXT", 1)[0].strip()


def test_explicit_title_keeps_header_short_and_body_whole(arqux_env) -> None:
    out = create_issue(
        "high", LONG_DESC, title="TIMELOG: el bloque abierto no tiene duracion",
        path=str(arqux_env.proj_root), ctx=GOV,
    )
    assert out.profile == "OUT-WORK", out
    text = Path(out.fields["file"]).read_text(encoding="utf-8")

    assert _header(text) == "# ISSUE: TIMELOG: el bloque abierto no tiene duracion"
    assert len(_header(text)) < TITLE_MAX
    assert _problem(text) == LONG_DESC.strip()


def test_title_defaults_to_the_first_line(arqux_env) -> None:
    desc = "TIMELOG: bloque abierto sin duracion\n\nCuerpo completo del reporte."
    out = create_issue("high", desc, path=str(arqux_env.proj_root), ctx=GOV)
    text = Path(out.fields["file"]).read_text(encoding="utf-8")

    assert _header(text) == "# ISSUE: TIMELOG: bloque abierto sin duracion"
    assert _problem(text) == desc.strip()


def test_long_first_line_is_truncated_without_a_title(arqux_env) -> None:
    out = create_issue("high", LONG_DESC, path=str(arqux_env.proj_root), ctx=GOV)
    text = Path(out.fields["file"]).read_text(encoding="utf-8")

    assert _header(text).endswith("…")
    assert len(_header(text)) <= len("# ISSUE: ") + TITLE_MAX
    assert _problem(text) == LONG_DESC.strip()
    assert out.fields.get("warning")


def test_long_first_line_is_truncated_with_ellipsis(arqux_env) -> None:
    one_line = "X" * 400
    out = create_issue("medium", one_line, path=str(arqux_env.proj_root), ctx=GOV)
    text = Path(out.fields["file"]).read_text(encoding="utf-8")

    header = _header(text)
    assert len(header) <= len("# ISSUE: ") + TITLE_MAX
    assert header.endswith("…")
    assert _problem(text) == one_line
    assert out.fields.get("warning")


def test_body_is_not_duplicated_in_the_header(arqux_env) -> None:
    out = create_issue("low", "Solo un titulo", path=str(arqux_env.proj_root), ctx=GOV)
    text = Path(out.fields["file"]).read_text(encoding="utf-8")

    assert _header(text) == "# ISSUE: Solo un titulo"
    assert _problem(text) == "Solo un titulo"
    assert text.count("Solo un titulo") == 2  # header + body, not three times


def test_slug_comes_from_the_title(arqux_env) -> None:
    out = create_issue(
        "medium", LONG_DESC, title="TIMELOG bloque abierto",
        path=str(arqux_env.proj_root), ctx=GOV,
    )
    assert out.fields["issue_id"].endswith("-timelog-bloque-abierto")


def test_empty_desc_is_rejected(arqux_env) -> None:
    out = create_issue("medium", "   ", path=str(arqux_env.proj_root), ctx=GOV)
    assert out.profile == "OUT-ERROR"
    assert out.fields["code"] == "INVALID_ARGS"
