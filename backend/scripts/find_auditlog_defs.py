import importlib
import sys

# Try to import backend.models so classes exist
try:
    import backend.models
except Exception:
    pass

found = []
for name, mod in list(sys.modules.items()):
    if not mod:
        continue
    try:
        for attr_name in dir(mod):
            try:
                attr = getattr(mod, attr_name)
            except Exception:
                continue
            if isinstance(attr, type) and getattr(attr, "__name__", None) == "AuditLog":
                found.append(
                    (name, attr_name, id(attr), getattr(attr, "__module__", None))
                )
    except Exception:
        continue

for item in found:
    print(item)
print("Total found:", len(found))
