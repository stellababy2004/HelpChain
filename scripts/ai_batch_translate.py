#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.exc import OperationalError, ProgrammingError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from backend.helpchain_backend.src.app import create_app
    from backend.helpchain_backend.src.routes import admin as admin_routes
    from backend.models import UiTranslation
except Exception as exc:  # pragma: no cover - CLI import guard
    raise SystemExit(f"[ERROR] Failed to import app/models: {exc}")


def _configure_stdio_utf8() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Generate AI/rules translation suggestions for missing UI translations. "
            "This script is suggestion-only and does not write to DB."
        )
    )
    p.add_argument(
        "--target-locales",
        default="en,de,bg",
        help="Comma-separated locales to generate suggestions for (default: en,de,bg).",
    )
    p.add_argument(
        "--source-locale",
        default="fr",
        help="Source locale when pulling defaults from DB mode (default: fr).",
    )
    p.add_argument(
        "--source",
        choices=("registry", "db", "auto"),
        default="auto",
        help="Candidate key source: registry | db | auto (default: auto).",
    )
    p.add_argument(
        "--view",
        choices=("ops", "core", "inventory", "all"),
        default="ops",
        help="Registry view filter when source includes registry (default: ops).",
    )
    p.add_argument(
        "--provider",
        choices=("hf_local", "rules"),
        default="hf_local",
        help="Suggestion provider (default: hf_local, falls back to rules).",
    )
    p.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Tasks per batch in output JSON (default: 50).",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Max suggestions to generate per locale (default: 500).",
    )
    p.add_argument(
        "--output",
        default="",
        help="Output JSON path. Default: reports/ai_translation_tasks_<timestamp>.json",
    )
    p.add_argument(
        "--include-existing",
        action="store_true",
        help="Also include keys that already have DB override in target locale.",
    )
    return p.parse_args()


def _normalize_locales(raw: str) -> list[str]:
    out: list[str] = []
    for part in (raw or "").split(","):
        lc = part.strip().lower()
        if lc and lc not in out:
            out.append(lc)
    return out


def _registry_candidates(view: str) -> dict[str, dict]:
    rows = admin_routes._registry_entries_for_view(view)  # noqa: SLF001
    out: dict[str, dict] = {}
    for row in rows:
        key = str(row.get("key") or "").strip()
        if not key:
            continue
        out[key] = {
            "key": key,
            "default": str(row.get("default") or "").strip(),
            "domain": str(row.get("domain") or "public").strip() or "public",
            "kind": str(row.get("kind") or "tkey").strip() or "tkey",
            "tier": str(row.get("tier") or "core").strip() or "core",
        }
    return out


def _db_source_candidates(source_locale: str, registry_index: dict[str, dict]) -> dict[str, dict]:
    try:
        rows = (
            UiTranslation.query.filter(
                UiTranslation.locale == source_locale,
                UiTranslation.is_active.is_(True),
            )
            .order_by(UiTranslation.key.asc())
            .all()
        )
    except (OperationalError, ProgrammingError):
        print(
            "[WARN] ui_translations table is unavailable; DB source candidates skipped.",
            file=sys.stderr,
        )
        return {}
    out: dict[str, dict] = {}
    for row in rows:
        key = (row.key or "").strip()
        if not key:
            continue
        meta = registry_index.get(key, {})
        out[key] = {
            "key": key,
            "default": (row.text or "").strip() or str(meta.get("default") or "").strip(),
            "domain": str(meta.get("domain") or "public").strip() or "public",
            "kind": str(meta.get("kind") or "tkey").strip() or "tkey",
            "tier": str(meta.get("tier") or "core").strip() or "core",
        }
    return out


def _existing_keys_for_locale(locale: str) -> set[str]:
    try:
        rows = (
            UiTranslation.query.with_entities(UiTranslation.key)
            .filter(
                UiTranslation.locale == locale,
                UiTranslation.is_active.is_(True),
            )
            .all()
        )
    except (OperationalError, ProgrammingError):
        print(
            "[WARN] ui_translations table is unavailable; treating all keys as missing.",
            file=sys.stderr,
        )
        return set()
    return {str(k).strip() for (k,) in rows if str(k).strip()}


