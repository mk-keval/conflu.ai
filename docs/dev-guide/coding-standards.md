# Coding Standards

## Python

- **Type hints**: Required on all public functions and methods
- **Docstrings**: Google-style docstrings for all public APIs
- **Line length**: 100 characters (enforced by ruff)
- **Imports**: Use `from __future__ import annotations` at top of every file
- **Formatting**: ruff format (black-compatible)
- **Linting**: ruff with selected rule sets (E,F,I,N,W,UP,B,SIM,ARG,C4)
- **Type checking**: mypy with `--strict` mode

### Zero-Loop Policy

All indicator and signal computation MUST use vectorized operations (pandas/numpy/vectorbt). No explicit Python `for` loops in:
- Indicator calculations
- Signal generation
- Backtest simulations
- Risk computations

### Async Pattern

```python
from backend.app.core.logging import get_logger

log = get_logger(__name__)

async def my_async_function() -> Result:
    log.info("operation_start", param=value)
    result = await some_async_operation()
    log.info("operation_complete", param=value)
    return result
```

## TypeScript/React

- **Strict mode**: `strict: true` in tsconfig
- **No unused locals**: `noUnusedLocals: true`
- **No unused parameters**: `noUnusedParameters: true`
- **Path alias**: `@/` maps to `./src/`
- **State management**: Zustand for global state, React Query for server state
- **Styling**: Tailwind CSS with `clsx` + `tailwind-merge`
