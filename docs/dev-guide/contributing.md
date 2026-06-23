# Contributing

## Development Workflow

**🚨 MANDATORY: Branch Protection Rules**

- **NO direct commits to `main`** — All changes MUST go through Pull Requests
- **All work on feature branches** — Use branch prefixes: `feat/`, `fix/`, `chore/`, `docs/`, `refactor/`, `test/`
- **PRs require review** — At least one approval before merge
- **CI must pass** — All checks (tests, linting, type-check) must pass before merge

---

1. Create a feature branch from `main` (e.g., `git checkout -b feat/your-feature-name`)
2. Make changes following the coding standards
3. Write/update tests
4. Run `pytest backend/tests/ -v` to verify
5. Run `mypy backend/ --strict` to type-check
6. Run `ruff check backend/` to lint
7. Create a pull request to `main`
8. Wait for review approval and CI to pass
9. Merge via GitHub (squash and merge recommended)

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

## Branch Protection Setup (GitHub Repository Settings)

To enforce these rules automatically, configure branch protection on `main`:

1. Go to **Settings → Branches → Branch protection rules**
2. Add rule for `main` with:
   - ✅ Require a pull request before merging
   - ✅ Require approvals (minimum 1)
   - ✅ Dismiss stale PR approvals when new commits are pushed
   - ✅ Require status checks to pass before merging
   - ✅ Require branches to be up to date before merging
   - ✅ Require conversation resolution before merging
   - ✅ Do not allow bypassing the above settings

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

## Branch Naming Convention

| Prefix | Purpose | Example |
|--------|---------|---------|
| `feat/` | New features | `feat/user-authentication` |
| `fix/` | Bug fixes | `fix/login-redirect-loop` |
| `chore/` | Maintenance, config | `chore/update-dependencies` |
| `docs/` | Documentation | `docs/api-reference` |
| `refactor/` | Code restructuring | `refactor/risk-engine` |
| `test/` | Test additions | `test/integration-screener` |
| `perf/` | Performance improvements | `perf/query-optimization` |
| `security/` | Security fixes | `security/input-validation` |
