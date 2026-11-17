---
doc_type: reference
status: normative
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
<p align="center"><sub>Referencia · Normativo · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# Modelo de permisos de ArqUX

> La tabla de §4 es **generada desde el registro vivo** (`python scripts/generate_permissions_md.py`). No se edita a mano: si el registro cambia, se regenera.

ArqUX controla quién puede invocar cada handler con dos ejes independientes:

1. **Rol del agente** — resuelto desde el contexto de sesión (`ARQUX_AGENT_ROLE` como fallback de transporte). `src/arqux/permissions.py`.
2. **Nivel de enforce de reglas de política** — `CODE | PROMPT | HUMAN` en `learn-policies.cortex`. `src/arqux/core/policy_engine.py`.

---

## 1. Roles

| Rol | Identidades | Acceso |
|---|---|---|
| **GOVERNOR** | `alfred` | Los 115 handlers. Único que puede ejecutar `GOVERNOR_ONLY` (`workspace.init`, `project.init`). |
| **EXECUTOR** | `jarvis` | Todo excepto `GOVERNOR_ONLY`. |
| **AUDITOR** | `heimdall`, `seshat` | Solo lectura. El modelo es **denylist**: puede llamar cualquier handler excepto `GOVERNOR_ONLY`, `MUTATING_HANDLERS`, y las invocaciones mutantes de `CONDITIONAL_MUTATING`. Previews y `dry_run` siguen permitidos. |

Ejemplo real: `heimdall` (AUDITOR) puede llamar `cortex.read`, `blueprint.read` y `session.resume` — es lectura — pero `blueprint.ac` devuelve `PERMISSION_DENIED` porque muta. Por eso en este proyecto Heimdall **audita y reporta** y el gobernador **firma** los criterios.

El mapeo identidad→rol vive en `permissions.py` (`alfred`→GOVERNOR, `jarvis`→EXECUTOR, `heimdall`/`seshat`→AUDITOR).

## 2. Verificación HMAC

Tres handlers exigen firma HMAC-SHA256 además del rol — prueban que quien invoca **es** quien dice ser:

- `identity.record` — cualquiera podría firmar una lección como otro agente
- `evidence.record` — la evidencia debe ser atribuible a un agente verificado
- `blueprint.re_delegate` — la redelegación es un acto de gobierno

La firma liga `agent_id | handler | timestamp | payload_hash` (anti-replay). Con `ARQUX_STRICT_SECURITY=1` se verifica siempre; sin ella, en modo legacy.

## 3. Niveles de enforce de política

Las reglas `RUL`/`POL`/`GTE`/`THR`/`KNW`/`PRT`/`IDN` en `learn-policies.cortex` **deben** declarar `enforce`; su ausencia produce `ERR_MISSING_ENFORCE_LEVEL` (REQ-10, fail-closed en reglas malformadas).

| Nivel | Ejecuta | Ejemplo real |
|---|---|---|
| `CODE` | El runtime como hook pre/post-escritura vía `evaluate_hooks()` | `RUL:no_secret_commit` — `check:"secret_pattern"` bloquea escrituras gobernadas que contienen claves API o private keys (`POLICY_BLOCK`). Check nativo en `policy_engine.py`. |
| `PROMPT` | Se renderiza en el contexto del agente (AGENTS.md / payload de `wake`) | Mecanismo implementado en `policy_engine.py`; **sin regla PROMPT desplegada en este workspace hoy** (verificado 2026-11-15). |
| `HUMAN` | Puerta humana explícita — el runtime la expone, nunca auto-aplica | `POL:candidate_elevation` — `requires:"user_confirmation"` para elevar candidatos a lecciones. |

## 4. Tabla de autorización — 115 handlers

`Rol mínimo` = el rol más bajo que puede invocar el handler. `EXECUTOR*` marca handlers de `CONDITIONAL_MUTATING`: el auditor solo es denegado cuando los flags listados son truthy (y `dry_run` falsy).

