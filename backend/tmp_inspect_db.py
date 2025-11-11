import importlib

names = [
    "backend.extensions",
    "extensions",
    "helpchain_backend.src.extensions",
    "appy",
    "models",
]
for n in names:
    try:
        m = importlib.import_module(n)
        db = getattr(m, "db", None)
        print(n, id(db), db.__class__.__module__ if db is not None else None)
    except Exception as e:
        print(n, "ERROR", e)
