# ⬡ Auditoría Ejecutable de ArqUX

> **Modo:** `AUDITORÍA_EJECUTABLE_DETERMINISTA`
> **Identidad:** `HEIMDALL_ARQUX_AUDITOR`
> **Protocolo:** v1.0.0
> **Fecha de ejecución:** 2026-07-09 (UTC-3)

---

## 1. Identificación

| Campo | Valor |
|---|---|
| Proyecto | ArqUX |
| Repositorio | https://github.com/FidelErnesto03/arqux |
| Commit auditado | `44d4edebe04dde2ebe35713ed4ebd76cd419292b` |
| Branch | `master` |
| Último commit | `v0.4.0 — close 7 benchmark issues, apply security/concurrency/permissions patch` |
| Working tree | limpio (sin cambios sin confirmar) |
| Fecha | 2026-07-09 |
| Auditor | HEIMDALL_ARQUX_AUDITOR |
| Entorno | Linux x86_64, Python 3.12.13, pip 26.1.2, git 2.47.3 |
| Versión auditada | 0.4.0 |
| Autor del proyecto | Fidel Lozada / FidelErnesto03 |

### audit_input

```yaml
audit_input:
  project_name: "ArqUX"
  repository_url: "https://github.com/FidelErnesto03/arqux"
  repository_full_name: "FidelErnesto03/arqux"
  source_type: "REPOSITORY"
  retrieval_date: "2026-07-09"
  evaluation_scope: "TOTAL_EXECUTABLE_AUDIT"
  intended_use: "Evaluar ArqUX para adopción empresarial en modo piloto"
  enterprise_context: "Gobierno de agentes IA mediante identidades, contratos, Blueprints, memoria CORTEX, MCP handlers y evidencia verificable"
  external_validation_allowed: true
  destructive_actions_allowed: false
  protocol_version: "1.0.0"
  execution_status: "COMPLETED"
```

### environment

```yaml
environment:
  os: "Linux 5.10.134-013.8.3.kangaroo.al8.x86_64 x86_64 GNU/Linux"
  python_version: "3.12.13"
  pip_version: "26.1.2"
  git_version: "2.47.3"
  working_directory: "/home/z/my-project/arqux-audit/arqux"
```

---

## 2. Veredicto

**Decisión:** `NO_APTA_PARA_PILOTO`

**Score:** **50 / 100**

**Razón primaria:** Existen **5 bloqueadores P0** que impiden una adopción piloto controlada: (1) los tests de permisos afirman un modelo de "todos los roles tienen acceso total" que contradice la implementación declarada en `permissions.py`; (2) el paquete PyPI no incluye los 10 archivos de `skills/workflows/`; (3) 9 de 124 tests fallan en áreas críticas (permisos, blueprint, learn-trigger, protocol, rename); (4) un error silencioso `sync_brain: failed to sync meta-brain (NotFoundError $2/DOM:arqux)` aparece en cada `arqux init` / `project.init`; (5) la cobertura de `security.py` es solo del 20% con `cli.py` al 0%, lo que invalida cualquier afirmación de seguridad verificable.

### git

```yaml
git:
  commit_sha: "44d4edebe04dde2ebe35713ed4ebd76cd419292b"
  branch: "master"
  dirty: false
  latest_commit_message: "v0.4.0 — close 7 benchmark issues, apply security/concurrency/permissions patch"
```

### runtime

```yaml
runtime:
  import_ok: true
  cli_ok: true
  reported_version: "0.4.0"
  handler_count_runtime: 72
```

### version_consistency

```yaml
version_consistency:
  status: "VERIFICADO"
  values:
    pyproject: "0.4.0"
    constants: "0.4.0"
    init: "0.4.0"
    readme: "0.4.0"
    changelog_latest: "0.4.0 — 2026-07-08"
    cli: "0.4.0"
    import: "0.4.0"
```

---

## 3. Evidencia de instalación

| Check | Estado | Evidencia |
|---|---|---|
| Clone | ✅ OK | `git clone --depth 1` exitoso; commit `44d4ede` |
| Estructura base | ✅ OK | `README.md`, `pyproject.toml`, `LICENSE`, `CHANGELOG.md`, `src/arqux/`, `tests/` presentes |
| pip install -e ".[dev]" | ✅ OK | Instalación editable exitosa; `codec-cortex-0.4.3` resuelto desde PyPI |
| Import arqux | ✅ OK | `arqux.__version__ == "0.4.0"` |
| arqux --version | ✅ OK | `arqux 0.4.0` |
| Handlers CLI | ✅ OK | 72 handlers listados |
| PyPI install (venv limpio) | ✅ OK | `pip install arqux` exitoso; versión 0.4.0 |
| PyPI templates | ⚠️ PARCIAL | `templates/AGENTS.md`, `identities/*.cortex`, `skills/*.skill.md` incluidos; **`skills/workflows/*.md` NO incluidos** |

### Detalle de dependencias resueltas

```
arqux-0.4.0, codec-cortex-0.4.3, mcp-1.28.1, pydantic-2.13.4, click-8.4.2,
rich-15.0.0, pytest-9.1.1, pytest-asyncio-1.4.0, pytest-cov-7.1.0,
ruff-0.15.20, mypy-2.2.0
```

> **Nota:** El comentario en `pyproject.toml` líneas 32-34 advierte que `codec-cortex` podría no estar en PyPI y sugiere instalar desde GitHub. **Esto es innecesario**: `codec-cortex` v0.4.3 está publicado y se resuelve automáticamente. El comentario es pesimista y debería eliminarse.

---

## 4. Evidencia de inicialización

| Check | Estado | Evidencia |
|---|---|---|
| arqux init | ✅ OK | `OUT-MIN workspace=.../.arqux governor=anonymous workspace.init ok` |
| .arqux creado | ✅ OK | Directorio creado con subdirectorios `identities/`, `skills/`, `templates/`, `packages/`, `skills/originals/` |
| meta-brain.cortex | ✅ OK | Copiado desde template |
| projects.cortex | ✅ OK | Copiado desde template |
| identities copiadas | ✅ OK | 7 archivos: alfred, auditor, executor, governor, heimdall, jarvis, seshat |
| skills copiadas | ✅ OK | 6 archivos `*.skill.md` en `.arqux/skills/` |
| skills/workflows copiadas | ❌ FAIL | **Los 10 workflows NO fueron copiados** (gap de packaging) |
| templates copiadas | ✅ OK | 7 archivos en `.arqux/templates/` |
| AGENTS.md en .arqux/templates | ✅ OK | NO está en templates (correctamente movido al root) |
| Idempotencia | ✅ OK | Segundo `arqux init` devuelve exit=0 |
| No destructividad | ✅ OK | `LOCAL_CHANGE_MARKER` preservado tras re-init |
| Bug silencioso | ⚠️ WARN | `sync_brain: failed to sync meta-brain (NotFoundError $2/DOM:arqux)` en cada init (no fatal, swallowed) |
| Path anidado | ⚠️ WARN | `find_project_root` devuelve `…/.arqux/.arqux` (doble `.arqux`) |

