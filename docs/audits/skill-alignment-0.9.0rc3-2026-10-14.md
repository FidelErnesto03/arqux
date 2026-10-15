# ArqUX agent skills: release alignment and governance failure handling

Date: 2026-10-14. Author: Alfred. Assessment only; no fixes applied.

## Verdict and scope

The agent instruction surface is partially aligned, not fully aligned. It contains specific error triggers and governed issue handlers, but it does not provide a complete, consistently discoverable, distributed procedure for an agent encountering governance tool failures.

“Skill” here covers the entry contract (`AGENTS.md` and its deltas), protocol, workflow index, recovery workflows, CORTEX output rules, local `arqux-issues`, handler discovery, MCP error delivery, and issue lifecycle implementation. This is not a certification of every feature or every skill.

Reference version: repository `pyproject.toml` and the managed uv installation both identify as `0.9.0rc3`. The changelog labels this a candidate, not stable. Public web requests did not establish the latest published candidate: the accessible PyPI page was an older cached release and the candidate-specific request failed. No conclusion about the latest public release is drawn from that cache.

Governance documents were retrieved through MCP. Source code, tests, and package resources were inspected read-only. Working-state checkpoints are the only governance mutations associated with this assessment.

## Findings

### F-01 — High: documented force repair actually bypasses validation

Workspace and packaged `workflows/w09-crud-blocked.md` describe `force=True` as automatic completion of missing semantic fields and call it safe. They still describe CODEC-CORTEX transactions as the mutation implementation.

Current `src/arqux/core/state/_crud.py`, `_read_and_mutate`, instead rejects validation errors only when `not force`. With force, the existing incomplete document proceeds to the ArqUX atomic writer. `src/arqux/cortex/atomic.py` reserves its own force parameter for future use; it does not implement the promised semantic repair.

An in-memory diagnostic intercepted the atomic writer. A lesson missing `prevention` was rejected normally, accepted with force, and passed to the writer still missing `prevention`. This reproduced in both repository source and the managed installed package. No governance file was written by the diagnostic.

The same workflow recommends an unbounded `pip install --upgrade codec-cortex`, whereas the current `pyproject.toml` deliberately constrains the codec extra to `>=0.6.2,<0.7` because of API incompatibility in the candidate line.

### F-02 — High: incident reporting is local and its primary trigger is user reporting

The live `arqux-issues` definition triggers when the user reports a problem. It also defines maintenance triggers at session start, block closure, and explicit status requests. Those are real procedural triggers, but none defines an exhaustive governance-tool-failure intake procedure.

The skill expressly prohibits copying itself into `src/arqux/skills/` and says it is development-runtime-only. The managed package has no `skills/arqux-issues.skill.md`; the repository has no packaged counterpart. The `issue.*` handlers are distributed, while the detailed reporting method is not.

Neither the MCP wrapper nor the entry instructions provide a common bridge from a failed operation to this skill, duplicate lookup, evidence collection, or incident registration. The desired integration therefore cannot be described as fully native to an ordinary installation.

### F-03 — High: tool failures are delivered with `isError=false`

`src/arqux/server.py` turns handler results and caught exceptions into text and returns `list[TextContent]`. A synthetic MCP diagnostic exercised three branches:

| Branch | Text result | MCP isError |
| --- | --- | --- |
| Handler returns a domain error | OUT-ERROR / SYNTHETIC_ERROR | false |
| Handler raises an exception | OUT-ERROR / INTERNAL_ERROR | false |
| Handler does not exist | OUT-ERROR / NOT_FOUND | false |

This does not prove that every agent ignores such errors: an agent can inspect the text. It does prove that a client relying on the structured error flag will not receive the expected failure signal in these branches. There is no shared recovery hint attached to these generic wrapper errors, although `cortex.skill.md` requires actionable error hints.

### F-04 — High: LITE discovery omits the recovery and continuity tools

Live `handler.list(tier=LITE)` returned 24 handlers. Neither its output nor the repository tier map includes `issue.create`, `issue.list`, `skill.get`, `handler.how_to`, or `cortex.checkpoint`.

This is a discovery omission, not proof that these calls are blocked: they are callable in this session. Nevertheless, an agent following tier discovery as its capability source does not discover the tools that the protocol recommends for help, skill loading, reporting, and checkpoints. NANO is intentionally read-only; any recovery route must respect that distinction.

Live `handler.how_to(intent="problemas errores herramientas gobernanza registrar issue")` returned `GUIDE_NOT_FOUND`. The returned corpus lists eight topics and contains no governance incident/recovery topic. The response again had `isError=false`.

### F-05 — High: recovery instructions conflict with the current contract

The current workspace/project contract requires MCP-only governance access and forbids CLI fallback. Live and packaged `protocol.skill.md` allow CLI fallback. W09 recommends `arqux brain repair` and `arqux verify`; the current CLI command registry contains neither a `brain` group nor a `verify` command.

