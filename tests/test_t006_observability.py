"""Regression tests for T-006 — observability: unambiguous write metrics
and a discoverable brain section schema."""

from __future__ import annotations

from pathlib import Path

from arqux.handlers.cortex import entry_add_handler
from arqux.permissions import PermissionContext

_CONTEXT = PermissionContext(agent_id="test", role="governor")

_SAMPLE = """$0

# -- $0: TEST GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# LNG   | lesson     | attrs      | M | Episodic       | Learned lesson

$7: LESSONS

LNG:existing{type:"process", cause:"c", lesson:"l", prevention:"p"}
"""


def test_entry_add_reports_entry_bytes_separate_from_file_bytes(tmp_path: Path) -> None:
    """bytes_written/entry_bytes = entry size; file_bytes = whole file size."""
    f = tmp_path / "brain.cortex"
    f.write_text(_SAMPLE)
    value = 'type:"process", cause:"c", lesson:"a specific lesson body", prevention:"p"'
    out = entry_add_handler(str(f), "$7", "LNG", "metric_test", value, force=True, ctx=_CONTEXT)
    assert out.profile == "OUT-WORK", str(out.fields)

    entry_bytes = out.fields["entry_bytes"]
    file_bytes = out.fields["file_bytes"]
    assert out.fields["bytes_written"] == entry_bytes
    assert 0 < entry_bytes < file_bytes
    # entry size matches the rendered entry text
    assert entry_bytes == len(
        f"LNG:{out.fields['name']}{{{value}}}".encode()
    )
    # file_bytes matches the actual file size on disk
    assert file_bytes == len(f.read_text(encoding="utf-8").encode("utf-8"))


def test_cortex_ref_sections_matches_brain_template(tmp_path: Path) -> None:
    """cortex.ref(sections=true) without sigil returns the standard
    $N → title → sigils map matching templates/brain.cortex."""
    import re

    from arqux.handlers.cortex.ref import ref_handler

    template = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "arqux"
        / "templates"
        / "brain.cortex"
    )
    expected: dict[str, dict] = {}
    for line in template.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\$(\d+):\s*(\w[\w ]*)$", line.strip())
        if not m:
            continue
        sid, title = f"${m.group(1)}", m.group(2).strip()
        expected[sid] = {"title": title, "sigils": []}

    out = ref_handler(sections=True, ctx=_CONTEXT)
    assert out.profile == "OUT-WORK"
    sections = out.fields["sections"]
    assert "$0" in sections and sections["$0"]["title"] == "GLOSSARY"
    titled = {sid: spec for sid, spec in sections.items() if sid != "$0"}
    assert set(titled) == set(expected), "section ids drifted from template"
    for sid, spec in expected.items():
        assert sections[sid]["title"].upper() == spec["title"].upper(), (
            f"{sid} title drifted: {sections[sid]['title']!r} != {spec['title']!r}"
        )

    assert sections["$1"]["title"] == "IDENTITY"
    assert "IDN" in sections["$1"]["sigils"]
    assert sections["$8"]["title"] == "ACTIVE_CONTEXT"
    assert sections["$8"]["sigils"] == ["WRK"]
    assert sections["$6"]["title"] == "PULSE"
    assert sections["$7"]["sigils"] == ["LNG"]
    assert sections["$19"]["title"] == "ARQUX METADATA"
    assert sections["$19"]["sigils"] == ["ARQX"]
    assert sections["$2"]["sigils"] == ["FCS"]
    assert sections["$10"]["sigils"] == ["KNW"]
    assert sections["$11"]["sigils"] == ["ERR"]

    # sigil lookup still works with sections param present
    out2 = ref_handler("WRK", sections=False, ctx=_CONTEXT)
    assert out2.profile == "OUT-WORK"
    assert out2.fields["sigil"] == "WRK"
