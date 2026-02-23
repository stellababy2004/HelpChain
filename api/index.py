import os
import sys
from collections.abc import Callable

# Ensure project root is on path
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

_cached_inner = None


def _load_inner_app():
    global _cached_inner
    if _cached_inner is None:
        # Import lazily to avoid heavy imports for health probes
        from run import application as _application

        _cached_inner = _application
    return _cached_inner


def _commit_sha() -> str:
    """Best-effort commit SHA detection for previews and CI.
    Checks common environment variables set by Vercel/GitHub and finally
    looks for a COMMIT_SHA file at the repo root.
    """
    for key in (
        "VERCEL_GIT_COMMIT_SHA",
        "VERCEL_GIT_COMMIT_REF",
        "GITHUB_SHA",
        "COMMIT_SHA",
    ):
        v = os.getenv(key)
        if v:
            return str(v)
    try:
        root = os.path.dirname(os.path.dirname(__file__))
        p = os.path.join(root, "COMMIT_SHA")
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as fh:
                return fh.read().strip()
    except Exception:
        pass
    return "unknown"


def _derive_path(environ: dict) -> str:
    """Best-effort original path detection across multiple reverse-proxy headers.
    Falls back to scanning the environ values to catch rewrites that hide the
    original path (e.g. mapping everything to /api/index.py).
    """
    keys = (
        "HTTP_X_FORWARDED_URI",
        "HTTP_X_FORWARDED_PATH",
        "HTTP_X_ORIGINAL_URI",
        "HTTP_X_ORIGINAL_URL",
        "HTTP_X_REWRITE_URL",
        "REQUEST_URI",
        "RAW_PATH",
        "PATH_INFO",
    )
    for k in keys:
        v = environ.get(k)
        if isinstance(v, str) and v.strip():
            val = v.strip()
            # If platform rewrites to this file path, treat as root
            if val.endswith("/api/index.py") or val.endswith("/api/index"):
                return "/"
            return val
    # Fallback: scan for common probe substrings in all string values
    try:
        joined = " \n ".join(
            str(v) for v in environ.values() if isinstance(v, (str, bytes))
        )
        for probe in ("/health", "/api/_health", "/admin/login", "/api/analytics"):
            if probe in joined:
                return probe
    except Exception:
        pass
    return "/"


def app(environ, start_response: Callable):
    try:
        path = _derive_path(environ)
        method = (environ.get("REQUEST_METHOD") or "GET").upper()
        # Serve favicon directly to avoid invoking backend on assets
        try:
            if path.endswith("/favicon.ico") or path.endswith("/favicon.png"):
                import base64

                png_b64 = b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAuMB9D7rWqkAAAAASUVORK5CYII="
                buf = base64.b64decode(png_b64)
                headers = [
                    ("Content-Type", "image/png"),
                    ("Cache-Control", "public, max-age=3600"),
                    ("Content-Length", str(len(buf))),
                ]
                start_response("200 OK", headers)
                return [buf]
        except Exception:
            pass
        # Lightweight version endpoint for smokes and diagnostics
        if path.endswith("/_version") or path.endswith("/api/_version"):
            import json

            sha = _commit_sha()
            # Attempt to detect inner app module/name
            app_obj = None
            inner_name = None
            try:
                app_obj = _load_inner_app()
                # Flask app exposes import_name; WSGI callable may be wrapper
                inner_name = getattr(app_obj, "import_name", None) or getattr(
                    app_obj, "__name__", None
                )
            except Exception:
                inner_name = None
            data = {
                "status": "ok",
                "commit": sha,
                "inner_app": inner_name or "unknown",
                "source": "api/index.py",
            }
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            headers = [
                ("Content-Type", "application/json; charset=utf-8"),
                ("X-App-Commit", sha),
                ("Cache-Control", "no-store"),
                ("Content-Length", str(len(body))),
            ]
            start_response("200 OK", headers)
            return [body]
        # Delegate HTML routes to Flask; avoid placeholder pages for preview
        # Do not short-circuit root; delegate to Flask to render templates
        # Handle /api/root explicitly in case project-level routing points here
        if method == "GET" and (path == "/api/root" or path == "/api/root/"):
            html = (
                "<html><head><title>HelpChain Preview</title></head>"
                '<body style="font-family: Arial, sans-serif; padding:24px">'
                "<h1>HelpChain Preview</h1>"
                "<p>Лек fallback за /api/root.</p>"
                "</body></html>"
            )
            body = html.encode("utf-8")
            headers = [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Length", str(len(body))),
            ]
            start_response("200 OK", headers)
            return [body]
        if path.endswith("/health") or path.endswith("/api/_health"):
            body = b"ok"
            headers = [
                ("Content-Type", "text/plain; charset=utf-8"),
                ("Content-Length", str(len(body))),
            ]
            start_response("200 OK", headers)
            return [body]
        if path.endswith("/api/analytics"):
            body = b'{"status":"ok","source":"api-wrapper"}'
            headers = [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(body))),
            ]
            start_response("200 OK", headers)
            return [body]
        # Delegate admin/login and other HTML routes to Flask to render templates
    except Exception:
        # Fall through to the inner app on any wrapper error
        pass
    # Delegate everything else, with preview-safe traceback on failure
    try:
        return _load_inner_app()(environ, start_response)
    except Exception:
        import traceback

        tb = traceback.format_exc()
        body = tb.encode("utf-8", errors="replace")
        headers = [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Cache-Control", "no-store"),
            ("Content-Length", str(len(body))),
        ]
        start_response("500 Internal Server Error", headers)
        return [body]


# For local debug
if __name__ == "__main__":
    # Run the inner Flask app via the wrapper
    from werkzeug.serving import run_simple

    run_simple("0.0.0.0", int(os.environ.get("PORT", 5000)), app, use_reloader=False)
