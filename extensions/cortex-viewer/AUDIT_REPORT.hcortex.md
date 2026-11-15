<!-- HCORTEX v=1.0 t=canonical k=audit -->

# AUDIT REPORT — arqux-cortex-viewer 0.2.0

**Fecha:** 2026-11-15 · **Ejecutor:** Alfred (BLP-011 CODEC-CORTEX → traslado ARQUX/CYCLE-16)
**Contrato:** spec CORTEX del Arquitecto + pack 0.2.0 aprobado
**Ubicación:** `ARQUX/extensions/cortex-viewer/` (reubicado desde `CODEC-CORTEX/editors/vscode/` por decisión de marca — el artefacto ArqUX vive bajo el repo ArqUX)
**Toolchain:** codec-cortex 1.0.2-rc.1 (cortex Rust + codec-cortex Go en `~/.local/bin`)
**Host:** node v25.9.0 · npm 11.21.1 · vsce 4.1.1 · VS Code (`code` CLI)

## §1 Pipeline de auditoría

| step | command | exit | artifact_check |
|---|---|---|---|
| a02 | `npm run compile` | 0 | `out/` generado; tsc strict 0 errores |
| a03 | `npm test` | 0 | **24/24 PASS** (12 previos + 12 nuevos cortexModel/canonicalize) |
| a04 | `vsce package --out arqux-cortex-viewer-0.2.0.vsix` | 0 | VSIX 155 files / 443.4 KB, **0 warnings** |
| a05 | `code --install-extension …-0.2.0.vsix --force` | 0 | `arqux.arqux-cortex-viewer-0.2.0` en `~/.vscode/extensions` |
| a06 | `tar -czf …-0.2.0-bundle.tar.gz && sha256sum` | 0 | bundle + `.sha256` emitidos |

## §2 Verificaciones de seguridad

| id | enforce | resultado | evidencia |
|---|---|---|---|
| SEC-01 | CODE_HARD | PASS | `grep -rn 'exec(' src/` = 0 coincidencias literales (solo comentario); `spawn()` + `shell:false` + args array + stdin |
| SEC-02 | CSP_STRICT | PASS | `default-src 'none'`; `script-src 'nonce-<32B>'`; nonce único por shell |
| SEC-03 | CODE_HARD | PASS | `markdown-it` `html:false`; payload `<script>` escapado end-to-end |
| SEC-04 | CODE_HARD | PASS | `grep 'fetch/axios/http' src/` = 0 llamadas; zero telemetry |
| SEC-05 | CI_GATE | PASS | vsce exit 0, **0 warnings**; icono oficial 128×128 PNG |
| SEC-06 | SCHEMA_C14N | PASS | gate `from-hcortex`+`validate`+`loss-report` intacto |

## §3 Features 0.2.0 verificadas

| feature | resultado | evidencia |
|---|---|---|
| IntelliSense (sigilos + %enum + attr keys) | PASS | `CortexCompletionProvider` sobre `cortexModel` (parseDoc); triggers `%`,`{`,`:` |
| Hover (contrato + catálogo errores) | PASS | `CortexHoverProvider`; catálogo `errors-1.0.md` parseado a código→superficies |
| Outline / breadcrumbs | PASS | `CortexSymbolProvider`: `$0 KERNEL+glosario` (decls hijas) + `§N` secciones con capa |
| Format Document canónico | PASS | `canonicalize` por stdin; test idempotencia PASS; `formatOnSave` vía `onWillSaveTextDocument` |
| Quick Fixes | PASS | `I001`→declarar sigilo; `G005/G010`→insert `$0:format`; KERNEL→insert; `G020`→`desc:"TODO"` |
| Snippets | PASS | 7 snippets en `snippets/cortex.json` (escape `\$` para literales `$0`/`$N`) |
| Settings | PASS | `cortex.toolchainPath` (priority-0 override en bridge), `cortex.debounceMs`, `cortex.formatOnSave` |
| LSP ADR | PASS | `LSP-DESIGN.md`: transporte stdio, sync incremental, fases, `codec --server` futuro |

## §4 Bug detectado en test (resuelto)

`parseDoc` contaba usos post-sección como declaraciones (4≠2 sigilos).
Fix: solo líneas antes del primer `$N>0` son decls de glosario. Test añadido.

## §5 Hashes

| artefacto | sha256 |
|---|---|
| `arqux-cortex-viewer-0.3.0.vsix` (esbuild bundle, 16 files / 300.84 KB, 0 warnings) | `e1c786912465af12969021473f181684461dd2315e72118e7d52c1187d5f7010` |
| `arqux-cortex-viewer-0.3.0-bundle.tar.gz` | `e0aba028dcee40be7c1903efac385c5aeeedb6c92af17eeb041d60c4a3eb3c28` |
| `arqux-cortex-viewer-0.2.0.vsix` (post-traslado, repo→arqux, catálogo vendoreado) | `d49690101c90ceb6f0f9542613f7aa146035d63ef1cb9a09d1457ae675ed8f16` |
| `arqux-cortex-viewer-0.2.0-bundle.tar.gz` | `2fa4179d11fc3e6bf8fb4f3ffc92f70d9c23d42b9a7dbab36904eb600735ab73` |
| `arqux-cortex-viewer-0.2.0.vsix` (pre-traslado, CODEC-CORTEX) | `f1d4b60cbab51f76801d2ee783fcadaee747c21d92edf8220352cb6877ee869b` |

## §6 0.3.0 — cortex-ls + preview polish (CYCLE-17/BLP-002)

| item | resultado | evidencia |
|---|---|---|
| LSP server `out/server/server.js` (stdio JSON-RPC, LSP 3.17) | PASS | handshake stdio `initialize` → 11 capabilities; `didOpen` → `publishDiagnostics` con `I001` severity Error end-to-end |
| Handlers portados (completion/hover/symbols/codeAction/formatting/definition/references/rename/semanticTokens/folding) | PASS | `src/server/core.ts` puro; 9 tests nuevos directos sobre handlers |
| providers.ts eliminado | PASS | `LanguageClient` en extension.ts (stdio, initOptions toolchainPath+debounceMs); `grep providers` → 0 refs |
| Preview polish (details/toolbar/active) | PASS | `<details>` por §N + glosario, filtro `#hc-filter`, goto `#hc-goto`, `data-sigil` + msg `active` cursor-follow |
| Build bundling | PASS | esbuild 0.24.2: `extension.js` 1.0MB + `server.js` 460KB; vsix 543→16 files, 999→301 KB, **0 warnings** |
| Tests | PASS | 43/43 mocha (32 legado + 11 nuevos) |
| SEC greps | PASS | sin `child_process.exec`/`shell:true`/network en src/ |
| npm audit | NOTA | 3 vulns en **devDependencies solamente** (esbuild dev-server, serialize-javascript vía mocha) — nada viaja en el vsix |
