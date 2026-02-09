import requests

BASE = "http://127.0.0.1:5000"


def check(path, expect_200=True):
    url = BASE + path
    try:
        r = requests.get(url)
        status = r.status_code
        ok = status == 200 if expect_200 else status != 404
        print(f"{path}: {status} {'✅' if ok else '❌'}")
    except Exception as e:
        print(f"{path}: ERROR {e}")


# Main page
check("/")

# Service worker
check("/sw.js", expect_200=False)  # 200 if exists, else should not be called

# VAPID public key
check(
    "/api/notification/vapid-public-key", expect_200=False
)  # 200 if exists, else should not be called

# Example static CSS file
check("/static/css/design-system.css")

# Example static JS file (if you have one)
check("/static/js/main.js", expect_200=False)  # Change filename if needed
