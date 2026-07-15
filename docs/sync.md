# Documentación del Módulo `arqux.sync`

## Ubicación

```
src/arqux/sync.py                  → Módulo principal
src/arqux/handlers/sync/__init__.py → Handler MCP: `sync.run`
src/arqux/handlers/sync.py         → Importador re-export (shim)
```

## Naturaleza

El módulo `sync` es **fail-silent**: nunca interrumpe el handler que lo llama.
Cualquier error es registrado con `logger.exception()` y absorbido.
Es el mecanismo que mantiene sincronizado `brain.cortex` tras cada mutación exitosa.

---

## Funciones Disponibles

### 1. `sync_brain()` — Función pública principal

**Ubicación:** `src/arqux/sync.py`, línea 20

**Firma:**
```python
def sync_brain(
    project_root: Path,
    event: str,
    *,
    focus: str | None = None,
    metrics: dict[str, Any] | None = None,
    detail: str = "",
) -> None
```

**Descripción:**
Actualiza `brain.cortex` tras una mutación exitosa de un handler. Modifica:

| Sección | Campo | Qué hace |
|---------|-------|----------|
| `$8/WRK:current` | phase, current, blocked, updated, event | Marca el estado actual del agente |
| `$2/FCS:current` | what, priority, status, updated, event | Solo si `focus` está provisto |
| `$6/KNW:*` | métricas | Solo si `metrics` está provisto |
| `$2/DOM:arqux` (meta-brain) | blueprints, tests, handlers, etc. | Solo si `metrics` está provisto |

**Parámetros:**
- `project_root` — Ruta al directorio del proyecto (o al `.arqux/` mismo; auto-detecta).
- `event` — Nombre canónico del evento: `"blueprint.approve"`, `"task.complete"`, `"cycle.create"`, etc.
- `focus` — *(opcional)* Valor para `FCS:current`. Solo para eventos mayores (approve, create, close).
- `metrics` — *(opcional)* `dict[str, Any]` de contadores a fusionar. Ej: `{"blueprints_done": 17}`.
- `detail` — *(opcional)* Texto legible sobre el evento.

**Comportamiento especial:**
- Si `project_root is None` → retorna silenciosamente.
- Si `brain.cortex` no existe en la ruta resuelta → retorna silenciosamente (normal en workspaces nuevos).
- Si `crud_update` no está disponible (importación fallida) → retorna silenciosamente.

---

### 2. `_update_metrics()` — Privada

**Ubicación:** `src/arqux/sync.py`, línea 120

**Firma:**
```python
def _update_metrics(
    brain_path: Path,
    metrics: dict[str, Any],
    ts: str,
) -> None
```

**Descripción:**
Fusiona los contadores de `metrics` en la sección `$6` de `brain.cortex` como entradas `KNW`.

- Si la clave es `"tasks_done"` → status `"done"`
- Si no → status `"current"`

Cada métrica se escribe con los campos: `name`, `value`, `updated`, `topic: "metrics"`, `content`, `status`.

---

### 3. `_count_blueprints()` — Privada

**Ubicación:** `src/arqux/sync.py`, línea 154

**Firma:**
```python
def _count_blueprints(root: Path) -> dict[str, int]
```

**Descripción:**
Cuenta los blueprints por estado escaneando `BLP-*.md` en `.arqux/cycles/` o `cycles/`.

**Valores de retorno (todos inicializados en 0):**
```python
{
    "done": 0, "draft": 0, "cancelled": 0,
    "review": 0, "in_progress": 0, "ready": 0, "blocked": 0,
}
```

El conteo se basa en la expresión regular `^status:\s*"([^"]+)"` sobre cada archivo.

---

### 4. `_count_tests()` — Privada

**Ubicación:** `src/arqux/sync.py`, línea 179

**Firma:**
```python
def _count_tests(root: Path) -> int
```

**Descripción:**
Cuenta archivos de test `*.py` en el directorio `tests/` del proyecto.

---

### 5. `_sync_meta_brain()` — Privada

**Ubicación:** `src/arqux/sync.py`, línea 191

**Firma:**
```python
def _sync_meta_brain(
    project_root: Path,
    metrics: dict[str, Any],
    event: str,
    ts: str,
) -> None
```

**Descripción:**
Sincroniza métricas y conteos al meta-brain (`meta-brain.cortex`, sección `$2/DOM:arqux`).

Campos escritos en DOM:arqux:
- `updated`, `last_event` (siempre)
- `blueprints_done`, `blueprints_draft`, `blueprints_cancelled`, `blueprints_completed` (contados del FS, fallback a valores de `metrics`)
- `tests` (conteo de archivos)
- `handlers`, `tasks_done`, `tasks_active`, `cycles_closed` (si están en `metrics`)

---

### 6. `sync_run_handler()` — Handler MCP `sync.run`

**Ubicación:** `src/arqux/handlers/sync/__init__.py`

**Firma:**
```python
def sync_run_handler(
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT
```

**Descripción:**
Handler MCP que permite sincronización manual de `brain.cortex` a meta-brain con métricas completas.

**Parámetros:**
- `path` — Ruta al proyecto (auto-detectada si omitida).

**Uso:**
```python
# Desde handler
from arqux.handlers.sync import sync_run_handler

# Llamada con path
result = sync_run_handler(path="/ruta/al/proyecto")

# Llamada sin path (auto-detecta)
result = sync_run_handler()
```

---

## Patrón de Uso en Handlers

Cada handler mutante llama a `sync_brain()` como **última línea antes del return**:

```python
# Ejemplo: task.create (task.py:129)
sync_brain(
    root,
    "task.create",
    metrics={"tasks_active": 1},
    detail=f"task {task_id} created in {cycle_id}",
)

# Ejemplo: blueprint.complete (review.py:79)
sync_brain(
    root,
    "blueprint.complete",
    focus="Verificar ACs y aprobar",
    metrics={"blueprints_completed": 1},
    detail=f"BLP {bp_id} completed",
)

# Ejemplo: cycle.close (cycle.py:588)
sync_brain(root, "cycle.close", focus="Ciclo cerrado",
           metrics={"cycles_closed": 1}, detail=f"cycle {cycle_id} closed")

# Ejemplo: skill.edit (skill.py:497)
sync_brain(arqux.parent, "skill.edit",
           detail=f"section ${section} of {name} written")

# Ejemplo: project.bind (project.py:284)
sync_brain(root, "project.bind", detail=f"agent {agent_id} bound as {role}")
```

---

## Convenciones de Importación

```python
# Desde handlers/ directo
from ..sync import sync_brain

# Desde handlers/blueprint/ (subpaquete anidado)
from ...sync import sync_brain

# Handler MCP manual
from ...sync import sync_brain  # en handlers/sync/__init__.py
```

---

## Handlers que Llaman a sync_brain

| Módulo | Evento(s) |
|--------|-----------|
| `blueprint.lifecycle` | `blueprint.create`, `blueprint.complete` |
| `blueprint.review` | `blueprint.complete`, `blueprint.approve`, `blueprint.fail` |
| `task` | `task.create`, `task.complete` |
| `cycle` | `cycle.create`, `cycle.close` |
| `skill` | `skill.edit` |
| `project` | `project.bind` |

> **Regra AXM:** Handlers de solo lectura (list, read, get, status, lessons) **NO** deben llamar a `sync_brain()`.
