import sys
from pathlib import Path

# Support both possible package directory names used in different clones:
# - backend/helpchain-backend/src (older)
# - backend/helpchain_backend/src (current)
SRC_DIR = Path(__file__).resolve().parent / "backend" / "helpchain_backend" / "src"
if not SRC_DIR.exists():
    SRC_DIR = Path(__file__).resolve().parent / "backend" / "helpchain-backend" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app import Config, create_app  # noqa: E402

app = create_app(Config)

if __name__ == "__main__":
    print("init_admin ready")
