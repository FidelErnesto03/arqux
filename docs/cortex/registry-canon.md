# Canon — `learn-policies.cortex` (config del motor de aprendizaje)

**Estado:** canon vigente (ALFRED · CYCLE-16 · 2026-11-15, post-G-8,
auditado por Heimdall).
**Alcance:** `<project>/.arqux/learn-policies.cortex` — configuración
del motor. **Una por proyecto** (decisión del Arquitecto).

---

## 1. Qué es

**No es un registro ni memoria: es la configuración ejecutable del
motor de aprendizaje.** Reglas `POL` + umbrales `THR` + protecciones
`PRT`/`KNW` + gates `GTE`.

| Propiedad | Valor |
|---|---|
| Nivel | 2, `usage:"skill"` — documento de configuración ejecutable |
| Ubicación | `<project>/.arqux/` — por proyecto (15+ copias vivas) |
| Mutación | **sin handler gobernado hoy** — escritura por template en `project.init`/`workspace.init` (`handlers/project.py:66`, `workspace.py:101`); mutación posterior = deuda (gap G-5, no existe `learn.policy.*`) |

## 2. Layout real (7 secciones, verificado)

| # | Título | Contenido |
|---|---|---|
| $0 | glosario | `$0:format` + 7 contratos (`ARQX`, `IDN`, `THR`, `POL`, `PRT`, `GTE`, `KNW`) |
| $1 | `IDENTITY` | `IDN:learn_policies{name, version, target, status}` — **defecto de datos**: falta `ARQX:artifact` (el artefacto no porta ficha propia) |
| $2 | `SCORING` | `THR:golden_fibonacci` (secuencia de umbrales) |
| $3 | `PROTECTED TARGETS` | `PRT:critical_sigils` (protección por sigilo) |
| $4 | `CANDIDATE-DRIVEN LEARNING` | `POL:candidate_detection`, `POL:candidate_elevation`… |
| $5 | `POLICY-DRIVEN LEARNING` | `POL:from→to{action, lift_when}` + nota DSL del archivo |
| $6 | `GATES` | `GTE:default_mutation`, `GTE:critical_mutation` |
| $7 | `CONFIGURABLE THRESHOLDS` | `KNW:*` — cooling, feedback, protected_patterns |

## 3. Semántica operativa (verificada contra `plan_patch`)

- **Campos vivos** de `POL`: `from`, `to`, `action`.
- **Campos inertes** (documentación, no evaluados): `source`, `target`,
  `lift_when`, `requires`, `when >=` — `lift_when` tiene cero
  consumidores en `src/`; `requires:"admin_policy"` está **muerto por
  no-modelado**: `plan.py:94` hace `getattr(chosen, "requires")` pero
  `PolicyEntry` (algorithms/policy.py) no porta ese campo — el branch
  `admin_confirmed` es inalcanzable (la nota `$5` del propio archivo,
  "requires: is not modeled", es **correcta**).
- **DSL real**: `when:` admite solo `==, !=, in, not in, and, or, not`
  — `>=` y `|` no expresables (cualquier otro token → parse error
  fail-closed, conditions.py).
- **`POL:block_ses_to_lng`** (`$5`): bloqueo **ACTIVO e intencional**
  instalado 2026-11-15 — `aggregate_value()` produce boilerplate
  (`lesson:"closed"`); levantar solo al cerrarse el issue de
  agregación. No es "stale": es la compuerta que hoy protege `$8`.
- **Perillas inertes** (`$7`): cooling/feedback/protected_patterns
  parsean sin efecto en el camino de detección — reactivar
  (learning.md §6.6) o retirar. Pendiente Arquitecto.
- **Dualidad de protección**: `PRT` protege por sigilo (`$3`);
  `KNW:protected_patterns` por patrón (`$7`) — hoy `plan_patch` usa
  `_PROTECTED_SIGILS` hardcodeado e ignora ambas (deuda G-5). La clave
  del PRT era `items:` (muerta — `policy.py:190` lee
  `sigils|targets|protected`); corregida a `sigils:` en el archivo de
  ARQUX (CYCLE-16) — sigue sin consumidor hasta G-5.

## 4. Nota de consolidación (G-8)

Los **registros de estado** del workspace ya no son archivos — viven
como secciones del meta-brain (`meta-brain-canon.md`):

| Ex-archivo | Destino |
|---|---|
| `agents.cortex` | meta-brain `$10 REGISTRY` (`IDN:*`) |
| `projects.cortex` | meta-brain `$10 REGISTRY` (`DOM:*`) |
| `context.cortex` | meta-brain `$7 ACTIVE_CONTEXT` (`WRK:current`) |
| `learn-policies.cortex` (workspace) | eliminada — una por proyecto |

Regla: **un índice que el meta-brain ya porta no merece archivo
propio**.

## 5. Referencias

- `learning.md` — consumidor; §4 motor actual, §6 propuesta
- `meta-brain-canon.md` — `$10 REGISTRY`
- `migration.md` §1 — consolidación ejecutada
