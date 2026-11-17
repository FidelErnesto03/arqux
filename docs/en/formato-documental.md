---
doc_type: canon
status: normative
version: 1.0.0
verified: 2026-11-16
---

<!-- DOC-BRAND -->
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../../docs/assets/brand/arqux-logo-primary-dark.svg">
    <img alt="ArqUX" src="../../docs/assets/brand/arqux-logo-primary-light.svg" width="240">
  </picture>
</p>
<p align="center"><sub>Canon · Normative · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# ArqUX document format — official documentation presentation

*English translation — canonical source: `docs/es/formato-documental.md`*

Normative specification of the public documents' visual surface. Identity source: **ArqUX Brand Kit v1.0** (`Proyecto_X/docs/brand-kit-v1/`). The brand blocks are **generated**, not hand-written — applied by `scripts/format_docs.py` and verified by `tests/e2e/test_docs_contract.py`.

## 1. The brand piece

Every public document opens with the `DOC-BRAND` block after its front-matter:

```html
<!-- DOC-BRAND -->
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="{REL}docs/assets/brand/arqux-logo-primary-dark.svg">
    <img alt="ArqUX" src="{REL}docs/assets/brand/arqux-logo-primary-light.svg" width="240">
  </picture>
</p>
<p align="center"><sub>{doc_type} · {status} · ArqUX {version}</sub></p>
<!-- /DOC-BRAND -->
```

- `{REL}` = relative prefix from the doc to the repo root (`./` at root, `../../../` under `docs/es/guias/`). Paths are **relative** — the corpus reads on GitHub, locally and on any mirror without touching a URL.
- `<picture>` resolves light/dark via `prefers-color-scheme` — the kit rule "light logo on light surface, dark on dark" holds on both GitHub themes.
- The `<sub>` ribbon translates the front-matter: `doc_type` and `status` localized to the document's language (ES corpus → Spanish labels, `docs/en/` → English labels), `version` literal. It only appears when the doc has front-matter.
- `width="240"` fixed — the lockup never drops below the tested legibility size (kit rule).

## 2. The footer

Every document closes with `DOC-FOOT`:

```html
<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX {version} · verified {verified} · <a href="{REL}docs/{lang}/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
```

The footer answers three reader questions without scrolling: which version it describes, when it was verified, and where the corpus map lives. The index link is language-aware: ES docs point to `docs/es/README.md`, EN docs to `docs/en/README.md`.

## 3. Typography and color (token layer)

Markdown renders with the host typography (GitHub); the brand stack stays reserved for controlled surfaces (portal, VS Code, generated HTML): **IBM Plex Sans/Inter** for interface, **IBM Plex Mono/JetBrains Mono** for technical material — `tokens/arqux-colors.css` from the kit is the reference.

Color roles when writing diagrams or inline HTML in docs:

| Token | Role in docs |
|---|---|
| `ink-950 #0A1420` | Text/structure |
| `amber-700 #D77A00` | Brand path, action — **never** small text on light background |
| `teal-400 #61D9C6` | Shared-context connections — sparing use |
| success/warning/error | Semantic states, never decoration |

Color never carries state alone — same kit principle (WCAG 2.2 AA).

## 4. Logo usage rules (from the kit, applied to docs)

- Use the kit SVGs (vendored in `docs/assets/brand/`) — do not rebuild the mark with text or approximate its geometry.
- No extra glow/gradient/outline/rotation/crop — the master already carries its effect.
- No tagline attached to the logo — the `<sub>` ribbon is the only allowed companion and comes from the front-matter.
- Standalone symbol (`arqux-symbol.svg`) for favicon/avatar/icon; full lockup for headers.

## 5. Structural uniformity by `doc_type`

| doc_type | Canonical skeleton |
|---|---|
| `tutorial` | title → goal/time → prerequisites → steps with real commands → "next" |
| `guide` | title → actor-purpose → verified procedure → see also |
| `reference` | title → generated or verified lookup table(s) → regeneration if applicable |
| `explanation` | title → question it answers → reasoning → honest limits |
| `canon` | title → literal norm → literal `.cortex` examples → exceptions |
| `report` | title → measured data → data scope → date |

Golden rule already in force: **content is verified or marked** — the brand is presentation, never a substitute for evidence (the kit's "Product truth": identity does not fabricate claims).

## 6. Declared exceptions

No brand block (justification in `scripts/format_docs.py` `NO_BRAND`):

- `AGENTS*.md` — governance kernels, not user documentation
- `CHANGELOG.md` — its own keep-a-changelog format
- `PILOT_MODE.md` — retired stub
- `llms.txt` — machine index (llmstxt.org format)
- `docs/es/especificacion/secciones-cerebro-canon.md` — canonical shard without front-matter
- `HANDLERS.md` — receives the brand **from its generator** (`generate_handlers_md.py`), not from the script — regeneration does not erase it

## 7. Operation

```bash
python scripts/format_docs.py           # apply/repair header+footer across the corpus
python scripts/format_docs.py --check   # verify presence (run by the gate)
```

Idempotent via `DOC-BRAND`/`DOC-FOOT` markers: re-running replaces the blocks without touching content. Markers inside fenced code blocks (like the examples above) are preserved — the stripper is fence-aware. New doc → run `format_docs.py` after writing its front-matter.

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-16 · <a href="../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
