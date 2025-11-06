import sys
import traceback
from pathlib import Path

proj_root = Path(__file__).resolve().parent
sys.path.insert(0, str(proj_root / "helpchain-backend"))

try:
    from src.app import app
except Exception:
    traceback.print_exc()
    raise SystemExit(1) from None

try:
    with app.test_client() as client:
        resp = client.get("/api/some_endpoint")
        print("STATUS:", resp.status_code)
        print("DATA:")
        print(resp.get_data(as_text=True))
except Exception:
    traceback.print_exc()
