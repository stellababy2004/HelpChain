import sys
import traceback

try:
    import os

    sys.path.insert(0, os.path.join(os.getcwd(), "backend"))
    import models_with_analytics as mwa

    print("Imported models_with_analytics OK, module:", mwa)
    try:
        from backend.extensions import db

        print("backend.extensions.db:", db)
    except Exception as e:
        print("Importing backend.extensions.db raised:", e)
        traceback.print_exc()
except Exception as e:
    print("Importing models_with_analytics raised:", e)
    traceback.print_exc()
print("sys.modules contains models:", "models" in sys.modules)
print("sys.modules contains backend.models:", "backend.models" in sys.modules)
print("sys.modules contains extensions:", "extensions" in sys.modules)
print("sys.modules contains backend.extensions:", "backend.extensions" in sys.modules)