---

## 5. Verificación de AGENTS.md

| Check | Estado | Evidencia |
|---|---|---|
| Template existe | ✅ OK | `src/arqux/templates/AGENTS.md` (7737 bytes) |
| Contiene `ARQUX GLOSSARY` | ✅ OK | 1 ocurrencia |
| Package data lo incluye | ✅ OK | `pyproject.toml` declara `templates/*.md` |
| workspace.init lo instala | ✅ OK | `<workspace>/AGENTS.md` creado |
| No queda en `.arqux/templates/` | ✅ OK | `test ! -f .arqux/templates/AGENTS.md` pasa |
| Hash template vs instalado | ✅ OK | `bb1ad4b47378eeb3ee0b9a8a34411b360405a67c1a07805453ab512f1c0f436c` (idénticos) |

**Veredicto:** `AGENTS_TEMPLATE_INSTALL_VERIFIED` ✅

---

## 6. Handlers

| Fuente | Conteo | Observación |
|---|---:|---|
| runtime `arqux handlers` | 72 | Lista determinística, ordenada alfabéticamente |
| `handler_count()` | 72 | Coincide con CLI |
| README badge | **71** | ⚠️ STALE — badge dice `MCP Handlers-71`, no actualizado tras v0.4.0 |
| CHANGELOG v0.4.0 | 72 | Documenta bump `71 → 72 (cycle.mature added)` |
| CHANGELOG v0.3.5 | 54 | Histórico: "54 MCP handlers across 11 modules" |
| Código fuente | 72 | `REGISTRY` en `src/arqux/handlers/__init__.py` |
| Tests de superficie | 0 | No existe test que valide el conteo total contra REGISTRY |

**Estado:** `INCONSISTENTE` ⚠️

### Clasificación por módulo

| Módulo | Handlers | Cubre |
|---|---:|---|
| blueprint | 18 | create, define, mature, ready, assign, claim, update, complete, fail, cancel, approve, re_delegate, block_for_architect, read, list, task, ac, gate |
| cortex | 13 | entry.add/delete/get/list/move/update, learn, learn.elevate, read, render, render.diagram, render.validate_file, verify, write |
| cycle | 5 | close, create, current, list, mature |
| evidence | 3 | list, read, record |
| identity | 1 | record |
| project | 5 | bind, init, lessons, status, unbind |
| protocol | 4 | adopt, pause, release, resume |
| session | 5 | close, context.get, context.set, resume, status |
| setup | 1 | plantuml |
| skill | 6 | convert, edit, evolve, import, list, record |
| task | 7 | claim, complete, create, fail, list, read, update |
| workspace | 3 | init, lessons, status |
| **Total** | **72** | — |

> El código fuente menciona un "24-handler governance budget" en `src/arqux/handlers/__init__.py:432` sin definir claramente cuáles son esos 24 handlers ni cómo se relacionan con el total de 72. Esto genera ambigüedad.

### Punto de mejora esperado

Crear `HANDLERS.md` generado automáticamente desde `REGISTRY` que liste los 72 handlers con su categoría (governance/utility), rol mínimo requerido, y si requieren HMAC.

---

## 7. Permisos y seguridad

| Check | Estado | Evidencia |
|---|---|---|
| `permissions.py` existe | ✅ OK | Define `READ_ONLY_PREFIXES`, `GOVERNOR_ONLY`, `EXECUTOR_ALLOWED`, `HMAC_REQUIRED` |
| `ARQUX_STRICT_ROLES=1` | ✅ OK | Variable de entorno documentada en docstring |
| `ARQUX_STRICT_SECURITY=1` | ✅ OK | Variable de entorno documentada |
| Auditor denegado en strict | ✅ OK | `PermissionDenied` al intentar `workspace.init` con `role=auditor` |
| Executor denegado en strict | ✅ OK | `PermissionDenied` al intentar `workspace.init` con `role=executor` (es GOVERNOR_ONLY) |
| Governor con acceso total | ✅ OK | Sin restricciones en `check()` |
| HMAC sign/verify funcional | ✅ OK | `sign_request` produce 64-char hex; `verify_request` valida correctamente con `.arqux/secrets/<agent>.key` |
| Tamper detection de firma | ✅ OK | Firma alterada → `IdentityVerificationError` |
| `require_hmac` sin verified | ⚠️ BUG | Lanza `AttributeError` en vez de `PermissionDenied` limpio |
| Tests de permisos coherentes | ❌ FAIL | `test_all_roles_can_call_any_handler` y `test_can_always_returns_true` **afirman modelo contrario** al declarado |
| `SECURITY.md` | ❌ MISSING | Vacío crítico para enterprise |
| `permissions.py.bak` en VCS | ⚠️ WARN | Backup del archivo antiguo (con docstring "All handlers are available to all roles") cometido en git |
| `CHANGELOG.md` línea 64 | ⚠️ WARN | "identity.record allowed for all roles" — pero v0.4.0 removió `identity.record` de `READ_ONLY_PREFIXES` (regresión no documentada) |

### Contradicción tests vs implementación (P0)

```python
# tests/test_permissions.py — docstring STALE
"""Tests for permission system — all roles have full access.
Arqux trusts agents to follow their identity's behavioral contract.
Roles guide WHAT an agent should do, not what it CAN do.
"""

def test_all_roles_can_call_any_handler() -> None:
    """Every role can access every handler — shared mind for all."""
    # AFIRMA: todos los roles pueden llamar cualquier handler
    # FALLA: permissions.py v0.4.0 RESTringe executor y auditor
```

vs.

```python
# src/arqux/permissions.py — implementación v0.4.0
# AUDITOR: read-only (READ_ONLY_PREFIXES)
# EXECUTOR: EXECUTOR_ALLOWED + READ_ONLY_PREFIXES (no GOVERNOR_ONLY)
# GOVERNOR: full access
# HMAC_REQUIRED: identity.record
```

