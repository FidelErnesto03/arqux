---
# Cycle Manifest Template (CYCLE_MANIFEST_TEMPLATE.md)
# Copied by cycle.create() to create CYCLE-NNN/MANIFEST.md
# HCORTEX format — human + machine readable

cycle_id: ""
name: ""
project_ref: ""
status: "draft"
governor: ""
created_at: ""
updated_at: ""
closed_at: ""
planned_start: ""
planned_end: ""
quality_gates@: {
  has_clear_purpose: false,
  has_explicit_scope: false,
  has_measurable_objectives: false,
  has_operational_guidelines: false,
  has_control_points: false,
  aligns_with_project: false,
}
_template_ref: "CYCLE_MANIFEST_TEMPLATE.md"
---

# Manifest: {name}

> Cycle governing document. Defines identity, scope, objectives, guidelines, and control points. Source of truth for all Blueprints within this cycle.

---

## §1: Purpose

_Why does this cycle exist? What problem does it address within the project?_

**Relationship to project objectives:**
_Which project objectives (from brain.cortex OBJ) does this cycle contribute to?_


## §2: Scope & Limits

**In scope for this cycle:**
- _Item 1_
- _Item 2_

**Out of scope (explicitly excluded):**
- _Item 1_
- _Item 2_

> What is out of scope must NOT be addressed by any Blueprint in this cycle.


## §3: Objectives

_Concrete, measurable cycle objectives. Each Blueprint must contribute to at least one._

- [ ] **CYC-OBJ-1:** _Objective — success criterion_
- [ ] **CYC-OBJ-2:** _Objective — success criterion_
- [ ] **CYC-OBJ-3:** _Objective — success criterion_


## §4: Guidelines

_Operational guidelines governing all Blueprints in this cycle._

1. _Guideline 1 — e.g., "Infrastructure Blueprints take priority over feature Blueprints"_
2. _Guideline 2 — e.g., "Every Blueprint must include a PUML diagram in the design section"_
3. _Guideline 3 — e.g., "No Blueprint closes without running all required validations"_
4. _Guideline 4 — e.g., "Dependencies between Blueprints must be resolved before the dependent starts"_

**Blueprint creation guidelines:**
1. _Every Blueprint must reference the cycle objective it contributes to_
2. _Critical Blueprints must include a rollback plan_
3. _Each Blueprint must estimate its impact on the cycle's success criteria_


## §5: Control Points

_Milestones, reviews, and validation points. Execution stops at each point._

| ID | Type | Planned Date | Description | Pass Criterion |
|---|---|---|---|---|
| CP-01 | Design Review | _YYYY-MM-DD_ | _Description_ | _What must pass?_ |
| CP-02 | Mid-point Check | _YYYY-MM-DD_ | _Description_ | _What must pass?_ |
| CP-03 | Final Review | _YYYY-MM-DD_ | _Description_ | _What must be validated?_ |

> Control points are mandatory. The governor must inform the Architect when approaching one.


## §6: Blueprints (Index)

_Brief index of Blueprints assigned to this cycle. Auto-populated._

| BLP ID | Title | Status | Priority | Objective | Governor |
|---|---|---|---|---|---|
| _BLP-NNN_ | _Title_ | _draft/ready/..._ | _critical/high/medium/low_ | _CYC-OBJ-N_ | _agent_ |


## §7: Status & Metrics

**Current status:** draft
**Total Blueprints:** 0 | **Draft:** 0 | **Maturating:** 0 | **Ready:** 0 | **In Progress:** 0 | **Done:** 0
**Progress:** 0%
**Next control point:** _CP-NN — Date_
**Started:** _YYYY-MM-DD_ | **Planned end:** _YYYY-MM-DD_


## §8: Cycle Rules

_Rules specific to this cycle._

1. _Rule 1_
2. _Rule 2_


## §9: Quality Contract

| Gate | Status |
|---|---|
| has_clear_purpose | ☐ |
| has_explicit_scope | ☐ |
| has_measurable_objectives | ☐ |
| has_operational_guidelines | ☐ |
| has_control_points | ☐ |
| aligns_with_project | ☐ |

> All gates must be ✅ before cycle.ready(). See blueprint-workflow skill, §4.1.
