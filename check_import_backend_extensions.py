import sys, os, traceback

sys.path.insert(0, os.path.join(os.getcwd(), "backend"))
try:
    import backend.extensions as ext

    print("backend.extensions imported OK:", ext)
except Exception as e:
    print("backend.extensions import raised:", type(e).__name__, e)
    traceback.print_exc()
