# Changelog

## 0.4.2 — diagramas en el preview

- **Diagram rendering**: `body:"..."` (y cualquier string attr) cuyo
  valor contiene ```` ```puml ````, `@startuml` o ```` ```mermaid ````
  se renderiza como **SVG inline** dentro de su schema card.
- Renderers **locales, sin red**: `plantuml -pipe -tsvg` y `mmdc`
  (mermaid-cli) — spawn `shell:false`, timeout 15s, salida sanitizada
  (sin `<script>`, sin handlers `on*`).
- **Caché por sha256(lang+source)**: un diagrama se renderiza una vez
  por contenido distinto, no por cada refresh.
- **Fallback limpio**: sin binario o render fallido → el bloque
  `fuente puml|mermaid` colapsable con el source decodificado (`\n`
  reales), nunca texto escapado crudo.
- La exportación `.html` incluye los SVG ya renderizados.

## 0.4.1 — workspace-level intelligence

Workspace pack (BLP-004, CYCLE-17): the unit of analysis moves from
document to corpus.

- **Workspace symbols** (`Ctrl+T`): sigil tokens (declaration + usage)
  and `§N` sections across every `.cortex` in the workspace — fed by a
  new in-memory `WorkspaceIndex` (`src/server/workspaceIndex.ts`).
- **`cortex.validateWorkspace`**: validates the whole corpus through the
  codec (open documents shadow disk state), aggregates results into the
  Problems panel and a `CORTEX Workspace` output report. Capped at 200
  docs / 30 s budget.
- **Document links**: `%ENUM` references inside strings link to their
  `$0:enum_*` declaration (intra-doc).
- **File watching**: `**/*.cortex` watcher (`synchronize.fileEvents`)
  invalidates and re-indexes files on disk changes; open documents
  always win.
- **Filesystem containment** (security audit H-02): the corpus scan
  never follows symlinks, verifies every path under a declared
  `workspaceFolders` root, and caps at 500 files / 1 MB per file.
  Index is memory-only — zero persistence.

## 0.4.0 — info comes to you

Language-surface pack (BLP-003, CYCLE-17): contract knowledge renders
ambiently — no invocation needed.

- **Inlay hints** (`cortex-ls`): `·type·weight` ghost label after every
  declared `SIGIL:inst` usage; `:type` after each contract field key
  inside `{…}`.
- **CodeLens**: over each glossary declaration `N uso(s)` → opens native
  Find References; over each `§N` `M sigilo(s)` count; over `$0` the
  `C14N` badge.
- **Signature help** inside `SIGIL:inst{…}` — contract field signature
  (`type, weight, focus, desc, fields` or declared `fields`), triggers
  on `{` `,` `:`.
- **Selection ranges** (smart expand): token → attr-block → line →
  containing `§N` → document.
- **Inline diagnostics** (Error Lens style, client-side): end-of-line
  severity-colored messages driven by `cortex-ls` publishDiagnostics.
  Toggle via `cortex.inlineDiagnostics` (default `true`) — also from the
  status menu.
- **Status bar quickpick**: clicking the CORTEX badge opens
  `cortex.statusMenu` — diagnostics count, active runtime, full sha256
  hash, and a settings shortcut for `toolchainPath` (opens Settings UI;
  never writes settings silently).

## 0.3.0 — cortex-ls + preview polish

- **`cortex-ls`: dedicated LSP server** (ADR-0.3.0). All language
  intelligence moved out of the extension host into a stdio JSON-RPC
  server (`src/server/`): diagnostics, completion, hover, symbols,
  formatting, quick fixes, definition, references, rename, semantic
  tokens and folding. Reusable by any LSP client (Neovim, Zed,
  JetBrains) — VS Code connects via `vscode-languageclient`.
- **Collapsible chapters**: every `§N` section and the glossary render
  inside a `<details>` chapter — fold dense documents at will.
- **Preview toolbar**: `Filtrar…` input hides non-matching
  cards/chips/glossary rows live; `§ Ir a…` dropdown jumps to any
  section (auto-opens folded chapters).