<!-- GENERATED:PERMISSIONS_TABLE — regenerar: python scripts/generate_permissions_md.py -->
<!-- 115 handlers — generado desde REGISTRY + permissions.py -->
| Handler | Rol mínimo | HMAC | Condición |
|---|---|---|---|
| `blueprint.ac` | EXECUTOR | no | muta — auditor denegado |
| `blueprint.block_for_architect` | EXECUTOR | no | muta — auditor denegado |
| `blueprint.cancel` | EXECUTOR | no | muta — auditor denegado |
| `blueprint.claim` | EXECUTOR | no | muta — auditor denegado |
| `blueprint.complete` | EXECUTOR | no | muta — auditor denegado |
| `blueprint.create` | EXECUTOR | no | muta — auditor denegado |
| `blueprint.execute` | EXECUTOR | no | muta — auditor denegado |
| `blueprint.fail` | EXECUTOR | no | muta — auditor denegado |
| `blueprint.frontmatter.update` | AUDITOR | no | lectura |
| `blueprint.list` | AUDITOR | no | lectura |
| `blueprint.re_delegate` | EXECUTOR | sí | muta — auditor denegado |
| `blueprint.read` | AUDITOR | no | lectura |
| `blueprint.ready` | EXECUTOR | no | muta — auditor denegado |
| `blueprint.synthesize` | EXECUTOR | no | muta — auditor denegado |
| `blueprint.task` | EXECUTOR | no | muta — auditor denegado |
| `blueprint.update` | EXECUTOR | no | muta — auditor denegado |
| `context.detect` | AUDITOR | no | lectura |
| `context.full` | AUDITOR | no | lectura |
| `cortex.checkpoint` | EXECUTOR | no | muta — auditor denegado |
| `cortex.corpus.list` | AUDITOR | no | lectura |
| `cortex.corpus.query` | AUDITOR | no | lectura |
| `cortex.entry.add` | EXECUTOR | no | muta — auditor denegado |
| `cortex.entry.delete` | EXECUTOR | no | muta — auditor denegado |
| `cortex.entry.get` | AUDITOR | no | lectura |
| `cortex.entry.list` | AUDITOR | no | lectura |
| `cortex.entry.move` | EXECUTOR | no | muta — auditor denegado |
| `cortex.entry.update` | EXECUTOR | no | muta — auditor denegado |
| `cortex.file.validate` | EXECUTOR* | no | auditor denegado si `fix` |
| `cortex.format` | AUDITOR | no | lectura |
| `cortex.gc` | EXECUTOR* | no | auditor denegado si `force` |
| `cortex.learn` | AUDITOR | no | lectura |
| `cortex.learn.elevate` | EXECUTOR* | no | auditor denegado si `apply` |
| `cortex.migrate` | EXECUTOR* | no | sin flag — muta siempre; dry_run/preview permiten lectura |
| `cortex.patch` | EXECUTOR* | no | sin flag — muta siempre; dry_run/preview permiten lectura |
| `cortex.read` | AUDITOR | no | lectura |
| `cortex.ref` | AUDITOR | no | lectura |
| `cortex.render` | AUDITOR | no | lectura |
| `cortex.render.diagram` | AUDITOR | no | lectura |
| `cortex.render.validate_file` | AUDITOR | no | lectura |
| `cortex.verify` | AUDITOR | no | lectura |
| `cortex.write` | EXECUTOR | no | muta — auditor denegado |
| `cycle.close` | EXECUTOR | no | muta — auditor denegado |
| `cycle.create` | EXECUTOR | no | muta — auditor denegado |
| `cycle.current` | AUDITOR | no | lectura |
| `cycle.list` | AUDITOR | no | lectura |
| `cycle.reopen` | AUDITOR | no | lectura |
| `cycle.synthesize` | EXECUTOR | no | muta — auditor denegado |
| `evidence.list` | AUDITOR | no | lectura |
| `evidence.read` | AUDITOR | no | lectura |
| `evidence.record` | EXECUTOR | sí | muta — auditor denegado |
| `handler.how_to` | AUDITOR | no | lectura |
| `handler.list` | AUDITOR | no | lectura |
| `identity.elevate` | EXECUTOR* | no | auditor denegado si `apply` |
| `identity.get` | AUDITOR | no | lectura |
| `identity.record` | EXECUTOR | sí | muta — auditor denegado |
| `identity.switch` | EXECUTOR | no | muta — auditor denegado |
| `issue.create` | EXECUTOR | no | muta — auditor denegado |
| `issue.list` | AUDITOR | no | lectura |
| `issue.read` | AUDITOR | no | lectura |
| `issue.update` | EXECUTOR | no | muta — auditor denegado |
| `loop.activate` | AUDITOR | no | lectura |
| `loop.advance` | AUDITOR | no | lectura |
| `loop.complete` | AUDITOR | no | lectura |
| `loop.deactivate` | AUDITOR | no | lectura |
| `loop.list` | AUDITOR | no | lectura |
| `loop.register` | AUDITOR | no | lectura |
| `loop.remove` | AUDITOR | no | lectura |
| `loop.suggest` | AUDITOR | no | lectura |
| `loop.wake` | AUDITOR | no | lectura |
| `project.bind` | EXECUTOR | no | muta — auditor denegado |
| `project.init` | GOVERNOR | no | solo gobernador |
| `project.lessons` | AUDITOR | no | lectura |
| `project.status` | AUDITOR | no | lectura |
| `project.unbind` | EXECUTOR | no | muta — auditor denegado |
| `protocol.adopt` | EXECUTOR | no | muta — auditor denegado |
| `protocol.onboard` | EXECUTOR | no | muta — auditor denegado |
| `protocol.pause` | EXECUTOR | no | muta — auditor denegado |
| `protocol.release` | EXECUTOR | no | muta — auditor denegado |
| `protocol.resume` | EXECUTOR | no | muta — auditor denegado |
| `session.bootstrap` | EXECUTOR | no | muta — auditor denegado |
| `session.close` | EXECUTOR | no | muta — auditor denegado |
| `session.context.get` | AUDITOR | no | lectura |
| `session.context.set` | EXECUTOR | no | muta — auditor denegado |
| `session.handoff` | EXECUTOR | no | muta — auditor denegado |
| `session.pulse.compact` | EXECUTOR | no | muta — auditor denegado |
| `session.pulse.gc` | EXECUTOR* | no | sin flag — muta siempre; dry_run/preview permiten lectura |
| `session.resume` | AUDITOR | no | lectura |
| `session.status` | AUDITOR | no | lectura |
| `setup.plantuml` | EXECUTOR | no | muta — auditor denegado |
| `skill.convert` | EXECUTOR | no | muta — auditor denegado |
| `skill.edit` | EXECUTOR* | no | auditor denegado si `content` |
| `skill.evolve` | EXECUTOR* | no | auditor denegado si `apply` |
| `skill.get` | AUDITOR | no | lectura |
| `skill.import` | EXECUTOR | no | muta — auditor denegado |
| `skill.install` | EXECUTOR | no | muta — auditor denegado |
| `skill.list` | AUDITOR | no | lectura |
| `skill.record` | EXECUTOR | no | muta — auditor denegado |
| `sync.reconcile` | EXECUTOR | no | muta — auditor denegado |
| `sync.run` | EXECUTOR | no | muta — auditor denegado |
| `task.claim` | EXECUTOR | no | muta — auditor denegado |
| `task.complete` | EXECUTOR | no | muta — auditor denegado |
| `task.create` | EXECUTOR | no | muta — auditor denegado |
| `task.fail` | EXECUTOR | no | muta — auditor denegado |
| `task.list` | AUDITOR | no | lectura |
| `task.read` | AUDITOR | no | lectura |
| `task.run` | EXECUTOR | no | muta — auditor denegado |
| `task.update` | EXECUTOR | no | muta — auditor denegado |
| `timelog.project` | EXECUTOR* | no | auditor denegado si `action!=preview` |
| `timelog.purge` | EXECUTOR* | no | auditor denegado si salvo `preview` |
| `timelog.query` | AUDITOR | no | lectura |
| `timelog.review` | EXECUTOR | no | muta — auditor denegado |
| `timelog.summary` | AUDITOR | no | lectura |
| `workspace.init` | GOVERNOR | no | solo gobernador |
| `workspace.lessons` | AUDITOR | no | lectura |
| `workspace.status` | AUDITOR | no | lectura |
<!-- /GENERATED:PERMISSIONS_TABLE -->

