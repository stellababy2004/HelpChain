from __future__ import annotations

from datetime import UTC, datetime, timedelta

from flask import Blueprint, jsonify, render_template
from sqlalchemy import func

from backend.extensions import db
from backend.helpchain_backend.src.models import Case
from backend.helpchain_backend.src.services.early_warning import detect_ews
from .admin import admin_required, admin_required_404, admin_role_required, _current_structure_id


admin_command_bp = Blueprint("admin_command", __name__, url_prefix="/admin")


def _world_bbox():
    return (-90.0, -180.0, 90.0, 180.0)


def _build_warning_reason(alert: dict) -> str:
    reasons = []
    if (alert.get("growth_ratio") or 0) > 2:
        reasons.append("growth_ratio > 2")
    if (alert.get("critical_cases") or 0) >= 3:
        reasons.append("critical_cases >= 3")
    if (alert.get("avg_risk") or 0) >= 75:
        reasons.append("avg_risk >= 75")
    return ", ".join(reasons) if reasons else "risk threshold exceeded"


@admin_command_bp.get("/command")
@admin_required
@admin_role_required("readonly", "ops", "superadmin")
def admin_command_dashboard():
    admin_required_404()
    sid = _current_structure_id()
    if not sid:
        return render_template(
            "admin/command_dashboard.html",
            kpis={"active_cases": 0, "critical_cases": 0, "early_warnings": 0, "avg_risk": 0, "cases_last_7d": 0},
            critical_cases=[],
            early_warnings=[],
        )

    critical_cases = (
        Case.query.filter(Case.structure_id == sid)
        .order_by(func.coalesce(Case.risk_score, 0).desc(), Case.id.desc())
        .limit(10)
        .all()
    )

    warnings_raw = detect_ews(sid, _world_bbox())
    early_warnings = []
    for alert in warnings_raw:
        early_warnings.append(
            {
                "district": f"{alert['lat']:.2f}, {alert['lon']:.2f}",
                "alert_level": alert.get("level", "warning"),
                "reason": _build_warning_reason(alert),
                "growth_ratio": alert.get("growth_ratio", 0),
                "avg_risk": alert.get("avg_risk", 0),
                "critical_cases": alert.get("critical_cases", 0),
            }
        )

    kpis = _compute_command_kpis(sid)
    return render_template(
        "admin/command_dashboard.html",
        kpis=kpis,
        critical_cases=critical_cases,
        early_warnings=early_warnings,
    )


def _compute_command_kpis(structure_id: int) -> dict:
    try:
        now = datetime.now(UTC)
        since_7 = now - timedelta(days=7)
        base = Case.query.filter(Case.structure_id == structure_id)
        active_cases = base.filter(func.lower(Case.status) != "closed").count()
        critical_cases = base.filter(func.coalesce(Case.risk_score, 0) >= 90).count()
        avg_risk = base.with_entities(func.avg(func.coalesce(Case.risk_score, 0))).scalar() or 0
        cases_last_7d = base.filter(Case.created_at >= since_7).count()
        early_warnings = len(detect_ews(structure_id, _world_bbox()))
        return {
            "active_cases": int(active_cases),
            "critical_cases": int(critical_cases),
            "avg_risk": int(round(avg_risk)),
            "early_warnings": int(early_warnings),
            "cases_last_7d": int(cases_last_7d),
        }
    except Exception:
        return {
            "active_cases": 0,
            "critical_cases": 0,
            "avg_risk": 0,
            "early_warnings": 0,
            "cases_last_7d": 0,
        }


@admin_command_bp.get("/api/command-kpis")
@admin_required
@admin_role_required("readonly", "ops", "superadmin")
def admin_command_kpis():
    admin_required_404()
    sid = _current_structure_id()
    if not sid:
        return jsonify(
            {
                "active_cases": 0,
                "critical_cases": 0,
                "avg_risk": 0,
                "early_warnings": 0,
                "cases_last_7d": 0,
            }
        )
    return jsonify(_compute_command_kpis(sid))
