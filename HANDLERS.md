---
doc_type: reference
status: informative
version: 1.0.0
verified: 2026-11-17
---

<!-- DOC-BRAND -->
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./docs/assets/brand/arqux-logo-primary-dark.svg">
    <img alt="ArqUX" src="./docs/assets/brand/arqux-logo-primary-light.svg" width="240">
  </picture>
</p>
<p align="center"><sub>Referencia · Informativo · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# Referencia de handlers MCP

Total: **116** handlers en 18 dominios.

Generado del registro real. No editar a mano: regenerar con `python scripts/generate_handlers_md.py`.

## Índice por dominio

- [Blueprints](#blueprints) — 16 handlers
- [Ciclos](#ciclos) — 6 handlers
- [Contexto](#contexto) — 2 handlers
- [Cortex / memoria](#cortex--memoria) — 24 handlers
- [Evidencia](#evidencia) — 3 handlers
- [Identidades](#identidades) — 4 handlers
- [Issue](#issue) — 4 handlers
- [Loop VAMOS](#loop-vamos) — 9 handlers
- [Protocol](#protocol) — 5 handlers
- [Proyectos](#proyectos) — 5 handlers
- [Registro MCP](#registro-mcp) — 2 handlers
- [Sesiones](#sesiones) — 9 handlers
- [Setup / PlantUML](#setup--plantuml) — 1 handlers
- [Sincronía](#sincronía) — 2 handlers
- [Skills](#skills) — 8 handlers
- [Tareas](#tareas) — 8 handlers
- [Timelog](#timelog) — 5 handlers
- [Workspace](#workspace) — 3 handlers

## Blueprints

### `blueprint.ac`

Verify one AC in §12.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `ac_id` | `string` | **sí** | — | AC ID like AC-01 |
| `bp_id` | `string` | **sí** | — |  |
| `evidence` | `string` | no | — | Evidence if verified |
| `path` | `string` | no | — |  |
| `reason` | `string` | no | — | Reason if failed |
| `status` | `string` | **sí** | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `blueprint.block_for_architect`

Block for Architect manual review.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `bp_id` | `string` | **sí** | — |  |
| `cycle` | `string` | no | — |  |
| `path` | `string` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `blueprint.cancel`

Cancel a Blueprint. Governor-only. State → cancelled.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `bp_id` | `string` | **sí** | — |  |
| `cycle` | `string` | no | — |  |
| `path` | `string` | no | — |  |
| `reason` | `string` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `blueprint.claim`

Executor claims the Blueprint. ready → in_progress + implicit executor assignment. Executor resolved from: agent_id param (governor) > declared executor > active session context > authenticated agent.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `agent_id` | `string` | no | — | Explicit executor assignment (governor-only). |
| `bp_id` | `string` | **sí** | — |  |
| `cycle` | `string` | no | — |  |
| `path` | `string` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `blueprint.complete`

Declare execution complete. in_progress → done (completado + aprobado en 1 paso).

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `bp_id` | `string` | **sí** | — |  |
| `cycle` | `string` | no | — |  |
| `evidence` | `string` | no | — |  |
| `path` | `string` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `blueprint.create`

Create a new Blueprint from BLP_TEMPLATE.md in draft state.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `cycle` | `string` | no | — | Cycle ID. Uses most recent if omitted. |
| `obj` | `string` | **sí** | — | Blueprint objective |
| `path` | `string` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `blueprint.execute`

Execute a Blueprint: verify §3 preconditions, run §14 tasks sequentially, verify §12 ACs, mark complete (BLP-010 meta-handler). Supports dry_run mode.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `bp_id` | `string` | **sí** | — | Blueprint ID. |
| `content` | `string` | no | — | CORTEX content with keys bp_id, evidence, fail_reason. |
| `dry_run` | `boolean` | no | False | If true, report what would happen without modifying state. |
| `path` | `string` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `blueprint.fail`

Blueprint hit an obstacle. State → blocked.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `bp_id` | `string` | **sí** | — |  |
| `cycle` | `string` | no | — |  |
| `path` | `string` | no | — |  |
| `reason` | `string` | **sí** | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `blueprint.frontmatter.update`

Set/repair Blueprint frontmatter scalars (title, cycle) — the sanctioned write path for fields no other handler can set. Derives title from the body marker/heading when omitted.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `bp_id` | `string` | **sí** | — |  |
| `cycle` | `string` | no | — | New cycle id (optional). |
| `path` | `string` | no | — |  |
| `title` | `string` | no | — | New title (optional; derived from body if omitted). |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `blueprint.list`

List Blueprints with optional filters. Paginated: limit + offset; fields total, returned, offset, next_offset report the pagination state.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `cycle` | `string` | no | — |  |
| `limit` | `integer` | no | — | Max blueprints per page (default: all). |
| `offset` | `integer` | no | 0 | Blueprints to skip before the page. |
| `path` | `string` | no | — |  |
| `status` | `string` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `blueprint.re_delegate`

Re-delegate after verification failure. Re-opens a done/blocked blueprint.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `bp_id` | `string` | **sí** | — |  |
| `cycle` | `string` | no | — |  |
| `path` | `string` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `blueprint.read`

Read a full Blueprint (HCORTEX or CORTEX format).

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `bp_id` | `string` | **sí** | — |  |
| `cycle` | `string` | no | — |  |
| `format` | `string` | no | hcortex |  |
| `path` | `string` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `blueprint.ready`

Architect declares Blueprint ready for execution. draft → ready.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `bp_id` | `string` | **sí** | — |  |
| `cycle` | `string` | no | — |  |
| `path` | `string` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `blueprint.synthesize`

GUIDE MODE: creates or finds the BLP and returns the next pending section. Agent writes sections via blueprint.update(). Creates and persists the BLP file when it does not exist. The write cycle is the explicit cycle= or the context cycle; a closed cycle is refused (BLP-022).

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `bp_id` | `string` | **sí** | — | Blueprint ID e.g. 'BLP-007'. Created with status=draft if not exists. |
| `content` | `string` | no | — | Per-section CORTEX payload: $1:{body} $2:{body} ... Section bodies are written through the same marker-safe path as blueprint.update. Omit for GUIDE MODE. |
| `cycle` | `string` | no | — | Cycle to write to. Defaults to the context cycle; a closed cycle is refused without creating a file. |
| `path` | `string` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `blueprint.task`

Update one task's checkbox in §14. Status: in_progress/completed.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `bp_id` | `string` | **sí** | — |  |
| `evidence` | `string` | no | — | Optional evidence note |
| `path` | `string` | no | — |  |
| `status` | `string` | **sí** | — |  |
| `task_id` | `string` | **sí** | — | Task ID like T-1.1 |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `blueprint.update`

Update Blueprint progress with a note or refine a single section.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `bp_id` | `string` | **sí** | — |  |
| `content` | `string` | no | — | Section content (text or markdown) |
| `cycle` | `string` | no | — |  |
| `note` | `string` | no | — | Progress note to append |
| `path` | `string` | no | — |  |
| `puml` | `string` | no | — | PlantUML source for diagram sections |
| `section` | `string` | no | — | Section number like '§3' or '3' |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

## Ciclos

### `cycle.close`

Close a cycle (no new tasks can be added).

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `cycle_id` | `string` | **sí** | — |  |
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |
| `summary` | `string` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `cycle.create`

Open a new cycle in the active project.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `description` | `string` | no | — |  |
| `name` | `string` | no | — |  |
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `cycle.current`

Get the currently active cycle.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `cycle.list`

List cycles in the active project.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |
| `status` | `string` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `cycle.reopen`

Reopen a closed cycle so its manifest can be amended.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `cycle_id` | `string` | **sí** | — |  |
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `cycle.synthesize`

Populate a cycle's MANIFEST.md sections in a single call.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `content` | `string` | **sí** | — |  |
| `cycle_id` | `string` | **sí** | — |  |
| `path` | `string` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

## Contexto

### `context.detect`

Scan upward from a path for a .arqux/ directory. Returns {found: bool, path: str|null, kind: 'project'|'workspace'|null}.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `path` | `string` | no | — | Starting path. Defaults to cwd. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `context.full`

Return the full project context: project name, available cycles, current cycle, agents bound, skills available.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `path` | `string` | no | — | Starting path. Defaults to cwd. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

## Cortex / memoria

### `cortex.checkpoint`

Persist the agent's working state (WRK:current) as a single CORTEX line in brain.cortex §8. Accepts content as key:value pairs (fcs:,obj:,tasks:,state:).

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `content` | `string` | **sí** | — | CORTEX content: fcs:...,obj:...,tasks:...,state:... |
| `path` | `string` | no | — | Path to project root. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `cortex.corpus.list`

List .cortex files in a corpus/root directory.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `path` | `string` | no | — | Root path to scan (default cwd). |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `cortex.corpus.query`

Query corpus .cortex files by path substring/pattern.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `path` | `string` | no | — | Root path to scan (default cwd). |
| `pattern` | `string` | **sí** | — | Substring to match in file paths. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `cortex.entry.add`

Add a new entry to a .cortex file. Accepts a 'content' CORTEX entry string (BLP-005, canal I) — when provided, fields extracted from content override individual params. Output metrics: bytes_written/entry_bytes = size of the serialized entry as written on disk (writer's form, quoting included); file_bytes = whole file size after the write.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `content` | `string` | no | — | CORTEX entry string 'sigil:name{key:val,...}' — overrides sigil/name/value when present (canal I). |
| `create_section` | `boolean` | no | False |  |
| `force` | `boolean` | no | False |  |
| `name` | `string` | no | — | Entry name |
| `path` | `string` | **sí** | — | Path to .cortex file |
| `section` | `string` | no | — | Section ID e.g. $5 |
| `sigil` | `string` | no | — | Sigil e.g. LNG |
| `value` | `string` | no | — | Entry value (attrs body or plain text). Optional when content parses as CORTEX. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `cortex.entry.delete`

Delete an entry matching a CORTEX selector from a .cortex file. Output metrics: bytes_written/file_bytes = whole file size after the rewrite (unlike entry.add, where bytes_written is the serialized entry size).

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `force` | `boolean` | no | False |  |
| `path` | `string` | **sí** | — | Path to .cortex file |
| `selector` | `string` | **sí** | — | CORTEX selector |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `cortex.entry.get`

Read entries matching a CORTEX selector from a .cortex file. format='cortex' returns raw CORTEX entries (canal I); format='hcortex' (default) returns parsed dicts (canal E).

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `format` | `string` | no | hcortex | Output format: cortex (raw entry strings, canal I) or hcortex (parsed dicts, canal E). |
| `path` | `string` | **sí** | — | Path to .cortex file |
| `selector` | `string` | **sí** | — | CORTEX selector e.g. $2/FCS:current or LNG:* |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `cortex.entry.list`

List entries in a .cortex file, optionally filtered. Filters: section/sigil params, or a 'selector' in the cortex.entry.get vocabulary ('$N', '$N/SIGIL', '$N/SIGIL:name' or 'SIGIL[:name]'); explicit section/sigil params override the selector-derived components. format='cortex' returns raw CORTEX entries (canal I); format='hcortex' (default) returns parsed dicts (canal E); format='compact' returns one raw entry per line. Paginated: limit (default 50) + offset; fields total, returned, offset, next_offset report the pagination state.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `format` | `string` | no | hcortex | Output format: cortex (raw entry strings, canal I), hcortex (parsed dicts, canal E) or compact (one raw entry per line). |
| `limit` | `integer` | no | 50 | Max entries per page. |
| `offset` | `integer` | no | 0 | Entries to skip before the page. |
| `path` | `string` | **sí** | — | Path to .cortex file |
| `section` | `string` | no | — | Filter by section ID |
| `selector` | `string` | no | — | CORTEX selector filter: '$N', '$N/SIGIL', '$N/SIGIL:name' or 'SIGIL[:name]'. Explicit section/sigil params override selector-derived components. |
| `sigil` | `string` | no | — | Filter by sigil |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `cortex.entry.move`

Move an entry between sections in a .cortex file. Output metrics: bytes_written/file_bytes = whole file size after the rewrite (unlike entry.add, where bytes_written is the serialized entry size).

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `path` | `string` | **sí** | — | Path to .cortex file |
| `selector` | `string` | **sí** | — | CORTEX selector |
| `to_section` | `string` | **sí** | — | Target section ID e.g. $7 |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `cortex.entry.update`

Update an entry selected by a CORTEX selector. Output metrics: bytes_written/file_bytes = whole file size after the rewrite (unlike entry.add, where bytes_written is the serialized entry size).

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `append` | `boolean` | no | False | Append to existing body |
| `force` | `boolean` | no | False |  |
| `path` | `string` | **sí** | — | Path to .cortex file |
| `replace_body` | `string` | no | — | New body text (cuerpo/bloque entries) |
| `selector` | `string` | **sí** | — | CORTEX selector e.g. $5/LNG:lesson |
| `set_` | `string` | no | — | Key:value pairs to merge (attrs entries). Not JSON — raw 'key:val,key2:val2' |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `cortex.file.validate`

Scan a .cortex file for duplicate entry names and optionally fix them.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `fix` | `boolean` | no | False | If true, rename duplicates with _XXXX suffix |
| `path` | `string` | **sí** | — | Path to .cortex file or directory containing .cortex files |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante solo con `--fix`; lectura permite auditor

---

### `cortex.format`

Transform content between CORTEX (machine) and HCORTEX (human-readable). target='hcortex' (default) renders sigils as readable headers; target='cortex' parses headers back.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `content` | `string` | no | — | Source text to transform. If omitted, reads from path. |
| `path` | `string` | no | — |  |
| `target` | `string` | no | hcortex |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `cortex.gc`

Garbage-collect or repair duplicate entries in a .cortex file. Duplicates share the same (section, sigil, name). Optional section/sigil/name filters restrict which duplicate groups are affected (all provided filters must match; unfiltered affects every duplicate group). keep='first' (default) conserves the first first_kept occurrences in file order; keep='last' conserves the last ones (metrics: retains the most recent values). mode='dedupe' (default) removes extra occurrences; mode='rename' preserves every occurrence and renames extras to the next sequential numeric id in the (section, sigil) namespace — global max numeric suffix + 1, incremented per rename (e.g. E_0157 extras -> E_0343, E_0344...); names without a numeric suffix get _001, _002... appended. Embedded event/id attrs are updated consistently (storage uses E_0157, API/event attr uses E-0157). dry_run=True (default) previews removals and the new names that would be assigned without mutating; force=True applies the mutation in a single atomic rewrite. Output metrics: bytes_written/file_bytes = whole file size after the rewrite (unlike entry.add, where bytes_written is the serialized entry size).

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `dry_run` | `boolean` | no | True | Preview affected occurrences without mutating. |
| `first_kept` | `integer` | no | 1 | Number of occurrences to keep per duplicate group. |
| `force` | `boolean` | no | False | Required to perform the mutation. |
| `keep` | `string` | no | first | Which occurrences keep the original name: first or last in file order. |
| `mode` | `string` | no | dedupe | dedupe removes extra occurrences; rename preserves all and assigns unique sequential names; purge_dialect removes rc.1 artifacts injected into $0 (BUG-1 residual: $0:format line + generated sigil-schema declarations unreachable via entry CRUD). |
| `name` | `string` | no | — | Only affect duplicate groups with this entry name (e.g. 'E_0157'). |
| `path` | `string` | **sí** | — | Path to .cortex file. |
| `section` | `string` | no | — | Only affect duplicate groups in this section (e.g. '$6'; '6' also accepted). |
| `sigil` | `string` | no | — | Only affect duplicate groups with this sigil (e.g. 'AUD'). |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: mutante solo con `--force`; lectura permite auditor

---

### `cortex.learn`

Scan a project brain through the CODEC-CORTEX Learning Engine.
Returns scored entries and elevation candidates.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `content` | `string` | no | — | CORTEX content with keys scope, path (optional; overrides individual params). |
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |
| `scope` | `string` | no | project |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `ENGINE_UNAVAILABLE`, `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `cortex.learn.elevate`

Elevate a learning candidate (SES->LNG or LNG->KNW).
Default is dry-run (shows diff without applying).
Pass apply=true with confirm_hash from a reviewed dry-run to write the elevation to brain.cortex.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `apply` | `boolean` | no | False | If true, apply the elevation. Default is dry-run. |
| `candidate_id` | `string` | **sí** | — | Candidate ID from cortex.learn output |
| `confirm_hash` | `string` | no | — | Preview hash from a reviewed dry-run. Required when apply=true. |
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante solo con `--apply`; lectura permite auditor

---

### `cortex.migrate`

Migrate a .cortex file by applying a named transform (reseccionar|resigilar). Writes atomically (BLP-010 meta-handler). Supports dry_run mode.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `content` | `string` | no | — | CORTEX content with keys source_path, target_path, transform. |
| `dry_run` | `boolean` | no | False |  |
| `source_path` | `string` | **sí** | — |  |
| `target_path` | `string` | **sí** | — |  |
| `transform` | `string` | **sí** | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: mutante (gate interno); auditor solo lectura

---

### `cortex.patch`

Patch multiple entries in a .cortex file from a CORTEX content payload (BLP-010 meta-handler). Accepts content as '$SELECTOR:{new_body}'. Supports dry_run mode.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `content` | `string` | **sí** | — | CORTEX content with selectors and new bodies. |
| `dry_run` | `boolean` | no | False |  |
| `path` | `string` | **sí** | — | Path to .cortex file. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: mutante (gate interno); auditor solo lectura

---

### `cortex.read`

Read and parse a .cortex file. mode='cortex' (default) returns raw CORTEX entries as dict (canal I); mode='hcortex' renders human-readable markdown (canal E).

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `mode` | `string` | no | cortex | Output format: cortex (raw dict, canal I) or hcortex (markdown, canal E). |
| `path` | `string` | **sí** | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `MISSING_DEPENDENCY`, `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `cortex.ref`

Return the definition of a CORTEX sigil (name, type, risk, layer, description). Reads from local sigil cache. sections=true returns the standard brain.cortex section map (section id → title → sigils) instead.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `path` | `string` | no | — |  |
| `sections` | `boolean` | no | False | Return the standard brain.cortex section map ($N → title → sigils) instead of a sigil definition. |
| `sigil` | `string` | no | — | Sigil identifier (case-insensitive), e.g. 'WRK', 'lng'. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `cortex.render`

Render a .cortex file to HCORTEX READ markdown.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `path` | `string` | **sí** | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `MISSING_DEPENDENCY`, `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `cortex.render.diagram`

Render a PlantUML diagram to SVG/PNG. Requires plantuml.jar.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `format` | `string` | no | svg |  |
| `path` | `string` | no | — |  |
| `source` | `string` | **sí** | — | PUML source text (@startuml block) |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `cortex.render.validate_file`

Validate all PUML blocks in a file. Returns D1-D5 checklist.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `path` | `string` | **sí** | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `cortex.restore_backup`

Restore a .cortex file from its .bak (generation=0, default) or .bak.1 (generation=1) backup — the ONLY sanctioned restore path (manual copy/rename is forbidden, AXM:no_direct_edit). Validates the backup first; dry_run=True (default) previews without mutating; applying requires dry_run=False and force=True. The pre-restore state is rotated into the backup chain, never lost. Backups are a safety net for the last write, not history — for history use PULSE/timelog or arqux backup tarballs.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `dry_run` | `boolean` | no | True | Preview without mutating (default true). |
| `force` | `boolean` | no | False | Required (with dry_run=False) to apply the restore. |
| `generation` | `integer` | no | 0 | 0 = .bak (most recent), 1 = .bak.1. |
| `path` | `string` | **sí** | — | Path to the .cortex file (or to its .bak/.bak.1). |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: mutante solo con `--force`; lectura permite auditor

---

### `cortex.verify`

Verify a .cortex file's structure using CODEC-CORTEX.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `path` | `string` | **sí** | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `MISSING_DEPENDENCY`, `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `cortex.write`

Write (atomically) a .cortex file from CORTEX source text. Output metrics: bytes_written/file_bytes = whole file size written (the mutation is the full file).

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `content` | `string` | **sí** | — |  |
| `force` | `boolean` | no | False |  |
| `path` | `string` | **sí** | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `MISSING_DEPENDENCY`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

## Evidencia

### `evidence.list`

Query the evidence trail. Paginated: limit (default 100) + offset; fields total, returned, offset, next_offset report the pagination state.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `cycle` | `string` | no | — |  |
| `limit` | `integer` | no | 100 | Max events per page. |
| `offset` | `integer` | no | 0 | Events to skip before the page. |
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |
| `since` | `string` | no | — |  |
| `task_id` | `string` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `evidence.read`

Read a single evidence event by ID.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `event_id` | `string` | **sí** | — |  |
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `evidence.record`

Append an evidence entry to the brain's PULSE section.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `kind` | `string` | **sí** | — |  |
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |
| `payload` | `string` | **sí** | — |  |
| `task_id` | `string` | **sí** | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

## Identidades

### `identity.elevate`

Elevate a brain.cortex $8 LNG lesson into an agent identity contract (AXM or LIM) — the behavioral learning line. Default is dry-run returning the proposal + preview_hash; apply=true requires confirm_hash matching the reviewed proposal.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `agent` | `string` | **sí** | — | Target identity (e.g. alfred, jarvis). |
| `apply` | `boolean` | no | False | Apply the elevation (requires confirm_hash). |
| `confirm_hash` | `string` | no | — | preview_hash from the dry-run proposal. |
| `contract_type` | `string` | **sí** | — | AXIOM → AXM sigil | LIMIT → LIM sigil. |
| `lesson_id` | `string` | **sí** | — | LNG entry name in brain $8 (e.g. verify_post_write_state). |
| `path` | `string` | no | — | Path to project root. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Permiso mínimo**: mutante solo con `--apply`; lectura permite auditor

---

### `identity.get`

Return agent identity data from .arqux/identities/<agent>.cortex or the packaged identities. Default agent_id is 'alfred'.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `agent_id` | `string` | no | — | Agent identifier. Defaults to 'alfred'. |
| `path` | `string` | no | — | Starting path for resolving the project/workspace root. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `identity.record`

Record a behavioral lesson into the authenticated agent's identity file; explicit agent_id must match the caller (BLP-002).

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `agent_id` | `string` | no | — | Agent identifier (default: current agent) |
| `cause` | `string` | no |  | What caused this lesson |
| `kind` | `string` | no | behavioral | Lesson kind: behavioral/process/format/rule/infrastructure |
| `lesson` | `string` | **sí** | — | Lesson text |
| `name` | `string` | no | — | Explicit LNG entry name. Recommended: without it the name is derived from the first word of the lesson, which collides on common articles (LNG:al, LNG:en, ...). |
| `path` | `string` | no | — | Path to search up from for .arqux/identities/ |
| `prevention` | `string` | no | — | How to prevent this lesson from recurring. Required for LNG entries. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `identity.switch`

Hot identity switch in one atomic call (BLP-011): validate the identity exists, hydrate the full contract, register handoff + PULSE audit, update the active context and return the header. Accepts content CORTEX and dry_run (meta-handler BLP-010).

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `agent_id` | `string` | no | — | Target identity (case-insensitive). |
| `content` | `string` | no | — | CORTEX content with keys agent_id, summary, blps, tasks. |
| `dry_run` | `boolean` | no | False |  |
| `path` | `string` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

## Issue

### `issue.create`

Report a new issue (status: open) in <project>/.arqux/issues/ with a PULSE event. Severity: low|medium|high|blocking. The header uses title when given, else the first line of desc, truncated to 120 chars; the full desc is the body under ## PROBLEM.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `desc` | `string` | **sí** | — | Problem description (full body). |
| `handler` | `string` | no | — | Who detected it (defaults to caller). |
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |
| `severity` | `string` | **sí** | — |  |
| `title` | `string` | no | — | Short header line (max 120 chars). Defaults to the first line of desc. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `issue.list`

List issues in <project>/.arqux/issues/, optionally filtered by status.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |
| `status` | `string` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `issue.read`

Read one issue file verbatim by id (file stem).

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `issue_id` | `string` | **sí** | — |  |
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `issue.update`

Update an issue's status/severity with a PULSE-traced transition. status=verified REQUIRES audit_ref (the PULSE event id of the auditor's verdict — the validator profile is the auditor).

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `audit_ref` | `string` | no | — | PULSE event id of the auditor's verdict (required for verified). |
| `issue_id` | `string` | **sí** | — |  |
| `note` | `string` | no | — |  |
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |
| `severity` | `string` | no | — |  |
| `status` | `string` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

## Loop VAMOS

### `loop.activate`

Arm a registered loop for dispatch (armed|paused|stalled → active; retries reset).

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `claimant` | `string` | no | — |  |
| `name` | `string` | **sí** | — |  |
| `path` | `string` | no | — |  |

**Retorna**: `Any` → `OUT-WORK` / `OUT-ERROR`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `loop.advance`

Advance the loop to the next phase: index+1, checkpoint persisted in §LOOPS, progress event appended to the session timelog.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `checkpoint` | `string` | no | — |  |
| `claimant` | `string` | no | — |  |
| `name` | `string` | **sí** | — |  |
| `next_` | `string` | no | — |  |
| `path` | `string` | no | — |  |

**Retorna**: `Any` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `loop.complete`

Close an active loop (→ done); the dispatcher stops signalling it.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `claimant` | `string` | no | — |  |
| `name` | `string` | **sí** | — |  |
| `path` | `string` | no | — |  |
| `summary` | `string` | no | — |  |

**Retorna**: `Any` → `OUT-WORK` / `OUT-ERROR`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `loop.deactivate`

Silence an active loop (→ paused) without removing it.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `claimant` | `string` | no | — |  |
| `name` | `string` | **sí** | — |  |
| `path` | `string` | no | — |  |

**Retorna**: `Any` → `OUT-WORK` / `OUT-ERROR`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `loop.list`

List registered loops (name, state, recurrence, next) — tombstoned entries excluded.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `path` | `string` | **sí** | — |  |

**Retorna**: `Any` → `OUT-WORK` / `OUT-ERROR`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `loop.register`

Register an autonomous loop in the brain §LOOPS registry (state armed). phases[] + recurrence (on_bootstrap|every_bootstrap|cooldown:<n>h|on_heartbeat) + max_stall(<n>m) declare the cycle.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `checkpoint` | `string` | no | — |  |
| `content` | `string` | no | — |  |
| `expected_duration` | `string` | no | — |  |
| `max_stall` | `string` | no | — |  |
| `name` | `string` | **sí** | — |  |
| `next_` | `string` | no | — |  |
| `owner` | `string` | no | — |  |
| `path` | `string` | no | — |  |
| `phases` | `array` | no | — |  |
| `recurrence` | `string` | no | — |  |
| `session` | `string` | no | — |  |

**Retorna**: `Any` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `loop.remove`

Eliminate a loop from the registry (tombstone; requires deactivate first if active).

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `claimant` | `string` | no | — |  |
| `name` | `string` | **sí** | — |  |
| `path` | `string` | no | — |  |

**Retorna**: `Any` → `OUT-WORK` / `OUT-ERROR`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `loop.suggest`

Suggest a recurrence for a loop (or all) based on its execution pattern — read-only.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `name` | `string` | no | — |  |
| `path` | `string` | **sí** | — |  |

**Retorna**: `Any` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `loop.wake`

Manually queue a WAKE for a loop — the next governed call surfaces it as pending_loop.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `checkpoint` | `string` | no | — |  |
| `name` | `string` | **sí** | — |  |
| `path` | `string` | no | — |  |

**Retorna**: `Any` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

## Protocol

### `protocol.adopt`

Onboard an agent with a role.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `agent_id` | `string` | **sí** | — |  |
| `path` | `string` | no | — | Path to workspace root. Defaults to cwd. |
| `role` | `string` | **sí** | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `protocol.onboard`

Onboard an agent with a role. Alias of protocol.adopt for w06 workflow compatibility.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `agent_id` | `string` | **sí** | — |  |
| `path` | `string` | no | — | Path to workspace root. Defaults to cwd. |
| `role` | `string` | **sí** | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `protocol.pause`

Suspend governance for the current session without losing state.

_sin parámetros_

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `protocol.release`

Fully detach an agent (clean exit, no orphans).

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `agent_id` | `string` | **sí** | — |  |
| `path` | `string` | no | — | Path to workspace root. Defaults to cwd. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `protocol.resume`

Resume governance after a pause.

_sin parámetros_

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

## Proyectos

### `project.bind`

Bind an agent identity to the current project with a role.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `agent_id` | `string` | **sí** | — |  |
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |
| `role` | `string` | **sí** | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `project.init`

Initialize .arqux/ in a project directory and register it in the
workspace.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `cycle` | `string` | no | — | Optional cycle name to auto-create after project init (P1-D). |
| `name` | `string` | **sí** | — | Project name |
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |
| `seed` | `string` | no | — | Optional pre-prepared brain.cortex CORTEX content.
When provided, writes it directly as brain.cortex in one step.
Use when the agent has already studied the project context
and can provide FCS, OBJ, RSK, KNW, etc. directly. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Permiso mínimo**: governor únicamente

---

### `project.lessons`

List lessons local to the current project.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `project.status`

Active project status (cycles, tasks, agents).

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `project.unbind`

Release an agent binding from the current project.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `agent_id` | `string` | **sí** | — |  |
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

## Registro MCP

### `handler.how_to`

Usage guide by intent (BLP-012): curated how-to from the packaged guides.cortex corpus — exact handler sequence with example. Omit intent for self-describing help (available topics + usage). No-match returns available topics + hints to handler.list / skill.get. Read-only; accepts content CORTEX with key intent (BLP-010).

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `content` | `string` | no | — | CORTEX content with key intent (BLP-010). |
| `intent` | `string` | no | — | What you want to do (e.g. 'cambiar de identidad', 'crear un blueprint'). Optional: omit for the topic list + usage. |
| `path` | `string` | no | — |  |

**Retorna**: `Any` → `OUT-WORK` / `OUT-ERROR`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `handler.list`

Discover available handlers classified by module, filtered by tier (NANO|LITE|FULL). Paginated: limit (default 50) + offset; fields _total, _returned, _offset, _next_offset report the pagination state. compact=true returns names only. Replaces hardcoded handler tables in AGENTS.md (BLP-010 meta-handler).

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `compact` | `boolean` | no | False | Return handler names only (no descriptions). |
| `limit` | `integer` | no | 50 | Max handlers per page. |
| `offset` | `integer` | no | 0 | Handlers to skip before the page. |
| `tier` | `string` | **sí** | — | Tier to filter handlers by. |

**Retorna**: `dict[str, Any]` → `OUT-WORK` / `OUT-ERROR`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

## Sesiones

### `session.bootstrap`

Bootstrap a session using the authenticated identity. An explicit agent_id must match the caller (BLP-002). Returns cortex_context (canal I) and hcortex_dashboard (canal E).

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `agent_id` | `string` | no | — | Optional identity selector; must match the authenticated caller. |
| `path` | `string` | no | — | Starting path. Defaults to cwd. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `session.close`

Close the session bound to this execution (or the explicit session_ref) and write its portable summary to brain SESSIONS. Never closes the newest session of the project when it belongs to another execution.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `blps` | `string` | no | — | Comma-separated active blueprint IDs (e.g. BLP-006,BLP-007). |
| `decisions` | `string` | no | — | Comma-separated key decisions made. |
| `gaps` | `string` | no | — | Comma-separated detected gaps or pending items. |
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |
| `session_ref` | `string` | no | — | Explicit SESxxx to close. Defaults to this execution's session. |
| `summary` | `string` | **sí** | — | Short human-readable summary of what was accomplished. |
| `tasks` | `string` | no | — | Comma-separated pending task IDs. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `session.context.get`

Read the current context pointer and return the formatted header.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `path` | `string` | no | — | Path to workspace root. Defaults to cwd. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `session.context.set`

Set the current session context pointer (project + scope + optional BLP) and open or re-attach the real session bound to this execution. Validates project exists and returns the formatted header.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `blp` | `string` | no | — | Optional active BLP ID (e.g. BLP-014) |
| `intent` | `string` | no | new | 'new' opens or recovers this execution's session; 'resumed' re-attaches session_ref without changing its id or original start. |
| `path` | `string` | no | — | Path to workspace root. Defaults to cwd. |
| `project` | `string` | **sí** | — | Project name (e.g. ARQUX) |
| `scope` | `string` | **sí** | — | Scope within project (e.g. CYCLE-01) |
| `session_ref` | `string` | no | — | Explicit SESxxx reference; required when intent='resumed'. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `session.handoff`

Serialize the current session context as CORTEX and write a handoff PULSE for the target agent (BLP-010 meta-handler). Supports dry_run mode.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `content` | `string` | no | — | CORTEX content with keys target_agent, summary, blps, tasks. |
| `dry_run` | `boolean` | no | False |  |
| `path` | `string` | no | — |  |
| `target_agent` | `string` | **sí** | — | ID of the agent receiving the handoff. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `session.pulse.compact`

Compact pulse entries for a session. With ses_ref, selection is by membership: only that session's events are summarized and concurrent or legacy events are never reassigned by position. Writes a consolidated LNG lesson; canonical timelog events are append-only and are never pruned.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `dry_run` | `boolean` | no | False |  |
| `path` | `string` | no | — |  |
| `ses_ref` | `string` | no | — | Select by session membership instead of position. |
| `session_id` | `string` | **sí** | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `session.pulse.gc`

Explicit sweep of residual brain-PULSE entries (legacy compatibility only): prunes AUD entries outside the window — rank>PULSE_KEEP_COUNT(20) or age>PULSE_KEEP_DAYS(5) — into the rolling LNG:pulse_sweep archive. Canonical session-timelog $5 EVENTS are append-only and are never swept; the write path never sweeps.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `dry_run` | `boolean` | no | False |  |
| `path` | `string` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante (gate interno); auditor solo lectura

---

### `session.resume`

Restore the context of a session. Read-only: selects by explicit session_ref, else the session bound to this execution, else rejects an ambiguous choice instead of taking the newest session. Brains without real session identity keep the legacy PULSE selection.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |
| `session_ref` | `string` | no | — | Explicit SESxxx reference. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `session.status`

Read session metadata without restoring full context. Read-only, same selection rules as session.resume.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |
| `session_ref` | `string` | no | — | Explicit SESxxx reference. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

## Setup / PlantUML

### `setup.plantuml`

Download and install plantuml.jar to ~/.arqux/bin/.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `force` | `boolean` | no | False |  |
| `path` | `string` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

## Sincronía

### `sync.reconcile`

Reconcile brain.cortex with filesystem reality. Supports cycle-level (cycle_id) or project-level reconcile.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `cycle_id` | `string` | no | — | If set, reconcile only this cycle's MANIFEST.md (BLP table + metrics). |
| `level` | `string` | no | — | Reconciliation scope level. Default: auto. |
| `path` | `string` | no | — | Path to project root. Auto-detected from cwd if omitted. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `sync.run`

Manually sync a project brain.cortex to meta-brain with full metrics.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `path` | `string` | no | — | Path to project root. Auto-detected from cwd if omitted. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

## Skills

### `skill.convert`

Convert a skill from original format to CORTEX ultra-dense.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `name` | `string` | **sí** | — | Skill name |
| `path` | `string` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `skill.edit`

Edit (read, write, or section-edit) a skill file in .arqux/skills/. Without content: returns the skill content. With content but no section: atomically replaces the entire skill file. With content and section: replaces only that CORTEX section (e.g. $0, $1, $2.1). Accepts content as CORTEX with keys name, body, section (BLP-009).

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `content` | `string` | no | — | New content, or CORTEX entry 'name:...,body:...,section:...' (BLP-009). Omit to read current content. |
| `name` | `string` | **sí** | — | Skill name (e.g. handlers) |
| `path` | `string` | no | — | Path to workspace/project root |
| `section` | `string` | no | — | Section ID to replace (e.g. $0, $1, $2.1). Only valid with content. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: mutante solo con `--content`; lectura permite auditor

---

### `skill.evolve`

Apply an approved adaptation to a skill. Default is dry-run.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `adaptation_id` | `string` | **sí** | — | Adaptation entry selector |
| `apply` | `boolean` | no | False | If true, apply the evolution |
| `name` | `string` | **sí** | — | Skill name |
| `path` | `string` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante solo con `--apply`; lectura permite auditor

---

### `skill.get`

Read a skill file via the universal resolver (BLP-012) — read-only counterpart of skill.edit. Accepts root names, relative subpaths ('workflows/w10-x') or unique nested names. NOT_FOUND/AMBIGUOUS return actionable guidance. Accepts content CORTEX with key name.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `content` | `string` | no | — | CORTEX content with key name (BLP-010). |
| `name` | `string` | **sí** | — | Skill name or relative subpath (e.g. protocol, workflows/w10-identity-handoff) |
| `path` | `string` | no | — | Path to workspace/project root |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `skill.import`

Acquire a skill from external source, store original in originals/. Accepts content as CORTEX with keys source, name, body (BLP-009).

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `content` | `string` | no | — | Raw skill content, or CORTEX entry 'source:...,name:...,body:...' (BLP-009). Omit to get instructions first. |
| `name` | `string` | **sí** | — | Skill name (e.g. oracle-apex) |
| `path` | `string` | no | — | Path to workspace/project root |
| `source` | `string` | **sí** | — | Origin (marketplace, platform, url:...) |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `skill.install`

Install a skill: import + validate + register in brain.cortex SKILLS/SKL (BLP-010 meta-handler). Supports dry_run mode.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `content` | `string` | no | — | CORTEX content with keys source, name, body. |
| `dry_run` | `boolean` | no | False | If true, report what would happen without modifying state. |
| `name` | `string` | **sí** | — | Skill name. |
| `path` | `string` | no | — |  |
| `source` | `string` | **sí** | — | Skill source. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `skill.list`

List all available skills in .arqux/skills/.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `path` | `string` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `skill.record`

Record a deviation (ADA) when a skill does not match the real context.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `actual` | `string` | **sí** | — | What was actually done |
| `expected` | `string` | **sí** | — | What the skill says |
| `name` | `string` | **sí** | — | Skill name |
| `path` | `string` | no | — |  |
| `reason` | `string` | **sí** | — | Why the deviation occurred |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

## Tareas

### `task.claim`

An executor claims a task → status: in_progress.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |
| `task_id` | `string` | **sí** | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `task.complete`

Mark a task done and record evidence.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `evidence` | `string` | no | — |  |
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |
| `task_id` | `string` | **sí** | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `task.create`

Create a governed task in the current cycle. Accepts a 'content' CORTEX entry string (BLP-009) with keys obj, pre[], proc[], ac[], blk[], assignee, complexity, priority — parsed values override individual params (merge rule: content wins; scalar list values coerce to single-item lists). obj is optional when content carries an obj key; INVALID_ARGS otherwise.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `ac` | `array` | no | — |  |
| `assignee` | `string` | no | — |  |
| `blk` | `array` | no | — |  |
| `complexity` | `string` | no | — |  |
| `content` | `string` | no | — | CORTEX entry string with keys obj,pre[],proc[],ac[],blk[],assignee,complexity,priority. Lists as key:[v1,v2,v3] (a scalar value coerces to a single-item list). Parsed values override individual params (BLP-009: content wins). |
| `cycle` | `string` | no | — | Target cycle ID (e.g. CYCLE-07). If omitted, uses the current cycle. |
| `obj` | `string` | no | — | Objective text. Optional when content carries an obj key. |
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |
| `pre` | `array` | no | — |  |
| `priority` | `string` | no | — |  |
| `proc` | `array` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `task.fail`

Mark a task blocked and record the cause.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |
| `reason` | `string` | **sí** | — |  |
| `task_id` | `string` | **sí** | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `task.list`

List tasks with filters. Paginated: limit + offset; fields total, returned, offset, next_offset report the pagination state.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `assignee` | `string` | no | — |  |
| `cycle` | `string` | no | — |  |
| `limit` | `integer` | no | — | Max tasks per page (default: all). |
| `offset` | `integer` | no | 0 | Tasks to skip before the page. |
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |
| `status` | `string` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `task.read`

Read a task (CORTEX or HCORTEX format).

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `format` | `string` | no | cortex |  |
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |
| `task_id` | `string` | **sí** | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `task.run`

Run a governed task: verify preconditions, execute procedure steps, mark complete or fail (BLP-010 meta-handler). Supports dry_run mode.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `content` | `string` | no | — | CORTEX content with keys task_id, evidence, fail_reason. |
| `dry_run` | `boolean` | no | False | If true, report what would happen without modifying state. |
| `path` | `string` | no | — |  |
| `task_id` | `string` | **sí** | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `INVALID_ARGS`, `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `task.update`

Update task progress, optionally change status.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `note` | `string` | **sí** | — |  |
| `path` | `string` | no | — | Path to project root. Defaults to cwd. |
| `status` | `string` | no | — |  |
| `task_id` | `string` | **sí** | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

## Timelog

### `timelog.project`

Optional external projection of a timelog batch. preview is read-only; prepare persists the batch identity; send requires an authorization bound to that identity; reconcile records the remote outcome. A crash between send and receipt leaves the result unknown. Projecting never purges the local origin.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `account` | `string` | no | — |  |
| `action` | `string` | no | preview |  |
| `authorization_ref` | `string` | no | — |  |
| `block_ids` | `array` | **sí** | — |  |
| `destination` | `string` | **sí** | — |  |
| `expected_revision` | `string` | no | — |  |
| `path` | `string` | no | — |  |
| `rounding` | `string` | no | none |  |
| `session_ref` | `string` | no | — |  |
| `target` | `string` | no | — |  |
| `units` | `string` | no | seconds |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante solo con `--action!=preview`; lectura permite auditor

---

### `timelog.purge`

Authorized archive/summarize/delete of an exact selection. preview=true (default) mutates nothing. Deleting removes the canonical file and its auxiliaries and leaves a content-free tombstone; the deleted content is never recreated.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `authorization_ref` | `string` | **sí** | — |  |
| `expected_revision` | `string` | no | — |  |
| `mode` | `string` | no | delete |  |
| `path` | `string` | no | — |  |
| `preview` | `boolean` | no | True |  |
| `selection` | `array` | **sí** | — | Exact block ids to affect. |
| `session_ref` | `string` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante solo con `--!preview`; lectura permite auditor

---

### `timelog.query`

Read-only view of a session's timelog: activity blocks with UTC durations, integrity flags and a union total. A multisession view keeps provenance and creates no joint file.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `limit` | `integer` | no | — |  |
| `offset` | `integer` | no | 0 |  |
| `path` | `string` | no | — | Project root. Defaults to cwd. |
| `session_ref` | `string` | no | — | Explicit SESxxx reference. |
| `view` | `string` | no | session |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `timelog.review`

Authorized correction of one activity block. Writes a revision with a reason and the user's authorization reference and marks previously projected receipts stale; it never edits a remote copy.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `authorization_ref` | `string` | **sí** | — | The user's explicit instruction reference. |
| `block_id` | `string` | **sí** | — |  |
| `changes` | `object` | **sí** | — | Fields to change (start/end/state). |
| `expected_revision` | `string` | no | — |  |
| `path` | `string` | no | — |  |
| `reason` | `string` | **sí** | — |  |
| `session_ref` | `string` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: mutante — governor/executor; auditor denegado

---

### `timelog.summary`

Read-only aggregate of the native record by period: day (blocks starting today), session (this session) or project (every canonical file). Totals use the union rule and are null while a block is open; open_elapsed_seconds is a window, not productive time.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `path` | `string` | no | — |  |
| `period` | `string` | no | day |  |
| `session_ref` | `string` | no | — |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

## Workspace

### `workspace.init`

Initialize .arqux/ at the workspace root.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `path` | `string` | no | — | Path to initialize as workspace root. Defaults to cwd. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Permiso mínimo**: governor únicamente

---

### `workspace.lessons`

List lessons elevated to the meta-brain.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `path` | `string` | no | — | Path to workspace root. Defaults to cwd. |
| `project` | `string` | no | — | Filter lessons by source project. |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

### `workspace.status`

Workspace status (OUT-MIN by default). Use --dashboard for rich output.

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `dashboard` | `boolean` | no | False | Show visual workspace dashboard. |
| `path` | `string` | no | — | Path to workspace root. Defaults to cwd. |
| `verbose` | `boolean` | no | False |  |

**Retorna**: `CortexOUT` → `OUT-WORK` / `OUT-ERROR`

**Errores posibles**: `NOT_FOUND`

**Permiso mínimo**: lectura — cualquier rol, incluido auditor

---

## Regeneración

Este documento deriva 100% del registro: `scripts/generate_handlers_md.py` lee `arqux.handlers.REGISTRY` (firma JSON-schema + docstring + errores del source) y `arqux.permissions` (clasificación mutante/condicional/governor). Cualquier handler nuevo aparece al regenerar — sin edición manual.

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-17 · <a href="./docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->

