"""CLI entry point.

Commands:
    arqux serve              — start the MCP server on stdio.
    arqux init               — initialize .arqux/ in the current directory.
    arqux status             — print workspace/project/cycle status.
    arqux call <handler>     — call any handler directly (no MCP required).
    arqux cortex-verify <p>  — verify SHA-256 integrity of a .cortex file.
    arqux setup-plantuml     — download plantuml.jar.
    arqux serve-plantuml     — start PlantUML render server.
    arqux --version

Patches applied (vs 0.4.2):
    - P1-A: arqux call unknown.handler exits 1 (was 0)
    - P1-B: arqux call with handler error exits 1 (was 0)
    - P1-C: arqux status does not silently swallow TypeError
    - P1-Q: new arqux cortex-verify command
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import click

from . import __version__
from .constants import PRODUCT_NAME


def _call_handler(name: str, raw_args: list[str]) -> str:
    """Dispatch a handler by name with key=value arguments.

    Returns the handler's CORTEX-OUT message as a string.
    """
    from .constants import OUT_ERROR, PERMISSION_DENIED
    from .cortex_out import CortexOUT
    from .handlers import REGISTRY
    from .permissions import PermissionContext, PermissionDenied

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

    # T-020 audit (C-2): enforce role checks on the CLI path — mirror
    # server._wrap_handler semantics (ctx.check with the effective call
    # kwargs so CONDITIONAL_MUTATING is judged on bound defaults;
    # PermissionDenied → clean OUT-ERROR, not a traceback).
    try:
        ctx.check(name, **kwargs)
    except PermissionDenied as exc:
        return CortexOUT.profile(
            OUT_ERROR,
            f"ERROR code={PERMISSION_DENIED} handler={name} reason={exc.reason}",
        ).to_text()

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
@click.option("--dashboard", is_flag=True, help="Show visual workspace dashboard.")
def cmd_status(path: str | None, verbose: bool, dashboard: bool):
    """Print workspace + project + cycle status."""
    from .handlers.cycle import current_cycle
    from .handlers.project import status as pr_status
    from .handlers.workspace import status as ws_status

    if dashboard:
        from .dashboard import build_dashboard
        result = build_dashboard(path=path, fmt="rich")
        click.echo(result.to_text())
        return

    ws = ws_status(verbose=verbose, path=path)
    click.echo(ws.to_text())

    # P1-C FIX: do not pass verbose to pr_status (it does not accept it).
    try:
        pr = pr_status(path=path)
        click.echo(pr.to_text())
    except Exception as e:
        if verbose:
            click.echo(f"[project status unavailable: {e}]", err=True)

    try:
        cy = current_cycle(path=path)
        click.echo(cy.to_text())
    except Exception as e:
        if verbose:
            click.echo(f"[cycle status unavailable: {e}]", err=True)


@main.command("serve")
@click.option("--verbose", is_flag=True, help="Verbose startup.")
def cmd_serve(verbose: bool):
    """Start the MCP server on stdio."""
    from .server import run_server
    run_server(verbose=verbose)


@main.command("voice-serve")
def cmd_voice_serve():
    """Start the arqux-voice MCP server on stdio (requires arqux[voice])."""
    try:
        from .voice.server import run
    except ImportError as exc:
        click.echo(
            f"ERROR: voice extra not installed ({exc}). "
            "Run: pip install 'arqux[voice]'", err=True)
        sys.exit(1)
    run()


@main.command("voice-doctor")
def cmd_voice_doctor():
    """Check the voice extension environment (devices, deps, models)."""
    try:
        from .voice.doctor import run
    except ImportError as exc:
        click.echo(
            f"ERROR: voice extra not installed ({exc}). "
            "Run: pip install 'arqux[voice]'", err=True)
        sys.exit(1)
    run()


@main.group("voice-daemon")
def cmd_voice_daemon():
    """Control the optional persistent local voice daemon."""


@cmd_voice_daemon.command("start")
@click.option("--foreground", is_flag=True,
              help="Keep the daemon attached to this terminal.")
@click.option("--name", default="arqux-voice-daemon", show_default=True)
@click.option("--mode", type=click.Choice(["solo", "meet"]), default="solo",
              show_default=True)
@click.option("--agent", default="alfred", show_default=True)
@click.option("--lang", default="es", show_default=True)
@click.option("--mic", default=None, help="PipeWire input selector.")
def cmd_voice_daemon_start(foreground: bool, name: str, mode: str,
                           agent: str, lang: str, mic: str | None):
    """Start listening independently from MCP/agent processes."""
    try:
        from .voice.daemon import start_daemon
        result = start_daemon(name=name, mode=mode, agent=agent, lang=lang,
                              mic=mic, foreground=foreground)
        click.echo(json.dumps(result, ensure_ascii=False, default=str))
    except ImportError as exc:
        click.echo(
            f"ERROR: voice extra not installed ({exc}). "
            "Run: pip install 'arqux[voice]'", err=True)
        raise click.exceptions.Exit(1) from exc
    except Exception as exc:  # noqa: BLE001
        click.echo(f"ERROR: {exc}", err=True)
        raise click.exceptions.Exit(1) from exc


@cmd_voice_daemon.command("status")
def cmd_voice_daemon_status():
    """Show daemon and persistent meeting status."""
    try:
        from .voice.daemon import daemon_status
        click.echo(json.dumps(daemon_status(), ensure_ascii=False, default=str))
    except ImportError as exc:
        click.echo(f"ERROR: voice extra not installed ({exc})", err=True)
        raise click.exceptions.Exit(1) from exc


@cmd_voice_daemon.command("stop")
def cmd_voice_daemon_stop():
    """Stop the daemon and release audio devices."""
    try:
        from .voice.daemon import stop_daemon
        click.echo(json.dumps(stop_daemon(), ensure_ascii=False, default=str))
    except ImportError as exc:
        click.echo(f"ERROR: voice extra not installed ({exc})", err=True)
        raise click.exceptions.Exit(1) from exc


@cmd_voice_daemon.command("restart")
@click.option("--name", default="arqux-voice-daemon", show_default=True)
@click.option("--mode", type=click.Choice(["solo", "meet"]), default="solo",
              show_default=True)
@click.option("--agent", default="alfred", show_default=True)
@click.option("--lang", default="es", show_default=True)
@click.option("--mic", default=None, help="PipeWire input selector.")
def cmd_voice_daemon_restart(name: str, mode: str, agent: str, lang: str,
                             mic: str | None):
    """Restart the persistent daemon with a fresh voice session."""
    try:
        from .voice.daemon import start_daemon, stop_daemon
        stop_daemon()
        result = start_daemon(name=name, mode=mode, agent=agent, lang=lang,
                              mic=mic)
        click.echo(json.dumps(result, ensure_ascii=False, default=str))
    except ImportError as exc:
        click.echo(f"ERROR: voice extra not installed ({exc})", err=True)
        raise click.exceptions.Exit(1) from exc


@main.group("session-bridge")
def cmd_session_bridge():
    """Control the independent canonical ArqUX host-session bridge."""


@cmd_session_bridge.command("serve")
@click.option("--socket", "socket_path", default=None,
              help="Unix socket path; defaults to ARQUX_HOST_BRIDGE_SOCKET or XDG_RUNTIME_DIR.")
@click.option("--request-timeout", default=90.0, type=float, show_default=True)
def cmd_session_bridge_serve(socket_path: str | None, request_timeout: float):
    """Run the host bridge broker in the foreground."""
    try:
        from .host_bridge import HostSessionBridge, host_bridge_socket_path, serve_host_bridge
        path = socket_path or str(host_bridge_socket_path())
        serve_host_bridge(path, HostSessionBridge(request_timeout_s=request_timeout))
    except Exception as exc:  # noqa: BLE001
        click.echo(f"ERROR: {exc}", err=True)
        raise click.exceptions.Exit(1) from exc


@main.command("comms-serve")
def cmd_comms_serve():
    """Start the arqux-comms MCP server on stdio (requires arqux[comms])."""
    try:
        from .comms.server import run
    except ImportError as exc:
        click.echo(
            f"ERROR: comms extra not installed ({exc}). "
            "Run: pip install 'arqux[comms]'", err=True)
        sys.exit(1)
    run()


@main.command("comms-doctor")
def cmd_comms_doctor():
    """Check the comms extension environment (deps, token, egress)."""
    try:
        from .comms.doctor import run
    except ImportError as exc:
        click.echo(
            f"ERROR: comms extra not installed ({exc}). "
            "Run: pip install 'arqux[comms]'", err=True)
        sys.exit(1)
    run()


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
    # P1-A/P1-B FIX: non-zero exit code on ERROR.
    if isinstance(result, str) and (result.startswith("ERROR") or "OUT-ERROR" in result):
        sys.exit(1)


@main.command("cortex-verify")
@click.argument("path", type=click.Path(exists=True))
def cmd_cortex_verify(path: str):
    """Verify SHA-256 integrity of a .cortex file (P1-Q).

    Exit codes:
        0 — integrity verified
        1 — tamper detected or no $INTEGRITY header
    """
    from .security import TamperError, verify_cortex
    try:
        verify_cortex(path)
        click.echo(f"OK: {path} integrity verified")
    except TamperError as e:
        click.echo(f"FAIL: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"ERROR: {type(e).__name__}: {e}", err=True)
        sys.exit(1)


@main.command("doctor")
@click.option("--fix", is_flag=True, help="Apply automatic repairs.")
def cmd_doctor(fix: bool):
    """Diagnose workspace/project health and optionally repair (BLP-007)."""
    from .doctor import run_all

    result = run_all(fix=fix)
    click.echo(result.to_text())


@main.command("quickstart")
@click.option("--path", default=None, help="Directory to bootstrap (default: cwd)")
def cmd_quickstart(path: str | None):
    """Interactive workspace onboarding for new agents (BLP-008)."""
    from .quickstart import quickstart as qs

    result = qs(path=path)
    click.echo(result.to_text())


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


# === BLP-011: backup / restore =============================================

@main.command("backup")
def cmd_backup():
    """Create a timestamped .tar.gz backup of .arqux/ with sha256 (BLP-011)."""
    from .backup import backup as do_backup

    result = do_backup()
    click.echo(result.to_text())


@main.command("restore")
@click.argument("backup_file", type=click.Path(exists=True))
def cmd_restore(backup_file: str):
    """Restore .arqux/ from a backup file (BLP-011)."""
    from .backup import restore as do_restore

    result = do_restore(backup_file)
    click.echo(result.to_text())


# === BLP-035: migrate ======================================================

@main.command("migrate")
@click.argument("path", type=click.Path(exists=True))
@click.option("--level", type=int, required=True, help="0=PACKAGE, 1=BEHAVIORAL, 2=SKILL, 3=BRAIN")
@click.option("--name", required=True, help="Canonical artifact name")
@click.option("--usage", required=True, help="state|skill|identity|lesson|config")
@click.option("--kind", default="native", help="native|inherited|adapted")
@click.option("--agent", default=None, help="Optional agent name (lessons)")
@click.option("--source", default=None, help="Optional upstream source URL")
@click.option("--upstream-version", default=None, help="Optional upstream version")
def cmd_migrate(
    path: str, level: int, name: str, usage: str, kind: str,
    agent: str | None, source: str | None, upstream_version: str | None,
):
    """Inject ARQX:artifact into a .cortex file (BLP-041). Idempotent."""
    from .migrator import migrate_file

    migrated = migrate_file(
        path, level=level, name=name, usage=usage, kind=kind,
        agent=agent, source=source, upstream_version=upstream_version,
    )
    click.echo(f"{'MIGRATED' if migrated else 'ALREADY_HAS_METADATA'}: {path}")


@main.command("cortex-migrate")
@click.argument("path", type=click.Path(exists=True))
@click.option("--apply", is_flag=True, help="Write changes; default is dry-run.")
@click.option("--no-backup", is_flag=True, help="Do not retain the atomic-write backup.")
def cmd_cortex_migrate(path: str, apply: bool, no_backup: bool):
    """Inspect or migrate legacy CORTEX files for CODEC-CORTEX 1.0.0rc1.

    A file or directory may be supplied. The default is a non-mutating
    preview; --apply performs atomic writes after CODEC verification.
    """
    from .cortex.migration import migrate_file, migrate_tree

    target = Path(path)
    kwargs = {"dry_run": not apply, "keep_backup": not no_backup}
    results = migrate_tree(target, **kwargs) if target.is_dir() else [migrate_file(target, **kwargs)]
    click.echo(json.dumps(results, ensure_ascii=False, indent=2, default=str))


# === BLP-035: validate =====================================================

@main.command("validate")
@click.argument("path", type=click.Path(exists=True))
@click.option("--strict", is_flag=True, help="Fail on warnings too")
def cmd_validate(path: str, strict: bool):
    """Validate a .cortex file: ARQX:artifact + structural + semantic (BLP-035/036/037)."""
    from .formats import read_cortex_artifact
    from .validators import ValidatorFactory

    artifact = read_cortex_artifact(path)
    click.echo(f"File: {path}")
    click.echo(f"Level: {artifact.metadata.level.name} ({artifact.metadata.level.value})")
    click.echo(f"Name:  {artifact.metadata.name}")
    click.echo(f"Usage: {artifact.metadata.usage.value}")
    click.echo(f"Kind:  {artifact.metadata.kind.value}")
    if artifact.warnings:
        click.echo(f"Metadata warnings: {', '.join(artifact.warnings)}")

    result = ValidatorFactory.validate(artifact)
    click.echo(f"\nValidation: {'PASS' if result.is_valid else 'FAIL'}")
    for err in result.errors:
        click.echo(f"  [{err.severity.upper()}] {err.code}: {err.message}")
    for w in result.warnings:
        click.echo(f"  [WARN] {w.code}: {w.message}")

    if not result.is_valid or (strict and (result.errors or result.warnings)):
        sys.exit(1)


# === BLP-038: elevate ======================================================

@main.command("elevate")
@click.option("--source", required=True, help="Source container path")
@click.option("--target", required=True, help="Target container path/section")
@click.option("--type", "contract_type", required=True,
              help="AXIOM|LIMIT (behavioral), CNST|CLAIM (procedural), KNW (contextual)")
@click.option("--lesson-id", required=True, help="Lesson sigil name to elevate")
@click.option("--line", default="behavioral",
              type=click.Choice(["behavioral", "procedural", "contextual"]))
@click.option("--agent", default=None, help="Agent name (required for behavioral)")
@click.option("--apply", is_flag=True, help="Apply the elevation (default is dry-run)")
def cmd_elevate(
    source: str, target: str, contract_type: str, lesson_id: str,
    line: str, agent: str | None, apply: bool,
):
    """Elevate a lesson via the unified motor (BLP-038).

    Default is dry-run. Pass --apply to actually write.
    """
    from .learning import elevate

    try:
        result = elevate(
            source=source, target=target, contract_type=contract_type,
            lesson_id=lesson_id, line=line, agent=agent,
            dry_run=not apply, apply=apply,
        )
        click.echo(json.dumps(result, indent=2, default=str))
    except Exception as exc:
        click.echo(f"ERROR: {type(exc).__name__}: {exc}", err=True)
        sys.exit(1)


# === BLP-039: identity =====================================================

@main.group("identity")
def cmd_identity_group():
    """Manage agent identities (BLP-039)."""
    pass


@cmd_identity_group.command("resolve")
@click.argument("name")
@click.option("--identities-dir", default=None, help="Override identities directory")
def cmd_identity_resolve(name: str, identities_dir: str | None):
    """Resolve an agent identity by name."""
    from .identity import IdentityManager

    im = IdentityManager(identities_dir=identities_dir) if identities_dir else IdentityManager()
    try:
        ctx = im.bind_to_session(name)
        click.echo(f"Agent: {ctx.agent}")
        click.echo(f"Identity: {ctx.identity.path}")
        click.echo(f"Level: {ctx.identity.metadata.level.name}")
        axm = ctx.contracts_by_type("AXM")
        lim = ctx.contracts_by_type("LIM")
        click.echo(f"AXM contracts: {len(axm)}")
        for c in axm:
            click.echo(f"  - {c.get('name', '?')}: {c.get('body', '')[:80]}")
        click.echo(f"LIM contracts: {len(lim)}")
        for c in lim:
            click.echo(f"  - {c.get('name', '?')}: {c.get('body', '')[:80]}")
    except Exception as exc:
        click.echo(f"ERROR: {type(exc).__name__}: {exc}", err=True)
        sys.exit(1)


@cmd_identity_group.command("elevate")
@click.option("--agent", required=True, help="Agent name (e.g. jarvis)")
@click.option("--lesson-id", required=True, help="Lesson sigil name (e.g. lsn-042)")
@click.option("--type", "contract_type", required=True,
              type=click.Choice(["AXIOM", "LIMIT"]))
@click.option("--pattern", default="", help="Lesson pattern (becomes AXM/LIM body)")
@click.option("--evidence-ref", default="", help="Optional evidence reference")
@click.option("--identities-dir", default=None, help="Override identities directory")
def cmd_identity_elevate(
    agent: str, lesson_id: str, contract_type: str,
    pattern: str, evidence_ref: str, identities_dir: str | None,
):
    """Inject an AXM/LIM into an agent's identity (BLP-039 / BLP-038)."""
    from .identity import IdentityManager

    im = IdentityManager(identities_dir=identities_dir) if identities_dir else IdentityManager()
    try:
        result = im.elevate_to_identity(
            agent=agent, lesson_id=lesson_id, contract_type=contract_type,
            pattern=pattern, evidence_ref=evidence_ref,
        )
        click.echo(json.dumps(result, indent=2))
    except Exception as exc:
        click.echo(f"ERROR: {type(exc).__name__}: {exc}", err=True)
        sys.exit(1)


