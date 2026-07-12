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

You should receive an acknowledgment within **48 hours**. If you don't, please follow up.

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

- **GOVERNOR**: Full access to all handlers (Alfred)
- **EXECUTOR**: Universal access except `workspace.init` and `project.init` (Jarvis)
- **AUDITOR**: Read-only access + governance handlers (Heimdall, Seshat)

### HMAC Identity Verification

Handlers requiring explicit identity verification:
- `identity.record`
- `evidence.record`
- `blueprint.approve`
- `blueprint.re_delegate`

Set `ARQUX_STRICT_SECURITY=1` to enforce HMAC verification.

### Cortex Integrity

All `.cortex` files support SHA-256 integrity hashes. Enable strict verification with `ARQUX_STRICT_SECURITY=1`.

## Security Best Practices

1. Always run with `ARQUX_STRICT_ROLES=1` in production
2. Use `ARQUX_STRICT_SECURITY=1` for HMAC enforcement
3. Store agent secrets in `.arqux/secrets/` with mode 0600
4. Rotate agent secrets periodically via `generate_secret()`
5. Never commit `.key` files to version control
