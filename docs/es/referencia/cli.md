---
doc_type: reference
status: normative
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
<p align="center"><sub>Referencia · Normativo · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# Referencia CLI `arqux`

Referencia exhaustiva de la CLI de ArqUX 1.0.0: cada comando, cada flag, cada exit code, un ejemplo real ejecutado. Fuente única de verdad: el árbol click de `src/arqux/cli.py` — si esta página difiere del código, la página miente.

## Convenciones

- `arqux <cmd> --help` es siempre autoritativo sobre esta página.
- `--path` existe en varios comandos; default: directorio actual.
- `arqux call <handler> key=valor` invoca cualquier handler sin MCP — las llaves del handler son `key=value` en línea.
- Variables de entorno (`ARQUX_AGENT_ID`, `ARQUX_AGENT_ROLE`, `ARQUX_STRICT_*`): ver `docs/es/referencia/configuracion.md` cuando exista.
- Exit codes: 0 éxito; 1 error funcional o verificación fallida; 2 error de uso (parser click). Códigos simbólicos (`ERR_*`, `EXPORT_BLOCKED`) se documentan por comando.

## Tabla resumen

| Comando | Propósito | Grupo |
|---|---|---|
| `init` | Inicializar `.arqux/` | Inicio |
| `quickstart` | Onboarding guiado de workspace | Inicio |
| `status` | Estado workspace+proyecto+ciclo | Inspección |
| `doctor` | Diagnóstico de salud con `--fix` | Inspección |
| `call` | Invocar un handler directo | Gobierno |
| `cycle`, `project` | Atajos a handlers `cycle.*`/`project.*` | Gobierno |
| `handlers` | Listar handlers disponibles | Gobierno |
| `validate` | Validar un `.cortex` | CORTEX |
| `cortex-verify` | Verificar sello SHA-256 | CORTEX |
| `cortex-migrate` | Migrar formato legacy a CODEC 1.0 | CORTEX |
| `migrate` | Inyectar `ARQX:artifact` en `.cortex` | CORTEX |
| `elevate` | Elevar una lección (dry-run por defecto) | CORTEX |
| `review` | Ciclo → HCORTEX Markdown | Reportes |
| `from-hcortex` | HCORTEX → `.cortex` (round-trip) | Reportes |
| `evidence export` | Bundle de evidencia con gate de privacidad | Evidencia |
| `policy keygen/sign/verify` | Ed25519 para artefactos | Evidencia |
| `backup`, `restore` | Respaldo `.tar.gz` + restauración | Operación |
| `push-delta`, `pull-policy` | Journal autoritativo de políticas | Sync |
| `sync-harnesses`, `drift-check` | Proyección a AGENTS/CLAUDE/GEMINI + drift | Sync |
| `loop-watch` | Vigilar loops autónomos | Sync |
| `wake` | Boot payload denso para agentes | Agentes |
| `identity list/resolve/elevate` | Identidades de agente | Agentes |
| `skill list/resolve/import` | Skills con procedencia | Agentes |
| `serve` | Servidor MCP por stdio | Servicios |
| `session-bridge serve` | Broker host-bridge (socket Unix) | Servicios |
| `serve-plantuml`, `setup-plantuml`, `render-diagram` | Render de diagramas | Servicios |
| `comms-serve`, `comms-doctor` | Extensión comms (`arqux[comms]`) | Extensiones |
| `voice-serve`, `voice-doctor`, `voice-daemon` | Extensión voice (`arqux[voice]`) | Extensiones |

---

## Inicio y estado

### `arqux init`

Inicializa `.arqux/` en el directorio. Sobre workspace ya gobernado aborta sin `--force` — nunca sobrescribe `.arqux/*.cortex`.

| Flag | Tipo | Default | Efecto |
|---|---|---|---|
| `--path` | texto | cwd | Ruta a inicializar |
| `--verbose` | flag | off | Perfil OUT-AUDIT |
| `--force` | flag | off | Re-inicializar workspace gobernado |

```bash
$ arqux init --path /tmp/ws
OUT-MIN workspace=/tmp/ws/.arqux governor=anonymous workspace.init ok
```

### `arqux quickstart`

Onboarding guiado: valida workspace gobernado + `AGENTS.md` y lista los siguientes pasos (identidad, rol, primeros comandos).

