# arqux ci-check — Blueprint de abordaje futuro

> **Estado:** Pendiente para CYCLE-03
> **Dependencias:** BLP-007 (arqux doctor), BLP-010 (arqux status --dashboard)
> **Prioridad:** Media (posterior a implementacion de BLPs 003-012)

## Objetivo

Crear el comando `arqux ci-check` para ejecutar en GitHub Actions (y otros CI/CD) que verifique automaticamente la salud del gobierno ArqUX sin necesidad de un agente interactivo.

## Comportamiento esperado

```
$ arqux ci-check
┌─ CI Check Report ───────────────────────────────────────────┐
│                                                              │
│  Workspace: /workspace                                       │
│                                                              │
│  Checks:                                                     │
│  ✅ Todos los BLPs en estado blocked tienen escalamiento     │
│  ✅ Todos los BLPs en estado ready tienen ACs verificables   │
│  ✅ No hay ciclos abiertos sin BLPs asignados               │
│  ✅ arqux doctor: todos los checks pasan                    │
│  ✅ Cobertura de tests >= 70%                               │
│                                                              │
│  Resumen: 5/5 checks pasaron                                │
│                                                              │
│  Output JSON: ci-check-report.json                           │
└──────────────────────────────────────────────────────────────┘
```

## Output dual

El comando debe producir dos salidas:

### 1. Humano (stdout)
Tabla HCORTEX con colores, legible en terminal y en PR comments.

### 2. Maquina (archivo JSON)
```json
{
  "workspace": "/workspace",
  "timestamp": "2026-07-11T16:00:00Z",
  "checks": [
    {"name": "blocked_blps_escalated", "status": "pass", "detail": "0 blocked BLPs"},
    {"name": "ready_blps_have_acs", "status": "pass", "detail": "5 ready BLPs with ACs"},
    {"name": "open_cycles_assigned", "status": "pass", "detail": "1 active cycle"},
    {"name": "arqux_doctor", "status": "pass", "detail": "6/6 checks pass"},
    {"name": "test_coverage", "status": "pass", "detail": "71% >= 70%"}
  ],
  "summary": {"total": 5, "passed": 5, "failed": 0}
}
```

## Checks a implementar

| Check | Fuente | Dependencia |
|---|---|---|
| BLPs bloqueados sin escalar | `blueprint.list(status=blocked)` | Handler existente |
| BLPs ready sin ACs | `blueprint.list(status=ready)` + leer ACs | BLP-012 (fixture) |
| Ciclos abiertos sin asignacion | `cycle.list(status=open)` | Handler existente |
| Salud del workspace | `arqux doctor` (modo JSON) | BLP-007 |
| Cobertura de tests | `pytest --cov-fail-under=70` | BLP-002 |

## Como abordar

1. **BLP-007** debe implementar `arqux doctor` primero (diagnostico + --fix)
2. **BLP-010** debe implementar `arqux status --dashboard` (integracion de datos)
3. ci-check reusa la logica de ambos, agregando:
   - Output JSON para parsear en CI
   - Exit code no-cero si hay checks fallidos (para que CI falle)
   - Integracion con GitHub Actions (crear PR comment con resultados)
4. El comando debe poder ejecutarse sin agente (sin MCP, sin ARQUX_AGENT_ID)

## Notas arquitectonicas

- ci-check NO debe modificar estado — solo leer
- ci-check debe funcionar sin variables de entorno de agente
- El output JSON permite a GitHub Actions u otros CI parsear y decidir
- El flag `--format json` permite seleccionar output
- Por defecto: output humano (HCORTEX) + archivo JSON
