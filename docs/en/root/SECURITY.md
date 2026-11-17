---
doc_type: canon
status: normative
version: 1.0.0
verified: 2026-11-15
---

<!-- DOC-BRAND -->
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../../../docs/assets/brand/arqux-logo-primary-dark.svg">
    <img alt="ArqUX" src="../../../docs/assets/brand/arqux-logo-primary-light.svg" width="240">
  </picture>
</p>
<p align="center"><sub>Canon · Normative · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# Security policy

English twin of the canonical [`SECURITY.md`](../../../SECURITY.md).

## Supported versions

| Version | Supported |
|---|---|
| 1.0.x | ✅ |
| ≤ 0.9.x | ❌ — upgrade to 1.0.x |

> Honest note: `pip install arqux` may still serve the 0.9.x series from PyPI while the repository declares 1.0.0. Only the 1.0.x line receives security fixes.

## How to report a vulnerability

**Channel: GitHub Security Advisories (Private Vulnerability Reporting).**

1. Open the [`FidelErnesto03/arqux`](https://github.com/FidelErnesto03/arqux) repository.
2. **Security** tab → **Advisories** → **Report a vulnerability**.
3. The report is private by default: only maintainers see it until coordinated disclosure.

Include in the report:

- Description of the impact and the conditions to trigger it
- Reproduction steps or a minimal PoC
- Affected version (`arqux --version` / `pyproject.toml`)
- Involved files or handlers, if known

**Do not use public issues or PRs** for undisclosed vulnerabilities.

## What to expect (honest windows, best effort)

We are a small project; we declare realistic targets, not contractual SLAs:

| Phase | Target window |
|---|---|
| Acknowledgement | ~7 days |
| Triage and severity assessment | ~14 days |
| Fix + release | Depends on severity; criticals are prioritized |
| Coordinated disclosure | After the fix release, agreed with you |

If a window is exceeded, a bump on the advisory is welcome — do not publish before the disclosure agreement.

## Scope

**Report (in-scope):**

- Bypass of the permissions model (an AUDITOR executing mutating handlers)
- Bypass or weakness of HMAC verification or of the fail-closed codec boundary
- Invalid Ed25519 signatures accepted / SHA-256 integrity evaded
- Vulnerabilities in core dependencies that affect ArqUX
- Governed writes that evade the `secret_pattern` check or other `enforce:CODE` rules

**Do not report here (out-of-scope):**

- Undesired behavior of third-party LLM agents (hallucinations, model jailbreaks)
- Vulnerabilities in external MCP harnesses/clients, not in ArqUX code
- Problems in your own policy rules or configuration
- Denial of service via the user's own environment resources

## Disclosure

Coordinated: we publish the advisory together with the fix, crediting the reporter if desired. Please do not disclose until then.

## Eating our own cooking

This product applies to itself what it sells: governance policies and evidence are signed with pure Ed25519 (REQ-12) and `.cortex` file integrity is verified via SHA-256 (`arqux cortex-verify`). If you find a way to forge that evidence chain, it is exactly the class of finding we care most about.

See also: [`THREAT_MODEL.md`](THREAT_MODEL.md) — full threat model · [`PERMISSIONS.md`](PERMISSIONS.md) — authorization model.

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
