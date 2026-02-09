from backend.helpchain_backend.src.app import create_app

app = create_app()

paths = {}
for r in app.url_map.iter_rules():
    paths.setdefault(r.rule, []).append(r.endpoint)

dupes = {k: v for k, v in paths.items() if len(v) > 1}

print("\n=== ROUTE AUDIT ===")
if not dupes:
    print("OK ✅ No duplicate routes")
else:
    print("DUPLICATES ❌")
    for path, endpoints in dupes.items():
        print(f"{path} -> {endpoints}")
