---
doc_type: reference
status: normative
version: 1.0.0
verified: 2026-11-15
---

<!-- DOC-BRAND -->
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../../docs/assets/brand/arqux-logo-primary-dark.svg">
    <img alt="ArqUX" src="../../docs/assets/brand/arqux-logo-primary-light.svg" width="240">
  </picture>
</p>
<p align="center"><sub>Referencia · Normativo · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# Documentación de ArqUX — Español

Esta es la puerta única a la biblioteca en español. Si un documento no aparece aquí, no existe para el lector.

**Español es la lengua de origen.** `docs/en/` aloja el **espejo completo** del corpus ES — misma ruta y nombre de archivo. `docs/es/especificacion/` (especificación normativa) es el corpus canónico en español — es la fuente, no traducción. Regla: el nombre de archivo y directorio siempre coincide con el idioma del contenido.

## Contrato de front-matter

Todo documento público abre con un bloque YAML de cuatro campos:

```yaml
---
doc_type: canon | tutorial | guide | reference | explanation | report
status:   normative | informative | historical
version:  1.0.0        # semver del producto que describe
verified: 2026-11-15   # fecha ISO del último check contra el código
---
```

- `doc_type`: un solo tipo por documento. Si no encaja, el documento se divide — no se mezclan tipos.
- `status`: `normative` obliga, `informative` describe, `historical` archiva sin vigencia.
- `verified`: un documento sin verificación reciente probablemente miente.

## Taxonomía de carpetas

| Carpeta | doc_type | Función |
|---|---|---|
| `docs/es/tutorial/` | tutorial | Aprender haciendo — recorridos completos verificados |
| `docs/es/guias/` | guide | How-to por actor y tarea concreta |
| `docs/es/referencia/` | reference | Consulta exacta — CLI, errores, configuración, formatos |
| `docs/es/explicacion/` | explanation | El por qué — arquitectura, fronteras, casos límite |
| `docs/es/especificacion/` | canon | Canon CORTEX normativo — corpus ES de origen (no traducción) |
| `docs/en/` | según documento | **Espejo EN** del canon ES — misma ruta y nombre de archivo |
| `docs/es/especificacion/` | canon | **Especificación normativa** — corpus ES de origen |
| Raíz del repo | según documento | Documentos de proyecto (README, ARCHITECTURE, SECURITY, …) |

## ¿Quién eres?

| Audiencia | Empieza por | Sigue con |
|---|---|---|
| Humano evaluando | `README.md` (raíz) | `docs/es/tutorial/` |
| Tech Lead auditando | `ARCHITECTURE.md`, `THREAT_MODEL.md` | `docs/es/guias/`, `EVIDENCE.md` |
| CISO / cumplimiento | `EVIDENCE.md`, `THREAT_MODEL.md` | `docs/es/guias/evidencia-y-cumplimiento.md`, `docs/es/referencia/` |
| Agente / integrador | `HANDLERS.md`, `docs/es/especificacion/` | `docs/es/explicacion/` |

## Inventario vivo

### Raíz del proyecto

| Documento | doc_type | Rol |
|---|---|---|
| `README.md` | reference | Puerta del producto — quick start |
| `ARCHITECTURE.md` | explanation | Arquitectura del sistema |
| `THREAT_MODEL.md` | canon | Modelo de amenazas |
| `EVIDENCE.md` | report | Qué evidencia produce ArqUX |
| `PERMISSIONS.md` | reference | Permisos por handler |
| `SECURITY.md` | reference | Canal de reporte de vulnerabilidades |
| `CONTRIBUTING.md` | guide | Cómo contribuir |
| `HANDLERS.md` | reference | Registro de handlers MCP |
| `CHANGELOG.md` | report | Historia de releases |
| `CODE_OF_CONDUCT.md` | guide | Normas de comunidad — Contributor Covenant 2.1 ES con canal de enforcement |
| `PILOT_MODE.md` | stub | Retirado en 1.0.0 — stub que redirige a `docs/es/guias/despliegue.md` |
| `AGENTS.md`, `AGENTS.lite.md`, `AGENTS.full.md` | canon | Contratos de gobernanza para agentes — kernel del framework, no documentación de usuario |

### `docs/` — biblioteca

| Documento | doc_type | Rol |
|---|---|---|
| `docs/README.md` | reference | Índice global de la biblioteca |
| `docs/es/README.md` | reference | Este documento — portal y contrato |
| `docs/es/tutorial/inicio-rapido.md` | tutorial | De cero a workspace gobernado + agente MCP en ~10 min — verificado end-to-end |
| `docs/en/` completo (35 docs + índice + `root/`) | espejo | Gemelo EN de todo el corpus ES — tutorial, guías, referencia, explicación, especificación y raíz |
| `docs/en/explanation/diagrams/` | — | Assets PlantUML/SVG de los documentos |
| `docs/es/especificacion/` (17 docs + índice) | canon | Especificación normativa del formato CORTEX — **ES, corpus de origen** |
| `docs/es/guias/evidencia-y-cumplimiento.md` | guide | Guía CISO — evidencia firmada end-to-end y verificación offline |
| `docs/es/guias/proyectar-agentes.md` | guide | Multi-harness — `sync-harnesses` + `drift-check`, la regla "regenera, no edites" |
| `docs/es/guias/auditar-trabajo.md` | guide | Ritual del Tech Lead — `review` → `cortex-verify` → `evidence.list` → decisión |
| `docs/es/guias/sincronizar-equipo.md` | guide | Journal autoritativo — `pull-policy` → `push-delta`, conflicto `ERR_CONFLICT_VERSION` resuelto |
| `docs/es/guias/arranque-agente.md` | guide | `arqux wake` — contexto de arranque por rol, integración bootstrap, medidas reales |
| `docs/es/guias/despliegue.md` | guide | Despliegue 1.0.0 — modos, env vars, hardening, journal compartido, perf medido (retira `PILOT_MODE.md`) |
| `docs/es/formato-documental.md` | canon | Formato documental oficial — cabecera/pie de marca generados, tokens del Brand Kit v1.0, excepciones |
| `docs/es/referencia/formatos.md` | reference | Spec de artefactos de producto — seal, bundle, journal, firma, HCORTEX |
| `docs/es/referencia/cli.md` | reference | Referencia CLI exhaustiva — toda la superficie `arqux`, flags, exit codes, ejemplos |
| `docs/es/referencia/errores.md` | reference | Catálogo del contrato de fallos — cada código con causa, recuperación y test |
| `docs/es/referencia/configuracion.md` | reference | Superficie configurable única — env vars, rutas, permisos, defaults, perfiles |

### Exclusiones declaradas

- `docs/es/explicacion/` completa (5 docs + índice); `docs/es/tutorial/` iniciado con `inicio-rapido.md`; especificacion/guias/referencia ya tienen contenido.
- Material interno (estrategia, auditorías operativas, roadmap, ADRs) vive fuera del repositorio en `ARQUX-internal/`. No se publica.

## Regla de contribución

Documento nuevo → elegir carpeta por `doc_type` → front-matter completo → **añadir línea a este índice** → el gate `test_docs_consistency` valida. Documento sin entrada en índice = gate rojo.

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="../../docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
