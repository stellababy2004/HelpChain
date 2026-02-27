from __future__ import annotations

from sqlalchemy import text

from backend.extensions import db

TENANT_LEAK_KEY = "tenant_leak_total"


def guardrail_get(key: str) -> int:
    row = db.session.execute(
        text('SELECT value FROM guardrail_counters WHERE "key" = :key'),
        {"key": key},
    ).first()
    return int(row[0]) if row else 0


def guardrail_incr(key: str, delta: int = 1) -> int:
    inc = int(delta)
    if inc <= 0:
        return guardrail_get(key)

    db.session.execute(
        text(
            """
            INSERT INTO guardrail_counters ("key", value, updated_at)
            VALUES (:key, :delta, CURRENT_TIMESTAMP)
            ON CONFLICT ("key")
            DO UPDATE SET
              value = guardrail_counters.value + :delta,
              updated_at = CURRENT_TIMESTAMP
            """
        ),
        {"key": key, "delta": inc},
    )
    row = db.session.execute(
        text('SELECT value FROM guardrail_counters WHERE "key" = :key'),
        {"key": key},
    ).first()
    db.session.commit()
    return int(row[0]) if row else 0


def tenant_leak_get() -> int:
    return guardrail_get(TENANT_LEAK_KEY)


def tenant_leak_inc(value: int = 1) -> int:
    return guardrail_incr(TENANT_LEAK_KEY, value)
