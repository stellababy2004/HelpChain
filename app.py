# Root Flask entrypoint for Vercel and simple local run
# This file imports the Flask `app` instance from backend/appy.py so
# hosting providers (Vercel) that search for app.py/main.py can find it.


try:
    from backend.appy import app
except Exception:
    import os
    import sys

    sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))
    from appy import app  # type: ignore


if __name__ == "__main__":
    # Local dev run
    app.run(host="0.0.0.0", port=8000, debug=True)

    # Or, for production with gevent and Flask-SocketIO
    from gevent import monkey

    monkey.patch_all()
    from flask_socketio import SocketIO

    socketio = SocketIO(app, async_mode="gevent")
    socketio.run(app, host="0.0.0.0", port=5000)