| Flag | Tipo | Default | Efecto |
|---|---|---|---|
| `--path` | texto | cwd | Directorio a bootstrap |

```bash
$ arqux quickstart --path /tmp/ws
✅ Workspace already governed at /tmp/ws
📋 Next steps:
  1. Set your identity:     export ARQUX_AGENT_ID=<name>
  2. Set your role:         export ARQUX_AGENT_ROLE=governor|executor|auditor
```

### `arqux status`

Estado combinado: workspace, proyecto activo, ciclo.

| Flag | Tipo | Default | Efecto |
|---|---|---|---|
| `--path` | texto | cwd | Ruta a inspeccionar |
| `--verbose` | flag | off | Salida extendida |
| `--dashboard` | flag | off | Dashboard visual |

```bash
$ arqux status --path /tmp/ws
OUT-MIN workspace=/tmp/ws/.arqux manifest=true meta_brain=True
OUT-ERROR code=NOT_FOUND no project initialized
```

### `arqux doctor`

Diagnóstico de salud del workspace/proyecto (8+ checks). `--fix` aplica reparaciones.

| Flag | Tipo | Default | Efecto |
|---|---|---|---|
| `--fix` | flag | off | Aplicar reparaciones automáticas |

```bash
$ arqux doctor
OUT-WORK context=workspace checks=8 passed=8 failed=0 warned=0
  [✅] nested .arqux: No .arqux inside .arqux
  [✅] meta-brain.cortex: ok (4096 bytes)
```

---

## Gobierno

### `arqux call HANDLER [key=valor ...]`

Invoca cualquier handler directamente — sin servidor MCP. La forma de depuración y scripting.

```bash
$ arqux call workspace.status
OUT-MIN workspace=/tmp/ws/.arqux manifest=true …
$ arqux call blueprint.list status=done cycle=CYCLE-16
```

### `arqux cycle SUB [ARGS]`, `arqux project SUB [ARGS]`

Atajos de primer nivel a los handlers `cycle.*` y `project.*`. `SUB` es el sufijo del handler; los args son `key=value`.

```bash
$ arqux cycle current
$ arqux cycle create name=CYCLE-17
$ arqux project status
```

### `arqux handlers`

Lista todos los handlers registrados (nombres punteados `workspace.status`, `blueprint.claim`, …).

```bash
$ arqux handlers | wc -l
115
```

---

## CORTEX

### `arqux validate PATH`

Valida un `.cortex`: `ARQX:artifact` + estructura + semántica. Exit 0 pasa (warnings permitidos), `--strict` convierte warnings en fallos.

| Flag | Tipo | Efecto |
|---|---|---|
| `--strict` | flag | Fallar también en warnings |

```bash
$ arqux validate .arqux/meta-brain.cortex
Validation: PASS
  [WARN] E027_MALFORMED_SECTION: Section $10 title mismatch…
```

### `arqux cortex-verify PATH`

Verifica el sello de integridad SHA-256 (y los `HSH` de `seal.cortex`).

**Exit codes**: 0 — integridad verificada; 1 — tamper detectado, `ERR_HASH_MISMATCH`, o sin header `$INTEGRITY`.

```bash
$ arqux cortex-verify .arqux/brain.cortex
OK: .arqux/brain.cortex integrity verified
$ arqux cortex-verify seal.cortex        # tras alterar un artefacto
FAIL: [ERR_HASH_MISMATCH] cycle.cortex: recorded=148f… actual=01ed…   (exit 1)
```

### `arqux cortex-migrate PATH`

Inspecciona o migra archivos CORTEX legacy a CODEC-CORTEX 1.0. Preview no-mutante por defecto.

| Flag | Tipo | Efecto |
|---|---|---|
| `--apply` | flag | Escribir cambios (default: dry-run) |
| `--no-backup` | flag | No retener backup atómico |

```bash
$ arqux cortex-migrate archivo.cortex       # preview
[ { "dry_run": true, "status": "preview" } ]
```

### `arqux migrate PATH`

Inyecta `ARQX:artifact` + contrato en un `.cortex`. Idempotente.

| Flag | Tipo | Efecto |
|---|---|---|
| `--level` | entero | **req.** 0=PACKAGE, 1=BEHAVIORAL, 2=SKILL, 3=BRAIN |
| `--name` | texto | **req.** Nombre canónico del artefacto |
| `--usage` | texto | **req.** `state\|skill\|identity\|lesson\|config` |
| `--kind` | texto | `native\|inherited\|adapted` |
| `--agent` | texto | Nombre de agente (lecciones) |
| `--source`, `--upstream-version` | texto | Procedencia externa |

