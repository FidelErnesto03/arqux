---
skill_id: blueprint-synthesize
name: blueprint.synthesize
version: "1.0.0"
status: planned
kind: native
usage: skill
layer: 2
blp_ref: BLP-007
---

# Skill: blueprint.synthesize

## §1: IDENTITY

IDN:synthesize{name:"blueprint.synthesize", purpose:"Write a Blueprint's content sections in a single call from a CORTEX content payload", version:"1.0.0", status:"planned"}

## §2: DESCRIPTION

`blueprint.synthesize` accepts a CORTEX content payload containing all 18
sections (or any subset) of a Blueprint and writes them to the BLP `.md`
file in one atomic operation.

This replaces the previous pattern of `blueprint.create` followed by 18
`blueprint.update` calls. With synthesize, the Architect can produce a
complete BLP from a single CORTEX message (canal I).

The handler uses `parse_blp_template()` from `arqux.blueprint.template`
to validate that each section ID in the content matches a marker in
`BLP_TEMPLATE.md`. Unknown section IDs are rejected with `INVALID_ARGS`.

## §3: INPUTS

| Name      | Type   | Required | Description |
|-----------|--------|----------|-------------|
| bp_id     | string | yes      | Blueprint ID (e.g. "BLP-007"). If the BLP file does not exist, it is created with status=draft. |
| content   | string | yes      | CORTEX content payload. Format: `$N:{...}` per section, or a single `$0:{...}` body containing all sections. |
| path      | string | no       | Starting path for resolving the project root. Defaults to cwd. |
| ctx       | object | no       | Permission context (auto-injected by the MCP runtime). |

### Content format

The `content` parameter is a CORTEX string. Two forms are accepted:

**Per-section form (recommended):**

```
$1:{Planteamiento del problema...}
$2:{Objetivo...}
$3:{- [ ] Precondición 1}
...
$18:{| Compuerta | Estado |...}
```

**Single-body form (legacy):**

```
$0:{
  1: "Planteamiento...",
  2: "Objetivo...",
  ...
}
```

In the per-section form, the section ID is the part after `$` and
before `:`. The body is everything between `{` and the matching `}`.

## §4: OUTPUTS

Returns `OUT-WORK` with:

- `blueprint_id` (str) — the BLP ID
- `path` (str) — path to the written BLP `.md` file
- `sections_written` (list[str]) — list of section IDs written
- `sections_skipped` (list[str]) — list of section IDs in content but
  not in the template (rejected)
- `bytes_written` (int)
- `created` (bool) — true if the BLP file was created (vs. updated)

## §5: VALIDATION RULES

1. **bp_id must match `BLP-NNN`** — 3-digit zero-padded number.
2. **content must be non-empty** — `INVALID_ARGS` otherwise.
3. **Section IDs must match template markers** — any section ID in
   content that does not match a `<!-- BLP:N -->` marker in
   `BLP_TEMPLATE.md` is rejected with `INVALID_ARGS`. The list of valid
   IDs is discovered dynamically via `parse_blp_template()`.
4. **Atomic write** — the BLP file is written to a temp file first,
   then renamed. A crash mid-write never leaves a half-written BLP.
5. **No status change** — synthesize does NOT change the BLP status.
   If the BLP was `draft`, it stays `draft`. Synthesize only writes content.
6. **Frontmatter preserved** — when updating an existing BLP, the
   frontmatter (status, governor, executor, quality_gates, etc.) is
   preserved. Only the body sections are replaced.
7. **PULSE** — a PULSE event is appended to brain.cortex on success.

## §6: USAGE

```
blueprint.synthesize(
  bp_id="BLP-007",
  content='''
$1:{Implementar cortex.ref handler que devuelve definición de sigilo.}
$2:{cortex.ref operativo y testeado.}
$3:{- [ ] CODEC-CORTEX disponible}
$12:{
- [ ] **AC-01:** cortex.ref("WRK") returns OUT-WORK
- [ ] **AC-02:** cortex.ref("XYZQ") returns OUT-ERROR NOT_FOUND
}
''',
  path="/path/to/project"
)
```

## §7: RELATIONSHIPS

- **Depends on:** `arqux.blueprint.template.parse_blp_template` (BLP-013)
- **Replaces:** `blueprint.create` + N× `blueprint.update` for programmatic BLP authoring
- **Does NOT replace:** `blueprint.update` (one section at a time)
- **Used by:** `blueprint.execute` (BLP-010) for re-writing sections during execution

## §8: WORKFLOW UPDATES

`workflows.skill.md` w08 (blueprint-lifecycle) should be updated to
reference `blueprint.synthesize` instead of `blueprint.create` + 18×
`blueprint.update` for programmatic authoring. The simplified lifecycle
(create → ready → claim → complete) is defined in w08 v2.1.
