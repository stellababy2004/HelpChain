import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
os.environ.setdefault("HELPCHAIN_TEST_DEBUG", "1")
print("PYTHONPATH includes:", sys.path[0])
try:
    import importlib

    import backend.extensions as ext

    print("extensions.db:", getattr(ext, "db", None))
    for mod in ("backend.models", "models", "helpchain_backend.src.models"):
        try:
            m = importlib.import_module(mod)
            print("imported", mod)
        except Exception as e:
            print("failed import", mod, "->", e)
    try:
        tables = sorted(list(ext.db.metadata.tables.keys()))
    except Exception as e:
        tables = f"ERROR: {e}"
    print("metadata tables:", tables)
except Exception as e:
    print("unexpected error:", e)
