---
doc_type: explanation
status: informative
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
<p align="center"><sub>Explanation · Informative · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# `arqux.sync` module documentation

*English translation — canonical source: `docs/es/explicacion/sync.md`*

## Location

```
src/arqux/sync.py                  → Main module
src/arqux/handlers/sync/__init__.py → MCP handler: `sync.run`
src/arqux/handlers/sync.py         → Re-export importer (shim)
```

## Nature

The `sync` module is **fail-silent**: it never interrupts the handler that calls it.
Any error is logged with `logger.exception()` and absorbed.
It is the mechanism that keeps `brain.cortex` synchronized after every successful mutation.

---

## Available functions

### 1. `sync_brain()` — Main public function

**Location:** `src/arqux/sync.py`, line 20

**Signature:**
```python
def sync_brain(
    project_root: Path,
    event: str,
    *,
    focus: str | None = None,
    metrics: dict[str, Any] | None = None,
    detail: str = "",
) -> None
```

**Description:**
Updates `brain.cortex` after a successful handler mutation. Modifies:

| Section | Field | What it does |
|---------|-------|--------------|
| `$8/WRK:current` | phase, current, blocked, updated, event | Marks the agent's current state |
| `$2/FCS:current` | what, priority, status, updated, event | Only if `focus` is provided |
| `$6/KNW:*` | metrics | Only if `metrics` is provided |
| `$2/DOM:<project>` (meta-brain) | blueprints, tests, handlers, etc. | Only if `metrics` is provided |

**Parameters:**
- `project_root` — Path to the project directory (or to `.arqux/` itself; auto-detects).
- `event` — Canonical event name: `"blueprint.approve"`, `"task.complete"`, `"cycle.create"`, etc.
- `focus` — *(optional)* Value for `FCS:current`. Only for major events (approve, create, close).
- `metrics` — *(optional)* `dict[str, Any]` of counters to merge. E.g. `{"blueprints_done": 17}`.
- `detail` — *(optional)* Human-readable text about the event.

**Special behavior:**
- If `project_root is None` → returns silently.
- If `brain.cortex` does not exist at the resolved path → returns silently (normal in new workspaces).
- If `crud_update` is unavailable (import failed) → returns silently.

---

### 2. `_update_metrics()` — Private

**Location:** `src/arqux/sync.py`, line 120

**Signature:**
```python
def _update_metrics(
    brain_path: Path,
    metrics: dict[str, Any],
    ts: str,
) -> None
```

**Description:**
Merges the `metrics` counters into section `$6` of `brain.cortex` as `KNW` entries.

- If the key is `"tasks_done"` → status `"done"`
- Otherwise → status `"current"`

Each metric is written with fields: `name`, `value`, `updated`, `topic: "metrics"`, `content`, `status`.

---

### 3. `_count_blueprints()` — Private

**Location:** `src/arqux/sync.py`, line 154

**Signature:**
```python
def _count_blueprints(root: Path) -> dict[str, int]
```

**Description:**
Counts blueprints by status by scanning `BLP-*.md` under `.arqux/cycles/` or `cycles/`.

**Return values (all initialized to 0):**
```python
{
    "done": 0, "draft": 0, "cancelled": 0,
    "review": 0, "in_progress": 0, "ready": 0, "blocked": 0,
}
```

The count is based on the regex `^status:\s*"([^"]+)"` over each file.

---

### 4. `_count_tests()` — Private

**Location:** `src/arqux/sync.py`, line 179

**Signature:**
```python
def _count_tests(root: Path) -> int
```

**Description:**
Counts `*.py` test files in the project's `tests/` directory.

---

### 5. `_sync_meta_brain()` — Private

**Location:** `src/arqux/sync.py`, line 191

**Signature:**
```python
def _sync_meta_brain(
    project_root: Path,
    metrics: dict[str, Any],
    event: str,
    ts: str,
) -> None
```

**Description:**
Syncs metrics and counters to the meta-brain (`meta-brain.cortex`, section `$2`).

