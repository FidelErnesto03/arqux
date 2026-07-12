# Observación: Cobertura de Blueprint Handler (BLP-005)

**Fecha**: 2026-07-11
**Contexto**: Durante la ejecución de BLP-005 (Corregir tests de handlers críticos),
se lograron los siguientes incrementos de cobertura:

| Handler | Antes | Después | Objetivo |
|---------|-------|---------|----------|
| `handlers/session.py` | 56% | **88%** | ≥70% ✅ |
| `handlers/skill.py` | 36% | **70%** | ≥70% ✅ |
| `handlers/blueprint.py` | 55% | **55%** | ≥70% ❌ |
| Global | 65% | **72%** | ≥70% ✅ |

**Por qué blueprint.py no alcanzó**: El archivo `handlers/blueprint.py` tiene 752 líneas
y contiene 18 handlers que operan sobre archivos BLP-*.md reales mediante CODEC-CORTEX.
Para alcanzar 70% se necesita un fixture de integración que monte un ciclo completo con
blueprints reales — un esfuerque significativo que requiere coordinación.

**Propuesta**: Discutir con Alfred si se debe:
1. Crear un BLP dedicado para fixture de integración de Blueprint
2. Aceptar 55% como parcial y priorizar otras areas del ciclo
3. Refactorizar blueprint.py para separar lógica de negocio de persistencia
