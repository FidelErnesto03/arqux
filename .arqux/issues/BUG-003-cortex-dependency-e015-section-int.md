# BUG-003: Defectos de BUG-002 que viven en la dependencia `cortex` (CODEC-CORTEX)
# Severity: medium | Status: verified | Handler: alfred | Date: 2026-07-16

**Reportado por:** Alfred
**Fecha:** 2026-07-16T21:30:00Z
**Estado:** triaged (evaluado — pendiente de escalar a CODEC-CORTEX como upstream)
**Contexto:** BLP-017 corrigió el defecto de ARQUX (entry.add content suple section).
Los otros dos defectos de BUG-002 residen en el paquete dependiente
`cortex` (instalado en el tool `arqux` y desarrollado en CODEC-CORTEX),
por lo que NO se corrigen dentro del proyecto ARQUX.

---

## Defecto A — Mensaje E015 truncado

`cortex/crud/transactions.py:97` ensambla el `AtomicWriteError` thus:

```python
"; ".join(d.get("code", "") + ": " + d.get("message", "")[:80] for d in non_bypassable[:3])
```

- Corta cada mensaje de diagnóstico a **80 caracteres** (`[:80]`).
- Solo itera los primeros **3** errores no-bypassables (`non_bypassable[:3]`).

Reproducido: un `KNW` incompleto produce un mensaje que se corta en
`"...crit"`, perdiendo `"ical sigils MUST be complete to persist (SKILL.md §6)"`
y la lista completa de campos faltantes.

**Fix sugerido:** iterar todos los `non_bypassable` sin `[:80]`:
```python
"; ".join(f"{d.get('code','')}: {d.get('message','')}" for d in non_bypassable)
```

## Defecto B — `section` entero en `normalize_section_id`

`cortex/core/ast.py:304` hace `s = section_id.strip()` sin coercer a string.
El CLI dispatch convierte `section="6"` a entero, provocando
`AttributeError: 'int' object has no attribute 'strip'`.

Reproducido: `normalize_section_id(6)` lanza `AttributeError`.

**Fix sugerido:** `s = str(section_id).strip()`.

---

## Impacto

Estos dos defectos obligan a trial-and-error al escribir brains y rompen
`cortex.entry.add` cuando `section` llega como entero desde el shell.

## Acción requerida

Escalar a CODEC-CORTEX (proyecto ajeno a ARQUX) como issue upstream.
NO editar `/home/vatrox/workspace/CODEC-CORTEX/` ni el `cortex` de site-packages
desde el equipo de ARQUX sin autorización expresa del dueño de CODEC-CORTEX.

## UPDATE 2026-09-30

CODEC-CORTEX is now a convention/standard only — no upstream implementation exists to escalate to (Architect 2026-09-30). Both defects verified absent from ARQUX's own code: (A) no [:80]/[:3] diagnostic truncation in _crud.py/entries.py error paths; (B) normalize_section_id does not exist, section params typed str, int input degrades to ValueError/no-match — never AttributeError. Resolved by owning the codec surface: reader.py codec preference removed, own parser is single authority, inline-brace multiline loss fixed. Heimdall audit APPROVED-WITH-FOLLOWUPS, all follow-ups applied (E-0936). Commits 3b1f326, b46bbf5. Residual ownership tracked in T-031.
