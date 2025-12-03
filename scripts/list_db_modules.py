import sys
import importlib

modules_to_try = [
    'backend.extensions',
    'extensions',
    'backend.test_instrumentation',
    'backend.helpchain_backend.src.extensions',
    'backend.models',
    'models',
    'models_with_analytics',
]
for m in modules_to_try:
    try:
        importlib.import_module(m)
    except Exception:
        pass

found = {}
for name, mod in list(sys.modules.items()):
    try:
        db = getattr(mod, 'db', None)
        if db is not None and hasattr(db, 'init_app'):
            found.setdefault(id(db), []).append((name, getattr(mod, '__file__', None), type(db).__name__))
    except Exception:
        pass

if not found:
    print('No db-like objects found in sys.modules')
else:
    for k, v in found.items():
        print(f'id={k}:')
        for entry in v:
            print('  ', entry)
