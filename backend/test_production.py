import os

os.environ["PRODUCTION"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///test.db"

try:
    from appy import app

    print("App imported successfully in production mode")
except Exception as e:
    print(f"Error importing app: {e}")
    import traceback

    traceback.print_exc()
