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

# Configuración de ArqUX

Superficie configurable completa en un solo lugar: variables de entorno, rutas de archivos, permisos requeridos, defaults operativos y perfiles por escenario. Cada entrada cita dónde se consume en `src/` — el documento se audita con `grep`.

## Variables de entorno — núcleo

Variables que el código de `src/arqux` lee vía `os.environ`. El prefijo es configurable con `ARQUX_ENV_PREFIX` (las lecturas usan `{prefix}VAR`).

| Variable | Valores | Default | Efecto | Consumida por |
|---|---|---|---|---|
| `ARQUX_AGENT_ID` | texto | `anonymous` | Identidad del agente para firma HMAC y resolución de rol | `security.py`, `permissions.py` |
| `ARQUX_AGENT_SECRET` | secreto | vacío | Clave HMAC compartida — sin ella la autenticación falla cerrada (`IdentityVerificationError`) | `security.py` |
| `ARQUX_AGENT_ROLE` | `governor`/`auditor`/`executor` | `governor` | Rol aplicado en modo legacy (sin sesión); en estricto el rol viene de la sesión | `permissions.py` |
| `ARQUX_AGENT_SIGNATURE` | hex HMAC | — | Firma de la invocación en modo legacy | `permissions.py` |
| `ARQUX_AGENT_TIMESTAMP` | epoch | — | Timestamp firmado — fuera de ±300 s es rechazado | `permissions.py`, `security.py` |
| `ARQUX_PROJECT` | texto | — | Proyecto ligado a la credencial legacy | `permissions.py` |
| `ARQUX_STRICT_SECURITY` | `0`/`1` | `0` | Modo estricto de seguridad: enforcement completo de firma/rol | `security.py`, `permissions.py` |
| `ARQUX_STRICT_ROLES` | `0`/`1` | `0` | Denylist de handlers mutantes aplicada por rol (auditor → solo lectura) | `permissions.py` |
| `ARQUX_EXECUTION_KEY` | texto | — | Clave de ejecución que el transporte/host fija para correlación | `execution.py` |
| `ARQUX_STRICT_EXECUTION` | `0`/`1` | `0` | `1` deshabilita la clave implícita por proceso — exige clave explícita | `execution.py` |
| `ARQUX_ALLOW_IMPLICIT_EXECUTION` | `0`/`1` | `0` | `1` permite la clave implícita de proceso (fallback) | `execution.py` |
| `ARQUX_ENV_PREFIX` | texto | `ARQUX_` | Cambia el prefijo con que se leen todas las variables anteriores | `constants.py` |
| `ARQUX_SUSPENDED` | `0`/`1` | — | Suspende mutaciones vía protocol handlers (la setea/lee el propio handler) | `handlers/protocol.py` |
| `ARQUX_HOST_BRIDGE_SOCKET` | ruta | `$XDG_RUNTIME_DIR` | Socket del host bridge para transporte alterno | `host_bridge.py` |

### Variables de extensiones

**Comms** (`arqux[comms]` — fail-closed por diseño):

| Variable | Default | Efecto | Consumida por |
|---|---|---|---|
| `ARQUX_COMMS_EGRESS` | `off` | Gate de salida — sin `on` no hay egreso | módulo comms |
| `ARQUX_COMMS_ALLOWLIST` | vacío | Lista de destinos permitidos (vacía = todo bloqueado) | módulo comms |
| `ARQUX_COMMS_TELEGRAM_TOKEN` | — | Token del bot Telegram | módulo comms |

**Voice** (`arqux[voice]` — extra opcional). Los defaults viven en `src/arqux/voice/config.py`; requiere `numpy` y dependencias del extra — sin ellas `voice-doctor` falla con `ModuleNotFoundError`.

| Variable | Efecto |
|---|---|
| `ARQUX_VOICE_ENGINE` | Motor de voz seleccionado |
| `ARQUX_VOICE_MODELS` | Ruta/manifest de modelos |
| `ARQUX_VOICE_TTS` | Motor TTS |
| `ARQUX_VOICE_ENDPOINT` | Endpoint del servicio de voz |
| `ARQUX_VOICE_MIC` | Selector de entrada PipeWire (igual que `--mic`) |
| `ARQUX_VOICE_SINK` | Dispositivo de salida |
| `ARQUX_VOICE_MEETINGS` | Configuración de modo reuniones |
| `ARQUX_VOICE_DAEMON` | Flag de contexto daemon |
| `ARQUX_VOICE_DAEMON_LOG` / `ARQUX_VOICE_DAEMON_PID` / `ARQUX_VOICE_DAEMON_SOCKET` | Rutas del daemon (log, pidfile, socket) |
| `ARQUX_VOICE_AUTO_RECOVER` | Recuperación automática del daemon |
| `ARQUX_VOICE_CHUNK_MS` | Tamaño de chunk de audio (default `64` en config) |
| `ARQUX_VOICE_BARGE_GRACE_MS` / `ARQUX_VOICE_BARGE_MIN_FRAMES` / `ARQUX_VOICE_BARGE_MIN_RMS` | Umbrales de barge-in (grace, frames mínimos, RMS mínimo) |
| `ARQUX_VOICE_RSS_BUDGET_MB` | Presupuesto de memoria RSS |
| `ARQUX_VOICE_AGENT_ENDPOINT` / `ARQUX_VOICE_AGENT_MODEL` / `ARQUX_VOICE_AGENT_API_KEY` / `ARQUX_VOICE_AGENT_COMMAND` / `ARQUX_VOICE_AGENT_SYSTEM` / `ARQUX_VOICE_AGENT_TIMEOUT` / `ARQUX_VOICE_AGENT_BACKEND` | Configuración del backend de agente para el modo meet (`agent_backend.py`) |

