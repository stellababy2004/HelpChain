Tests notes

Canonical extensions and shim guidance

If you add new modules that need `db`, import like this:

```python
from extensions import db
```

or, if referencing from within the package:

```python
from backend.extensions import db
```

Avoid creating `SQLAlchemy()` in test-only shims or modules. Instead re-export the canonical `db`.

## Singleton DB invariant (what and why)

Short: the test suite and the app must use a single canonical SQLAlchemy instance so that model classes are registered against the same metadata/registry. Without this invariant you will see intermittent failures such as duplicate-mapper errors or tables that appear missing to parts of the code.

This repository enforces the invariant by: (1) providing a canonical `backend.extensions` module that owns `db`, and (2) injecting/aliasing it early during pytest startup. A regression test (`backend/tests/test_db_singleton.py`) runs in CI as a fast-fail to catch regressions early.

## How to run the singleton fast-fail test locally (PowerShell)

Run only the singleton test to verify the invariant quickly:

```powershell
# from the repository root, run in PowerShell
cd backend
pytest -q backend/tests/test_db_singleton.py -q
```

If that test passes, the canonical `db` invariant holds for your current environment. If it fails, avoid merging changes that create a new `SQLAlchemy()` instance; instead rework the code to re-export the canonical `db` from `backend.extensions` or add a small shim that imports and re-exports it.

## CI behavior

The CI workflow runs the singleton test immediately after "Set up Python" as a fast-fail step. This gives quick feedback and prevents long CI runs on PRs that reintroduce duplicate `SQLAlchemy()` instances.

If you want, I can add a short checklist for contributors showing the minimal pattern to import `db` and how to add a shim if needed.

## Shim example (safe re-export)

Create a small shim module that re-exports the canonical objects instead of creating new ones. Example (place in `helpchain_backend/src/extensions.py`):

```python
# helpchain_backend/src/extensions.py (shim)
from backend.extensions import db, mail, babel, cache

# Optionally re-export a login manager or other helpers already created by the canonical module
try:
	from backend.extensions import login_manager
except Exception:
	login_manager = None

__all__ = ("db", "mail", "babel", "cache", "login_manager")
```

This shim never calls `SQLAlchemy()` itself — it just imports the already-created objects and re-exports them.

## Small unit test for a shim

Add a lightweight pytest to verify the shim re-exports the canonical `db` instance (example file: `backend/tests/test_shim_reexport.py`).
