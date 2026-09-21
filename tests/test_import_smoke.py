"""Import smoke tests (BLP-006 / issue 2026-07-19-core-state-circular).

Regression guard: ``import arqux.handlers`` must not raise the circular
ImportError that once blocked the whole suite (fix T-005/G-9). A
subprocess is used so the check runs on a pristine interpreter even if
another test already imported the package.
"""

from __future__ import annotations

import subprocess
import sys


def test_import_arqux_handlers_clean() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import arqux.handlers; print('IMPORT_OK')"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "IMPORT_OK" in result.stdout


def test_import_core_state_and_brain() -> None:
    """Direct import of the modules involved in the original cycle."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import arqux.core.state; import arqux.core.state._brain;"
            " import arqux.pulse; print('IMPORT_OK')",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "IMPORT_OK" in result.stdout
