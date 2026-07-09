# Contributing to ArqUX

Thanks for your interest in contributing to ArqUX! This document provides guidelines and information for contributors.

## Development Setup

### Prerequisites
- Python 3.11+
- pip

### Setup
```bash
git clone https://github.com/FidelErnesto03/arqux.git
cd arqux
pip install -e ".[dev]"
```

### Verify Installation
```bash
pytest -q  # Run all tests
ruff check src/ tests/  # Run linter
mypy src/arqux/  # Run type checker
```

## Pull Request Process

1. **Fork** the repository
2. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```
3. **Make your changes** following the code standards below
4. **Run tests**: `pytest -q`
5. **Run linter**: `ruff check src/ tests/`
6. **Run type checker**: `mypy src/arqux/`
7. **Commit** with a conventional commit message (see below)
8. **Push** and create a Pull Request

## Code Standards

- **Linting:** [ruff](https://docs.astral.sh/ruff/) — configured in `pyproject.toml`
- **Types:** [mypy](https://mypy-lang.org/) — configured in `pyproject.toml`
- **Tests:** [pytest](https://docs.pytest.org/) with coverage — target: ≥80%
- All tests must pass before PR merge
- All lint checks must pass before PR merge

## Commit Convention

We use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat(scope):` — new feature
- `fix(scope):` — bug fix
- `docs(scope):` — documentation changes
- `test(scope):` — adding or updating tests
- `refactor(scope):` — code restructuring without behavior change
- `chore(scope):` — maintenance tasks

Examples:
- `feat(handlers): add cycle.activate handler`
- `fix(permissions): correct HMAC verification for auditor`
- `docs: update README with security section`

## Reporting Issues

- **Bug reports:** Include steps to reproduce, expected behavior, and actual behavior
- **Feature requests:** Describe the use case and proposed solution
- **Security issues:** See [SECURITY.md](SECURITY.md)

## License

By contributing to ArqUX, you agree that your contributions will be licensed under the Apache License 2.0.
