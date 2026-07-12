# Permissions Model

ArqUX implements a **three-role governance model** (v0.4.0).

## Roles

| Role | Agent | Description |
|------|-------|-------------|
| **GOVERNOR** | Alfred | Full access — creates cycles, assigns, approves, closes |
| **EXECUTOR** | Jarvis | Universal governance — claims tasks, updates, completes |
| **AUDITOR** | Heimdall, Seshat | Read-only + governance handlers (cannot mutate state) |

## Handler Access by Role

### Handlers accessible by all roles (universal governance)

All blueprint, task, cycle, evidence, cortex, session, project.bind, protocol.adopt, and workspace.status/lessons handlers.

### Governor-only handlers

| Handler | Reason |
|---------|--------|
| `workspace.init` | Initialization requires governor authority |
| `project.init` | Project creation is a governance action |

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
ctx.check("workspace.init")    # PermissionDenied
```
