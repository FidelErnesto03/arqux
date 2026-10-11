"""BLP-002 CA-02 and CA-03: the rebuild is equivalent and idempotent.

Deleting the derived index and rebuilding must produce an equivalent set
(CA-02), and two successive rebuilds must be byte-identical in identity
(CA-03). CA-06 requires the rebuild path to use the standard library only.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from arqux.memory import LocalStore

MEMORY_DIR = Path(__file__).resolve().parent.parent / "src" / "arqux" / "memory"

SAMPLE = """$0
$0:format{cortex:0.1,encoding:UTF-8}
SES:session{type:attrs,weight:B,fields:"input:text|output:text|outcome:text|date:text",focus:outcome,desc:"Session"}
LNG:lesson{type:attrs,weight:M,fields:"type:text|cause:text|lesson:text|prevention:text",focus:lesson,desc:"Lesson"}
KNW:knowledge{type:attrs,weight:B,fields:"topic:text|content:text|status:text",focus:content,desc:"Knowledge"}
$1:SESSIONS
SES:s1{input:"q",output:"a",outcome:"ok",date:"2026-10-01"}
$2:LESSONS
LNG:l1{type:"process",cause:"x",lesson:"y",prevention:"z"}
$3:KNOWLEDGE
KNW:k1{topic:"t",content:"c",status:"current"}
"""


def _write_source(tmp_path: Path) -> Path:
    source = tmp_path / "brain.cortex"
    source.write_text(SAMPLE, encoding="utf-8")
    return source


def test_delete_index_and_rebuild_is_equivalent(tmp_path: Path) -> None:
    source = _write_source(tmp_path)
    index = tmp_path / "index.json"
    store = LocalStore(index, [source])

    first = store.rebuild()
    first_set = {(r.address, r.kind) for r in first.records}
    assert first_set, "the rebuild projected nothing"

    index.unlink()  # the derived index is disposable
    second = store.rebuild()

    assert {(r.address, r.kind) for r in second.records} == first_set
    assert second.content_hash == first.content_hash


def test_two_successive_rebuilds_hash_identically(tmp_path: Path) -> None:
    source = _write_source(tmp_path)
    store = LocalStore(tmp_path / "index.json", [source])

    first = store.rebuild()
    second = store.rebuild()

    assert first.content_hash == second.content_hash
    assert [r.address for r in first.records] == [r.address for r in second.records]
    # ``rebuilt_at`` may differ; identity must not depend on it.
    assert all(
        a.stable_dict() == b.stable_dict()
        for a, b in zip(first.records, second.records, strict=False)
    )


def test_sources_are_recorded_with_hashes(tmp_path: Path) -> None:
    source = _write_source(tmp_path)
    index = LocalStore(tmp_path / "index.json", [source]).rebuild()
    assert index.sources[str(source)]
    assert len(index.sources[str(source)]) == 64


def _imported_top_level_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import inside the package
                modules.add("arqux")
            elif node.module:
                modules.add(node.module.split(".")[0])
    return modules


def test_memory_core_uses_standard_library_only() -> None:
    """CA-06: no mandatory third-party dependency on the rebuild path."""
    allowed = set(sys.stdlib_module_names) | {"arqux"}
    offenders: dict[str, set[str]] = {}
    for module_file in sorted(MEMORY_DIR.glob("*.py")):
        extra = _imported_top_level_modules(module_file) - allowed
        if extra:
            offenders[module_file.name] = extra
    assert not offenders, f"third-party imports in the memory core: {offenders}"
