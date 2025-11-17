import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(HERE)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app import app  # type: ignore


def main():
    with app.test_client() as client:
        r = client.get("/api")
        print("status:", r.status_code)
        for h in [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "Referrer-Policy",
            "Permissions-Policy",
            "Content-Security-Policy",
            "Content-Security-Policy-Report-Only",
        ]:
            print(h + ":", r.headers.get(h))


if __name__ == "__main__":
    main()
