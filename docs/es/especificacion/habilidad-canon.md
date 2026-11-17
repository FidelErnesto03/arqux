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

# Canon — `skills/*.skill.md` (Nivel 2 / SKILL)

**Estado:** canon vigente (ALFRED · CYCLE-16 · 2026-11-15, auditado
por Heimdall).
**Alcance:** `<workspace>/.arqux/skills/` y `<project>/.arqux/skills/`
— capacidades del framework (16 skills vigentes).

---

## 1. Qué es

Una **capacidad**: procedimiento + contrato de un dominio funcional.
Nivel 2 — entre la identidad (quién) y el brain (qué sabe el proyecto).

## 2. Las tres variantes físicas reales

| Variante | Sobre | Ejemplos reales |
|---|---|---|
| **A — sobre sigilado + cuerpo prosa** | secciones `$N` con entradas + `## §` markdown explicativo | `comms`, `arqux-issues` |
| **B — frontmatter YAML** | `---` (`skill_id`, `name`, `version`, `status`, `kind`, `usage`, `layer`, `blp_ref`) + `§N` markdown con entradas incrustadas | `blueprint-synthesize`, `voice` |
| **C — puro sobre** | íntegramente `$0`–`$N` sigilado, sin prosa | `cortex`(×2), `workflows`(×2), `autonomia`, `diagram`, `learning`, `protocol` |

**Ningún `.skill.md` declara `$0:format`** (0/16) ni `ARQX:artifact`
— los skills son tolerant por diseño: el sobre es lo gobernado, el
cuerpo markdown nunca strict-parsea.

### Sigilos ejecutables reales

Dominantes: `AXM`, `STP`, `IDN`, `HDL`, `FMT`, `LOOP`. Minoritarios:
`WK` (5 ocurrencias), `REG` (0). El cuerpo markdown es opcional y su
posición varía — en varios skills todo el contrato vive en secciones.

### `skills/workflows/` — patrón índice+subdir

`workflows.skill.md` es índice (`IDN:wN{file:"workflows/wNN-*.md"}`)
de archivos `wNN-*.md` planos (no `.skill.md`). Divergencias reales:
ws porta 12 archivos (falta `w12` **y `w14`**), proyecto 13 (falta
`w03`); el índice referencia `w00-triage.md` **inexistente** (ambos
niveles) y a nivel proyecto además referencia `w03` colgante —
dos referencias rotas + `w12`/`w14` no indexados (deuda de datos).

## 3. Reglas

1. **Un dominio por skill** — no mega-skills.
2. **Lo ejecutable va en el sobre** — `AXM`/`STP`/`HDL`/`IDN`; la
   prosa explica, no ejecuta.
3. **Descubrimiento, no hardcodeo** — match por tarea (`skill.list`,
   `skill.get`).
4. **Puentes externos aparte** — providers externos (Teamwork:
   `timelog-compliance`) viven fuera de `.arqux/skills/`, on-request
   (`AXM:external_providers_decoupled`).
5. **Tensión conocida**: `voice.skill.md` declara `layer: 3` en
   frontmatter — contradice "nivel 2" si el frontmatter manda
   (pendiente Arquitecto).

## 4. Asimetría de sets

ws (9 skills): autonomia, comms, voice extra. Proyecto (7): incluye
`arqux-issues` (única de proyecto — fuente del formato de issues).

## 5. Referencias

- `formato.md` — sobre `.cortex` vs cuerpo markdown, strict/tolerant
- `artefactos.md` §2.3 — ficha nivel 2
- `gobernanza-canon.md` — `arqux-issues.skill.md`

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="../../../docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
