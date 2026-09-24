# Permissions Model

ArqUX implements a **three-role governance model** (v0.4.3).

## Roles

| Role | Agent | Description |
|------|-------|-------------|
| **GOVERNOR** | Alfred | Full access — creates cycles, assigns, approves, closes |
| **EXECUTOR** | Jarvis | Universal governance — claims tasks, updates, completes. Cannot call init handlers. |
| **AUDITOR** | Heimdall, Seshat | **Read-only (denylist)** — can call any handler EXCEPT `GOVERNOR_ONLY`, `MUTATING_HANDLERS`, and `CONDITIONAL_MUTATING` invocations that actually mutate. |

## Handler Access by Role

The auditor model is a **denylist**, not an allowlist: every handler not in
`GOVERNOR_ONLY` / `MUTATING_HANDLERS` is auditor-callable, and handlers in
`CONDITIONAL_MUTATING` are auditor-callable in their non-mutating mode
(dry-run previews, read modes). (`READ_ONLY_PREFIXES` was removed in T-020 —
it was dead code never consulted by `check()`.)

### Governor-only handlers

| Handler | Reason |
|---------|--------|
| `workspace.init` | Initialization requires governor authority |
| `project.init` | Project creation is a governance action |

### Mutating handlers (DENIED for AUDITOR — P0-B, reconciled T-020)

The full `MUTATING_HANDLERS` frozenset is defined in `src/arqux/permissions.py`.
Auditor role is denied all of these handlers — including (but not limited to):

- `blueprint.create`, `blueprint.update`, `blueprint.cancel`, `blueprint.fail`,
  `blueprint.execute`, `blueprint.synthesize`, `blueprint.re_delegate`
- `task.create`, `task.claim`, `task.update`, `task.complete`, `task.fail`, `task.run`
- `cycle.create`, `cycle.close`, `cycle.synthesize`
- `cortex.entry.add`, `cortex.entry.delete`, `cortex.entry.update`,
  `cortex.entry.move`, `cortex.write`, `cortex.checkpoint`
- `protocol.adopt`, `protocol.onboard`, `protocol.release`, `protocol.pause`, `protocol.resume`
- `evidence.record`, `identity.record`
- `session.context.set`, `session.close`, `session.bootstrap`,
  `session.handoff`, `session.pulse.compact` (`session.resume` is a pure
  read — auditor-allowed)
- `project.bind`, `project.unbind`, `project.init`
- `skill.record`, `skill.import`, `skill.convert`, `skill.install`
- `sync.run`, `sync.reconcile`, `setup.plantuml`

### Conditional mutators (DENIED for AUDITOR only when the call mutates — T-020)

`CONDITIONAL_MUTATING` maps a handler to the param flag(s) that make the call
mutating. The auditor is denied only when **all** listed flags are truthy AND
`dry_run` is falsy — previews and read modes stay allowed:

| Handler | Mutates when |
|---------|--------------|
| `cortex.learn.elevate` | `apply=true` (default is a dry-run elevation diff) |
| `cortex.file.validate` | `fix=true` (default only reports duplicates) |
| `cortex.gc` | `force=true` AND `dry_run=false` (defaults preview) |
| `cortex.patch` | `dry_run` falsy (default mutates; `dry_run=true` previews) |
| `cortex.migrate` | `dry_run` falsy (default mutates; `dry_run=true` previews) |
| `skill.evolve` | `apply=true` (default shows the proposed change) |
| `skill.edit` | `content` provided (no content = read mode) |

The dispatch layer (`server._wrap_handler`) binds signature defaults before
evaluating, so an omitted `dry_run` is judged at its declared default
(e.g. `cortex.gc(force=true)` still previews because `dry_run` defaults true).

### HMAC-required handlers (require verified identity)

| Handler | Why HMAC |
|---------|----------|
| `identity.record` | Identity claims require proof |
| `evidence.record` | Evidence must be attributable |
| `blueprint.re_delegate` | Governance action requires verification |

## Environment Variables

| Variable | Values | Effect |
|----------|--------|--------|
| `ARQUX_AGENT_ROLE` | `governor`, `executor`, `auditor` | Sets active role |
| `ARQUX_STRICT_ROLES` | `0` (default), `1` | Enables strict role enforcement |
| `ARQUX_STRICT_SECURITY` | `0` (default), `1` | Enables HMAC enforcement |
| `ARQUX_AGENT_ID` | string | Agent identity name |
| `ARQUX_AGENT_SIGNATURE` | hex string | HMAC signature for verified requests |
| `ARQUX_AGENT_TIMESTAMP` | Unix timestamp | Signature generation time |

## Quick Reference

```python
# Strict mode example
os.environ["ARQUX_STRICT_ROLES"] = "1"
ctx = PermissionContext(agent_id="jarvis", role="executor")
ctx.check("task.create")       # OK
ctx.check("workspace.init")    # PermissionDenied (governor-only)

# Auditor is read-only
ctx = PermissionContext(agent_id="heimdall", role="auditor")
ctx.check("blueprint.read")    # OK
ctx.check("blueprint.cancel")  # PermissionDenied (mutating handler; auditor is read-only)
```

## Backward Compatibility

When `ARQUX_STRICT_ROLES` is not set (default), the system operates in legacy mode:
- Role defaults to GOVERNOR
- All handlers are allowed (no enforcement)

This is **not recommended for production**. Always set `ARQUX_STRICT_ROLES=1` for pilot deployments.
