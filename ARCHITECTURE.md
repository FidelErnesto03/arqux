---
doc_type: explanation
status: informative
version: 1.0.0
verified: 2026-11-15
---

<!-- DOC-BRAND -->
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./docs/assets/brand/arqux-logo-primary-dark.svg">
    <img alt="ArqUX" src="./docs/assets/brand/arqux-logo-primary-light.svg" width="240">
  </picture>
</p>
<p align="center"><sub>Explicación · Informativo · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# Arquitectura de ArqUX

> Versión del documento: 1.0.0 — cada capa y dependencia nombrada existe en `src/arqux/` y `pyproject.toml` hoy.

ArqUX es una capa de gobernanza para equipos de agentes IA. Se sitúa entre el usuario, el agente, el modelo y el workspace, y entrega contratos de identidad, handlers MCP, ciclo de vida Blueprint, memoria CORTEX y evidencia verificable.

---

## 1. Vista de capas

```text
┌─────────────────────────────────────────────────────────┐
│                  Usuario / Operador                      │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│                 CLI (click) — src/arqux/cli.py           │
│  init | status | call | serve | quickstart | doctor |    │
│  sync-harnesses | drift-check | wake | review |          │
│  evidence export | policy sign/verify | push-delta |     │
│  pull-policy | cortex-verify | backup | restore          │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│         MCP Server (stdio) — src/arqux/server.py         │
│  Expone 115 handlers via Model Context Protocol          │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│      Handler Registry — src/arqux/handlers/ (18 módulos) │
│  blueprint 16 · cortex 23 · session 9 · loop 9 · task 8  │
│  cycle 6 · protocol 5 · project 5 · timelog 5 · issue 4  │
│  identity 4 · evidence 3 · workspace 3 · context 2 ·     │
│  handler 2 · sync 2 · setup 1 · skill 8                  │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│      Permisos + Política                                 │
│  permissions.py — 3 roles (GOVERNOR/EXECUTOR/AUDITOR),   │
│  MUTATING_HANDLERS, HMAC_REQUIRED, ARQUX_STRICT_*        │
│  core/policy_engine.py — enforce:CODE|PROMPT|HUMAN       │
│  (reglas CODE corren como hooks pre-write; REQ-10)       │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│      Estado — src/arqux/cortex/ + core/state             │
│  Frontera codec-cortex (>=1.0,<1.1) fail-closed:         │
│  parser estricto + escritura transaccional atómica +     │
│  guarda post-escritura con rollback (sin codec → error)  │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│      Seguridad + Journal + Evidencia                     │
│  security.py — HMAC-SHA256 + $INTEGRITY (sha256)         │
│  signing.py — Ed25519 puro RFC 8032 (REQ-12)             │
│  journal.py — orden total + ERR_CONFLICT_VERSION (REQ-13)│
│  evidence_export.py — bundle.cortex firmado (REQ-11)     │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│      Memoria institucional — src/arqux/memory/           │
│  learning engine nativo: authority | events | feedback | │
│  models | rebuild | recall | store (Apache-2.0)          │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│         Filesystem — .arqux/                             │
│  meta-brain.cortex | brain.cortex | projects.cortex |    │
│  identities/ | skills/ | templates/ | timelog/ | cycles/ │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Componentes

### 2.1 CLI (`src/arqux/cli.py`)

Interfaz click. La superficie 1.0.0 agrupa:

- **Workspace/proyecto:** `init`, `status`, `quickstart`, `doctor`, `project`, `cycle`, `validate`, `migrate`, `cortex-migrate`, `backup`, `restore`
- **Acceso directo a handlers:** `call <handler>` (cualquier handler sin MCP), `handlers` (lista los 115), `cortex-verify` (integridad SHA-256), `elevate`, `identity`, `skill`
- **M2 — ergonomía multi-harness:** `sync-harnesses` proyecta `.arqux/` a `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` y `.opencode/instructions.md` con `source_hash` común; `drift-check` detecta ediciones manuales (REQ-07). `wake --identity <rol>` emite un payload CORTEX <1500 tokens con estado, reglas y tarea activa (REQ-08). `review --cycle <id>` recompila el ciclo a HCORTEX con `loss_count == 0` (REQ-09).
- **M3 — plataforma/compliance:** `evidence export` empaqueta spans de ejecución en `bundle.cortex` con `--redact-private` por defecto (REQ-11). `policy keygen|sign|verify` firma Ed25519 pura sin dependencias nuevas (REQ-12). `push-delta`/`pull-policy` sincronizan contra el journal autoritativo con bloqueo optimista (REQ-13).
- **Servidores:** `serve` (MCP core stdio), `serve-plantuml`, `session-bridge`, `loop-watch`, `comms-serve`, `voice-serve`, `voice-daemon`.

### 2.2 MCP Server (`src/arqux/server.py`)

Expone los 115 handlers por stdio (Model Context Protocol). Cada handler valida su `input_schema` (jsonschema) y devuelve `CortexOUT` — salida textual parseable (`OUT-WORK`/`OUT-ERROR`/`OUT-MIN`). Clientes: cualquier harness que hable MCP.

### 2.3 Handler Registry (`src/arqux/handlers/`)

Un `REGISTRY` único de nombre de handler a spec (función + JSON Schema + descripción). 18 módulos, 115 handlers — el registro vivo es la fuente canónica del conteo (lo verifica `scripts/check_surfaces.py`).

### 2.4 Permisos (`src/arqux/permissions.py`)

Modelo de tres roles:

| Rol | Identidad | Acceso |
|---|---|---|
| **GOVERNOR** | Alfred | Todos los handlers |
| **EXECUTOR** | Jarvis | Todo excepto `workspace.init`/`project.init` |
| **AUDITOR** | Heimdall, Seshat | Solo lectura — `MUTATING_HANDLERS` denegados |

Los handlers `HMAC_REQUIRED` exigen identidad verificada antes de ejecutar. `ARQUX_STRICT_ROLES=1` fuerza chequeo de rol; `ARQUX_STRICT_SECURITY=1` fuerza verificación HMAC.

### 2.5 Motor de política (`src/arqux/core/policy_engine.py`)

Reglas de política con nivel `enforce` obligatorio: `CODE` (hook pre-write ejecutable), `PROMPT` (inyección en contexto) o `HUMAN` (aprobación). Ausencia de nivel → `ERR_MISSING_ENFORCE_LEVEL` (REQ-10).

### 2.6 Estado (`src/arqux/cortex/` + `core/state/`)

Persistencia en archivos `.cortex` (entradas por sigilo `$N`, validadas). La frontera con **codec-cortex** (`>=1.0,<1.1`, dependencia core desde 1.0.0) es **fail-closed**: parse estricto, secciones resueltas antes de mutar, escritura atómica con rollback y verificación post-escritura — si el codec falta, la escritura aborta con `RuntimeError`, nunca escribe sin validar. Detalle completo en `docs/es/explicacion/frontera-codec.md`.

### 2.7 Seguridad (`security.py`, `signing.py`, `journal.py`, `evidence_export.py`)

- **HMAC-SHA256** (`security.py`): verificación de identidad ligada a `agent_id|handler|timestamp|payload_hash` (anti-replay). Secrets en `.arqux/secrets/`, modo 0600.
- **Integridad SHA-256**: cabecera `$INTEGRITY` por archivo; `arqux cortex-verify` detecta tampering. El cierre de ciclo emite `seal.cortex` con hash por artefacto + raíz (REQ-03).
- **Ed25519 puro** (`signing.py`, REQ-12): `SIGNATURE_VALID` o `ERR_INVALID_SIGNATURE`, sin dependencia externa. El extra `crypto` solo cubre la API legada `security.py`.
- **Journal autoritativo** (`journal.py`, REQ-13): deltas disjuntos se ordenan determinísticamente; conflicto sobre la misma base → `ERR_CONFLICT_VERSION`.
- **Export de evidencia** (`evidence_export.py`, REQ-11): `bundle.cortex` con identidad, skill, archivos, timestamps y SHA-256; un campo `visibility:"private"` sin `--allow-raw` bloquea el export (`EXPORT_BLOCKED`).

### 2.8 Memoria (`src/arqux/memory/`)

Motor de aprendizaje nativo (Apache-2.0): `authority` (permisos de aprendizaje), `events`, `feedback`, `models`, `rebuild`, `recall`, `store`. Tres niveles de elevación: lección conductual → conocimiento contextual → habilidad procedural.

### 2.9 Extensiones (fuera del core)

- `comms/` — puente Telegram como servidor MCP stdio aparte (`comms-serve`), extra `comms`.
- `voice/` — participación de voz local (STT faster-whisper + TTS Piper/Kokoro + VAD Silero), servidor y daemon aparte, extra `voice`.
- `plantuml` — render de diagramas (`serve-plantuml`, `render-diagram`, `setup-plantuml`).

---

## 3. Flujo de datos 1.0.0

### 3.1 Invocación de handler

```text
arqux call blueprint.create obj="X" cycle=CYCLE-01
  │
  ▼  cli.py — resuelve handler, parsea key=value, PermissionContext.from_env()
