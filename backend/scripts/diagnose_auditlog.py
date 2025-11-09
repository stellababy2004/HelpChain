#!/usr/bin/env python3
"""Diagnostic: enumerate all registered AuditLog mapped classes and where they come from."""
import sys
import traceback

print("Starting AuditLog diagnostic...")
# Ensure parent directory (project root) is on sys.path so package imports like 'backend' resolve
import os

parent_dir = os.path.abspath(os.path.join(os.getcwd(), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
print("Prepended parent to sys.path:", parent_dir)
# Import the application module to ensure models are imported/registered
appy_mod = None
try:
    import importlib
    import os
    import runpy

    try:
        appy_mod = importlib.import_module("appy")
        print("Imported appy module via importlib")
    except Exception:
        # fallback: try executing appy.py in cwd
        appy_path = os.path.join(os.getcwd(), "appy.py")
        if os.path.exists(appy_path):
            print(
                f"Found appy.py at {appy_path}, executing with runpy.run_path to load symbols"
            )
            appy_globals = runpy.run_path(appy_path)

            # wrap into an object-like namespace
            class _G:
                pass

            appy_mod = _G()
            for k, v in appy_globals.items():
                setattr(appy_mod, k, v)
        else:
            raise
except Exception as e:
    print("Failed to import or load appy:", e)
    traceback.print_exc()

app = None
if appy_mod is not None:
    # appy_mod may be a module-like object or a dict wrapper; try both
    try:
        app = getattr(appy_mod, "app", None)
    except Exception:
        app = None

if app is None:
    print("No 'app' found in appy; proceeding without app context")

# Try to import canonical db
try:
    from backend.extensions import db

    print("Imported backend.extensions.db")
except Exception as e:
    print("Failed to import backend.extensions.db:", e)
    # fallback to top-level
    try:
        from extensions import db

        print("Imported extensions.db (fallback)")
    except Exception as e2:
        print("Failed to import fallback extensions.db:", e2)
        sys.exit(1)

# Ensure we're in app context if possible
if app is not None:
    ctx = app.app_context()
    ctx.push()
    popped = True
else:
    popped = False

reg = getattr(getattr(db, "Model", None), "registry", None)
if reg is None:
    print("No declarative registry found on db.Model.registry; aborting")
    if popped:
        ctx.pop()
    sys.exit(1)

print("Registry object:", reg)

# Collect matches from registry.mappers
matches = []
for m in reg.mappers:
    try:
        cls = m.class_
    except Exception:
        continue
    if getattr(cls, "__name__", None) == "AuditLog":
        matches.append((cls, getattr(cls, "__module__", None), id(cls)))

print("Found via reg.mappers:")
for cls, mod, objid in matches:
    modfile = getattr(sys.modules.get(mod), "__file__", None)
    print(f" - class id={objid} module={mod} file={modfile} repr={cls!r}")

# Inspect registry._class_registry if present
cr = getattr(reg, "_class_registry", None)
if cr is None:
    print("No _class_registry on registry")
else:
    print("Inspecting registry._class_registry entries (short names) ...")
    found = []
    for k, v in list(cr.items()):
        # v may be a weakref or the class
        try:
            candidate = v() if callable(v) and not isinstance(v, type) else v
        except Exception:
            candidate = v
        if getattr(candidate, "__name__", None) == "AuditLog":
            found.append(
                (k, candidate, getattr(candidate, "__module__", None), id(candidate))
            )
    if not found:
        print("No AuditLog entries in _class_registry")
    else:
        for k, cls, mod, objid in found:
            modfile = getattr(sys.modules.get(mod), "__file__", None)
            print(
                f"_class_registry key={k} -> id={objid} module={mod} file={modfile} cls={cls!r}"
            )

# Scan loaded modules to see who exposes an AuditLog attribute
print("Scanning sys.modules for modules that expose 'AuditLog' attribute...")
exposed = []
for modname, modobj in list(sys.modules.items()):
    if not modobj:
        continue
    try:
        attr = getattr(modobj, "AuditLog", None)
    except Exception:
        continue
    if attr is None:
        continue
    exposed.append(
        (
            modname,
            getattr(attr, "__module__", None),
            id(attr),
            getattr(modobj, "__file__", None),
        )
    )

if not exposed:
    print("No modules expose an 'AuditLog' attribute")
else:
    print("Modules exposing AuditLog:")
    for modname, attrmod, objid, modfile in exposed:
        print(
            f" - sys.modules['{modname}'] (file={modfile}) exposes AuditLog -> attr module={attrmod} id={objid}"
        )

print("Diagnostic complete")
if popped:
    ctx.pop()
