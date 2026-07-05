# ARQUX Agent Identities

This directory contains identity files for AI agents operating under the
Arqux governance framework. Each identity file is a canonical CODEC-CORTEX
`.cortex` document that defines an agent's role, personality, axioms,
limits, and behavioral lessons.

## Available identities

- **alfred.cortex** — Default identity. Personal assistant of the Architect.
  Alfred manages workspace governance: opens cycles, creates tasks, records
  evidence. STANDBY-FIRST, CORTEX-OUT, and HCORTEX discipline. Always
  addresses the user as "el Arquitecto".

- **jarvis.cortex** — Technical executor of the Architect. Claims tasks
  from the active cycle, implements solutions, captures evidence. Cannot
  create cycles or tasks.

- **governor.cortex** — Role-level governor template. Expected behavior for
  any agent acting as governor. Always addresses the user as "el Arquitecto".

- **executor.cortex** — Role-level executor template. Expected behavior for
  any agent acting as executor. Always addresses the user as "el Arquitecto".

- **auditor.cortex** — Role-level auditor template. Read-only compliance and
  review agent. Always addresses the user as "el Arquitecto".

## Core principle

All identities share a fundamental axiom: **the user is "el Arquitecto"**
(the Architect). The agent — whether Alfred, Jarvis, or a custom identity —
executes, suggests, informs, reports. **Never decides for the Architect.**

Decisions about direction, priority, and scope always belong to the Architect.

## Identity file format

Each identity file uses canonical CODEC-CORTEX sigil format with a `$0`
glossary. Sections:

```
$1: IDENTITY    — IDN:agent{name, role, purpose}
$2: FOCUS       — FCS:default{what, priority, status}
$3: AXIOMS      — AXM:rule{free-text principle}
$4: LIMITS      — LIM:name{limit, severity}
$5: LESSONS     — LNG:name{type, cause, lesson}
$6: DESCRIPTION — DESC:persona{free-text persona}
```

## Custom identities

To create a custom identity:

1. Copy one of the existing files:
   ```bash
   cp identities/alfred.cortex identities/my-agent.cortex
   ```
2. Edit the IDN section with your agent's name and role.
3. Place the file in the package's `identities/` directory.
4. Set `ARQUX_AGENT_ID=my-agent` as environment variable.

The identity file is also used for behavioral lessons — these apply
regardless of which project the agent is bound to (§12 in AGENTS.md).
