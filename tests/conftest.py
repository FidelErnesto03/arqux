"""Shared pytest fixtures.

Every test runs in a fresh tmp_path with no inherited governance state.
Permission contexts are constructed explicitly so tests do not depend
on the host's environment variables.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from arqux import constants
from arqux.permissions import PermissionContext
from arqux.constants import (
    PRODUCT_NAME_UPPER,
    ROLE_AUDITOR,
    ROLE_EXECUTOR,
    ROLE_GOVERNOR,
)


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """A clean workspace root directory."""
    return tmp_path


@pytest.fixture
def governor_ctx() -> PermissionContext:
    return PermissionContext(agent_id="test-governor", role=ROLE_GOVERNOR)


@pytest.fixture
def executor_ctx() -> PermissionContext:
    return PermissionContext(agent_id="test-executor", role=ROLE_EXECUTOR)


@pytest.fixture
def auditor_ctx() -> PermissionContext:
    return PermissionContext(agent_id="test-auditor", role=ROLE_AUDITOR)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove any ARQUX_* env vars set by previous tests."""
    for key in list(os.environ.keys()):
        if key.startswith(f"{PRODUCT_NAME_UPPER}_"):
            monkeypatch.delenv(key, raising=False)
