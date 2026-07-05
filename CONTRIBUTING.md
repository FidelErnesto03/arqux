# Contributing to Arqux

This project is developed using the framework itself (dogfooding, per §8 of the
founding brief). Every feature is a governed task in `.<product>/cycles/`.

## Workflow

1. **Pick or create a task.**
   Browse open tasks via the framework. If none exists for your work, ask the
   governor to create one via `task.create`.

2. **Claim the task.**
   An executor calls `task.claim` to take ownership. The task transitions to
   `in_progress`.

3. **Do the work.**
   Update progress via `task.update` with concrete notes. Record intermediate
   evidence via `evidence.record`.

4. **Complete or block.**
   Call `task.complete` (with evidence summary) or `task.fail` (with reason).

5. **Review.**
   An auditor can run a retrospective via the `cycle-retrospective` skill.

## Code style

- Python 3.10+.
- Line length: 100 (enforced by ruff).
- Type hints required on all public functions.
- Tests required for new handlers. Target ≥80% coverage on handler modules.

## Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(cycle): add close-cycle summary support
fix(task): correct state transition from blocked to in_progress
docs(agents): clarify permission table
```

## Running tests

```bash
pip install -e ".[dev]"
pytest
ruff check src tests
mypy src
```

## Adding a new handler

You cannot add a new handler without removing an existing one (24-handler
budget, per §5.5 of the brief). If you believe a new handler is necessary:

1. Open a task proposing the new handler AND identifying which existing
   handler to remove.
2. Justify the swap in the task's `# OBJ` section.
3. The governor decides whether to proceed.

## Reporting bugs

Open a GitHub issue with:
- Expected behavior
- Actual behavior
- Steps to reproduce
- `arqux --version` output
- Relevant `pulse.jsonl` entries (if applicable)
