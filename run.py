import os

from backend.appy import app

if __name__ == "__main__":
    print("DB:", app.config.get("SQLALCHEMY_DATABASE_URI"))
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