**Esto es exactamente el escenario P0 descrito en la sección 12.3 del protocolo.**

### Pruebas mínimas esperadas (ausentes)

El protocolo exige pruebas equivalentes a:

```python
def test_auditor_cannot_mutate_in_strict_roles(): ...        # AUSENTE
def test_executor_cannot_call_governor_only_handler_in_strict_roles(): ...  # AUSENTE
def test_governor_can_call_governor_only_handler(): ...      # AUSENTE
def test_hmac_required_handlers_fail_without_signature_in_strict_security(): ...  # AUSENTE
def test_legacy_mode_is_explicitly_legacy_not_pilot(): ...   # AUSENTE
```

Ninguna existe. La superficie de permisos strict mode **no está validada por tests**.

---

## 8. Seguridad

| Check | Estado | Evidencia |
|---|---|---|
| `SECURITY.md` existe | ❌ MISSING | `security_policy: VACIO_CRITICO_FOR_ENTERPRISE` |
| `security.py` existe | ✅ OK | 248 statements |
| `generate_secret()` | ✅ OK | Produce secretos cryptográficamente seguros |
| `AgentIdentity` dataclass | ✅ OK | Carga desde `ARQUX_AGENT_ID` + `ARQUX_AGENT_SECRET` |
| `sign_request()` HMAC-SHA256 | ✅ OK | Devuelve 64-char hex |
| `verify_request()` con secret_store | ✅ OK | Valida correctamente con `.arqux/secrets/<agent>.key` |
| `verify_request()` sin secret_store | ❌ FAIL | Requiere path a directorio; no hay fallback a env var cuando `secret_store=None` (sí lo hay implícito vía `ARQUX_AGENT_SECRET`, pero la API no es obvia) |
| Tamper detection firma | ✅ OK | Firma alterada → `IdentityVerificationError` |
| Modo strict env vars | ✅ OK | `ARQUX_STRICT_SECURITY=1` + `ARQUX_STRICT_ROLES=1` funcionan |
| `arqux handlers` en strict | ✅ OK | Lista completa, sin warnings críticos |
| Handler mutante sin HMAC vía CLI | ⚠️ N/A | No hay CLI directo para invocar handlers mutantes (solo `arqux call`) |
| Cobertura `security.py` | ❌ CRÍTICO | **20%** (199 líneas sin cubrir) |
| Auto-signing al escribir `.cortex` | ❌ MISSING | `inject_hash_header` debe llamarse explícitamente |
| CLI para verificar integridad | ❌ MISSING | No existe `arqux verify` ni `arqux cortex verify` |

### Smoke test ejecutado

```python
secret = generate_secret()
agent = AgentIdentity(agent_id="jarvis", secret=secret)
payload = b'{"x":1}'
ts = int(time.time())
sig = sign_request(agent, "identity.record", payload, timestamp=ts)
# sig_len: 64
# verify_request con .arqux/secrets/jarvis.key: True
# verify_request con firma alterada: IdentityVerificationError ✅
```

---

## 9. Evidencia y auditabilidad

| Check | Estado | Evidencia |
|---|---|---|
| Handlers de evidencia | ✅ OK | `evidence.record`, `evidence.list`, `evidence.read` |
| Registra `actor` | ✅ OK | Campo `agent` (vía `ctx.agent_id`) |
| Registra `role` | ❌ MISSING | No se persiste el rol del agente en la entrada |
| Registra `timestamp` | ⚠️ IMPLÍCITO | No hay campo `ts` explícito; el event_id `E-0001` es secuencial, no temporal |
| Registra `task/blueprint` | ✅ OK | `task_id`, `cycle` |
| Registra `hash` del payload | ❌ MISSING | El payload se guarda como string plano |
| Detecta tamper a nivel archivo | ✅ OK | `verify_cortex()` con header `$INTEGRITY: sha256:<hex>` |
| Detecta tamper a nivel entrada | ❌ MISSING | Las entradas PULSE no tienen hash individual |
| CLI para verificar evidencia | ❌ MISSING | No existe `arqux verify-evidence` ni `arqux cortex verify` |
| Tamper test ejecutado | ✅ OK | Append detectado; content modification detectado |

### Ciclo de vida de evidencia verificado

```text
1. workspace.init            → /tmp/.../ws/.arqux creado
2. project.init              → project "audit-pilot" inicializado
3. cycle.create              → cycle "c1" creado
4. task.create               → task T-001 creado (status=draft)
5. evidence.record           → event_id=E-0001, storage=brain.pulse
6. evidence.list             → events=1 (from brain PULSE)
7. inject_hash_header        → # $INTEGRITY: sha256:13deea92f6bd...
8. verify_cortex (untampered) → OK
9. Append "# TAMPER_INJECTION" → verify_cortex → TamperError ✅ DETECTED
10. Modify "hello world" → "HACKED" → verify_cortex → TamperError ✅ DETECTED
```

**Estado:** `PARCIAL` — tamper detection a nivel archivo funciona, pero **no hay CLI**, **no hay auto-signing**, y **no hay hash por entrada**.

---

## 10. Tests

| Métrica | Valor |
|---|---|
| Comando | `pytest -q` |
| Exit code | 0 (pytest no falla por defecto con tests fallidos) |
| Pasados | 115 |
| Fallidos | **9** |
| Saltados | 0 |
| Duración | 11.05 s |
| Cobertura total | **53%** |
| Módulos con 0% cobertura | `cli.py`, `__main__.py`, `plantuml_server.py` |
| Módulos críticos con baja cobertura | `security.py` (20%), `concurrency.py` (17%), `plantuml.py` (27%), `formats.py` (47%), `handlers/blueprint.py` (50%), `handlers/cortex.py` (45%) |

### Tests fallidos (detalle)