## 5. Denegación y elevación

| Situación | Resultado | Referencia |
|---|---|---|
| Auditor invoca handler mutante | `PERMISSION_DENIED` (el servidor traduce `PermissionDenied` → error MCP/CLI; tratar como 403) | `docs/es/referencia/errores.md` |
| Regla `enforce:CODE` con `action:"deny"` dispara | `POLICY_BLOCK` — leer la regla que bloqueó (`pull-policy`), corregir el contenido | `core/policy_engine.py` |
| Handler `HMAC_REQUIRED` sin firma válida | `PERMISSION_DENIED` / firma inválida | `security.py` |
| El rol actual no alcanza | Pedir elevación: `identity.elevate` (condicional, flag `apply`) o invocar `arqux elevate` — escala a puerta HUMAN | `cli.py` |

Modo legacy: sin `ARQUX_STRICT_ROLES=1` el chequeo de rol es laxo (bypass governor histórico). **Nunca usar el modo laxo para esquivar una denegación** — la denegación es una señal de diseño.

## 6. Variables de entorno

Las que gobiernan autorización (definidas en `constants.py` / `permissions.py`):

| Variable | Efecto |
|---|---|
| `ARQUX_AGENT_ID` | Identidad del transporte (fallback; el contexto de sesión manda) |
| `ARQUX_AGENT_ROLE` | Rol del agente: `GOVERNOR`/`EXECUTOR`/`AUDITOR` (default GOVERNOR) |
| `ARQUX_AGENT_SECRET` | Secreto HMAC del agente |
| `ARQUX_AGENT_SIGNATURE` / `ARQUX_AGENT_TIMESTAMP` | Firma HMAC precomputed + timestamp |
| `ARQUX_EXECUTION_KEY` | Clave para ejecución estricta |
| `ARQUX_STRICT_ROLES=1` | Fuerza chequeo de rol (sin ella: bypass legacy) |
| `ARQUX_STRICT_SECURITY=1` | Fuerza verificación HMAC en `HMAC_REQUIRED` |
| `ARQUX_STRICT_EXECUTION=1` | Fuerza clave de ejecución |
| `ARQUX_ALLOW_IMPLICIT_EXECUTION` | Permite ejecución implícita |
| `ARQUX_SUSPENDED` | Suspende operación gobernada |
| `ARQUX_ENV_PREFIX` | Prefijo alternativo para todas las vars |
| `ARQUX_METADATA` | Metadatos de la sesión/agente |