```bash
$ arqux migrate doc.cortex --level 3 --name demo --usage state
MIGRATED: doc.cortex
```

### `arqux elevate`

Eleva una lección al nivel destino. Dry-run por defecto; `--apply` escribe.

| Flag | Tipo | Efecto |
|---|---|---|
| `--source` | texto | **req.** Contenedor origen |
| `--target` | texto | **req.** Contenedor/sección destino |
| `--type` | texto | **req.** `AXIOM\|LIMIT` (behavioral), `CNST\|CLAIM` (procedural), `KNW` (contextual) |
| `--lesson-id` | texto | **req.** Nombre del sigilo de la lección |
| `--line` | `behavioral\|procedural\|contextual` | Línea de elevación |
| `--agent` | texto | Requerido para behavioral |
| `--apply` | flag | Aplicar (default: dry-run) |

```bash
$ arqux elevate --source b.cortex --target b.cortex --type KNW --lesson-id demo
ERROR: Behavioral line only accepts contracts {'LIMIT','AXIOM'}; got 'KNW'
# la línea default es behavioral; KNW requiere --line contextual
```

### `arqux review --cycle ID`

Renderiza un ciclo a HCORTEX Markdown (humano + round-trip). Ver `docs/es/referencia/formatos.md`.

| Flag | Tipo | Efecto |
|---|---|---|
| `--cycle` | texto | **req.** ID del ciclo |
| `--path` | texto | Raíz del proyecto (default: cwd) |

```bash
$ arqux review --cycle CYCLE-16 > revision.md
# Cycle Review — CYCLE-16 …
```

### `arqux from-hcortex MD_PATH`

Recompila un reporte HCORTEX a `.cortex`. **Exit codes**: 0 — `loss_count == 0`; 1 — errores o pérdida > 0.

| Flag | Tipo | Efecto |
|---|---|---|
| `--out` | texto | `.cortex` destino (default: `<nombre>.cortex`) |

```bash
$ arqux from-hcortex revision.md
recompiled revision.cortex entries=2 loss_count=0
```

---

## Evidencia y firma

### `arqux evidence export`

Bundle de evidencia desde `.arqux/timelog/SES*.cortex` con gate de privacidad fail-closed. Spec completa: `docs/es/referencia/formatos.md`.

| Flag | Tipo | Efecto |
|---|---|---|
| `--out` | ruta | **req.** Bundle destino |
| `--path` | ruta | Raíz del proyecto (default: cwd) |
| `--redact-private` | flag | Excluir `visibility:"private"` registrando conteo |
| `--allow-raw` | flag | Incluir privado verbatim (auditoría; `raw:true`) |

**Exit codes**: 0 — bundle escrito; 1 — `EXPORT_BLOCKED` (privado sin flag) o flags mutuamente excluyentes.

```bash
$ arqux evidence export --out b.cortex
EXPORT_BLOCKED: 1 private-marked field(s) found — export blocked.   (exit 1)
$ arqux evidence export --out b.cortex --redact-private
bundle b.cortex spans=1 events=2 redacted=1
```

### `arqux policy keygen KEY_PATH`

Genera keypair Ed25519: `seed:` + `public:` hex, archivo `0600`.

```bash
$ arqux policy keygen emisor.key
key_id:e4178958… created emisor.key
```

### `arqux policy sign DOC --key PATH`

Anexa `SIG:signature` al documento (e inyecta `SIG:sig_contract` en `$0`). **Modifica el archivo** — trabajar sobre copia en demostraciones.

### `arqux policy verify DOC`

Verifica la firma. `--key` opcional: sin él, resuelve `public:` en `.arqux/keys/` junto al documento.

**Exit codes**: 0 — `SIGNATURE_VALID`; 1 — `ERR_INVALID_SIGNATURE`, `ERR_NO_SIGNATURE`, `ERR_KEY_MISMATCH`, `ERR_KEY_NOT_FOUND`.

```bash
$ arqux policy verify bundle.cortex --key emisor.key
SIGNATURE_VALID key_id:e4178958…
```

---

## Operación

### `arqux backup`