| Test | Módulo | Razón |
|---|---|---|
| `test_all_roles_can_call_any_handler` | test_permissions.py | `PermissionDenied: executor cannot call workspace.init` (test stale, modelo evolucionó) |
| `test_can_always_returns_true` | test_permissions.py | `assert False is True` para `executor.can('workspace.init')` (test stale) |
| `test_blueprint_ac_failed_returns_learning_instruction` | test_blueprint_learning.py | Fallo en lógica de AC failed |
| `test_blueprint_ac_verified_returns_message` | test_blueprint_learning.py | Fallo en lógica de AC verified |
| `test_blueprint_approve_blocks_failed_acceptance_criteria` | test_blueprint_learning.py | `blueprint.approve` no bloquea con AC failed |
| `test_blueprint_approve_blocks_unverified_acceptance_criteria` | test_blueprint_learning.py | `blueprint.approve` no bloquea con AC unverified |
| `test_learn_auto_trigger_on_record` | test_learn_trigger.py | Auto-trigger de cortex.learn no se dispara |
| `test_protocol_release_clears_env_vars` | test_protocol.py | `protocol.release` no limpia `ARQUX_AGENT_ID`/`ARQUX_AGENT_ROLE` (state leak) |
| `test_rename_replaces_all_three_casings` | test_rename.py | Script `rename-product.py` no reemplaza title-case |

### Cobertura por módulo crítico

| Módulo | Stmts | Miss | Cover | Crítico |
|---|---:|---:|---:|---|
| `permissions.py` | 107 | 27 | 75% | ⚠️ líneas strict mode no cubiertas |
| `security.py` | 248 | 199 | **20%** | 🚨 CRÍTICO — HMAC, signing, encryption sin cubrir |
| `handlers/workspace.py` | 81 | 8 | 90% | ✅ |
| `handlers/blueprint.py` | 737 | 368 | 50% | ⚠️ transiciones críticas no cubiertas |
| `handlers/cortex.py` | 267 | 146 | 45% | ⚠️ |
| `handlers/evidence.py` | 41 | 6 | 85% | ✅ |
| `server.py` | 75 | 37 | 51% | ⚠️ |
| `cli.py` | 117 | 117 | **0%** | 🚨 CRÍTICO — CLI sin tests |
| `plantuml_server.py` | 163 | 163 | **0%** | 🚨 CRÍTICO |
| `state.py` | 479 | 172 | 64% | ⚠️ |

---

## 11. CI/CD y documentación

### CI/CD

| Check | Estado | Evidencia |
|---|---|---|
| Workflow de tests | ❌ MISSING | No existe `.github/workflows/ci.yml` ni equivalente |
| Workflow de release | ✅ OK | `.github/workflows/release.yml` publica a PyPI en tags `v*.*.*` |
| Multi-Python testing | ❌ MISSING | Solo Python 3.11 en release workflow (no en CI) |
| CI valida packaging | ❌ MISSING | |
| CI valida `arqux init` | ❌ MISSING | |
| CI valida AGENTS.md | ❌ MISSING | |
| CI valida handlers | ❌ MISSING | |
| CI valida permisos | ❌ MISSING | |

```yaml
ci_status: "VACIO_CRITICO_FOR_ENTERPRISE"
pilot_impact: "RIESGO_MEDIO"
```

### Documentación

| Documento | Estado | Tamaño | Obligatorio piloto |
|---|---|---:|---|
| `README.md` | ✅ OK | 11823 bytes | ✅ Sí |
| `LICENSE` | ✅ OK | 11343 bytes (Apache-2.0) | ✅ Sí |
| `CHANGELOG.md` | ✅ OK | 3157 bytes | ✅ Sí |
| `SECURITY.md` | ❌ MISSING | — | ✅ Sí |
| `HANDLERS.md` | ❌ MISSING | — | ✅ Sí |
| `PERMISSIONS.md` | ❌ MISSING | — | ✅ Sí |
| `PILOT_MODE.md` | ❌ MISSING | — | ✅ Sí |
| `ARCHITECTURE.md` | ❌ MISSING | — | Deseable |
| `EVIDENCE.md` | ❌ MISSING | — | Deseable |
| `THREAT_MODEL.md` | ❌ MISSING | — | Deseable |
| `CONTRIBUTING.md` | ❌ MISSING | — | Deseable |

**Documentos obligatorios para piloto presentes: 3/7**

### Anti-patrones en VCS

| Archivo | Estado |
|---|---|
| `src/arqux/permissions.py.bak` | ⚠️ Cometido en git |
| `src/arqux/sync.py.bak` | ⚠️ Cometido en git |
| `src/arqux/handlers/cycle.py.bak` | ⚠️ Cometido en git |
| `.arqux/brain.cortex.bak` | ⚠️ Cometido en git |
| `.arqux/brain.cortex.bak-019` | ⚠️ Cometido en git |
| `.arqux/meta-brain.cortex.bak-20260708-143232` | ⚠️ Cometido en git |
| `.arqux/audit-2026-07-06.md` | ⚠️ Estado de auditoría interna cometido |

Los archivos `.bak` no deben versionarse. Sugieren flujo de trabajo manual sin git history limpio. El directorio `.arqux/` raíz contiene estado de runtime que no debería estar en el repositorio.

---

## 12. Blueprint lifecycle

| Check | Estado | Evidencia |
|---|---|---|
| State machine declarada | ✅ OK | `VALID_TRANSITIONS` en `handlers/blueprint.py:70` |
| Estados soportados | ✅ OK | draft, defined, maturing, ready, in_progress, review, blocked, done, cancelled |
| Transiciones válidas | ✅ OK | Validadas en `assert_valid_transition` |
| Gates de calidad | ✅ OK | `blueprint.gate` valida antes de `blueprint.ready` |
| Aprobación auditor | ✅ OK | `blueprint.approve` previsto (pero AC check roto) |
| Re-delegación | ✅ OK | `blueprint.re_delegate` existe |
| Bloqueo | ✅ OK | `blueprint.block_for_architect` existe |
| Evidencia mínima para cerrar | ⚠️ PARCIAL | AC verification existe pero **4 tests fallan** |
| Role enforcement | ✅ OK | architect→ready, executor→claim, auditor→approve |
| Tests de transición | ⚠️ PARCIAL | `test_gate.py` (5 tests), pero `test_blueprint_learning.py` tiene 4/9 fallando |

```yaml
blueprint_lifecycle:
  state_machine_declared: true
  transition_tests_present: true
  evidence_required_for_close: false  # AC verification roto
  role_enforcement_present: true
  verdict: "INCOMPLETO"
```

---

## 13. Score

### Dimensiones (escala 0-5)

| Dimensión | Peso | Score | Ponderado |
|---|---:|---:|---:|
| installation_and_packaging | 0.15 | 3 | 0.45 |
| runtime_initialization | 0.15 | 3 | 0.45 |
| handlers_and_surface_consistency | 0.15 | 3 | 0.45 |
| permissions_and_security | 0.20 | 2 | 0.40 |
| evidence_and_auditability | 0.15 | 3 | 0.45 |
| tests_and_ci | 0.10 | 1 | 0.10 |
| documentation_for_pilot | 0.10 | 2 | 0.20 |
| **Total** | **1.00** | — | **2.50** |