Since the DOM fix (BUG-003) the DOM entry is **dynamic**: the project name
is resolved via `_project_name()` (the brain's `IDN:project` → fallback to the
directory name) and normalized with `_normalize_dom_name()` (lowercase). If
`DOM:<project>` does not exist in the meta-brain, `_upsert_meta_dom()` creates
it — `DOM:arqux` is never written unless the project is actually named `arqux`.

Fields written to `DOM:<project>`:
- `updated`, `last_event` (always)
- `blueprints_done`, `blueprints_draft`, `blueprints_cancelled`, `blueprints_completed` (counted from the FS, fallback to `metrics` values)
- `tests` (file count)
- `handlers`, `tasks_done`, `tasks_active`, `cycles_closed` (if present in `metrics`)

### 5b. `reconcile_brain()` — Public

**Location:** `src/arqux/sync.py`

Deep project ↔ meta-brain synchronization. Preserves the project brain's
`OBJ`: an existing entry keeps its `goal`/`status`/`survive` — only `success`,
`updated` and `event` are refreshed — and mirrors metrics into the
meta-brain's `DOM:<project>`.

Tolerant behavior: if the brain has no `OBJ:*` entry in `$3`, it does not
abort — it records `'brain has no OBJ entry in §3'` in the result's
`errors[]`, creates a generic `OBJ:sync` and continues with the meta-brain
sync (`meta_synced=True`). In workspace context the meta-brain's
`FCS:current` is likewise preserved: only `updated`/`event` are refreshed, and
the generic `FCS` is created only if absent.

---

### 6. `sync_run_handler()` — MCP handler `sync.run`

**Location:** `src/arqux/handlers/sync/__init__.py`

**Signature:**
```python
def sync_run_handler(
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT
```

**Description:**
MCP handler that allows manual `brain.cortex` → meta-brain synchronization with complete metrics.

**Parameters:**
- `path` — Path to the project (auto-detected if omitted).

**Usage:**
```python
# From a handler
from arqux.handlers.sync import sync_run_handler

# Call with path
result = sync_run_handler(path="/path/to/project")

# Call without path (auto-detects)
result = sync_run_handler()
```

---

## Usage pattern in handlers

Every mutating handler calls `sync_brain()` as its **last line before return**:

```python
# Example: task.create (task.py:129)
sync_brain(
    root,
    "task.create",
    metrics={"tasks_active": 1},
    detail=f"task {task_id} created in {cycle_id}",
)

# Example: blueprint.complete (review.py:79)
sync_brain(
    root,
    "blueprint.complete",
    focus="Verify ACs and approve",
    metrics={"blueprints_completed": 1},
    detail=f"BLP {bp_id} completed",
)

# Example: cycle.close (cycle.py:588)
sync_brain(root, "cycle.close", focus="Cycle closed",
           metrics={"cycles_closed": 1}, detail=f"cycle {cycle_id} closed")

# Example: skill.edit (skill.py:497)
sync_brain(arqux.parent, "skill.edit",
           detail=f"section ${section} of {name} written")

# Example: project.bind (project.py:284)
sync_brain(root, "project.bind", detail=f"agent {agent_id} bound as {role}")
```

---

## Import conventions

```python
# From handlers/ directly
from ..sync import sync_brain

# From handlers/blueprint/ (nested subpackage)
from ...sync import sync_brain

# Manual MCP handler
from ...sync import sync_brain  # in handlers/sync/__init__.py
```

---

## Handlers that call sync_brain

| Module | Event(s) |
|--------|----------|
| `blueprint.lifecycle` | `blueprint.create`, `blueprint.complete` |
| `blueprint.review` | `blueprint.complete`, `blueprint.approve`, `blueprint.fail` |
| `task` | `task.create`, `task.complete` |
| `cycle` | `cycle.create`, `cycle.close` |
| `skill` | `skill.edit` |
| `project` | `project.bind` |

> **AXM rule:** read-only handlers (list, read, get, status, lessons) must **NOT** call `sync_brain()`.

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
