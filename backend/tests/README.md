Tests notes

Canonical extensions and shim guidance

- The project uses a single canonical `SQLAlchemy` instance exported from `backend.extensions` (importable as `extensions` or `backend.extensions`).
- Older/shim modules may exist under `helpchain_backend.src.extensions` — those shims should NOT create a local `SQLAlchemy()` instance. Instead they should import/re-export the canonical `db` and attach lightweight helpers (e.g. `login_manager`, `migrate`).
- In tests we ensure the canonical module is inserted into `sys.modules` early so all model modules bind to the same `db` instance. This prevents duplicate mappers and missing-table errors under SQLite test runs.

If you add new modules that need `db`, import like this:

```python
from extensions import db
```

or, if referencing from within the package:

```python
from backend.extensions import db
```

Avoid creating `SQLAlchemy()` in test-only shims or modules. Instead re-export the canonical `db`.
