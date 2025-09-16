import os
import sys
from jose import jwt
from dotenv import load_dotenv

load_dotenv(".env")
SECRET = os.getenv("HELPCHAIN_SECRET", "dev-secret-change-me")

# чети токена от аргумент или от stdin
if len(sys.argv) > 1 and sys.argv[1].strip():
    token = sys.argv[1].strip()
else:
    token = input("Paste token: ").strip()

try:
    claims = jwt.decode(token, SECRET, algorithms=["HS256"])
    print(claims)
except Exception as e:
    # при грешка покажи подробности и raw байтовете за диагностика
    print("Decode error:", repr(e))
    try:
        b = token.encode("utf-8", "backslashreplace")
        print("Token bytes (utf-8 with backslashreplace):", b)
    except Exception:
        pass