W11 recommends direct `mv`, Python writer calls, and constructing `$0.1` metadata. These bypass the current MCP-only rule. `src/arqux/doctor.py` explicitly treats `$0.1` metadata as obsolete and requires `$19`.

The packaged AGENTS entry also references absent `handlers.skill.md` and `mcp.skill.md`. The workflow index references `workflows/w00-triage.md`, which is absent from the packaged source and returned NOT_FOUND through live skill.get. These broken references weaken startup and fallback guidance.

### F-06 — Medium: a package version does not establish instruction synchronization

`workspace.init` copies skills and workflows only when destination files do not exist. This preserves customizations, but it is not an upgrade reconciliation procedure. `UPGRADE.cortex` discusses package, identities, AGENTS, state migration and verification without an explicit versioned skill/workflow merge step.

The live protocol includes discovery/how-to instructions absent from the packaged protocol. It also includes a Teamwork session-close gate and brain watermark, contradicting the current workspace rule that time registration runs only on request and remains outside governance artifacts.

Repository and managed-package bytes match for server.py, handler discovery, issue handlers, packaged protocol, workflow index and W09. They differ for `core/state/_crud.py`, despite the same 0.9.0rc3 label. This establishes code drift, not which module a running MCP process currently holds in memory.

### F-07 — Medium: reporting quality and verification promises exceed enforcement

The issue skill asks for reproducible context, expected/actual results, attempted workarounds, and evidence. `issue.create` accepts severity, description and detector, normalizes all description whitespace, and creates context containing only reporter/time, with pending lesson fields. Rich detail can be appended through `issue.update(note=...)`, but no mandatory intake step guarantees it.

`issue.update(status=verified)` checks that audit_ref exists among project PULSE IDs. It does not check the event's auditor identity, verdict, relationship to the issue, or a permitted prior lifecycle state. Thus the code enforces reference existence, a narrower guarantee than verified auditor approval. This finding is based on implementation inspection; no live issue was transitioned to test it.

## Existing mechanisms that should be retained

- Governed issue.create/read/list/update and PULSE traceability.
- Specific W09/W11 workflow selection rules, after correcting their methods.
- A generic error presentation trigger in cortex.skill.md.
- Session and work-block issue maintenance triggers in the local issue skill.
- Per-handler actionable diagnostics where already implemented.
- The separation between diagnosis, technical remediation, scope decisions, and independent verification.

## Proposed adequacy criteria — not implemented

1. Define one distributed governance-failure procedure, referenced by AGENTS, protocol, workflows and intent-based help. Keep development-only issue history separate from the generally distributed method.
2. Trigger on structured errors, OUT-ERROR text, transport timeouts/disconnections, permission denial, unsupported arguments, validation failures, concurrency conflicts, and success responses contradicted by read-back evidence. Expected workflow denials should be classified before becoming bugs.
3. Capture handler, sanitized arguments, project/context, relevant package/capability versions, expected/actual result, exact diagnostic, prior attempts and read-back state.
4. Diagnose read-only first. Reconcile unknown outcomes before retrying mutations. Define bounded retries, duplicate detection and escalation conditions. Never treat force as semantic repair.
5. Specify what happens if the reporting/checkpoint channel itself is unavailable: stop dependent mutations, preserve a pending report through an explicitly permitted channel, disclose the persistence limit, and reconcile after reconnection. Avoid recursive reporting attempts.
6. Distribute enough discovery and help for each tier and role without granting extra mutation rights.
7. Reconcile installed guidance with upstream versions using reviewed diffs/hashes, preserving local customizations and identity lessons.
8. Test fresh installation, existing-workspace upgrade, each error family, failed report persistence, repeated incidents, and genuine audit endorsement. Verify the agent-facing path as well as individual handlers.

## Verification and limits

Executed against repository source:

`python -m pytest -q tests/test_issue_handlers.py tests/test_server_call_tool.py tests/test_how_to.py tests/test_skill_get.py tests/test_packaging.py`

Result: **33 passed**. These tests demonstrate the existing components' covered behavior; they do not certify the absent integrated agent recovery procedure. Packaging tests exercise source resources and a temporary initialization, not an independently built release wheel.

Additional checks: live MCP skill/discovery/help reads; in-memory synthetic MCP error delivery; actual CLI command registry; mocked force validation behavior in repository and managed installation; selected source/package byte comparison. No real governance failure was induced and no production issue status was changed.

An attempt to register this report through `evidence.record` with an audit identifier was rejected with NOT_FOUND: that handler requires a task already present in a cycle's tasks directory. No task was fabricated or existing task reused for unrelated evidence. The report and working-state checkpoint persist the assessment; a PULSE evidence entry was not successfully created by that call.

Recommended work order: correct unsafe/misleading recovery guidance; define the distributed failure contract; connect discovery and structured error delivery; enforce evidence/endorsement guarantees; verify fresh-install and upgrade behavior end to end.
