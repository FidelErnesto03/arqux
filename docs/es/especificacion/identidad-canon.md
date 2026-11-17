---
doc_type: canon
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
<p align="center"><sub>Canon · Normativo · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# Canon — `identities/<agent>.cortex` (Nivel 1 / IDENTITY)

**Estado:** canon vigente (ALFRED · CYCLE-16 · 2026-11-15, auditado
por Heimdall).
**Alcance:** `<workspace>/.arqux/identities/*.cortex` — contrato
conductual de agente.

---

## 1. Qué es

El **contrato conductual** de un agente: quién es, qué axiomas rigen
su comportamiento, qué límites no cruza, cómo se describe. NO es
memoria: no acumula historia ni lecciones — solo contrato vigente.

| Propiedad | Valor |
|---|---|
| Nivel | 1 |
| Lectura | `identity.get` / `identity.switch` — **siempre por handler** |
| Mutación | el contrato se siembra por template (`workspace.init`/`protocol.adopt` registra solo en el registry, no en este archivo — `agents.cortex` retirado: el último residuo, con solo un `IDN:new-agent` fugado de un test sin `path`, fue archivado 2026-11-15) y muta por `identity.elevate` **supervisada** + Arquitecto. **No existe `protocol.register`** |

## 2. Layout canónico — dos variantes reales

| # | Título | Sigilos | Variante A (5/7) | Variante B (2/7: heimdall, seshat) |
|---|---|---|---|---|
| $0 | `GLOSSARY` | `$0:format` + `*_contract` | ✓ | ✓ |
| $1 | `IDENTITY` | `ARQX:artifact{level:1}` + `IDN:<agent>` | ✓ | ✓ |
| $2 | `AXIOMS` | `AXM:*` conductuales | ✓ | ✓ |
| $3 | `LIMITS` | `LIM:*` | ✓ | ✓ |
| $4 | `DESCRIPTION` | `DESC:*` | ✓ | — |
| $4 | `EXPERTISE` | `KNW:*` dominios | — | ✓ |
| $5 | `DESCRIPTION` | `DESC:*` | — | ✓ |

### $0 GLOSSARY

- **`$0:format` debe ser la primera línea** — 6/7 archivos emiten una
  declaración (`ARQX:arqx_contract`) **antes** del format (drift a
  homologar; la detección de dialecto lo exige temprano).
- **Nomenclatura `_contract` es la dominante** (6/7 archivos); el drift
  es `alfred.cortex` — usa forma corta (`ARQX:arqx`, `IDN:idn`,
  `AXM:axm`, `LIM:lim`, `DESC:desc`) para **todos** sus sigilos.
- Dos familias de glosario: "ARQUX **AGENT** IDENTITY GLOSSARY"
  (agentes nombrados: alfred, heimdall, jarvis, seshat) vs "ARQUX
  **ROLE** IDENTITY GLOSSARY" (roles: auditor, executor, governor —
  `IDN` sin `master`, `name` = rol).

### $1 IDENTITY

`ARQX:artifact{level:1, name, usage:"identity", kind:"native"}` como
primera entrada (regla transversal `formato.md`), seguida de
`IDN:<agent>{name, role/group, purpose, master?, version, status}`.
Heimdall porta además `edit:false` (atributo de permiso en el
descriptor).

### $2/$3 — conducta elevada

`AXM:*`/`LIM:*` — solo crece por **elevación desde el router**
(aprendizaje.md §6): conductual + transversal, siempre `propose` +
confirmación humana. Ejemplo real: `AXM:verify_post_write_state` con
`source_lesson` + `evidence_ref:"brain:$8/LNG:…"` (alfred:51).

### $4 EXPERTISE (variante B)

`KNW:*{name, topic, content, dominio, status}` — dominios de
experticia (security_vigilance, forensic_audit…). Nota: `dominio`
duplica `content` en heimdall/seshat — redundancia conocida.

### $4/$5 DESCRIPTION

`DESC:<agent|persona|role>{name, body}` — propósito en prosa; el
nombre varía (`persona` en alfred/jarvis, `role` en role-files).
`ROLE:*` declarado en versiones viejas del canon **no existe**.

## 3. Reglas

1. **Contrato, no almacén** — `BEHAVIORAL LESSONS` deprecado; las
   lecciones viven en brain `$8`.
2. **Lectura por handler siempre** — nunca lectura directa.
3. **Todo agente/subagente porta contrato** — inyectado al lanzar.
4. **Heimdall es read-only por contrato** — `LIM:no_mutation` +
   `AXM:read_only_by_default` + `edit:false`.
5. **La elevación exige humano** — ningún `AXM`/`LIM`/`KNW` se añade
   automáticamente.

## 4. Referencias

- `cerebro-canon.md` §3 — secciones del brain (origen de elevaciones)
- `aprendizaje.md` §2 — el router naturaleza×scope (+§6.4 modos)
- `artefactos.md` §2.2 — ficha nivel 1

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="../../../docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
