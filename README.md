<div align="center">

# ⬡ ArqUX

**Architectural User Experience for governed AI agents.**

[![Version](https://img.shields.io/badge/version-0.4.0-167A55?style=flat-square&labelColor=050807)](https://pypi.org/project/arqux/)
[![Status](https://img.shields.io/badge/status-beta-FFB020?style=flat-square&labelColor=050807)](https://pypi.org/project/arqux/)
[![License](https://img.shields.io/badge/license-Apache--2.0-2EC98D?style=flat-square\&labelColor=050807)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-8FE3C0?style=flat-square\&labelColor=050807)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-governance%20layer-167A55?style=flat-square\&labelColor=050807)](https://github.com/FidelErnesto03/arqux)
[![Getting Started](https://img.shields.io/badge/Getting%20Started-guide-2EC98D?style=flat-square\&labelColor=050807)](docs/guides/GETTING_STARTED.md)
[![Handlers](https://img.shields.io/badge/MCP%20Handlers-73-purple)](https://github.com/FidelErnesto03/arqux)
[![Agents](https://img.shields.io/badge/agents-4-red)](https://github.com/FidelErnesto03/arqux)
[![CORTEX](https://img.shields.io/badge/CORTEX-persistent%20memory-2EC98D?style=flat-square\&labelColor=050807)](https://github.com/FidelErnesto03/codec-cortex)
[![Coverage](https://img.shields.io/badge/coverage-71%25-167A55?style=flat-square\&labelColor=050807)](https://github.com/FidelErnesto03/arqux)

**The file is the protocol.**

</div>

---

Most teams are trying to build critical AI operations on top of temporary chat conversations.

**ArqUX changes the operating model.**

ArqUX is not a platform. It's governance infrastructure for your platform. You already have your agent stack — LangChain, CrewAI, Codex, Hermes. ArqUX goes underneath all of them. It decouples agent intelligence from agent governance, so any agent, with any model, on any framework, can operate under the same architectural control.

---

## ⬡ Why ArqUX exists

AI agents are becoming operational actors.

But enterprise environments cannot rely on agents that:

* forget previous decisions;
* mutate context without evidence;
* act outside their intended role;
* mix governance, execution, documentation, and audit responsibilities;
* depend on fragile prompt discipline;
* leave no institutional memory behind.

ArqUX introduces a governed layer between the user, the agent, the model, and the workspace.

```text
The model reasons.
The agent acts.
ArqUX governs.
```

---

## Core pipeline

```text
[ User Intention ]
       │
       ▼
[ Architectural Governance ]
       │
       ▼
[ Agent Identity ]
       │
       ▼
[ Behavioral Contract ]
       │
       ▼
[ Blueprint Lifecycle ]
       │
       ▼
[ Execution with Evidence ]
       │
       ▼
[ Persistent Institutional Memory ]
```

ArqUX decouples **agent intelligence** from **agent governance**.

The language model is not the center of the system.
The governed architecture is.

---

## The governed experience

This is what happens when an agent joins an ArqUX workspace.

### 1. Init

```bash
arqux init
```

A `.arqux/` directory appears. Inside it: `AGENTS.md` (every agent reads this first), `brain.cortex` (persistent memory), `identities/` (agent contracts), `cycles/` (work organized in cycles), `evidence/pulse.jsonl` (every action, timestamped). No server. No API key. A directory.

### 2. The agent discovers governance

Any agent entering the workspace reads `AGENTS.md`. It learns which project it's in, what cycle is active, which identity to assume, and what rules constrain its behavior. The agent doesn't guess. It reads.

### 3. Work is organized in Blueprints

No more "build this feature" directly from chat. Every piece of work becomes a Blueprint — a structured 18-section document that captures the problem, the solution, the acceptance criteria, and the execution plan. Blueprints are decision maps. They prevent architecture-by-accident.

### 4. Tasks are claimed, executed, verified

An executor claims a task. When done, evidence is recorded — test output, file changes, decisions made. No task is "done" until it leaves a trace.

### 5. Learning becomes institutional

When something goes wrong, the lesson isn't lost in chat scrollback. It's recorded in the agent's identity and elevated to the project brain. The next agent won't repeat the same mistake. The organization keeps the knowledge.

### 6. Any agent can join

Codex. OpenCode. Hermes. Gemini CLI. z.ai. Qwen. They don't share a runtime. They don't share a model. They share `.arqux/`.

---

## ⬢ The Hexagon Contract

The hexagon is the structural symbol of ArqUX.

It is not decoration.

It represents the six boundaries required for enterprise-grade agent operation:

```text
                 [ 1. Identity ]
                  Who is acting?
                       ▲
                       │
 [ 3. Context ] ◀── ⬡ ArqUX ──▶ [ 2. Contract ]
 From which state?                  Under what limits?
                       │
                       ▼
                 [ 5. Execution ]
              What is being changed?

 [ 6. Evidence ]                           [ 4. Decision ]
 How is it verified?                       What is determined?
```

| Boundary      | Question                       |
| ------------- | ------------------------------ |
| **Identity**  | Who is acting?                 |
| **Contract**  | Under which behavioral limits? |
| **Context**   | From which memory and state?   |
| **Decision**  | What is being determined?      |
| **Execution** | What is being changed?         |
| **Evidence**  | How is the action verified?    |

```text
The agent is the interface.
The hexagon is the contract.
ArqUX is the governance layer.
```

---

## What ArqUX provides

| Capability                    | Description                                                                   |
| ----------------------------- | ----------------------------------------------------------------------------- |
| **Governed agent identities** | Agents operate through specialized roles instead of generic behavior.         |
| **Behavioral contracts**      | Each identity is constrained by explicit AXM, LIM, and FCS rules.             |
| **Hot identity handoff**      | Switch between identities through natural invocation or explicit request.     |
| **Blueprint lifecycle**       | Design decisions are captured in structured 18-section Blueprints.            |
| **CORTEX memory**             | Decisions, lessons, state, and evidence are persisted in `.cortex` artifacts. |
| **MCP governance layer**      | ArqUX exposes governance operations through MCP handlers.                     |
| **Evidence trail**            | Actions, transitions, approvals, and lessons can be traced.                   |
| **Learning elevation**        | Knowledge can move from behavioral to contextual to procedural layers.        |

---

## Agent identities

ArqUX replaces the idea of “one assistant” with a team of specialized identities.

Each identity is not just a persona.
It is an **operational contract**.

| Identity       | Role     | Primary responsibility                                                 |
| -------------- | -------- | ---------------------------------------------------------------------- |
| **⬡ Alfred**   | Governor | Cycles, Blueprints, approvals, state, governance flow.                 |
| **⬡ Jarvis**   | Executor | Technical work, implementation, task claiming, completion evidence.    |
| **⬡ Seshat**   | Scribe   | Documentation, diagrams, reports, presentations, structured knowledge. |
| **⬡ Heimdall** | Guardian | Audit, monitoring, verification, risk detection, reporting.            |

Example handoff:

```text
"Hello Jarvis"          # Activates the technical executor.
"Switch to Seshat"      # Transfers the session to the documentation identity.
"Back to Alfred"        # Returns to governance mode.
```

Identity handoff prevents role confusion.

When the operating responsibility changes, the active identity must change with it.

---

## Blueprints

A Blueprint is ArqUX’s decision map.

It prevents agents from jumping directly from intention to execution by forcing architectural reasoning before operational mutation.

A governed Blueprint captures a design decision across 18 sections:

```text
§1  Problem
§2  Objective
§3  Preconditions
§4  Guiding Principle
§5  Context
§6  Scope
§7  Rules
§8  Technical Design
§9  Operational Design
§10 Contracts
§11 Work Procedure
§12 Acceptance Criteria
§13 Validations
§14 Tasks
§15 Risks
§16 Blocking Rule
§17 Expected Output
§18 Quality
```

Blueprints are designed to make agent work explicit, reviewable, and traceable.

---

## CORTEX memory

ArqUX uses `.cortex` artifacts to preserve governed memory across sessions, projects, and identities.

CORTEX memory may include:

* decisions;
* project state;
* lessons learned;
* role constraints;
* behavioral records;
* procedural knowledge;
* audit evidence;
* handoff state;
* Blueprint lifecycle data.

CORTEX is not a prompt cache.

It is a structured memory layer for agents operating under governance.

---

## Continuous learning

ArqUX treats learning as a governed pipeline.

The goal is not only to make the agent remember.
The goal is to prevent the organization from losing operational knowledge every time a session ends.

```text
[ Individual Lesson ]
        │
        ▼
[ Behavioral Record ]
        │
        ▼
[ Contextual Knowledge ]
        │
        ▼
[ Procedural Skill ]
        │
        ▼
[ Reusable Institutional Capability ]
```

A lesson that is not retained will be paid for again.

---

## MCP governance layer

MCP gives agents access to external capabilities.

ArqUX uses MCP as a governance channel: not only to expose tools, but to help agent clients interact with identity state, handoff rules, Blueprint lifecycles, CORTEX memory, and evidence records.

```text
MCP is the integration channel.
ArqUX is the governance layer.
```

---

## Two protocols. One governance layer.

ArqUX exposes governance through two complementary protocols.

**Level 1 — File system.** The universal protocol. Any agent that can read and write files can participate. No SDK, no library, no API key. Just read `AGENTS.md` and write to `.cortex` files. Every agent starts here.

**Level 2 — MCP.** The structured protocol. Agents that speak the Model Context Protocol get full governance: create blueprints, claim tasks, record evidence, sync brain state. MCP is the integration channel. ArqUX is the governance layer.

```text
Level 1 (universal):   Agent reads AGENTS.md, writes brain.cortex
Level 2 (structured):  Agent calls MCP handlers for full lifecycle
```

---

## Quick start

Install ArqUX:

```bash
pip install arqux
```

Initialize a workspace:

```bash
arqux init
```

Any agent can now join. Point your agent to the workspace:

```bash
# Example: OpenCode agent joining an ArqUX workspace
opencode --instructions "$(cat .arqux/AGENTS.md)"
```

The agent reads the governance contract. It discovers its identity, the active cycle, and the rules. It reads `brain.cortex` for context. It's ready to work under governance — without installing any ArqUX SDK.

---

## From prompt to governed architecture

```diff
- Without ArqUX:
- User: "Build this feature."
- Agent: Implements directly from chat context.
- Result: Fragile memory, unclear decision path, weak auditability.

+ With ArqUX:
+ User intention
+   → Blueprint
+   → Identity assignment
+   → Behavioral contract
+   → Task execution
+   → Evidence
+   → CORTEX memory
+   → Reusable learning
+
+ Result: The organization keeps the decision, the reason, the execution trace, and the lesson.
```

A temporary conversation becomes a governed operational cycle.

---

## Design principles

### 1. Architecture before automation

ArqUX does not celebrate uncontrolled autonomy.

It makes autonomy governable.

### 2. Identity before action

An agent must know who it is before it acts.

### 3. Contract before execution

A task is not valid only because it can be executed.

It must be executed under the correct behavioral contract.

### 4. Evidence before closure

A task is not complete until it leaves verifiable evidence.

### 5. Memory before repetition

A lesson that is not retained will be paid for again.

### 6. Handoff before confusion

When the operating role changes, identity must change explicitly.

---

## What ArqUX is not

ArqUX is not:

* a chatbot;
* a prompt collection;
* a UI skin;
* a generic agent personality pack;
* a memory hack;
* a replacement for the language model;
* a replacement for human architectural responsibility.

**ArqUX is the layer that makes agent work governable.**

---

## Positioning

### Short version

**ArqUX converts AI agents into governed infrastructure — agnostic of model, framework, or transport.**

### Technical version

**ArqUX is a governance layer for AI agents, combining identity contracts, MCP operations, Blueprint lifecycles, CORTEX memory, and verifiable evidence. It works through two protocols: file system (universal) and MCP (structured).**

### Enterprise version

**ArqUX enables organizations to operate AI agents in production without losing control, traceability, or institutional memory. Any agent, any stack.**

### Manifesto version

**The future of agents is not a smarter chat.
It is a more accountable architecture.
And it works with the agents you already have.**

---

## Roadmap

### v0.4.x — Foundation

* Governance framework.
* MCP handlers.
* Multi-identity model.
* Behavioral contracts.
* Blueprint lifecycle.
* CORTEX memory.
* Learning elevation.
* Dogfooding through ArqUX itself.

### v1.x — Operational maturity

* Stronger workspace lifecycle.
* Expanded CORTEX / HCORTEX operations.
* Improved validation and recovery.
* Better guided project onboarding.
* Richer operational reporting.

### v2.x — Enterprise scale

* Visual governance interface.
* Enterprise integrations.
* Institutional skill marketplace.
* Multi-project governance dashboard.
* Advanced audit and compliance workflows.

---

## Development installation

Clone the repository:

```bash
git clone https://github.com/FidelErnesto03/arqux.git
cd arqux
```

Install development dependencies:

```bash
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

---

## License

ArqUX is released under the **Apache License 2.0**.

See [`LICENSE`](LICENSE).

---

## Security

See [SECURITY.md](SECURITY.md) for information on reporting vulnerabilities.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute to ArqUX.

---

<div align="center">

**⬡ ArqUX**

**Governance infrastructure for AI agents.**

```text
The file is the protocol.
The hexagon is the contract.
ArqUX is the governance layer.
```

---

## Edge Cases

See [docs/reference/edge-cases/](docs/reference/edge-cases/) for documentation on edge cases and extreme scenarios.

</div>
