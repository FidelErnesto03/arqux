---
doc_type: explanation
status: informative
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
<p align="center"><sub>Explicación · Informativo · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# Casos límite del sistema

Cinco escenarios donde el comportamiento "correcto" no es obvio. Cada caso declara el comportamiento esperado, el real implementado, y el test que lo fija — el test es la promesa, el doc es la explicación.

## 1. Acceso concurrente al mismo archivo `.cortex`

**Escenario:** dos procesos escriben el mismo `.cortex` a la vez.

- **Esperado:** el locking evita corrupción; el segundo writer espera o falla limpio; cero pérdida.
- **Real:** `security.py` implementa locking vía `fcntl.flock()`; `secure_write_cortex()` adquiere lock exclusivo antes de escribir; sin lock, la operación falla con error claro.
- **Test:** `tests/test_security.py::test_secure_write_cortex`

## 2. `brain.cortex` vacío

**Escenario:** workspace inicializado con brain sin entradas o sin secciones.

- **Esperado:** `sync_brain()` crea las entradas por defecto (IDN, FCS, OBJ, WRK, DOM:arqux) sin crash; el brain queda usable.
- **Real:** `_build_brain_doc()` genera la plantilla completa con todas las secciones requeridas; `_sync_meta_brain()` puebla el meta-brain con `DOM:arqux`; un brain existente pero vacío es sobrescrito con la plantilla por el sync.
- **Test:** `tests/test_sync_brain.py::test_sync_brain_updates_wrk`

## 3. Sintaxis `.cortex` inválida

**Escenario:** archivo con entradas malformadas, secciones ausentes, sigils inválidos.

- **Esperado:** `cortex.verify()` detecta y reporta; las entradas inválidas se marcan sin tumbar el parser; las partes válidas siguen legibles.
- **Real:** el parser CODEC-CORTEX valida sintaxis estrictamente y devuelve lista estructurada de errores con números de línea; `cortex.verify` devuelve el reporte de verificación.
- **Test:** `tests/test_security.py::test_verify_cortex_missing_header_strict`

## 4. Handler inexistente

**Escenario:** la CLI intenta invocar un handler que no está en el REGISTRY.

- **Esperado:** error "unknown handler" + lista de disponibles; sin crash.
- **Real:** `cli.py` verifica REGISTRY antes del dispatch; el error incluye el nombre y los handlers disponibles; `cmd_call` imprime el error y sale limpio.
- **Test:** `tests/test_cli.py::test_call_unknown_handler`

## 5. Archivo de identidad ausente

**Escenario:** un handler lee un archivo de identidad (`identities/<id>.cortex`) que no existe.

- **Esperado:** `OUT-ERROR code=NOT_FOUND` con mensaje descriptivo; sin excepción sin manejar; el sistema sigue operando.
- **Real:** `cortex.entry.get()` devuelve NOT_FOUND; los handlers que dependen de la identidad propagan el NOT_FOUND; el error se loguea sin crashear el proceso.
- **Test:** `tests/test_learn_trigger.py::test_learn_auto_trigger_on_record`

> Los cinco casos compiten por el mismo principio: **el sistema reporta, no crashea** — cada frontera (disco, formato, registro, identidad) tiene un punto donde el fallo se convierte en diagnóstico en vez de excepción.

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="../../../docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
