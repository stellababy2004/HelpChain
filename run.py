import os
from backend.helpchain_backend.src.app import create_app

app = create_app()

if __name__ == "__main__":
    # Dev-only run: start the Flask app using built-in server
    # Avoid any direct DB schema mutations here; use Alembic migrations.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


