import sys
import importlib

sys.path.insert(0, r"c:\dev\HelpChain\HelpChain.bg\backend")
import os

os.environ.setdefault("HELPCHAIN_TESTING", "1")

try:
    appy = importlib.import_module("appy")
    app = getattr(appy, "app")
except Exception as e:
    print("IMPORT_ERROR", e)
    raise

rules = sorted(list(app.url_map.iter_rules()), key=lambda r: r.rule)
for r in rules:
    print(r.rule, "->", r.endpoint, list(r.methods))

# Also print whether methods for /admin/login include POST
for r in rules:
    if r.rule in ("/admin/login", "/admin_login"):
        print("MATCH:", r.rule, r.endpoint, list(r.methods))

print("\nApp config TESTING=", app.config.get("TESTING"))
