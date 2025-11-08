import importlib
import sys

sys.path.insert(0, ".")
try:
    m = importlib.import_module("conftest")
    print("conftest imported")
    names = [n for n in dir(m) if not n.startswith("_")]
    print("has app?", "app" in names)
    print("sample names:", names[:80])
except Exception as e:
    import traceback

    traceback.print_exc()
