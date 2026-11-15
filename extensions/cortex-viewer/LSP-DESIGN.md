# ADR-0.3.0: cortex-ls — Language Server para CORTEX 1.0

**Estado:** propuesto (target 0.3.0, no implementado en 0.2.0)
**Fecha:** 2026-11-15 · **Contexto:** arqux-cortex-viewer 0.2.0

## Decisión

Migrar la inteligencia de lenguaje de 0.2.0 (completions, hover, symbols,
diagnósticos, formatting) a un **Language Server Protocol** dedicado,
`cortex-ls`, en lugar de seguir creciendo providers dentro de la
extensión de VS Code.

## Motivación

- La arquitectura 0.1.x/0.2.0 hace **spawn-por-llamada**: cada validate,
  hash, canonicalize o to-hcortex lanza un proceso nuevo (1.5–2.5s de
  timeout por invocación, cold-start en cada operación).
- Las features que vendrán (sync incremental, workspace-wide diagnostics,
  go-to-declaration al glosario, references entre sigilos) requieren
  estado persistente del documento — imposible con spawn-per-call.
- LSP es el estándar de facto: un solo servidor sirve a VS Code,
  Neovim, Zed, JetBrains (vía LSP4IJ) y Helix sin reimplementar nada.

## Arquitectura propuesta

```
┌──────────┐   JSON-RPC/stdio   ┌───────────────────────────┐
│ VS Code  │ ◄───────────────► │      cortex-ls (TS)       │
│ Neovim   │                   │  ┌─────────────────────┐  │
│ Zed      │                   │  │ doc store (sync inc)│  │
│ JetBrains│                   │  └─────────────────────┘  │
└──────────┘                   │  ┌─────────────────────┐  │
                               │  │ cortexModel (pure)  │  │ ← reuse 0.2.0
                               │  └─────────────────────┘  │
                               │  ┌─────────────────────┐  │
                               │  │ CodecBridge         │  │ ← reuse 0.2.0
                               │  │ (spawn; futuro:     │  │
                               │  │  codec --server)    │  │
                               │  └─────────────────────┘  │
                               └───────────────────────────┘
```

## Capacidades LSP (fase 1)

| Método LSP | Equivale a provider 0.2.0 |
|---|---|
| `textDocument/didOpen, didChange` (incremental) | doc store + debounced validate |
| `textDocument/publishDiagnostics` | `parseCodecErrors` → Diagnostics |
| `textDocument/completion` | CortexCompletionProvider |
| `textDocument/hover` | CortexHoverProvider + catálogo errors-1.0.md |
| `textDocument/documentSymbol` | CortexSymbolProvider (§N + glosario) |
| `textDocument/formatting` | `canonicalize` |
| `textDocument/codeAction` | quick fixes (undeclared sigil, format) |

## Fase 2 (post-0.3.0)

- `definition`: instancia `OBJ:x` → su declaración en glosario
- `references`: todos los usos de un sigilo declarado
- `semanticTokens`: coloreo por tipo de sigilo / capa de sección
- `workspaceSymbol`: búsqueda cross-file de sigilos y secciones
- Diagnostics multi-archivo (refs rotas entre docs)
- **Modo servidor del codec** (`cortex --server` / stdin multiplexado):
  un proceso persistente que atiende N requests sin cold-start —
  requiere soporte en `codec-cortex` (issue a abrir).

## Transporte y despliegue

- **Transporte:** stdio (Content-Length framing, JSON-RPC 2.0).
  Opcional futuro: `--socket` para tests.
- **Distribución:** `cortex-ls` como binario npm standalone
  (`vscode-languageserver` + `vscode-languageserver-textdocument`),
  empaquetado dentro de la extensión Y publicable aparte para
  Neovim/Zed/JetBrains.
- **Compatibilidad cliente mínima:** LSP 3.17.

## Requisitos no funcionales (heredados)

- Offline-first: cero network; stdio únicamente.
- Sin `shell:true` — el server hereda CodecBridge con spawn+stdin.
- Presupuesto: completion < 100ms, diagnostics tras didChange < 300ms
  (doc ≤ 500 líneas).
- El documento canónico nunca se muta sin pasar por `canonicalize`.

## Qué se mueve vs qué se queda

| Módulo 0.2.0 | Destino |
|---|---|
| `cortexModel.ts` | mueve a `cortex-ls` (shared lib) |
| `providers.ts` | se reescribe como handlers LSP |
| `diagnostics.ts` | mueve al server (publishDiagnostics) |
| `codecBridge.ts` | mueve al server |
| `previewPanel.ts`, `webviewKit.ts`, `media/*` | **se queda** — el preview HCORTEX es VS Code-only, no es LSP |
| `extension.ts` | se reduce a: arrancar `cortex-ls` via `vscode-languageclient` + comandos de preview |

## Riesgos

- Duplicación temporal de completions entre extensión y server →
  mitigación: en 0.3.0 el server reemplaza los providers, no convive.
- `codec --server` no existe aún → la fase 1 convive con
  spawn-per-call dentro del server (mejora posterior transparente).
