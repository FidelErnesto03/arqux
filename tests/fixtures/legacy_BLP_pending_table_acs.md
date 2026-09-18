---
blueprint_id: "BLP-004"
title: "Legacy blueprint — pending status + table ACs (sanitized fixture)"
cycle: "CYCLE-01"
status: "pending"
governor: "alfred"
executor: "alfred"
created_at: "2026-09-13T16:00:00Z"
priority: "medium"
complexity: "standard"
test_status: "tested_in_ATUM"
test_result: "pass_with_fix_c01"
_template_ref: "BLP_TEMPLATE.md"
---

# BLP-004: Legacy format fixture (sanitized)

## §1: Planteamiento del Problema

Legacy BLP written by a pre-state-machine version. Status `pending` is not
part of the canonical lifecycle and ACs live in a markdown table in §11.

## §3: Precondiciones

- [ ] Precondición verificable de ejemplo

## §11: Criterios de Aceptacion

| AC | Descripcion | Verificacion | Estado |
|---|---|---|---|
| AC-01 | Trigger creado y ENABLED | query dba_triggers | pending |
| AC-02 | Job polling deshabilitado | query dba_scheduler_jobs | pending |
| AC-03 | Safety net creado y habilitado | query dba_scheduler_jobs | pending |
| AC-04 | Indice creado | query dba_indexes | pending |
| AC-05 | BD sigue OPEN | query v$instance | pending |
| AC-06 | Shared pool estable | query v$sgastat | pending |
| AC-07 | ORDS operativo | curl http_code=302 | pending |
| AC-08 | MCP operativo | tools list | pending |
| AC-09 | Test end-to-end | mensaje status<>0 | pending |
| AC-10 | Sin ORA-04031 1h | alert log | pending |
| AC-11 | Otros mensajes no afectados | log_collector | pending |
| AC-12 | Rollback disponible | script staged | pending |

## §12: Riesgos y Mitigaciones

- **R-08 (prc_register_worker_job)**: Si el cliente ejecuta el procedure, recreara el job polling.
- **R-09 (DBMS_JOB deprecado)**: Funciona en XE 21c pero esta deprecado.

## §13: Resultados de Test

| AC | Descripcion | Resultado | Nota |
|---|---|---|---|
| AC-01 | Trigger creado y ENABLED | PASS | Verificado Fase 2 |

## §14: Tareas

- [ ] **T-1.1:** Fase de creacion de objetos
- [ ] **T-1.2:** Fase de verificacion
