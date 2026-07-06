"""CLI entry point.

Commands:
    arqux serve              — start the MCP server on stdio.
    arqux init               — initialize .arqux/ in the current directory.
    arqux status             — print workspace/project/cycle status.
    arqux call <handler>     — call any handler directly (no MCP required).
    arqux setup-plantuml     — download plantuml.jar.
    arqux serve-plantuml     — start PlantUML render server.
    arqux --version
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Sequence

import click

from . import __version__
from .constants import PRODUCT_NAME, PRODUCT_NAME_TITLE




def _call_handler(name: str, raw_args: list[str]) -> str:
    """Dispatch a handler by name with key=value arguments.

    Returns the handler's CORTEX-OUT message as a string.
    """
    from .handlers import REGISTRY
    from .permissions import PermissionContext

    if name not in REGISTRY:
        # Try MCP-safe name (underscores → dots)
        dotted = name.replace("_", ".")
        if dotted in REGISTRY:
            name = dotted
        else:
            available = "\n".join(f"  {n}" for n in sorted(REGISTRY.keys()))
            return f"ERROR: unknown handler '{name}'. Available:\n{available}"

    spec = REGISTRY[name]
    ctx = PermissionContext.from_env()

    # Parse key=value arguments
    kwargs: dict[str, Any] = {}
    for arg in raw_args:
        if "=" in arg:
            key, val = arg.split("=", 1)
            # Try JSON parsing for complex values
            try:
                kwargs[key] = json.loads(val)
            except (json.JSONDecodeError, ValueError):
                kwargs[key] = val
        else:
            # Positional: use as first required param's value
            req = spec.input_schema.get("required", [])
            if req:
                kwargs[req[0]] = arg

    # Add path if not provided
    if "path" not in kwargs:
        kwargs["path"] = str(Path.cwd())

    # Call handler
    try:
        result = spec.fn(**kwargs, ctx=ctx)
    except TypeError as e:
        return f"ERROR: {e}. Expected params: {list(spec.input_schema.get('properties', {}).keys())}"

    if hasattr(result, "to_text"):
        return result.to_text()
    if hasattr(result, "message"):
        return str(result.message)
    return str(result)


@click.group()
@click.version_option(version=__version__, prog_name=PRODUCT_NAME, message="%(prog)s %(version)s")
def main():
    """Arqux — governance framework for AI agent teams."""
    pass

@main.command("init")
@click.option("--path", default=None, help="Path to initialize.")
@click.option("--verbose", is_flag=True, help="Use OUT-AUDIT profile.")
def cmd_init(path: str | None, verbose: bool):
    """Initialize .arqux/ in the current directory."""
    from .handlers.workspace import init_workspace

    result = init_workspace(path=path, verbose=verbose)
    click.echo(result.to_text())

@main.command("status")
@click.option("--path", default=None, help="Path to check.")
@click.option("--verbose", is_flag=True, help="Verbose output.")
def cmd_status(path: str | None, verbose: bool):
    """Print workspace + project + cycle status."""
    from .handlers.workspace import status as ws_status
    from .handlers.project import status as pr_status
    from .handlers.cycle import current_cycle

    ws = ws_status(verbose=verbose, path=path)
    click.echo(ws.to_text())

    try:
        pr = pr_status(verbose=verbose, path=path)
        click.echo(pr.to_text())
    except Exception:
        pass

    try:
        cy = current_cycle(path=path)
        click.echo(cy.to_text())
    except Exception:
        pass


@main.command("serve")
@click.option("--verbose", is_flag=True, help="Verbose startup.")
def cmd_serve(verbose: bool):
    """Start the MCP server on stdio."""
    from .server import run_server
    run_server(verbose=verbose)


@main.command("call")
@click.argument("handler")
@click.argument("args", nargs=-1)
def cmd_call(handler: str, args: tuple[str, ...]):
    """Call any Arqux handler directly (no MCP required).

    Examples:
        arqux call workspace.status
        arqux call blueprint.create obj="OAuth2 endpoint" cycle=CYCLE-01
        arqux call identity.record lesson="Always verify P0" kind=behavioral
        arqux call blueprint.list status=done cycle=CYCLE-01
    """
    result = _call_handler(handler, list(args))
    click.echo(result)


@main.command("setup-plantuml")
@click.option("--force", is_flag=True, help="Force re-download.")
def cmd_setup_plantuml(force: bool):
    """Install plantuml.jar to ~/.arqux/bin/."""
    from .plantuml import setup_plantuml as sp

    ok, msg = sp(force=force)
    click.echo(msg)
    sys.exit(0 if ok else 1)


@main.command("serve-plantuml")
@click.option("--port", type=int, default=9876, help="Port to listen on.")
def cmd_serve_plantuml(port: int):
    """Start PlantUML rendering server."""
    from .plantuml_server import start_server

    srv = start_server(port=port)
    import time

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        srv.shutdown()


@main.command("render-diagram")
@click.argument("puml_file")
@click.option("--format", "fmt", default="svg", type=click.Choice(["svg", "png"]))
@click.option("--output", "-o", default=None, help="Output directory.")
def cmd_render_diagram(puml_file: str, fmt: str, output: str | None):
    """Render a PUML file to SVG/PNG."""
    from pathlib import Path

    from .plantuml import render_puml

    source = Path(puml_file).read_text(encoding="utf-8")
    out_dir = Path(output) if output else None
    ok, result = render_puml(source, format=fmt, output_dir=out_dir)
    click.echo(result)
    sys.exit(0 if ok else 1)


@main.command("handlers")
def cmd_handlers():
    """List all available handlers."""
    from .handlers import list_handlers

    for name in sorted(list_handlers()):
        click.echo(name)
