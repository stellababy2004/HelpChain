"""
Shim for backwards compatibility: re-export the canonical extension
instances from the top-level `extensions` module so importing
`helpchain_backend.src.extensions` yields the same `db`/`mail`/`babel`
objects used by the rest of the application.

Avoid creating a distinct SQLAlchemy() instance here which would lead
to multiple registries and the classic "models registered twice" issue
during tests.
"""

"""
Shim that re-exports the canonical extension objects from the top-level
`backend.extensions` (or `extensions`) module. IMPORTANT: this shim must not
create a local SQLAlchemy() instance because that would lead to duplicate
metadata/mapper registration. If the canonical module is available we re-use
its `db`, otherwise we deliberately avoid instantiating SQLAlchemy here and
leave `db` as None — callers should import the canonical module when
available. The shim still creates lightweight helpers like `login_manager`.
"""

canonical = None
try:
    # Prefer the package-qualified canonical module
    import backend.extensions as canonical
except Exception:
    try:
        import extensions as canonical
    except Exception:
        canonical = None

if canonical is not None:
    # Re-export objects from the canonical module. Use getattr with a
    # sensible default for optional features (cache may be None).
    db = getattr(canonical, "db", None)
    babel = getattr(canonical, "babel", None)
    mail = getattr(canonical, "mail", None)
    cache = getattr(canonical, "cache", None)
else:
    # Do NOT instantiate SQLAlchemy() here. Leave db/babel/mail/cache as None
    # so that importing modules are forced to use the canonical module when
    # available (and tests that ensure canonical exists will work). This avoids
    # creating a separate metadata registry which causes duplicate-table issues.
    db = None
    babel = None
    mail = None
    cache = None

# Provide objects that some modules expect to exist here. These are
# lightweight and safe to instantiate even if `db` is None. The shim does
# not create a local SQLAlchemy() instance — it only provides helpers like
# `login_manager` used by tests and blueprints.
from flask_login import LoginManager
from flask_migrate import Migrate

# Migrate may be initialized later with the canonical db if available.
migrate = Migrate()
login_manager = LoginManager()
