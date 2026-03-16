from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.helpchain_backend.src.app import create_app
from backend.extensions import db
from backend.models import Request, Structure


def _choose_structure() -> Structure | None:
    default = Structure.query.filter_by(slug="default").first()
    if default:
        return default
    return Structure.query.order_by(Structure.id.asc()).first()


def backfill_request_structure_id() -> int:
    structure = _choose_structure()
    if not structure:
        print("No structures found. Nothing to backfill.")
        return 0

    null_q = Request.query.filter(Request.structure_id.is_(None))
    count = null_q.count()
    if count == 0:
        print(f"Using structure: {structure.id} / {structure.name}")
        print("Updated rows: 0")
        return 0

    null_q.update({Request.structure_id: structure.id}, synchronize_session=False)
    db.session.commit()

    print(f"Using structure: {structure.id} / {structure.name}")
    print(f"Updated rows: {count}")
    return count


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        backfill_request_structure_id()