Respaldo `.tar.gz` de `.arqux/` con timestamp + archivo `.sha256` hermano, en el directorio actual.

```bash
$ arqux backup
backup created: arqux-20261115T215719Z.tar.gz (62623 bytes, sha256=c93325d7…)
```

### `arqux restore BACKUP_FILE`

Restaura `.arqux/` **al path original registrado en el backup**; el estado previo se preserva como `.arqux.prev`.

```bash
$ arqux restore arqux-20261115T215719Z.tar.gz
restore ok from arqux-20261115T215719Z.tar.gz previous_backup=/tmp/ws/.arqux.prev
```

---

## Sync

### `arqux push-delta`

Aplica un delta de políticas al journal autoritativo. Optimistic locking.

| Flag | Tipo | Efecto |
|---|---|---|
| `--workspace` | texto | **req.** ID del workspace emisor |
| `--delta` | ruta | **req.** `.cortex` con las reglas |
| `--base` | entero | **req.** Versión del journal sobre la que se construyó |
| `--path` | ruta | Workspace con el journal (default: cwd) |

**Exit codes**: 0 — aplicado; 1 — `ERR_CONFLICT_VERSION` o `ERR_EMPTY_DELTA`.

```bash
$ arqux push-delta --workspace ws-1 --delta d.cortex --base 0
applied delta from ws-1: version=1 rules=1
$ arqux push-delta --workspace ws-1 --delta d.cortex --base 0   # mismo base, journal ya en 1
ERR_CONFLICT_VERSION: journal is at version 1, delta claims base 0   (exit 1)
```

### `arqux pull-policy`

Imprime la sección de política vigente del journal.

```bash
$ arqux pull-policy
# journal policy — version 1
RUL:no_raw_private{check:"secret_pattern", action:"deny", …}
```

### `arqux sync-harnesses`

Renderiza la gobernanza `.arqux/` a `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.opencode/instructions.md` con `source_hash` compartido.

| Flag | Tipo | Efecto |
|---|---|---|
| `--path` | texto | Raíz del proyecto (default: cwd) |

```bash
$ arqux sync-harnesses
source_hash:0badd4d4…
  wrote AGENTS.md  wrote CLAUDE.md  wrote GEMINI.md  wrote .opencode/instructions.md
```

### `arqux drift-check`

Detecta ediciones manuales en las proyecciones. **Exit codes**: 0 — todo coincide; 1 — `DRIFT_DETECTED` + diff.

```bash
$ arqux drift-check
OK AGENTS.md
OK CLAUDE.md
OK GEMINI.md
OK .opencode/instructions.md
```

### `arqux loop-watch`

Vigilante de loops autónomos: detecta stalls, encola WAKEs.

| Flag | Tipo | Efecto |
|---|---|---|
| `--path` | texto | Proyecto a vigilar |
| `--interval` | float | Segundos entre ticks |
| `--once` | flag | Un solo tick (pruebas) |

```bash
$ arqux loop-watch --once
loop-watch tick scanned=0 wakes=[] stalled=[] errors=0
```

---

## Agentes y skills

### `arqux wake --identity NOMBRE`

Payload de arranque ultra-denso para agentes: cortex:1.0 válido con estado del registry, reglas enforce y tarea en curso.

| Flag | Tipo | Efecto |
|---|---|---|
| `--identity` | texto | **req.** Identidad/rol (ver `.arqux/identities/*.cortex`) |
| `--path` | texto | Raíz del proyecto (default: cwd) |

```bash
$ arqux wake --identity alfred
$0:format{cortex:1.0, encoding:UTF-8}
IDN:wake{identity:"alfred", kind:"generic", workspace:"…", project:"none", …}
TSK:none{task_id:"none", note:"no in-progress task"}
```

### `arqux identity list` / `arqux identity resolve NAME`

Inventario y resolución de identidades de agente. `--identities-dir` sobreescribe el directorio.

```bash
$ arqux identity list
alfred  auditor  executor  governor  heimdall  jarvis  seshat
$ arqux identity resolve alfred
AXM contracts: 7 … LIM contracts: 4 …
```

### `arqux identity elevate`

Inyecta un `AXM`/`LIM` en la identidad de un agente.

