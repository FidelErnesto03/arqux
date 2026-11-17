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

# Formato `.cortex` — reglas físicas transversales

**Estado:** canon vigente (ALFRED · CYCLE-16 · 2026-11-15).
**Alcance:** TODO artefacto `.cortex` del framework — no solo brains.
La enumeración completa de artefactos vive en `artefactos.md`; el canon
de secciones del brain en `cerebro-canon.md`.

---

## 1. Qué es un `.cortex`

Documento CODEC-CORTEX: texto plano, secciones `$N` numeradas
secuencialmente desde `$0`, entradas `SIGIL:name{attrs}` por línea.
Sin ejecutables, sin formato binario — memoria legible por máquina y
humano.

| Nivel | Artefactos | Rol |
|---|---|---|
| **0** | `timelog/SESNNN_*.cortex`, `issues/*.cortex`, `contexts/exec-*.cortex` | episódico / registro por archivo |
| **1** | `identities/<agent>.cortex` | contrato conductual del agente |
| **2** | `skills/*.skill.md`, `cycles/**` (task/cycle), `learn-policies.cortex` | capacidad / config / unidad de trabajo |
| **3** | `brain.cortex`, `meta-brain.cortex` | memoria del proyecto / workspace |

## 2. Estructura física obligatoria

```
$0:format{cortex:1.0, encoding:UTF-8}
SIGIL:name{type:"<type>", weight:"<B|M|H>", focus:"<layer>",
           fields:"...", desc:"...", open:true|false}
   ... declaraciones ejecutables en $0 ...

$1: TITLE
ARQX:artifact{level:N, name:"...", usage:"...", kind:"...",
              version:"...", revision:"...", last_writer:"..."}
SIGIL:entry{...}
```

- **`$0` = espacio de declaraciones puro.** `$0:format` abre; las
  declaraciones ejecutables declaran cada sigilo emitido. Regla dura:
  G016 exige `type:` en todo símbolo de `$0` — por eso `$0` no puede
  contener registros de datos. **Drift dominante real**: la mayoría
  de artefactos emitidos por writers actuales (6/7 identidades, tasks
  de ciclos, templates, handoffs) llevan las declaraciones
  `*_contract` **antes** del `$0:format` — el format solo es "primero"
  en la minoría estricta; homologar.
- **`ARQX:artifact` = primera entrada del cuerpo** (`$1`, antes del
  primer dato del documento): el documento se declara a sí mismo en el
  punto más cercano al `$0` que el formato permite. Porta la revisión
  (`version`/`revision`/`last_writer` — patrón `TLG:identity`).
  **Excepciones reales**: los writers de timelog emiten `TLG:identity`
  antes del `ARQX`; `learn-policies.cortex` y los `.skill.md` no lo
  portan. (En issues `.cortex` el `ARQX` de `$0` es la *declaración*
  del sigilo; el *registro* sí está primero en `$1`.)
- **Posiciones legacy (solo lectura):** `$0.1`, `$15` titled, `$19` —
  aceptadas al leer. **Corrección del audit**: `$19` SIGUE siendo
  emitida hoy — emisores confirmados (lista no exhaustiva):
  `formats.py`, `writer.py`, `migrator.py`, `skill_store.py`,
  `session.py`, `protocol.py`, `_migrate.py`, `crud.py`, `entries.py`,
  `_lesson.py`, `_brain.py`, templates. La meta "jamás emitida" es el
  destino, no la realidad; los readers siguen resolviéndola por
  posición.

## 3. Declaraciones ejecutables

Todo sigilo emitido en el cuerpo DEBE estar declarado en `$0`:

```
AUD:audit{type:"attrs", weight:"B", fields:"value:any?",
          focus:"Episodic", desc:"...", open:true}
```

El writer las genera automáticamente; un writer hand-rolled debe
replicarlas. Nomenclatura canónica: `SIGIL:<sigil>_contract` para la
declaración del contrato — 6/7 identidades la usan; solo
`alfred.cortex` porta la forma corta `ARQX:arqx` (generación vieja —
drift cosmético a homologar).

## 4. Strict vs tolerant

- **Strict:** `$0:format` + declaraciones + `ARQX` + reglas de nivel
  (E024/E034 en brain: `FCS`/`OBJ` activos). Es la **meta** — el
  corpus real es mayoritariamente tolerant: 21/21 timelogs sin
  `$0:format`, ningún skill lo declara, issues con layouts
  heterogéneos. No todo writer nuevo emite strict hoy.
- **Tolerant:** forma legacy parseable sin declaraciones — válida como
  registro histórico append-only. No se reescribe por cosmética;
  se homologa en la próxima escritura legítima.
- **Verdad corta:** ningún handler devuelve `ok` antes de validar lo
  que escribió; malformado → abort + revert (`AXM:silent_corruption`).

## 5. Contrato del writer

Toda escritura nueva: (a) declara (`$0:format` + sigilos), (b) porta
`ARQX:artifact` en cabecera de `$1`, (c) coalesce `$0.1`/`$19` →
posición canónica, (d) conserva comentarios/títulos existentes,
(e) verifica post-escritura antes de devolver `ok`.

## 6. Referencias

- `niveles-cortex-arqux.md` — modelo de niveles
- `docs/en/explicacion/frontera-codec.md` — frontera ArqUX/CODEC (espejo EN)
- `artefactos.md` — censo completo de artefactos

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="../../../docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
