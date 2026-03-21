from __future__ import annotations

import threading
import time
from datetime import UTC, datetime, timedelta

from flask import current_app, jsonify, render_template, url_for
from sqlalchemy import func, or_, text

from backend.extensions import db
from ..models import NotificationJob, Request
from .admin import (
    CLOSED_STATUSES,
    _current_structure_id,
    _is_global_admin,
    _scope_requests,
    _sla_prediction_state,
    _table_exists,
    _to_utc_naive,
    admin_bp,
    admin_required,
    admin_required_404,
    suggest_best_professional,
)

try:
    import psutil
except Exception:  # pragma: no cover - keep admin routes import-safe
    psutil = None


_SYSTEM_HEALTH_CACHE = {"expires_at": None, "payload": None}
_SYSTEM_HEALTH_CACHE_LOCK = threading.Lock()
_SYSTEM_HEALTH_CACHE_TTL_SECONDS = 2


def _collect_db_latency_ms() -> int | None:
    started = time.perf_counter()
    try:
        db.session.execute(text("SELECT 1"))
        return int(round((time.perf_counter() - started) * 1000))
    except Exception:
        db.session.rollback()
        return None


def _collect_notification_queue_snapshot(now: datetime) -> dict[str, int | None]:
    out: dict[str, int | None] = {
        "pending": 0,
        "failed_15m": 0,
        "oldest_pending_min": None,
    }
    if not _table_exists("notification_jobs"):
        return out

    queue_query = NotificationJob.query
    try:
        if not _is_global_admin():
            sid = _current_structure_id()
            queue_query = queue_query.filter(
                (NotificationJob.structure_id == sid)
                | (NotificationJob.structure_id.is_(None))
            )
    except Exception:
        pass

    pending_filter = func.lower(NotificationJob.status).in_(("pending", "retry"))
    failed_cutoff = now - timedelta(minutes=15)

    out["pending"] = int(queue_query.filter(pending_filter).count() or 0)
    out["failed_15m"] = int(
        queue_query.filter(
            func.lower(NotificationJob.status) == "failed",
            NotificationJob.updated_at >= failed_cutoff,
        ).count()
        or 0
    )

    oldest_pending = (
        queue_query.with_entities(NotificationJob.created_at)
        .filter(pending_filter)
        .order_by(NotificationJob.created_at.asc())
        .first()
    )
    if oldest_pending and oldest_pending[0]:
        created_at = _to_utc_naive(oldest_pending[0])
        if created_at:
            out["oldest_pending_min"] = max(
                0, int((now - created_at).total_seconds() // 60)
            )

    return out


def _build_system_health_snapshot() -> dict[str, object]:
    now = datetime.now(UTC).replace(tzinfo=None)
    queue: dict[str, int | None] = {
        "pending": 0,
        "failed_15m": 0,
        "oldest_pending_min": None,
    }
    impacted_cases: list[dict[str, object]] = []
    errors: dict[str, str] = {}
    cpu_percent: float | None = None
    db_latency_ms: int | None = None

    snapshot: dict[str, object] = {
        "status": "ok",
        "cpu": None,
        "ram_used": None,
        "ram_total": None,
        "disk": None,
        "python_procs": None,
        "flask_running": True,
        "flask_status": "running",
        "api_ok": True,
        "api_status": "online",
        "db_latency_ms": None,
        "queue": queue,
        "system_risk": "unknown",
        "impacted_cases": impacted_cases,
        "last_updated_at": now.isoformat(timespec="seconds"),
        "errors": errors,
    }

    if psutil is None:
        errors.update(
            {
                "cpu": "psutil_unavailable",
                "ram": "psutil_unavailable",
                "disk": "psutil_unavailable",
                "python_procs": "psutil_unavailable",
            }
        )
    else:
        try:
            cpu_percent = round(float(psutil.cpu_percent(interval=0.1)), 1)
            snapshot["cpu"] = cpu_percent
        except Exception:
            errors["cpu"] = "cpu_probe_failed"

        try:
            memory = psutil.virtual_memory()
            snapshot["ram_used"] = int(memory.used / (1024 * 1024))
            snapshot["ram_total"] = int(memory.total / (1024 * 1024))
        except Exception:
            errors["ram"] = "ram_probe_failed"

        try:
            disk_usage = psutil.disk_usage(current_app.root_path)
            snapshot["disk"] = int(round(float(disk_usage.percent)))
        except Exception:
            errors["disk"] = "disk_probe_failed"

        try:
            python_procs = 0
            for proc in psutil.process_iter(["name", "cmdline"]):
                try:
                    name = (proc.info.get("name") or "").lower()
                    cmdline_parts = proc.info.get("cmdline") or []
                    cmdline = " ".join(cmdline_parts).lower()
                except (
                    psutil.AccessDenied,
                    psutil.NoSuchProcess,
                    psutil.ZombieProcess,
                ):
                    continue

                if "python" in name or "python" in cmdline:
                    python_procs += 1
            snapshot["python_procs"] = python_procs
        except Exception:
            errors["python_procs"] = "process_probe_failed"

    db_latency_ms = _collect_db_latency_ms()
    snapshot["db_latency_ms"] = db_latency_ms
    if db_latency_ms is None:
        snapshot["api_ok"] = False
        snapshot["api_status"] = "degraded"
        errors["api"] = "db_health_check_failed"

    try:
        queue = _collect_notification_queue_snapshot(now)
        snapshot["queue"] = queue
    except Exception:
        errors["queue"] = "queue_snapshot_failed"

    try:
        impacted_cases = _collect_system_health_impacted_cases()
        snapshot["impacted_cases"] = impacted_cases
    except Exception:
        errors["impacted_cases"] = "impacted_cases_unavailable"

    score = 0
    if not bool(snapshot.get("api_ok")):
        score += 50

    if db_latency_ms is None or db_latency_ms > 800:
        score += 40
    elif db_latency_ms > 300:
        score += 25

    if int(queue.get("pending") or 0) > 50:
        score += 15
    if int(queue.get("failed_15m") or 0) > 10:
        score += 20
    if (queue.get("oldest_pending_min") or 0) > 10:
        score += 20

    if cpu_percent is not None and cpu_percent > 85:
        score += 20
    elif cpu_percent is not None and cpu_percent > 70:
        score += 10

    if score >= 50:
        system_risk = "high"
    elif score >= 20:
        system_risk = "medium"
    else:
        system_risk = "low"

    snapshot["status"] = "degraded" if errors else "ok"
    snapshot["system_risk"] = system_risk
    return snapshot


def _build_system_health_error_snapshot(reason: str) -> dict[str, object]:
    now = datetime.now(UTC).replace(tzinfo=None)
    return {
        "status": "error",
        "cpu": None,
        "ram_used": None,
        "ram_total": None,
        "disk": None,
        "python_procs": None,
        "flask_running": True,
        "flask_status": "running",
        "api_ok": False,
        "api_status": "error",
        "db_latency_ms": None,
        "queue": {
            "pending": 0,
            "failed_15m": 0,
            "oldest_pending_min": None,
        },
        "system_risk": "unknown",
        "impacted_cases": [],
        "last_updated_at": now.isoformat(timespec="seconds"),
        "errors": {"snapshot": reason},
    }


def get_system_health_snapshot_cached() -> dict[str, object]:
    now = datetime.now(UTC)
    with _SYSTEM_HEALTH_CACHE_LOCK:
        expires_at = _SYSTEM_HEALTH_CACHE.get("expires_at")
        payload = _SYSTEM_HEALTH_CACHE.get("payload")
        if expires_at and payload and expires_at > now:
            return payload

    payload = _build_system_health_snapshot()

    with _SYSTEM_HEALTH_CACHE_LOCK:
        _SYSTEM_HEALTH_CACHE["payload"] = payload
        _SYSTEM_HEALTH_CACHE["expires_at"] = now + timedelta(seconds=15)

    return payload


def _collect_system_health_impacted_cases(limit: int = 5) -> list[dict[str, object]]:
    now = datetime.now(UTC).replace(tzinfo=None)
    open_filter = or_(
        Request.status.is_(None),
        ~func.lower(Request.status).in_(CLOSED_STATUSES),
    )
    stale_cutoff = now - timedelta(hours=24)
    candidates_query = (
        _scope_requests(Request.query)
        .filter(Request.deleted_at.is_(None))
        .filter(open_filter)
        .order_by(Request.created_at.asc())
    )
    if not _is_global_admin():
        current_sid = _current_structure_id()
        if current_sid:
            candidates_query = candidates_query.filter(Request.structure_id == current_sid)

    candidates = candidates_query.limit(200).all()

    impacted_cases: list[dict[str, object]] = []
    for row in candidates:
        reason = None
        priority = 0
        last_activity = getattr(row, "updated_at", None) or getattr(
            row,
            "created_at",
            None,
        )
        last_activity_naive = _to_utc_naive(last_activity)

        if getattr(row, "owner_id", None) is None:
            reason = "no_owner"
            priority = 1
        elif last_activity_naive and last_activity_naive < stale_cutoff:
            reason = "no_action_24h"
            priority = 2
        else:
            owner_sla = _sla_prediction_state(
                row,
                sla_kind="owner_assignment_overdue",
                now=now,
            )
            resolve_sla = _sla_prediction_state(
                row,
                sla_kind="resolution_overdue",
                now=now,
            )
            if owner_sla.get("state") in {"due_soon", "breached"} or resolve_sla.get(
                "state"
            ) in {"due_soon", "breached"}:
                reason = "sla_risk"
                priority = 3

        if not reason:
            continue

        actions: list[dict[str, str]] = []
        suggested_assignee = None
        if reason == "no_owner":
            suggested_assignee = suggest_best_professional(row)
            actions.append(
                {
                    "type": "assign",
                    "label": "Assign automatically",
                    "url": f"/admin/requests/{int(row.id)}/assign-suggested",
                }
            )
        elif reason == "no_action_24h":
            actions.append(
                {
                    "type": "notify",
                    "label": "Send reminder",
                    "url": f"/admin/requests/{int(row.id)}/notify-owner",
                }
            )
        elif reason == "sla_risk":
            actions.append(
                {
                    "type": "escalate",
                    "label": "Escalate case",
                    "url": f"/admin/requests/{int(row.id)}/escalate",
                }
            )

        title = (
            (getattr(row, "title", None) or "").strip()
            or (getattr(row, "category", None) or "").replace("_", " ").strip().title()
            or f"Request #{row.id}"
        )
        impacted_cases.append(
            {
                "id": int(row.id),
                "reason": reason,
                "priority": int(priority),
                "title": title,
                "url": url_for("admin.admin_request_details", req_id=row.id),
                "suggested_assignee": suggested_assignee,
                "actions": actions,
            }
        )

    impacted_cases.sort(key=lambda item: (-int(item["priority"]), int(item["id"])))
    return impacted_cases[:limit]


@admin_bp.get("/system-health")
@admin_required
def admin_system_health():
    admin_required_404()
    return render_template("admin/admin_system_health.html")


@admin_bp.get("/api/system-health")
@admin_required
def admin_system_health_api():
    admin_required_404()
    try:
        return jsonify(get_system_health_snapshot_cached())
    except Exception:
        current_app.logger.exception("admin_system_health_api_failed")
        return jsonify({"status": "error"}), 500
