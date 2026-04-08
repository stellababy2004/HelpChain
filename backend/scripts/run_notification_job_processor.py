#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def _prepare_import_path() -> None:
    this_file = Path(__file__).resolve()
    backend_dir = this_file.parents[1]
    repo_root = backend_dir.parent
    for path in (str(repo_root), str(backend_dir)):
        if path not in sys.path:
            sys.path.insert(0, path)


def main() -> int:
    _prepare_import_path()

    interval_seconds = max(5, int(os.getenv("HC_NOTIFICATION_PROCESSOR_INTERVAL", "30")))
    batch_size = max(1, int(os.getenv("HC_NOTIFICATION_PROCESSOR_BATCH", "25")))

    from run import app
    from backend.helpchain_backend.src.services.notification_jobs import (
        process_pending_notifications,
    )

    print(
        f"[HC] notification job processor started "
        f"(interval={interval_seconds}s batch={batch_size})"
    )

    while True:
        try:
            with app.app_context():
                stats = process_pending_notifications(limit=batch_size)
            print(
                "[HC] notification job processor tick: "
                f"scanned={stats.get('scanned', 0)} "
                f"completed={stats.get('sent', 0)} "
                f"requeued={stats.get('retried', 0)} "
                f"terminal={stats.get('failed', 0)}"
            )
        except KeyboardInterrupt:
            print("[HC] notification job processor stopped")
            return 0
        except Exception as exc:
            print(f"[HC] WARNING: notification job processor error: {exc}")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
