from __future__ import annotations

from threading import Lock

_LOCK = Lock()
_TENANT_LEAK_TOTAL = 0


def get_tenant_leak_total() -> int:
    with _LOCK:
        return int(_TENANT_LEAK_TOTAL)


def inc_tenant_leak_total(value: int = 1) -> int:
    global _TENANT_LEAK_TOTAL
    inc = int(value)
    if inc <= 0:
        return get_tenant_leak_total()
    with _LOCK:
        _TENANT_LEAK_TOTAL += inc
        return int(_TENANT_LEAK_TOTAL)


def render_prometheus_metrics() -> str:
    total = get_tenant_leak_total()
    lines = [
        "# HELP tenant_leak_total Tenant guardrail violations detected.",
        "# TYPE tenant_leak_total counter",
        f"tenant_leak_total {total}",
    ]
    return "\n".join(lines) + "\n"