| Flag | Tipo | Efecto |
|---|---|---|
| `--agent` | texto | **req.** Nombre del agente |
| `--lesson-id` | texto | **req.** Sigilo de la lección |
| `--type` | `AXIOM\|LIMIT` | **req.** |
| `--pattern` | texto | Cuerpo de la regla |
| `--evidence-ref` | texto | Referencia de evidencia |
| `--identities-dir` | texto | Directorio alternativo |

### `arqux skill list` / `arqux skill resolve NAME` / `arqux skill import NAME`

Skills con procedencia (`Adapted > Original > Native`). `import` incorpora skills de terceros.

| Flag (import) | Tipo | Efecto |
|---|---|---|
| `--source` | texto | **req.** URL/path upstream |
| `--content` / `--from-file` | texto | Contenido inline o archivo |
| `--upstream-version` | texto | Tag de versión |
| `--arqux-root` | texto | Override raíz `.arqux/` |

```bash
$ arqux skill list
autonomia        native   adapted  .arqux/skills/autonomia.skill.md
cortex           native   adapted  .arqux/skills/cortex.skill.md
…
```

---

## Servicios

Procesos de larga duración; no producen salida propia al arrancar correctamente.

### `arqux serve`

Servidor MCP por stdio — el punto de entrada de los handlers para el agente.

| Flag | Tipo | Efecto |
|---|---|---|
| `--verbose` | flag | Arranque verboso |

### `arqux session-bridge serve`

Broker host-bridge en foreground — socket Unix entre sesiones de agente.

| Flag | Tipo | Default | Efecto |
|---|---|---|---|
| `--socket` | texto | `ARQUX_HOST_BRIDGE_SOCKET` o `XDG_RUNTIME_DIR` | Path del socket |
| `--request-timeout` | float | 90.0 | Timeout de petición |

### `arqux serve-plantuml`

Servidor de render PlantUML.

| Flag | Tipo | Efecto |
|---|---|---|
| `--port` | entero | Puerto de escucha (default 9876) |

### `arqux setup-plantuml`

Instala `plantuml.jar` en `~/.arqux/bin/`. `--force` re-descarga.

### `arqux render-diagram PUML_FILE`

Render único de `.puml` a imagen.

| Flag | Tipo | Efecto |
|---|---|---|
| `--format` | `svg\|png` | Formato de salida |
| `-o`, `--output` | texto | Directorio destino |

```bash
$ arqux render-diagram diagramas/arquitectura.puml --format svg -o /tmp
/tmp/arquitectura.svg
```

---

## Extensiones

Extras opcionales — requieren `pip install arqux[comms]` / `arqux[voice]`.

### `arqux comms-serve` / `arqux comms-doctor`

Servidor MCP de la extensión comms y su diagnóstico. `comms-doctor` verifica dependencias, token, allowlist y egress — **fail-closed**: sin token y allowlist vacía, reporta fallos.

```bash
$ arqux comms-doctor
[PASS] dep:httpx        import ok
[FAIL] telegram:token   MISSING (set ARQUX_COMMS_TELEGRAM_TOKEN)
[FAIL] allowlist        EMPTY (fail-closed: nobody allowed)
[PASS] egress           OFF (default)
2 failure(s)
```

### `arqux voice-serve` / `arqux voice-doctor` / `arqux voice-daemon`

Extensión de voz. `voice-daemon` gestiona el demonio persistente:

| Subcomando | Efecto |
|---|---|
| `start` | Escuchar en background. Flags: `--foreground`, `--name`, `--mode solo\|meet`, `--agent`, `--lang`, `--mic` |
| `status` | Estado del demonio y la reunión |
| `stop` | Detener y liberar dispositivos |
| `restart` | Reinicio con sesión fresca (mismos flags que `start` menos `--foreground`) |

```bash
$ arqux voice-daemon status          # sin el extra instalado:
ERROR: voice extra not installed (No module named 'numpy')   (exit 1)
```

**Nota honesta**: `voice-doctor` sin el extra `arqux[voice]` termina en `ModuleNotFoundError: numpy` — un defecto de UX del producto (debería reportar como `voice-daemon`); la forma de corregir el entorno es `pip install arqux[voice]`.

---

## Referencias

- `docs/es/referencia/formatos.md` — artefactos producidos por estos comandos
- `docs/es/guias/evidencia-y-cumplimiento.md` — flujo CISO con evidence/policy
- `THREAT_MODEL.md` — exit codes de seguridad (`ERR_*`, `PERMISSION_DENIED`)

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="../../../docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
