# Brain — Project-Level Shared Mind

The `brain.cortex` is the **shared mind of the project**. Every agent
bound to this project reads and writes the same brain. All handoffs,
pulses, sessions, lessons, focus, and active context live HERE — not in
separate files. This guarantees that multiple agents working concurrently
share a single project mind.

## Focus
Current focus of the project — one sentence. Set by the governor.

## Objectives
Stable project-level goals (not tasks).

## Sessions
Agents currently bound to this project. Written by `project.bind`.

## Handoffs
Chronological log of work handed between agents. Written by handlers on
task transitions.

## Pulse
Append-only event trace — replaces `pulse.jsonl`. Written by
`evidence.record` and task handlers (`task.complete`, `task.fail`).

## Lessons
Contextual lessons — apply to this project only. Behavioral lessons
(how a role should act regardless of project) live in the identity's
`.cortex`, NOT here.

## Active Context
Currently active cycle/task — updated by handlers on task state changes.

## Risks
Project-specific risks and mitigations.

## Concurrency
Optimistic-locking state. The `brain_version` counter bumps on every
write. Do not edit by hand — handlers manage this automatically.

## Metadata
- **level:** 2
- **project:** <project-name>
- **brain_version:** 0
- **brain_last_writer:** (empty)
- **brain_updated:** (empty)
