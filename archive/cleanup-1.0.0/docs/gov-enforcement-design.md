# Diseño: Priorización Inmutable de Gobernanza ARqUX

**Estado:** Borrador para revisión
**Fecha:** 2026-07-13
**Autor:** agente (sesión abierta)

## Problema

El estándar ARqUX (AGENTS.md) exige, antes de cualquier salida:
- `AXM:first_response` → dashboard del workspace en formato HCORTEX.
- `AXM:header` → cabecera `⬡ AGENT|PROJECT|SCOPE` en toda respuesta.
- `WK:detect_tier` + `handler.list(tier)` → bootstrap de descubrimiento de handlers.

En la práctica, un agente/modelo nuevo puede omitirlo por reflejo, porque su
prompt base ("sé conciso, saluda natural") compite con AGENTS.md y gana lo
genérico. La causa raíz no es falta de instrucción: es **depender de la
disciplina del modelo**.

## Principio rector

> Gobernanza = estructura, no voluntad.
> El estándar debe ser imposible de omitir, no solo recomendado.

El prompt es "advisory": cualquier agente puede ignorarlo. La priorización
debe moverse a una **capa determinística** que el agente no pueda saltar.

## Mecanismos de enforce (por robustez)

| # | Mecanismo | Capa | Naturaleza |
|---|-----------|------|------------|
| 1 | Gate de arranque obligatorio | Harness / script de sesión | Bloquea el primer turno hasta `arqux_session_bootstrap` |
| 2 | Hook pre-respuesta (opencode) | Harness | Rechaza salida que no cumpla `⬡ ...` + HCORTEX |
| 3 | Validación de schema en formatter | Wrapper de salida | Inyecta cabecera/dashboard; el agente entrega solo contenido |
| 4 | AGENTS.md inyectado antes del base prompt | Prompt | Respaldo advisory (no principal) |

### 1. Gate de arranque obligatorio
Script de inicio que ejecuta `arqux_session_bootstrap` y **no libera el primer
turno** hasta que exista dashboard + cabecera. Sin bootstrap → sin respuesta.

### 2. Hook pre-respuesta
Regla de opencode que valida cada salida contra el patrón `⬡ AGENT|PROJECT|SCOPE`
y un bloque HCORTEX. Si no cumple, el harness descarta/rechaza la salida.

### 3. Validación de schema en formatter
Ninguna respuesta se entrega en texto plano. Pasa por un wrapper que coloca
cabecera y dashboard automáticamente.

### 4. AGENTS.md como fuente inyectada
Inyectado antes del base prompt, pero tratado solo como respaldo (sigue siendo
advisory).

## Aplicabilidad

Los mecanismos 1–3 son **agnósticos al agente/modelo**: aplican a cualquiera
que corra en el harness, no solo al agente actual.

## Pendiente de decisión

- ¿Implementar hook pre-respuesta + gate de bootstrap ahora en este workspace?
- ¿Qué hacer si el harness no soporta hooks (fallback a formatter)?
