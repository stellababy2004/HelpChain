from __future__ import annotations

from threading import Lock

_lock = Lock()
_tenant_leak_total = 0


def tenant_leak_inc(value: int = 1) -> int:
    global _tenant_leak_total
    inc = int(value)
    if inc <= 0:
        return tenant_leak_get()
    with _lock:
        _tenant_leak_total += inc
        return int(_tenant_leak_total)


def tenant_leak_get() -> int:
    with _lock:
        return int(_tenant_leak_total)
