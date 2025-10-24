import sys

sys.path.insert(0, ".")
from appy import app

if __name__ == "__main__":
    print("Starting minimal server...")
    try:
        app.run(
            host="127.0.0.1", port=5000, debug=False, use_reloader=False, threaded=False
        )
    except Exception as e:
        print(f"Server crashed with error: {e}")
        import traceback

        traceback.print_exc()
