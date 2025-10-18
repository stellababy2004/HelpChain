import sys
from pathlib import Path

# Add backend/helpchain-backend/src to sys.path
SRC_DIR = Path(__file__).resolve().parent / "backend" / "helpchain-backend" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app import Config, create_app  # noqa: E402

app = create_app(Config)

if __name__ == "__main__":
    print("init_admin ready")