- **Cursor-follow highlight**: the schema card of the sigil under the
  editor cursor lights up (weight-tinted border + outline), and its
  chapter auto-expands.
- `providers.ts` deleted — superseded by `src/server/core.ts`
  (transport-free handlers, unit-tested directly).

## 0.2.1 — Navigation & semantics pack

- **Go to Definition** (`F12`/`Ctrl+click`): sigil usage → glossary declaration.
- **Find All References** (`Shift+F12`): every `SIGIL:inst` occurrence
  (comment lines excluded).
- **Rename Symbol** (`F2`): renames the instance name across the
  declaration and all usages; validates `[A-Za-z_][\w-]*`.
- **Semantic tokens**: `$N:` heads → namespace, `$0:` decls → macro,
  `SIGIL:inst` → type (+`declaration` in glossary), `%ref` → enumMember
  (string-aware: no tokens inside quotes or comments).
- **Section folding**: each `$N` section folds until the next header.
- **CORTEX: Export Preview** (`$(export)` title action): writes the live
  HCORTEX render as `.md` (raw codec output) or `.html` (styled).
- Error catalog `errors-1.0.md` now bundled in `data/` — error-code
  hovers work in any workspace; workspace lookup remains as fallback.
- Repository moved to `arqux` (`extensions/cortex-viewer`); hover is
  now resilient: exact decl → contract, undeclared instance → base
  sigil contract, inline attrs, or "sin declaración" notice.

## 0.2.0 — Language intelligence pack

- **IntelliSense**: completions for declared sigil instances
  (`OBJ:item`), `%enum` values from `$0:enum_*` declarations, and
  contract attr keys from `fields:`.
- **Hover**: sigil instance → declared contract table + glossary line;
  CORTEX error codes → emitting surfaces from `docs/standard/errors-1.0.md`.
- **Outline / breadcrumbs**: document symbols for `$0 KERNEL + glosario`
  (sigil decls as children) and `§N` sections with capa.
- **Format Document** via codec `canonicalize` — the canonical byte form,
  idempotent; optional `cortex.formatOnSave`.
- **Quick fixes**: undeclared sigil → insert glossary declaration;
  missing `$0:format` / `$0:KERNEL` → insert; `G020` missing `desc` →
  append `desc:"TODO"`.
- **Snippets**: `cortex-doc`, `sigil`, `enum`, `sec`, `seccapa`, `obj`,
  `micro`.
- **Settings**: `cortex.toolchainPath` (explicit runtime override),
  `cortex.debounceMs`, `cortex.formatOnSave`.
- `LSP-DESIGN.md`: ADR for `cortex-ls`, the 0.3.0 language-server track
  (stdio JSON-RPC, incremental sync, reuse of cortexModel/CodecBridge,
  future `codec --server` mode).

## 0.1.1 — UX polish

- Editor title actions now render as native codicon icon-buttons with
  tooltips (`open-preview`, `split-horizontal`, `shield`, `edit`).
- Copy-hash control is an icon button (SVG, tooltip) instead of a text
  button; hover/active states follow VS Code toolbar styling.
- Status bar uses native `$(pass)`/`$(error)` codicons.

## 0.1.0 — Initial release

- Live HCORTEX 1.0 preview for `.cortex` documents.
- Real-time validation diagnostics mapped from codec-cortex error codes.
- C14N canonical hash badge with copy-to-clipboard.
- Declared loss-report indicator.
- Safe bidirectional editing of HCORTEX schema tables with the
  `from-hcortex` + `validate` + `loss-report` abort gate.
- Bidirectional scroll sync between editor sections and preview anchors.
- Runtime resolution chain: Rust `cortex` → Go `codec-cortex` →
  `python3 -m codec_cortex` → `codec-cortex-node`.
- Strict CSP webview (32-byte nonce per shell), `markdown-it` with
  `html:false`, zero telemetry.
