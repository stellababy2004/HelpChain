import os

from backend.appy import app

if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG") == "1" or os.getenv("FLASK_ENV") == "development"
    app.run(debug=debug, use_reloader=debug)
