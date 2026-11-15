# ArqUX CORTEX Viewer

Extensión oficial de VS Code para documentos **CORTEX 1.0**: render HCORTEX
en vivo, validación sintáctica en tiempo real, hash canónico C14N visible y
edición bidireccional segura — todo delegado al toolchain `codec-cortex`.

## Características

- **Preview HCORTEX 1.0 en vivo** — renderiza el documento `.cortex` activo
  como HCORTEX (secciones `§N`, tablas de esquema, glosario) mientras editas.
- **Validación en tiempo real** — diagnósticos inline con los códigos de
  error del codec (`G010`, `I001`, `S002`, …) en línea/columna exacta.
- **Hash C14N visible** — cabecera fija con `sha256:` corto y botón Copiar.
- **Loss-Report** — contador de pérdidas declaradas del render actual.
- **Edición bidireccional segura** — edita celdas de tablas en la preview;
  el cambio pasa por `from-hcortex` + `validate` + `loss-report` y se
  aborta si hay cualquier pérdida (`loss_count > 0`).
- **Scroll sincronizado** — el cursor del editor desplaza la preview a la
  sección `§N`; clic en un encabezado de la preview revela la línea `$N:`.
- **IntelliSense** — autocompleta sigilos declarados en el glosario
  (`OBJ:item`), valores `%enum` y claves de atributo del contrato
  `fields:`.
- **Hover inteligente** — sobre un sigilo muestra su contrato declarado;
  sobre un código de error (`G0xx`, `I0xx`…) muestra las superficies que
  lo emiten según `errors-1.0.md`.
- **Outline y breadcrumbs** — árbol de secciones `§N` y declaraciones del
  glosario en el panel Outline.
- **Format Document canónico** — `Shift+Alt+F` ejecuta `canonicalize`;
  opcional `cortex.formatOnSave`.
- **Quick Fixes** — sigilo no declarado → insertar declaración en el
  glosario; falta `$0:format`/`$0:KERNEL` → insertarlo; `G020` → añadir
  `desc:`.
- **Snippets** — `cortex-doc`, `sigil`, `enum`, `sec`, `seccapa`, `obj`,
  `micro`.
- **`cortex-ls` (LSP)** — toda la inteligencia de lenguaje corre en un
  servidor LSP stdio dedicado (`out/server/server.js`), reutilizable
  desde Neovim, Zed o JetBrains.
- **Preview navegable** — capítulos `§N` plegables, filtro en vivo de
  cards/glosario, dropdown `§ Ir a…`, y resaltado de la card del sigilo
  bajo el cursor.
- **Offline-first / zero-telemetry** — ninguna petición de red; todo corre
  local contra el toolchain instalado.

## Requisitos

`codec-cortex >= 1.0.1`, resoluble por la cadena de prioridad:

| # | Runtime | Comando |
|---|---------|---------|
| 1 | Rust | `cortex` |
| 2 | Go | `codec-cortex` |
| 3 | Python | `python3 -m codec_cortex` |
| 4 | Node | `codec-cortex-node` |

Instalación mínima (Python): `pip install codec-cortex`

## Uso

| Atajo | Acción |
|-------|--------|
| `Ctrl+Shift+V` (`Cmd+Shift+V` macOS) | Abre la preview HCORTEX |
| `Ctrl+K V` (`Cmd+K V` macOS) | Abre la preview al lado |

Comandos: `CORTEX: Open Preview`, `CORTEX: Open Preview to the Side`,
`CORTEX: Verify Canonical Hash`, `CORTEX: Apply HCORTEX Human Edit`.

## Ajustes

| Clave | Default | Efecto |
|-------|---------|--------|
| `cortex.toolchainPath` | `""` | Comando explícito del toolchain; vacío = cadena de prioridad |
| `cortex.debounceMs` | `250` | Debounce del refresh de preview/diagnósticos |
| `cortex.formatOnSave` | `false` | Canonicaliza el documento al guardar |

## Capturas (ASCII)

```
┌─ editor ────────────────┬─ preview ───────────────────────┐
│ $0:KERNEL               │ [VALID][C14N-1.0][b7127a… ⧉][0] │
│ $0:format{cortex:1.0,…} │ Runtime: cortex                 │
│ OBJ:x{type:attrs,…}     │─────────────────────────────────│
│ $1: META                │ ## §1: META                     │
│ OBJ:x{name:"codec"}     │ ### OBJ:x   ┌───────┐           │
│                         │             │ name  │           │
│                         │             │"codec"│           │
└─────────────────────────┴─────────────────────────────────┘
```

## Seguridad

- Sin `child_process.exec` ni `shell:true`; documentos viajan por stdin.
- CSP estricta en el Webview (`default-src 'none'`, nonce de 32 bytes).
- Sanitización XSS: `markdown-it` con `html:false`.
- Cero telemetría y cero llamadas de red.

## Límites declarados

- No implementa un parser propio: sin toolchain resoluble, la extensión
  muestra la notificación de instalación y no renderiza.
- La edición bidireccional cubre celdas de tablas HCORTEX (`schema:table`);
  otros nodos se editan en el editor de texto.
- `codec-cortex-node` usa `parse` como validador (no expone `validate`).

## Licencia

Apache-2.0 — ver `LICENSE`.
