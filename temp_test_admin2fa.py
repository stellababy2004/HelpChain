import os
import sys
import time

os.environ.setdefault("HELPCHAIN_TESTING", "1")
os.environ.setdefault("HELPCHAIN_TEST_DEBUG", "1")
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# Mirror test sys.path setup so `appy`/`appy_with_analytics` can be imported
root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(root, "backend", "helpchain-backend", "src"))
sys.path.insert(0, os.path.join(root, "backend", "helpchain-backend"))
sys.path.insert(0, os.path.join(root, "backend"))
sys.path.insert(0, root)

# Ensure the test app module is importable via the test harness (appy)
try:
    from appy import app
except Exception as e:
    print("IMPORT_ERROR", e)
    raise

client = app.test_client()
with client.session_transaction() as sess:
    sess["pending_email_2fa"] = True
    sess["email_2fa_code"] = "123456"
    sess["email_2fa_expires"] = time.time() + 600

resp = client.get("/admin/email_2fa")
print("STATUS_CODE:", resp.status_code)
print("LOCATION:", resp.headers.get("Location"))
print("BODY_START:", resp.get_data(as_text=True)[:400])