### Score final

```
weighted_score = 2.50 * 20 = 50 / 100
```

### Justificación por dimensión

- **installation_and_packaging (3):** Instalación desde fuente y PyPI funciona, pero `skills/workflows/*.md` no se empaqueta. El comentario sobre `codec-cortex` es pesimista.
- **runtime_initialization (3):** `arqux init` funciona, AGENTS.md se instala correctamente, pero hay un bug silencioso `sync_brain` en cada init y un path anidado `.arqux/.arqux`.
- **handlers_and_surface_consistency (3):** Runtime y API coinciden en 72, CHANGELOG también, pero README badge está stale en 71 y no hay test de superficie.
- **permissions_and_security (2):** Implementación declarativa correcta, HMAC funciona, pero los tests **contradicen** el modelo, `security.py` tiene 20% de cobertura, no hay auto-signing ni CLI verify, y `SECURITY.md` falta.
- **evidence_and_auditability (3):** Tamper detection a nivel archivo funciona, pero no hay hash por entrada, no hay CLI verify, y la evidencia no registra rol ni timestamp explícito.
- **tests_and_ci (1):** 9/124 tests fallan en áreas críticas, cobertura total 53%, `security.py` al 20%, `cli.py` al 0%, y **no existe CI workflow de tests**.
- **documentation_for_pilot (2):** Solo 3/7 documentos obligatorios para piloto presentes.

---

## 14. Lista de mejoras P0/P1/P2

### P0 — Bloqueantes para piloto

| ID | Hallazgo | Acción |
|---|---|---|
| P0-1 | Tests `test_all_roles_can_call_any_handler` y `test_can_always_returns_true` afirman modelo de "todos los roles con acceso total", contradiciendo `permissions.py` v0.4.0 | Reescribir tests para validar el modelo declarado: governor=full, executor=limited, auditor=read-only, HMAC_REQUIRED handlers. Agregar tests faltantes listados en sección 12.4 del protocolo |
| P0-2 | `skills/workflows/*.md` (10 archivos) no están declarados en `[tool.setuptools.package-data]` ni se copian al workspace tras `arqux init` | Agregar `"skills/workflows/*.md"` a `package-data` en `pyproject.toml` y actualizar `handlers/workspace.py` para copiar el subdirectorio recursivamente |
| P0-3 | 9 tests fallan en áreas críticas: `test_blueprint_learning` (4), `test_learn_trigger` (1), `test_permissions` (2), `test_protocol` (1), `test_rename` (1) | Corregir implementación o tests según corresponda. Los tests de blueprint/learn-trigger probablemente revelan bugs reales en AC verification y auto-trigger |
| P0-4 | `sync_brain: failed to sync meta-brain (NotFoundError $2/DOM:arqux)` aparece en cada `arqux init` y `project.init` (swallowed pero indica inconsistencia template vs código) | El `meta-brain.cortex` template no contiene la entrada `DOM:arqux` esperada por `sync.py`. Sincronizar template con el selector esperado, o ajustar el selector |
| P0-5 | Cobertura de `security.py` es 20% (199/248 líneas sin cubrir); `cli.py` es 0% | Agregar tests unitarios para: `generate_secret`, `AgentIdentity`, `sign_request`, `verify_request` (casos válidos/inválidos/tampered), `hash_cortex`, `inject_hash_header`, `verify_cortex`, `save_agent_secret`, `require_hmac` strict mode, `sign_cortex`/`verify_cortex_signature`. Agregar tests CLI con `click.testing.CliRunner` |

### P1 — Requeridos antes de piloto serio

| ID | Hallazgo | Acción |
|---|---|---|
| P1-1 | `SECURITY.md` no existe | Crear con: política de soporte de versiones, canal privado para reportes (security@), SLA de respuesta, matriz de amenazas resumida, criterios de severidad |
| P1-2 | `HANDLERS.md` no existe | Generar automáticamente desde `REGISTRY` con script `scripts/gen_handlers_doc.py`. Listar: nombre, descripción, rol mínimo, HMAC requerido, categoría (governance/utility) |
| P1-3 | `PERMISSIONS.md` no existe | Documentar los 3 roles, READ_ONLY_PREFIXES, GOVERNOR_ONLY, EXECUTOR_ALLOWED, HMAC_REQUIRED, ARQUX_STRICT_ROLES, ARQUX_STRICT_SECURITY, comportamiento legacy |
| P1-4 | `PILOT_MODE.md` no existe | Documentar: configuración mínima, variables de entorno, limitaciones conocidas, criterios de salida del piloto, monitoreo requerido |
| P1-5 | No existe CI workflow de tests (solo `release.yml`) | Crear `.github/workflows/ci.yml` con: matrix Python 3.10/3.11/3.12, `pytest -q`, `pytest --cov=arqux --cov-fail-under=70`, `ruff check`, `mypy`, validación de `arqux init`, validación de AGENTS.md hash |
| P1-6 | No hay test de packaging | Agregar test que: `python -m build`, instale wheel en venv limpio, verifique `templates/AGENTS.md` y `skills/workflows/*.md` incluidos |
| P1-7 | No hay test de `arqux init` end-to-end | Agregar test que: ejecute `arqux init` en tmpdir, valide `AGENTS.md` en root, valide hash, valide no destructividad |
| P1-8 | README badge stale: dice 71 handlers, runtime es 72 | Actualizar badge a 72 o generar dinámicamente desde `handler_count()` |
| P1-9 | `find_project_root` devuelve path anidado `.arqux/.arqux` | Revisar lógica en `state.py:find_project_root`; probablemente busca `.arqux` dentro del path dado, que ya termina en `.arqux` |
| P1-10 | `require_hmac` lanza `AttributeError` en strict mode cuando `verified=False` | Reemplazar por `raise PermissionDenied(...)` limpio. Bug en `permissions.py` línea ~282 |
| P1-11 | `protocol.release` no limpia `ARQUX_AGENT_ID` y `ARQUX_AGENT_ROLE` (state leak entre sesiones) | Agregar `os.environ.pop(...)` en `handlers/protocol.py:release` |
| P1-12 | Archivos `.bak` cometidos en VCS (`permissions.py.bak`, `sync.py.bak`, `cycle.py.bak`, `brain.cortex.bak`, `brain.cortex.bak-019`, `meta-brain.cortex.bak-...`) | Eliminar del repo, agregar `*.bak` y `*.bak-*` a `.gitignore`. Limpiar `.arqux/` del repo raíz (es estado de runtime) |
| P1-13 | CHANGELOG línea 64 dice "identity.record allowed for all roles" pero v0.4.0 lo removió de READ_ONLY_PREFIXES | Actualizar CHANGELOG o documentar la regresión explícitamente |
| P1-14 | No hay CLI para verificar integridad de `.cortex` | Agregar `arqux cortex verify <path>` que ejecute `verify_cortex()` |
| P1-15 | No hay auto-signing al escribir `.cortex` | Hacer que `crud_create`/`crud_update` en `state.py` llamen automáticamente `inject_hash_header` antes de escribir |
| P1-16 | Código menciona "24-handler governance budget" sin aclarar | Documentar en `HANDLERS.md` qué handlers son governance vs utility |
| P1-17 | `verify_request` falla con `secret_store=None` si no hay `.arqux/secrets/` en cwd o padres | Documentar explícitamente el orden de resolución: `ARQUX_AGENT_SECRET` env var → `.arqux/secrets/<agent>.key` (walk-up) → `secret_store` arg |

