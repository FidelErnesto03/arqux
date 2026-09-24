# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.4.x   | :white_check_mark: |
| < 0.4   | :x:                |

## Reporting a Vulnerability

To report a security vulnerability, please contact the maintainers directly:

- **Email**: security@arqux.dev
- **PGP Key**: Available at `https://arqux.dev/pgp-key.txt`

You should receive an acknowledgment within **48 hours**. If you don\'t, please follow up.

### Disclosure SLA

| Phase | Timeline |
|-------|----------|
| Acknowledgment | ≤ 48 hours |
| Triage & impact assessment | ≤ 5 business days |
| Patch release (CRITICAL) | ≤ 15 days |
| Patch release (MODERATE) | ≤ 45 days |
| Coordinated public disclosure | After patch release |

## Security Model

ArqUX implements a **three-role governance model** with optional HMAC-based identity verification:

- **GOVERNOR**: Full access to all handlers (Alfred). Can mutate state.
- **EXECUTOR**: Universal access except `workspace.init` and `project.init` (Jarvis). Can mutate state.
- **AUDITOR**: **Read-only** (Heimdall, Seshat). Denylist model — can call any handler except `GOVERNOR_ONLY`, `MUTATING_HANDLERS`, and `CONDITIONAL_MUTATING` invocations that actually mutate (dry-run previews and read modes stay allowed).

### MUTATING_HANDLERS (P0-B, reconciled T-020)

The following handlers mutate state unconditionally (or by default) and are denied to AUDITOR role:

- All `blueprint.*` except `blueprint.read`, `blueprint.list`
- All `task.create`, `task.claim`, `task.update`, `task.complete`, `task.fail`, `task.run`
- `cycle.create`, `cycle.close`, `cycle.synthesize`
- `evidence.record`
- `cortex.entry.add`, `cortex.entry.delete`, `cortex.entry.update`, `cortex.entry.move`, `cortex.write`, `cortex.checkpoint`
- `session.context.set`, `session.close`, `session.bootstrap`, `session.handoff`, `session.pulse.compact` (`session.resume` is a pure read — auditor-allowed)
- `project.bind`, `project.unbind`, `project.init`
- `protocol.adopt`, `protocol.onboard`, `protocol.release`, `protocol.pause`, `protocol.resume`
- `identity.record`
- `skill.record`, `skill.import`, `skill.convert`, `skill.install`
- `sync.run`, `sync.reconcile`, `setup.plantuml`
- `workspace.init`

### CONDITIONAL_MUTATING (T-020)

Denied to AUDITOR only when the invocation mutates (all gate flags truthy AND `dry_run` falsy):

- `cortex.learn.elevate` (`apply`), `cortex.file.validate` (`fix`), `cortex.gc` (`force` + `dry_run=false`),
  `cortex.patch` / `cortex.migrate` (mutate unless `dry_run=true`),
  `skill.evolve` (`apply`), `skill.edit` (`content` provided)

### HMAC Identity Verification

Handlers requiring explicit identity verification:
- `identity.record`
- `evidence.record`
- `blueprint.re_delegate`

Set `ARQUX_STRICT_SECURITY=1` to enforce HMAC verification.

### Cortex Integrity

All `.cortex` files support SHA-256 integrity hashes via the `$INTEGRITY` header.
Auto-signing is NOT applied on write; integrity is verified on demand via `arqux cortex-verify` (P1-P / P1-Q reconciliation — see BLP-014).

Verify integrity with:
```bash
arqux cortex-verify <path-to-cortex-file>
```

## Security Best Practices

1. Always run with `ARQUX_STRICT_ROLES=1` in production
2. Use `ARQUX_STRICT_SECURITY=1` for HMAC enforcement
3. Store agent secrets in `.arqux/secrets/` with mode 0600
4. Rotate agent secrets periodically via `generate_secret()`
5. Never commit `.key` files to version control
6. Verify `.cortex` integrity regularly with `arqux cortex-verify`
7. Use the AUDITOR role for any agent that should not mutate state — the enforcement is now strict (P0-B)

## Threat Model

See [THREAT_MODEL.md](THREAT_MODEL.md) for the full threat model.
