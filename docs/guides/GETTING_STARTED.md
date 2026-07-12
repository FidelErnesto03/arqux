# Getting Started with ArqUX

ArqUX (Architectural User Experience) is a governance framework for AI agent teams. It helps you organize, track, and verify the work your AI agents do — like a project management system designed specifically for human-AI collaboration.

## Three Documents, Three Audiences

| Document | For | Purpose |
|---|---|---|
| `AGENTS.md` | AI agents | Entry point: tells agents where they are and who governs them |
| `arqux quickstart` | Developers | CLI command that bootstraps a workspace |
| `GETTING_STARTED.md` | **You** | This guide — human-friendly walkthrough |

## Quick Start (5 Steps)

### 1. Install ArqUX

```bash
pip install arqux
```

### 2. Initialize a Workspace

```bash
# Create a directory for your projects
mkdir my-workspace && cd my-workspace

# Bootstrap governance
arqux quickstart
```

This creates `.arqux/` with the governance files, places `AGENTS.md` as the agent entry point, and prints next steps.

### 3. Set Your Identity

```bash
export ARQUX_AGENT_ID=my-name
export ARQUX_AGENT_ROLE=governor
```

Roles:
- **governor**: full access (create cycles, assign work, approve)
- **executor**: works on assigned tasks
- **auditor**: read-only review

### 4. Register a Project

```bash
arqux call project.init path=./my-project
```

This creates a project with its own brain, ready for cycles and blueprints.

### 5. Create a Cycle and Start Working

```bash
# Open a cycle
arqux call cycle.create name=CYCLE-01

# Define work
arqux call blueprint.create obj="My first feature"
arqux call blueprint.define BLP-001
arqux call blueprint.ready BLP-001

# Execute
arqux call blueprint.claim BLP-001
# ... do the work ...
arqux call blueprint.complete BLP-001
```

## Glossary (Human Language)

| Term | Meaning |
|---|---|
| **Workspace** | Root directory containing all your governed projects |
| **Project** | A specific codebase or domain under governance |
| **Cycle** | A working period (like a sprint) containing related blueprints |
| **Blueprint** | A defined piece of work with scope, criteria, and tasks |
| **Agent** | An AI assistant or human with a defined role |
| **Governor** | The person/agent who creates cycles and approves work |
| **Executor** | The person/agent who completes tasks |
| **Auditor** | The person/agent who verifies work quality |
| **Brain** | The project's memory — a file tracking state, focus, and lessons |
| **Evidence** | Proof that work was completed (test output, screenshots, logs) |
| **Cortex** | The file format used for governance state |

## Example: From Zero to First Blueprint

```bash
# Install
pip install arqux

# Bootstrap
mkdir demo && cd demo
arqux quickstart

# Set identity
export ARQUX_AGENT_ID=alice
export ARQUX_AGENT_ROLE=governor

# Create a project
arqux call project.init path=./my-app

# Start a cycle
cd my-app
arqux call cycle.create name=CYCLE-01

# Define work
arqux call blueprint.create obj="Add login page"
arqux call blueprint.define BLP-001
arqux call blueprint.ready BLP-001

# Execute
arqux call blueprint.claim BLP-001
# ... implement the login page ...
arqux call blueprint.complete BLP-001 evidence="Login page implemented"

# Close the cycle
arqux call cycle.close CYCLE-01
```

## Next Steps

- Run `arqux doctor` to check workspace health
- Run `arqux doctor --fix` to auto-repair common issues
- Read `SECURITY.md` for security model and HMAC configuration
- Read `PERMISSIONS.md` for detailed role documentation
- See all available handlers: `arqux handlers`