### P2 — Mejoras de madurez empresarial

| ID | Hallazgo | Acción |
|---|---|---|
| P2-1 | Sin dashboard visual | Construir `arqux dashboard` (TUI con rich o web con FastAPI) mostrando: proyectos, ciclos activos, blueprints por estado, evidencia reciente |
| P2-2 | Sin integración SSO | Agregar SSO via OIDC (Google/Microsoft/Auth0) para identidades de agentes en entornos empresariales |
| P2-3 | Sin marketplace de skills | Construir `arqux skill install <name>` que descargue desde un registry central |
| P2-4 | Sin dashboard multi-proyecto | Extender `arqux status` para listar todos los proyectos en un workspace jerárquico |
| P2-5 | Sin métricas de operación | Agregar `arqux metrics` que reporte: handlers invocados por día, blueprints completados, tiempo medio de ciclo, evidence.record por agente |
| P2-6 | Sin reportes ejecutivos | Agregar `arqux report --weekly` que genere PDF con resumen de actividad, blockers, lecciones aprendidas |
| P2-7 | Evidencia no registra rol ni timestamp | Agregar `role` y `ts` (ISO 8601) a cada entrada PULSE |
| P2-8 | Sin hash por entrada de evidencia | Cada `evidence.record` debe computar `sha256(payload)` y guardarlo en el PULSE entry |
| P2-9 | `THREAT_MODEL.md` deseable | Crear con: superficie de ataque (CLI, MCP server, plantuml server), vectores (env var injection, secret_store traversal, replay attack), mitigaciones |
| P2-10 | `ARCHITECTURE.md` deseable | Diagrama de componentes, flujo de datos, capas (CLI/MCP/handlers/state/cortex) |
| P2-11 | `CONTRIBUTING.md` deseable | Guía de contribución: branch naming, commit format, PR template, code review checklist |
| P2-12 | Signature digital en `.cortex` (`sign_cortex` requiere `private_key_pem` y `signer` args) | Documentar el flujo end-to-end: quién genera keypair, dónde se guarda la private key, cómo se distribuye la public key, cómo se verifica |

---

## 15. Plan recomendado de remediación

### Fase 1 — Desbloqueo (1-2 semanas)

**Objetivo:** Eliminar los 5 P0 para alcanzar `APROBADA_CON_RESERVAS_PARA_PILOTO`.

1. **Sprint 1 — Tests de permisos (P0-1, P0-3 parcial):**
   - Reescribir `tests/test_permissions.py` con docstring actualizado
   - Implementar los 5 tests mínimos del protocolo sección 12.4
   - Deprecar `test_all_roles_can_call_any_handler` y `test_can_always_returns_true`

2. **Sprint 1 — Packaging (P0-2):**
   - Agregar `"skills/workflows/*.md"` a `package-data`
   - Actualizar `handlers/workspace.py: init_workspace` para copiar `skills/workflows/` recursivamente
   - Agregar test `tests/test_packaging.py` que valide `importlib.resources.files("arqux").joinpath("skills/workflows/w01-workspace-init.md").is_file()`

3. **Sprint 1 — sync_brain fix (P0-4):**
   - Auditar `src/arqux/templates/meta-brain.cortex` vs selectors en `sync.py`
   - Agregar entrada `DOM:arqux` al template o ajustar selector
   - Agregar test que falle si `sync_brain` emite el warning

4. **Sprint 2 — Cobertura de seguridad (P0-5):**
   - Agregar `tests/test_security_hmac.py` con 15+ tests cubriendo: sign/verify happy path, tampered payload, tampered timestamp, replay attack, expired timestamp (clock skew), missing secret, wrong agent_id, strict mode, secret file permissions
   - Agregar `tests/test_security_cortex.py` con 10+ tests cubriendo: hash_cortex, inject_hash_header, verify_cortex (válido, tampered append, tampered content, missing header, wrong hash format)
   - Agregar `tests/test_cli.py` con CliRunner cubriendo: --version, handlers, init, status, call

### Fase 2 — Pre-piloto (2-3 semanas)

**Objetivo:** Eliminar los 17 P1 para alcanzar `APROBADA_PARA_PILOTO`.

5. **Documentación obligatoria (P1-1, P1-2, P1-3, P1-4):**
   - `SECURITY.md`, `HANDLERS.md` (autogenerado), `PERMISSIONS.md`, `PILOT_MODE.md`

6. **CI/CD (P1-5, P1-6, P1-7):**
   - `.github/workflows/ci.yml` con matrix Python 3.10/3.11/3.12
   - Tests de packaging y `arqux init` en CI
   - Gate de cobertura `--cov-fail-under=70`

7. **Bugs de implementación (P1-9, P1-10, P1-11, P1-13):**
   - Fix `find_project_root` path nesting
   - Fix `require_hmac` AttributeError
   - Fix `protocol.release` env var leak
   - Documentar regresión de `identity.record`

8. **Higiene de VCS (P1-12):**
   - Eliminar todos los `.bak` del repo
   - Agregar `.gitignore` entries
   - Limpiar `.arqux/` del repo raíz (mover a `.gitkeep` solo con estructura)

9. **Integridad verificable (P1-14, P1-15):**
   - `arqux cortex verify <path>` CLI
   - Auto-signing en `crud_create`/`crud_update`