def _chunk(items: list[dict], size: int) -> list[list[dict]]:
    if size <= 0:
        return [items]
    return [items[i : i + size] for i in range(0, len(items), size)]


def main() -> int:
    _configure_stdio_utf8()
    args = _parse_args()

    target_locales = _normalize_locales(args.target_locales)
    if not target_locales:
        raise SystemExit("[ERROR] No target locales provided.")

    app = create_app()
    now = datetime.now(timezone.utc)
    out_path = Path(args.output) if args.output else Path(
        "reports"
    ) / f"ai_translation_tasks_{now.strftime('%Y%m%dT%H%M%SZ')}.json"

    with app.app_context():
        supported = set(admin_routes._supported_locales())  # noqa: SLF001
        for locale in target_locales:
            if locale not in supported:
                raise SystemExit(f"[ERROR] Unsupported locale: {locale}")

        registry_index = _registry_candidates(args.view)
        db_index = _db_source_candidates(args.source_locale, registry_index)

        if args.source == "registry":
            candidates = dict(registry_index)
        elif args.source == "db":
            candidates = dict(db_index)
        else:
            candidates = dict(registry_index)
            for key, row in db_index.items():
                if key not in candidates:
                    candidates[key] = row
                elif not candidates[key].get("default") and row.get("default"):
                    candidates[key]["default"] = row["default"]

        keys_sorted = sorted(candidates.keys())

        report: dict[str, object] = {
            "generated_at": now.isoformat(),
            "source": args.source,
            "source_locale": args.source_locale,
            "view": args.view,
            "provider": args.provider,
            "batch_size": int(max(1, args.batch_size)),
            "limit_per_locale": int(max(1, args.limit)),
            "only_missing": not bool(args.include_existing),
            "summary": {},
            "tasks": [],
        }

        all_tasks: list[dict] = []
        for locale in target_locales:
            existing = _existing_keys_for_locale(locale) if not args.include_existing else set()
            generated = 0
            skipped_existing = 0
            skipped_no_suggestion = 0

            for key in keys_sorted:
                if generated >= args.limit:
                    break
                if key in existing:
                    skipped_existing += 1
                    continue

                meta = candidates[key]
                default = str(meta.get("default") or "").strip()
                domain = str(meta.get("domain") or "public").strip() or "public"
                source_text = admin_routes._source_text_for_ai(key=key, default=default)  # noqa: SLF001
                suggestions = admin_routes._ai_suggest(  # noqa: SLF001
                    key=key,
                    locale=locale,
                    default=default,
                    domain=domain,
                    source_text=source_text,
                    provider=args.provider,
                )
                if not suggestions:
                    skipped_no_suggestion += 1
                    continue

                all_tasks.append(
                    {
                        "locale": locale,
                        "key": key,
                        "domain": domain,
                        "default": default,
                        "source_text": source_text,
                        "provider": args.provider,
                        "status": "pending_approval",
                        "suggestions": suggestions,
                    }
                )
                generated += 1

            report["summary"][locale] = {
                "candidate_keys": len(keys_sorted),
                "generated": generated,
                "skipped_existing": skipped_existing,
                "skipped_no_suggestion": skipped_no_suggestion,
            }
            print(
                f"[{locale}] generated={generated} "
                f"skipped_existing={skipped_existing} skipped_no_suggestion={skipped_no_suggestion}"
            )

        batch_size = int(max(1, args.batch_size))
        report["tasks"] = all_tasks
        report["batches"] = _chunk(all_tasks, batch_size)
        report["total_tasks"] = len(all_tasks)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] wrote {out_path} (tasks={len(report['tasks'])})")
    print("[INFO] suggestion-only output; no DB writes were performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
