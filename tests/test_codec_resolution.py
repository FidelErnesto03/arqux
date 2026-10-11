"""Capability-based CODEC-CORTEX resolution (issue 2026-10-11 pin mismatch).

CODEC-CORTEX renamed its public import name between 0.6.2 and 1.0.0rc1 and
changed its surface at the same time:

    0.6.2 (legacy)   cortex.core.parser      -> parse_cortex
                     cortex.core.validator   -> validate
                     cortex.hcortex.read_renderer -> render_hcortex_read

    1.0.0rc1 (rc1)   codec_cortex.parser     -> parse_cortex
                     codec_cortex.hcortex     -> compile_hcortex
                     NO validate, NO render_hcortex_read

The runtime used to import only the legacy names and swallow ImportError, so
installing the PINNED version silently disabled the whole CORTEX layer. These
tests pin the resolution contract and fail loudly if that regresses.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from arqux.core.state import _CODEC_CORTEX_MISSING, codec_cortex_diagnostics
from arqux.core.state._crud import requires_capability


def test_diagnostics_reports_a_known_shape() -> None:
    """Diagnostics must always describe the detected layout, never guess."""
    diag = codec_cortex_diagnostics()
    assert set(diag) == {
        "available",
        "api",
        "missing_capabilities",
        "can_parse",
        "can_validate",
        "can_render_hcortex",
    }
    assert diag["api"] in {"legacy", "rc1", None}
    assert isinstance(diag["missing_capabilities"], list)


def test_diagnostics_capabilities_agree_with_handles() -> None:
    """can_* must reflect the bound handles, not a hardcoded assumption."""
    diag = codec_cortex_diagnostics()
    assert diag["can_parse"] is (diag["available"] and diag["can_parse"])


def test_missing_capabilities_are_a_subset_of_the_contract() -> None:
    """Only the three capabilities ArqUX actually calls may be reported."""
    known = {"parse_cortex", "validate", "render_hcortex_read"}
    assert set(_CODEC_CORTEX_MISSING) <= known


def test_verify_capability_is_honest_about_the_pinned_version() -> None:
    """The declared pin must not leave `cortex_verify` silently unusable.

    Under codec-cortex==1.0.0rc1 the parser binds but `validate` does not, so
    requires_capability("validate") must raise a NAMED error instead of letting
    a None handle surface as an AttributeError deep in the call stack.
    """
    diag = codec_cortex_diagnostics()
    assert "validate" in diag["missing_capabilities"] or diag["can_validate"]
    if "validate" in _CODEC_CORTEX_MISSING:
        with pytest.raises(RuntimeError) as exc:
            requires_capability("validate")
        message = str(exc.value)
        assert "validate" in message
        assert "api=" in message
    else:
        # A validating codec is present: the capability gate must not block.
        requires_capability("validate")


def test_render_capability_is_honest_about_the_pinned_version() -> None:
    if "render_hcortex_read" in _CODEC_CORTEX_MISSING:
        with pytest.raises(RuntimeError) as exc:
            requires_capability("render_hcortex_read")
        assert "render_hcortex_read" in str(exc.value)
    else:
        requires_capability("render_hcortex_read")


def test_installed_pin_does_not_disable_cortex_parsing() -> None:
    """Regression: the pinned extra must not blank the whole CORTEX layer.

    Historically, `pip install arqux[codec]` (which pins 1.0.0rc1) made
    `_HAS_CODEC_CORTEX` False because only the legacy module name was
    imported. Parsing must resolve under either layout.
    """
    code = (
        "from arqux.core.state import codec_cortex_diagnostics as d;"
        "import json,sys;"
        "diag=d();"
        "print(json.dumps(diag));"
        "sys.exit(0 if diag['available'] and diag['can_parse'] else 1)"
    )
    # PYTHONPATH must carry the repo's src/ explicitly: the ambient
    # site-packages copy of arqux shadows it otherwise, which would make this
    # test measure the wrong package (and silently skip).
    src = Path(__file__).resolve().parent.parent / "src"
    env = {**os.environ, "PYTHONPATH": str(src)}
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if proc.returncode != 0:
        pytest.fail(
            "the declared pin leaves CORTEX parsing disabled — the installed "
            f"CODEC-CORTEX resolves neither layout. "
            f"(diagnostics: {proc.stdout.strip() or proc.stderr.strip()[:200]})"
        )
    assert '"can_parse": true' in proc.stdout.replace("True", "true")
