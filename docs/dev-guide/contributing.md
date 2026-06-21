# Contributing

## Development Workflow

1. Create a feature branch from `main`
2. Make changes following the coding standards
3. Write/update tests
4. Run `pytest backend/tests/ -v` to verify
5. Run `mypy backend/ --strict` to type-check
6. Run `ruff check backend/` to lint
7. Create a pull request

## Code Review Checklist

- [ ] Tests pass for all new/modified code
- [ ] mypy strict mode passes
- [ ] ruff linter has no errors
- [ ] Type hints are complete on all public APIs
- [ ] Pydantic models for all request/response schemas
- [ ] Docstrings explain non-trivial logic
- [ ] No Python loops in indicator/signal computation (vectorized only)
- [ ] Async/await for all I/O operations
- [ ] Error handling follows existing patterns

## Commit Convention

We use conventional commits:

```
feat: add ATR position sizing
fix: correct indicator cache invalidation
docs: update API reference
test: add Monte Carlo edge cases
refactor: extract risk engine modules
ci: add GitHub Actions workflow
```
