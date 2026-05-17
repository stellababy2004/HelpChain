from __future__ import annotations

import argparse
import os
import sys

from backend.appy import app
from backend.extensions import db
from backend.models import Structure
from backend.helpchain_backend.src.services.weekly_operations_report import (
    enqueue_weekly_operations_report,
)


def _parse_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(
        description="Queue weekly operational report email digests."
    )
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--structure-id", type=int, default=None)
    parser.add_argument("--all-structures", action="store_true")
    parser.add_argument("--send-now", action="store_true")
    parser.add_argument(
        "--base-url",
        default=os.getenv("PUBLIC_BASE_URL", "https://helpchain.live"),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    with app.app_context():
        structure_ids: list[int | None]

        if args.all_structures:
            structure_ids = [
                sid
                for (sid,) in db.session.query(Structure.id)
                .order_by(Structure.id.asc())
                .all()
            ]
        else:
            structure_ids = [args.structure_id]

        total_queued = 0

        for structure_id in structure_ids:
            result = enqueue_weekly_operations_report(
                structure_id=structure_id,
                days=args.days,
                base_url=args.base_url,
                send_now=args.send_now,
            )
            queued = int(result.get("queued", 0) or 0)
            total_queued += queued

            print(
                "weekly_operations_report "
                f"structure_id={structure_id} "
                f"structure_name={result.get('structure_name')} "
                f"queued={queued}"
            )

        print(f"weekly_operations_report total_queued={total_queued}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