### Fase 3 — Piloto controlado (4-8 semanas)

**Objetivo:** Ejecutar piloto controlado con métricas y monitoreo.

10. Desplegar en entorno aislado con `ARQUX_STRICT_SECURITY=1 ARQUX_STRICT_ROLES=1`
11. Configurar `secrets/` con `save_agent_secret` para cada identidad
12. Habilitar auto-signing de `.cortex` y verificar `arqux cortex verify` pasa en cada commit
13. Recoger métricas semanalmente con `arqux metrics` (P2-5)
14. Review quincenal de `evidence.list` para auditar actividad

### Fase 4 — Madurez empresarial (continuo)

15. Implementar P2 por orden de prioridad: dashboard (P2-1), métricas (P2-5), threat model (P2-9), SSO (P2-2)
16. Marketplace de skills (P2-3) cuando la comunidad supere 10 contributors

---

## 16. JSON normalizado

```json
{
  "audit_metadata": {
    "protocol_version": "1.0.0",
    "audit_mode": "AUDITORÍA_EJECUTABLE_DETERMINISTA",
    "auditor_identity": "HEIMDALL_ARQUX_AUDITOR",
    "execution_date": "2026-07-09",
    "execution_status": "COMPLETED"
  },
  "project": {
    "name": "ArqUX",
    "repository_url": "https://github.com/FidelErnesto03/arqux",
    "commit_sha": "44d4edebe04dde2ebe35713ed4ebd76cd419292b",
    "branch": "master",
    "version": "0.4.0",
    "license": "Apache-2.0",
    "author": "FidelErnesto03"
  },
  "environment": {
    "os": "Linux x86_64",
    "python_version": "3.12.13",
    "pip_version": "26.1.2",
    "git_version": "2.47.3"
  },
  "installation": {
    "from_source_ok": true,
    "from_pypi_ok": true,
    "import_ok": true,
    "cli_ok": true,
    "reported_version": "0.4.0",
    "pypi_versions_available": ["0.3.0", "0.3.1", "0.3.2", "0.3.5", "0.4.0"],
    "pypi_templates_included": {
      "templates/AGENTS.md": true,
      "templates/learn-policies.cortex": true,
      "templates/meta-brain.cortex": true,
      "identities/jarvis.cortex": true,
      "skills/cortex.skill.md": true,
      "skills/workflows/w01-workspace-init.md": false
    }
  },
  "init": {
    "arqux_init_ok": true,
    "agents_md_installed": true,
    "agents_md_hash_match": true,
    "agents_md_hash": "bb1ad4b47378eeb3ee0b9a8a34411b360405a67c1a07805453ab512f1c0f436c",
    "non_destructive": true,
    "idempotent": true,
    "workflows_copied": false,
    "silent_sync_brain_error": true,
    "path_nesting_bug": true
  },
  "handlers": {
    "runtime_count": 72,
    "api_count": 72,
    "readme_badge_count": 71,
    "changelog_count": 72,
    "consistent": false,
    "by_module": {
      "blueprint": 18,
      "cortex": 13,
      "cycle": 5,
      "evidence": 3,
      "identity": 1,
      "project": 5,
      "protocol": 4,
      "session": 5,
      "setup": 1,
      "skill": 6,
      "task": 7,
      "workspace": 3
    }
  },
  "version_consistency": {
    "status": "VERIFICADO",
    "pyproject": "0.4.0",
    "constants": "0.4.0",
    "init": "0.4.0",
    "readme": "0.4.0",
    "changelog_latest": "0.4.0",
    "cli": "0.4.0",
    "import": "0.4.0"
  },
  "permissions": {
    "model_declared": true,
    "strict_mode_env_var": "ARQUX_STRICT_ROLES",
    "hmac_required_handlers": ["identity.record"],
    "tests_contradict_implementation": true,
    "failing_tests": [
      "test_all_roles_can_call_any_handler",
      "test_can_always_returns_true"
    ],
    "expected_tests_missing": [
      "test_auditor_cannot_mutate_in_strict_roles",
      "test_executor_cannot_call_governor_only_handler_in_strict_roles",
      "test_governor_can_call_governor_only_handler",
      "test_hmac_required_handlers_fail_without_signature_in_strict_security",
      "test_legacy_mode_is_explicitly_legacy_not_pilot"
    ],
    "require_hmac_attribute_error": true,
    "permissions_py_bak_committed": true
  },
  "security": {
    "security_md_exists": false,
    "security_py_exists": true,
    "hmac_sign_ok": true,
    "hmac_verify_ok": true,
    "tamper_detection_signature": true,
    "tamper_detection_cortex_file": true,
    "tamper_detection_per_entry": false,
    "auto_signing_on_write": false,
    "cli_verify_command": false,
    "coverage_pct": 20,
    "strict_security_env_var": "ARQUX_STRICT_SECURITY",
    "strict_security_works": true
  },
  "evidence": {
    "handlers": ["evidence.record", "evidence.list", "evidence.read"],
    "records_actor": true,
    "records_role": false,
    "records_timestamp": false,
    "records_task_blueprint": true,
    "records_payload_hash": false,
    "tamper_detection_file_level": true,
    "tamper_detection_entry_level": false,
    "cli_verify_evidence": false
  },
  "tests": {
    "total": 124,
    "passed": 115,
    "failed": 9,
    "skipped": 0,
    "duration_sec": 11.05,
    "coverage_total_pct": 53,
    "failing": [
      "test_blueprint_learning.py::test_blueprint_ac_failed_returns_learning_instruction",
      "test_blueprint_learning.py::test_blueprint_ac_verified_returns_message",
      "test_blueprint_learning.py::test_blueprint_approve_blocks_failed_acceptance_criteria",
      "test_blueprint_learning.py::test_blueprint_approve_blocks_unverified_acceptance_criteria",
      "test_learn_trigger.py::test_learn_auto_trigger_on_record",
      "test_permissions.py::test_all_roles_can_call_any_handler",
      "test_permissions.py::test_can_always_returns_true",
      "test_protocol.py::test_protocol_release_clears_env_vars",
      "test_rename.py::test_rename_replaces_all_three_casings"
    ],
    "critical_modules_low_coverage": {
      "security.py": 20,
      "cli.py": 0,
      "plantuml_server.py": 0,
      "concurrency.py": 17,
      "plantuml.py": 27
    }
  },
  "ci_cd": {
    "ci_workflow_exists": false,
    "release_workflow_exists": true,
    "multi_python_testing": false,
    "ci_validates_packaging": false,
    "ci_validates_init": false,
    "ci_validates_agents_md": false,
    "ci_validates_handlers": false,
    "ci_validates_permissions": false,
    "status": "VACIO_CRITICO_FOR_ENTERPRISE"
  },
  "documentation": {
    "present": ["README.md", "LICENSE", "CHANGELOG.md"],
    "missing_mandatory": ["SECURITY.md", "HANDLERS.md", "PERMISSIONS.md", "PILOT_MODE.md"],
    "missing_desirable": ["ARCHITECTURE.md", "EVIDENCE.md", "THREAT_MODEL.md", "CONTRIBUTING.md"],
    "mandatory_for_pilot_present_count": 3,
    "mandatory_for_pilot_required_count": 7
  },
  "blueprint_lifecycle": {
    "state_machine_declared": true,
    "transition_tests_present": true,
    "evidence_required_for_close": false,
    "role_enforcement_present": true,
    "verdict": "INCOMPLETO"
  },
  "vcs_hygiene": {
    "bak_files_committed": [
      "src/arqux/permissions.py.bak",
      "src/arqux/sync.py.bak",
      "src/arqux/handlers/cycle.py.bak",
      ".arqux/brain.cortex.bak",
      ".arqux/brain.cortex.bak-019",
      ".arqux/meta-brain.cortex.bak-20260708-143232"
    ],
    "runtime_state_committed": true
  },
  "score": {
    "weighted_score": 50,
    "max_score": 100,
    "dimensions": {
      "installation_and_packaging": {"score": 3, "weight": 0.15, "weighted": 0.45},
      "runtime_initialization": {"score": 3, "weight": 0.15, "weighted": 0.45},
      "handlers_and_surface_consistency": {"score": 3, "weight": 0.15, "weighted": 0.45},
      "permissions_and_security": {"score": 2, "weight": 0.20, "weighted": 0.40},
      "evidence_and_auditability": {"score": 3, "weight": 0.15, "weighted": 0.45},
      "tests_and_ci": {"score": 1, "weight": 0.10, "weighted": 0.10},
      "documentation_for_pilot": {"score": 2, "weight": 0.10, "weighted": 0.20}
    }
  },
  "verdict": {
    "decision": "NO_APTA_PARA_PILOTO",
    "reason": "5 P0 blockers: tests de permisos contradicen implementación, skills/workflows no empaquetado, 9 tests fallan en áreas críticas, sync_brain silencioso falla en cada init, security.py solo 20% cobertura",
    "p0_blockers_count": 5,
    "p1_risks_count": 17,
    "p2_improvements_count": 12
  },
  "improvements": {
    "P0": [
      "Tests de permisos contradicen implementación declarada",
      "skills/workflows/*.md no empaquetados en PyPI",
      "9 tests fallan en áreas críticas (permisos, blueprint, learn-trigger, protocol, rename)",
      "sync_brain: NotFoundError $2/DOM:arqux en cada arqux init (silencioso)",
      "Cobertura security.py 20%, cli.py 0% — seguridad no verificable"
    ],
    "P1": [
      "SECURITY.md, HANDLERS.md, PERMISSIONS.md, PILOT_MODE.md faltantes",
      "No existe CI workflow de tests",
      "No hay tests de packaging ni de arqux init",
      "README badge stale (71 vs 72)",
      "find_project_root devuelve path anidado .arqux/.arqux",
      "require_hmac lanza AttributeError en strict mode",
      "protocol.release no limpia env vars",
      "Archivos .bak cometidos en VCS",
      "CHANGELOG línea 64 contradictoria con v0.4.0",
      "No hay CLI para verificar integridad .cortex",
      "No hay auto-signing al escribir .cortex",
      "24-handler governance budget no documentado",
      "verify_request no documenta orden de resolución de secret_store",
      "Falta test de packaging",
      "Falta test de arqux init end-to-end",
      "Falta CONTRIBUTING.md, ARCHITECTURE.md, THREAT_MODEL.md, EVIDENCE.md",
      "Comentario pesimista sobre codec-cortex en pyproject.toml"
    ],
    "P2": [
      "Dashboard visual (TUI o web)",
      "Integración SSO (OIDC)",
      "Marketplace de skills",
      "Dashboard multi-proyecto",
      "Métricas de operación (arqux metrics)",
      "Reportes ejecutivos (arqux report --weekly)",
      "Evidencia debe registrar role y timestamp",
      "Hash por entrada de evidencia",
      "THREAT_MODEL.md con matriz de amenazas",
      "ARCHITECTURE.md con diagrama de componentes",
      "CONTRIBUTING.md con guía de contribución",
      "Documentar flujo sign_cortex/verify_cortex_signature end-to-end"
    ]
  }
}
```

