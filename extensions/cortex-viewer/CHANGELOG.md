# Changelog

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