### Variable solo de tests

`BENCHMARK_PUBLISH` aparece en `tests/` (publicación de benchmark), no en `src/` — no es configurable de producto; se documenta aquí para que el operador no la busque en runtime.

### Nombres que parecen variables pero son constantes internas

`ARQUX_VERSION`, `ARQUX_DIR`, `ARQUX_FORMAT_DECL`, `ARQUX_GLOSSARY_TEXT`, `ARQUX_METADATA`, `ARQUX_META_SECTION`, `ARQUX_META_TITLE`, `ARQUX_META_SIGIL`, `ARQUX_META_ENTRY`, `ARQUX_META_PRIORITY` — constantes Python en `constants.py`/`formats.py`. **No se configuran por entorno** — documentados para evitar confusión al grepear.

## Rutas del sistema de archivos

| Ruta | Contenido | Permisos | ¿Versionar? |
|---|---|---|---|
| `<proyecto>/.arqux/` | Gobernanza del proyecto | — | Sí (salvo excepciones abajo) |
| `.arqux/brain.cortex` | Brain nivel 3 — memoria gobernada | convencional | Sí |
| `.arqux/secrets/<agent>.key` | Clave HMAC por agente | **0600 obligatorio** — `security.py` lo exige | **Nunca** — secreto simétrico |
| `.arqux/keys/` | Keypairs Ed25519 (`seed:` + `public:`) | **0600** al crearse con `policy keygen` | `public:` compartible; `seed:` **nunca** |
| `.arqux/journal.cortex` | Journal de políticas autoritativo | convencional | Sí — es historial |
| `.arqux/timelog/SES*.cortex` | Timelogs por sesión | convencional | Sí — evidencia |
| `.arqux/handoffs/`, `cycles/`, `blueprints/` | Artefactos de ciclo | convencional | Sí |
| `<workspace>/.arqux/meta-brain.cortex` | Meta-brain del workspace | convencional | No — estado local del workspace |
| `<workspace>/.arqux/identities/*.cortex` | Contratos de identidad | convencional | No — viven en el workspace |
| `AGENTS.md` `CLAUDE.md` `GEMINI.md` `.opencode/instructions.md` | Proyecciones de gobernanza | generadas | Regeneradas por `sync-harnesses` — no editar a mano |
| `$XDG_RUNTIME_DIR/arqux-*` | Sockets de bridge/daemon | runtime | No |

## Defaults operativos (verificados en código)

| Parámetro | Valor | Ubicación |
|---|---|---|
| Ventana de skew HMAC | **300 s** (±5 min) | `security.py` — `MAX_CLOCK_SKEW_SECONDS` |
| Timeout de `fcntl.flock` | **10 s** | `concurrency.py` |
| `session-bridge --request-timeout` | **90.0 s** | `cli.py` |
| Permiso de `secrets/*.key` | **0600** exigido | `security.py` |
| Permiso de keypair Ed25519 | **0600** al keygen | `signing.py` — verificado en ejecución |

## Perfiles por escenario

| Perfil | Configuración mínima | Notas |
|---|---|---|
| Desarrollo local | Ninguna env var — modo laxo por defecto | Los roles son laxos sin `STRICT_ROLES`/`STRICT_SECURITY`; cómodo para iterar |
| Producción gobernada | `ARQUX_AGENT_ID` + `ARQUX_AGENT_SECRET` + `ARQUX_STRICT_SECURITY=1` + `ARQUX_STRICT_ROLES=1` + `secrets/` 0600 | Denylist de roles activa; auditor queda read-only (`PERMISSION_DENIED` verificado en vivo) |
| Air-gapped | Igual que producción; sin acceso a red | Todo el núcleo opera offline: init, MCP stdio, firmas Ed25519 puras (sin libs externas — `signing.py` es pure-python por diseño). Verificado: `uv run arqux init/status/validate/policy` funcionan sin conectividad. Extras voice/comms requieren sus dependencias pre-instaladas |
| CI | `ARQUX_AGENT_ID=ci` + secreto de pipeline | Los docs/`validate`/`doctor` son no-interactivos y usables en pipeline |

## Reglas de seguridad por ruta

- `secrets/` y `seed:` de keypairs → `.gitignore` obligatorio; el producto exige 0600 pero no impide el commit — la barrera es del operador.
- Campos `visibility:"private"` en timelogs → gate `EXPORT_BLOCKED` al exportar (ver `errores.md`).
- Las proyecciones de harness (AGENTS/CLAUDE/GEMINI) son de solo-lectura conceptual: `drift-check` marca edición manual como `DRIFT_DETECTED`.

## Referencias

- `docs/es/referencia/cli.md` — flags por comando (no repetidos aquí)
- `docs/es/referencia/errores.md` — códigos que estas rutas/variables producen al fallar
- `THREAT_MODEL.md` — justificación de cada control
- `docs/es/guias/evidencia-y-cumplimiento.md` — manejo de claves y bundles

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="../../../docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