---

## 17. Apéndice — Logs de ejecución

### Comandos ejecutados (resumen)

```bash
# Entorno
python --version          # Python 3.12.13
pip --version             # pip 25.1.1
git --version             # git version 2.47.3

# Clone
git clone --depth 1 https://github.com/FidelErnesto03/arqux.git
# HEAD: 44d4edebe04dde2ebe35713ed4ebd76cd419292b

# Instalación editable
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"   # exit 0

# Verificación
arqux --version           # arqux 0.4.0
arqux handlers | wc -l    # 72

# Inicialización
arqux init --path /tmp/tmp.VETtj9b4cq
# AGENTS.md instalado, hash bb1ad4b4... match

# Tests
pytest -q                 # 115 passed, 9 failed
pytest --cov=arqux        # 53% total

# PyPI
pip install arqux         # exit 0, v0.4.0

# Seguridad
python -c "from arqux.security import ..."
# sign_request OK, verify_request OK con .arqux/secrets/<agent>.key

# Tamper detection
sign_cortex + verify_cortex (untampered): OK
verify_cortex (append tampered): TamperError DETECTED
verify_cortex (content tampered): TamperError DETECTED
```

### Evidencia hash

```
src/arqux/templates/AGENTS.md sha256: bb1ad4b47378eeb3ee0b9a8a34411b360405a67c1a07805453ab512f1c0f436c
<workspace>/AGENTS.md        sha256: bb1ad4b47378eeb3ee0b9a8a34411b360405a67c1a07805453ab512f1c0f436c
brain.cortex (post init)     sha256: 13deea92f6bd4e9a3dac38d2812d9f5c6d1ac9266b8bc05f517e970eb3a28063
```