Familias adicionales (no de autorización, listadas por completitud): `ARQUX_DIR`, `ARQUX_VERSION`, `ARQUX_FORMAT_DECL`, `ARQUX_GLOSSARY_TEXT`, `ARQUX_META_*` (SIGIL/SECTION/TITLE/ENTRY/PRIORITY), `ARQUX_HOST_BRIDGE_SOCKET`, `ARQUX_COMMS_*` (TELEGRAM_TOKEN, ALLOWLIST, EGRESS), `ARQUX_VOICE_*`. Inventario completo: `docs/es/referencia/configuracion.md`.

## 7. Cómo regenerar la tabla

```bash
python scripts/generate_permissions_md.py
```

El script importa `arqux.handlers.REGISTRY` y los conjuntos de `arqux.permissions` (`GOVERNOR_ONLY`, `MUTATING_HANDLERS`, `CONDITIONAL_MUTATING`, `HMAC_REQUIRED`) y emite las 115 filas en orden determinista. Si el conteo difiere de `handler.list`, la tabla está obsoleta — regenerar, nunca parchear a mano.

## Referencias

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — capas y flujo handler→política→estado
- [`HANDLERS.md`](HANDLERS.md) — firma y descripción de cada handler
- [`THREAT_MODEL.md`](THREAT_MODEL.md) — por qué existe cada control
- `docs/es/referencia/errores.md` — códigos `PERMISSION_DENIED` / `POLICY_BLOCK`
- `docs/es/referencia/configuracion.md` — env vars completas

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="./docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
