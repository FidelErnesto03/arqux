"""CLI entry point.

Exposes three commands:
    arqux serve    — start the MCP server on stdio.
    arqux init     — initialize .arqux/ in the current directory.
    arqux status   — print workspace/project/cycle status.
    arqux --version
"""

from __future__ import annotations

import sys
from typing import Sequence

import click

from . import __version__
from .constants import PRODUCT_NAME, PRODUCT_NAME_TITLE


@click.group(
    help=f"{PRODUCT_NAME_TITLE} — minimum-viable governance framework for AI agent teams."
)
@click.version_option(version=__version__, prog_name=PRODUCT_NAME)
def cli() -> None:
    """Top-level command group."""


@cli.command(help="Start the MCP server on stdio.")
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    help="Log handler invocations to stderr (for debugging).",
)
def serve(verbose: bool) -> None:
    """Start the MCP server."""
    # Import lazily so `--version` and `--help` do not require MCP deps.
    from .server import run_server

    run_server(verbose=verbose)


@cli.command(help="Initialize .arqux/ in the current directory.")
@click.option(
    "--workspace",
    is_flag=True,
    default=False,
    help="Initialize as a workspace root (creates meta-brain + projects index).",
)
@click.option(
    "--project",
    "project_name",
    default=None,
    help="Register the current directory as a project with this name.",
)
def init(workspace: bool, project_name: str | None) -> None:
    """Initialize governance in the current directory."""
    from .handlers.workspace import init_workspace
    from .handlers.project import init_project

    if not workspace and project_name is None:
        # Default: initialize as both workspace and a project named "default".
        workspace = True
        project_name = "default"

    if workspace:
        result = init_workspace(path=".", verbose=True)
        click.echo(result.to_text())

    if project_name is not None:
        result = init_project(name=project_name, path=".", verbose=True)
        click.echo(result.to_text())


@cli.command(help="Print workspace/project/cycle status.")
@click.option(
    "--profile",
    type=click.Choice(["OUT-MIN", "OUT-WORK", "OUT-AUDIT", "OUT-FULL"]),
    default="OUT-WORK",
    help="CORTEX-OUT profile to use for the output.",
)
def status(profile: str) -> None:
    """Print current status."""
    from .cortex_out import format_status
    from .state import find_workspace_root

    root = find_workspace_root()
    if root is None:
        click.echo(f"ERROR code=NOT_FOUND reason=no_workspace_init")
        sys.exit(1)

    click.echo(format_status(root, profile=profile))


def main(argv: Sequence[str] | None = None) -> None:
    """Console-script entry point."""
    cli(args=list(argv) if argv is not None else None)


if __name__ == "__main__":
    main()