@cmd_identity_group.command("list")
@click.option("--identities-dir", default=None, help="Override identities directory")
def cmd_identity_list(identities_dir: str | None):
    """List known agent identities."""
    from .identity import IdentityManager

    im = IdentityManager(identities_dir=identities_dir) if identities_dir else IdentityManager()
    for name in im.list_identities():
        click.echo(name)


# === BLP-040: skill ========================================================

@main.group("skill")
def cmd_skill_group():
    """Manage skills with provenance (BLP-040)."""
    pass


@cmd_skill_group.command("import")
@click.argument("name")
@click.option("--source", required=True, help="Upstream source URL/path")
@click.option("--content", default=None, help="Inline content (alternative to --from-file)")
@click.option("--from-file", default=None, help="Read content from file")
@click.option("--upstream-version", default=None, help="Upstream version tag")
@click.option("--arqux-root", default=None, help="Override .arqux/ root path")
def cmd_skill_import(
    name: str, source: str, content: str | None, from_file: str | None,
    upstream_version: str | None, arqux_root: str | None,
):
    """Import a third-party skill (BLP-040)."""
    from .skill_store import SkillRepository

    if content is None and from_file:
        content = Path(from_file).read_text(encoding="utf-8")
    if content is None:
        click.echo("ERROR: provide --content or --from-file", err=True)
        sys.exit(1)

    root = Path(arqux_root) if arqux_root else Path.cwd() / ".arqux"
    repo = SkillRepository(root)
    result = repo.import_skill(
        source=source, name=name, content=content,
        upstream_version=upstream_version,
    )
    click.echo(json.dumps(result, indent=2))


