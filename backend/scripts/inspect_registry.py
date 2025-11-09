import importlib
import inspect
import os
import sys

# ensure parent dir is on sys.path so package `backend` can be imported
sys.path.insert(0, os.path.abspath(".."))
print("sys.path[0]=", sys.path[0])
try:
    m = importlib.import_module("backend.models")
    print("imported backend.models ->", m)
except Exception as e:
    print("import backend.models failed:", e)
try:
    from backend.extensions import db

    print("db:", db)
    model_base = getattr(db, "Model", None)
    print("model_base:", model_base)
    rc = (
        getattr(model_base, "_decl_class_registry", None)
        if model_base is not None
        else None
    )
    print("_decl_class_registry type:", type(rc))
    if rc:
        matches = []
        for k, v in rc.items():
            try:
                if getattr(v, "__name__", None) == "AuditLog":
                    matches.append((k, getattr(v, "__module__", None), id(v)))
            except Exception:
                pass
        print("registry AuditLog matches:", matches)
except Exception as e:
    print("registry introspect failed:", e)
# scan sys.modules for classes named AuditLog
found = []
for mname, mobj in list(sys.modules.items()):
    try:
        for attrname, attrval in getattr(mobj, "__dict__", {}).items():
            if inspect.isclass(attrval) and attrval.__name__ == "AuditLog":
                found.append((mname, attrname, id(attrval), attrval.__module__))
    except Exception:
        pass
print("sys.modules AuditLog classes:", found)
