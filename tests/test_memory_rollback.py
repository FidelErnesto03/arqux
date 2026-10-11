"""BLP-004 CA-03 and CA-04: base install without extras, and a rehearsed rollback.

CA-04: the rollback is rehearsed in isolation before the gate — the Memory
Core is disabled by discarding its derived index and the canonical CORTEX is
proved untouched (hash identical). CA-03: the base install imports without any
semantic or optional dependency.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

from arqux.memory import LocalStore

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

SAMPLE = """$0
$0:format{cortex:0.1,encoding:UTF-8}
KNW:knowledge{type:attrs,weight:B,fields:"topic:text|content:text|status:text",focus:content,desc:"Knowledge"}
$1:KNOW
KNW:k1{topic:"t",content:"c",status:"current"}
"""


def test_rollback_disables_memory_core_without_touching_cortex(tmp_path: Path) -> None:
    source = tmp_path / "brain.cortex"
    source.write_text(SAMPLE, encoding="utf-8")
    before = hashlib.sha256(source.read_bytes()).hexdigest()

    index = tmp_path / "index.json"
    store = LocalStore(index, [source])
    store.rebuild()
    assert index.is_file(), "the derived index was not created"

    # Rollback: disabling the Memory Core only discards the derived index.
    index.unlink()

    # The canonical CORTEX is untouched — byte for byte.
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before

    # The system degrades to a canonical CORTEX read on demand.
    result = store.load()
    assert result.origin == "rebuild"
    assert result.records


def test_base_install_imports_without_semantic_extras() -> None:
    """CA-03: the base install must not need any semantic/optional dependency.

    ``cortex`` (the CORTEX codec) is a base dependency of ArqUX, not a semantic
    extra, so it is not forbidden here; the semantic providers are.
    """
    semantic = ("numpy", "faiss", "sentence_transformers", "torch", "transformers", "sklearn", "scipy")
    program = (
        "import arqux.memory, sys; "
        f"bad=[m for m in {semantic!r} if m in sys.modules]; "
        "print(bad)"
    )
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    proc = subprocess.run(
        [sys.executable, "-c", program], capture_output=True, text=True, env=env
    )
    assert proc.returncode == 0, proc.stderr[-400:]
    assert proc.stdout.strip() == "[]", f"semantic extras imported: {proc.stdout.strip()}"