@cmd_skill_group.command("list")
@click.option("--arqux-root", default=None, help="Override .arqux/ root path")
def cmd_skill_list(arqux_root: str | None):
    """List all skills with provenance (BLP-040)."""
    from .skill_store import SkillRepository

    root = Path(arqux_root) if arqux_root else Path.cwd() / ".arqux"
    repo = SkillRepository(root)
    skills = repo.list_all()
    if not skills:
        click.echo("(no skills found)")
        return
    for s in skills:
        click.echo(f"{s['name']:30s}  {s['kind']:10s}  {s['store']:10s}  {s['path']}")


@cmd_skill_group.command("resolve")
@click.argument("name")
@click.option("--arqux-root", default=None, help="Override .arqux/ root path")
def cmd_skill_resolve(name: str, arqux_root: str | None):
    """Resolve a skill by priority: Adapted > Original > Native (BLP-040)."""
    from .skill_store import SkillRepository

    root = Path(arqux_root) if arqux_root else Path.cwd() / ".arqux"
    repo = SkillRepository(root)
    try:
        contract = repo.resolve(name)
        click.echo(f"Name:   {contract.declaration.name}")
        click.echo(f"Kind:   {contract.declaration.kind}")
        click.echo(f"Path:   {contract.path}")
        if contract.original_ref:
            click.echo(f"Original: {contract.original_ref}")
        if contract.warnings:
            click.echo(f"Warnings: {', '.join(contract.warnings)}")
    except Exception as exc:
        click.echo(f"ERROR: {type(exc).__name__}: {exc}", err=True)
        sys.exit(1)
