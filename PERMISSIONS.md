# Permissions Model

ArqUX implements a **three-role governance model** (v0.4.3).

## Roles

| Role | Agent | Description |
|------|-------|-------------|
| **GOVERNOR** | Alfred | Full access — creates cycles, assigns, approves, closes |
| **EXECUTOR** | Jarvis | Universal governance — claims tasks, updates, completes. Cannot call init handlers. |
| **AUDITOR** | Heimdall, Seshat | **Strictly read-only** — can only call `READ_ONLY_PREFIXES` handlers. Cannot mutate state. |

## Handler Access by Role

### Read-only handlers (allowed for AUDITOR)

`workspace.status`, `workspace.lessons`, `project.status`, `project.lessons`,
`cycle.list`, `cycle.current`, `task.read`, `task.list`, `evidence.list`,
`evidence.read`, `cortex.read`, `cortex.verify`, `cortex.render`,
`cortex.learn`, `cortex.learn.elevate`, `skill.list`, `blueprint.read`,
`blueprint.list`.

### Governor-only handlers

| Handler | Reason |
|---------|--------|
| `workspace.init` | Initialization requires governor authority |
| `project.init` | Project creation is a governance action |

### Mutating handlers (DENIED for AUDITOR — P0-B)

The full `MUTATING_HANDLERS` frozenset is defined in `src/arqux/permissions.py`.
Auditor role is denied all of these handlers — including (but not limited to):

- `blueprint.create`, `blueprint.update`, `blueprint.cancel`, `blueprint.fail`, `blueprint.approve`
- `task.create`, `task.update`, `task.complete`, `task.fail`
- `cycle.create`, `cycle.mature`, `cycle.close`
- `cortex.entry.add`, `cortex.entry.delete`, `cortex.entry.update`, `cortex.write`
- `protocol.adopt`, `protocol.release`
- `evidence.record`, `identity.record`
- `session.context.set`, `session.close`
- `project.bind`, `project.unbind`

### HMAC-required handlers (require verified identity)

| Handler | Why HMAC |
|---------|----------|
| `identity.record` | Identity claims require proof |
| `evidence.record` | Evidence must be attributable |
| `blueprint.approve` | Approval requires verified authority |
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
