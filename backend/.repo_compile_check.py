import os
import py_compile

SKIP_DIRS = {"venv", ".venv", ".git", "node_modules", "__pycache__"}

errors = []
for root, dirs, files in os.walk("."):
    # skip unwanted directories
    parts = set(root.split(os.sep))
    if parts & SKIP_DIRS:
        continue
    for f in files:
        if not f.endswith(".py"):
            continue
        path = os.path.join(root, f)
        try:
            py_compile.compile(path, doraise=True)
        except Exception as e:
            errors.append((path, e))

if not errors:
    print("OK: no compile errors found")
    raise SystemExit(0)

print(f"Found {len(errors)} compile error(s):")
for p, e in errors:
    print(p + ":")
    print("  " + str(e))

raise SystemExit(1)
