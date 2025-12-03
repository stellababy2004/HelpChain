import os
import sys

# Ensure repo root is on PYTHONPATH when running this script
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import importlib

# Provide legacy top-level module aliases so imports that expect
# `models`/`analytics_service` still work when running this script.
try:
    backend_models = importlib.import_module("backend.models")
    sys.modules.setdefault("models", backend_models)
except Exception:
    pass

from backend import appy

app = appy.app

with app.test_client() as c:
    # Inspect locale debug endpoint
    r = c.get("/_locale")
    print("/_locale ->", r.status_code, r.get_data(as_text=True))

    # Check session cookie existence and session content via test-only endpoint if available
    try:
        r2 = c.get("/_admin_session")
        print("/_admin_session ->", r2.status_code, r2.get_data(as_text=True))
    except Exception as e:
        print("/_admin_session not available or failed:", e)

    # Now set language to BG, then ensure the force-clear will remove it on next request
    c.get("/set_language/bg", follow_redirects=True)
    print("After set_language/bg, session language (if any) check:")
    r3 = c.get("/_locale")
    print("/_locale ->", r3.status_code, r3.get_data(as_text=True))

    # Final: ensure that subsequent request no longer has session['language'] set
    r4 = c.get("/")
    print("/ -> status", r4.status_code)
    # print some snippet of the page head to show html lang
    text = r4.get_data(as_text=True)
    head = text[:800]
    print("Page head snippet:\n", head)
