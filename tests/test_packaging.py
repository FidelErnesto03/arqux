"""Tests for arqux packaging — BLP-025.

Validates that:
- skills/workflows/*.md are declared in package-data (CA-01)
- Workflows are accessible via importlib.resources (CA-03)
- arqux init copies workflows to .arqux/skills/workflows/ (CA-05)
"""

from __future__ import annotations

import importlib.resources
import subprocess
import tempfile
from pathlib import Path

import pytest


WORKFLOW_COUNT = 11
EXPECTED_WORKFLOWS = [
    "w01-workspace-init.md",
    "w02-govern-project.md",
    "w03-session-start.md",
    "w04-reactive-task.md",
    "w05-identity-evolution.md",
    "w06-agent-adoption.md",
    "w07-skill-lifecycle.md",
    "w08-blueprint-lifecycle.md",
    "w09-crud-blocked.md",
    "w10-identity-handoff.md",
    "w11-cortex-file-repair.md",
]


class TestWorkflowsInPackage:
    """CA-01 / CA-03: Workflows must be declared in package-data and accessible."""

    def test_workflows_accessible_via_importlib(self) -> None:
        """Each workflow must be importable from the installed package."""
        for wf in EXPECTED_WORKFLOWS:
            ref = importlib.resources.files("arqux").joinpath(f"skills/workflows/{wf}")
            assert ref.is_file(), f"Workflow {wf} not found in installed package"

    def test_workflow_count_in_package(self) -> None:
        """At least 10 workflow files must be present."""
        wf_dir = importlib.resources.files("arqux").joinpath("skills/workflows")
        assert wf_dir.is_dir(), "skills/workflows/ directory not in package"
        md_files = [p for p in wf_dir.iterdir() if p.name.endswith(".md")]
        assert len(md_files) >= WORKFLOW_COUNT, (
            f"Expected at least {WORKFLOW_COUNT} workflows, found {len(md_files)}"
        )


class TestInitCopiesWorkflows:
    """CA-05: arqux init must copy workflows to the workspace."""

    def test_init_copies_workflows(self) -> None:
        """Run arqux init in a tmpdir and verify workflows are present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                ["arqux", "call", "workspace.init", f"path={tmpdir}"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert result.returncode == 0, f"workspace.init failed: {result.stderr}"

            workflows_dst = Path(tmpdir) / ".arqux" / "skills" / "workflows"
            assert workflows_dst.is_dir(), "workflows directory not created"

            md_files = [f for f in workflows_dst.iterdir() if f.name.endswith(".md")]
            assert len(md_files) >= WORKFLOW_COUNT, (
                f"Expected at least {WORKFLOW_COUNT} workflows after init, "
                f"found {len(md_files)}"
            )
