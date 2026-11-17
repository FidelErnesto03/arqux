---
doc_type: reference
status: normative
version: 1.0.0
verified: 2026-11-15
---

# Biblioteca ArqUX

Documentación pública del producto. Tres colecciones:

| Colección | Idioma | Rol | Autoridad |
|---|---|---|---|
| `es/` | Español | Biblioteca de usuario — tutoriales, guías por actor, referencia, explicación | Primaria (mandato ES-first) |
| `en/` | Inglés | **Espejo completo 1:1** de `es/` — misma ruta y nombre, cuerpo en inglés | Derivada del canon ES |
| `es/especificacion/` | Español | Especificación normativa del formato CORTEX (17 docs) | **Corpus de origen** |

## Reglas de la biblioteca

- Todo documento declara front-matter: `doc_type`, `status`, `version`, `verified`.
- `doc_type`: `tutorial | guide | reference | explanation | spec | report`.
- `status`: `normative | informative | historical`.
- `verified`: fecha ISO del último check contra el código — un doc sin verificación reciente es un doc que probablemente miente.
- Documento nuevo sin entrada en el índice = gate rojo (`test_docs_consistency`).
- Paridad bilingüe: cada doc de `es/` tiene gemelo en `en/` con la misma ruta relativa y nombre — la regla `test_en_es_mirror_parity` del gate lo verifica; los docs raíz tienen gemelos en `en/root/`.

## Índice por tipo (docs/es/)

| Tipo | Carpeta | Función |
|---|---|---|
| Tutorial | `es/tutorial/` | Aprender haciendo — recorrido completo verificado |
| Guía | `es/guias/` | How-to por actor (humano, lead, CISO, agente, equipo) |
| Referencia | `es/referencia/` | Consulta exacta — CLI, errores, configuración, formatos |
| Explicación | `es/explicacion/` | El por qué — arquitectura, fronteras, casos límite |
| Especificación | `es/especificacion/` + `en/especificacion/` | Canon CORTEX — corpus ES de origen + espejo EN 1:1 |

## Material interno

Estrategia, roadmap, auditorías operativas y ADRs internos viven **fuera del repositorio** en `ARQUX-internal/` — por decisión del Arquitecto (2026-11-15). Lo que no se publica no engaña ni expone.