handlers/blueprint.py:create
  │  1. enforce_ctx(ctx, "blueprint.create")   — rol + HMAC si aplica
  │  2. gate de política (policy_engine)       — reglas enforce:CODE
  │  3. valida input_schema + estado (ciclo con MANIFEST maduro)
  ▼
cortex/ escritura transaccional
  │  parse estricto → mutación AST → verificación codec → escritura atómica
  │  (fail-closed: error → rollback, nada queda a medias)
  ▼
evidencia + sync
  │  evento en brain PULSE (sesión/timelog) → meta-brain si aplica
  ▼
CortexOUT → click.echo → exit 0
```

### 3.2 Sello y journal

```text
cycle.close
  │  genera seal.cortex: SHA-256 por artefacto + raíz del árbol
  ▼
push-delta
  │  empaqueta delta firmable contra journal autoritativo
  │  misma base modificada → ERR_CONFLICT_VERSION (bloqueo optimista)
  ▼
pull-policy — trae política consolidada en orden total
```

---

## 4. Dependencias (pyproject.toml, verificado)

**Core (5):**

| Dependencia | Pin | Función |
|---|---|---|
| `mcp` | `>=1.0.0,<2` | Runtime MCP (pin <2: server.py usa decorators lowlevel) |
| `codec-cortex` | `>=1.0,<1.1` | Codec CORTEX/HCORTEX — verify/render/REQ-04/REQ-09 |
| `jsonschema` | `>=4.20` | Validación de `input_schema` en server.py |
| `click` | `>=8.1.0` | CLI |
| `rich` | `>=13.0.0` | Salida de terminal / dashboard |

**Extras:**

| Extra | Contenido | Para |
|---|---|---|
| `crypto` | `cryptography>=41` | API legada `security.py` (REQ-12 no la necesita) |
| `voice` | faster-whisper, kokoro-onnx, piper-tts, onnxruntime, numpy, onnx-asr, huggingface-hub | Extensión de voz local |
| `comms` | `httpx>=0.24` | Puente Telegram |
| `dev` | pytest, pytest-asyncio | Desarrollo |

> `pydantic` salió del core en 1.0.0 (llega transitivo vía `mcp`).

---

## 5. Layout `.arqux/`

```text
<workspace>/
├── AGENTS.md                     # contrato de entrada — lo lee todo agente
└── .arqux/
    ├── meta-brain.cortex         # memoria del workspace (registry de proyectos)
    ├── projects.cortex           # índice de proyectos
    ├── learn-policies.cortex     # políticas del motor de aprendizaje
    ├── identities/               # 7 contratos de identidad (.cortex) — solo workspace
    ├── secrets/                  # claves HMAC (modo 0600)
    ├── skills/                   # definiciones de skill + workflows
    ├── templates/                # BLP_TEMPLATE, CYCLE_MANIFEST_TEMPLATE…
    ├── timelog/                  # SESxxx_<ts>.cortex — bloques de actividad
    └── packages/

<workspace>/<proyecto>/.arqux/
    ├── brain.cortex              # memoria gobernada del proyecto
    ├── issues/                   # issues del proyecto
    └── cycles/
        └── CYCLE-NN/
            ├── MANIFEST.md       # documento rector del ciclo
            ├── cycle.cortex
            └── blueprints/
                └── BLP-NNN.md    # documento de decisión de 18 secciones
```

---

## 6. Referencias

- [`README.md`](README.md) — puerta del producto
- [`HANDLERS.md`](HANDLERS.md) — los 115 handlers con firma y permiso
- [`PERMISSIONS.md`](PERMISSIONS.md) — permiso por handler, generado del registro
- [`THREAT_MODEL.md`](THREAT_MODEL.md) — modelo de amenazas
- [`EVIDENCE.md`](EVIDENCE.md) — modelo de evidencia
- [`docs/es/explicacion/frontera-codec.md`](docs/es/explicacion/frontera-codec.md) — la frontera codec-cortex
- [`docs/es/referencia/configuracion.md`](docs/es/referencia/configuracion.md) — env vars y rutas

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="./docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
