import os
import tempfile
from datetime import UTC, datetime, timedelta

from ..extensions import db
from ..models import Request


def utc_now() -> datetime:
    """Return naive UTC timestamp without relying on datetime.utcnow."""
    return datetime.now(UTC).replace(tzinfo=None)


# опитваме се да намерим моделите; ако липсват - не вдигаме ImportError при зареждане
MODELS_AVAILABLE = True
try:
    from ..models.help_request import HelpRequest
    from ..models.volunteer import Volunteer
except Exception:
    try:
        from ..models import HelpRequest, Volunteer
    except Exception:
        HelpRequest = None
        Volunteer = None
        MODELS_AVAILABLE = False

try:
    from ..models.audit import AuditLog
except Exception:
    AuditLog = None


class HelpChainController:
    def __init__(self):
        print("HelpChainController initialized")  # Debug log
        pass

    def create_help_request(self, data):
        # Логика за създаване на заявка за помощ
        pass

    def get_help_requests(self):
        # Логика за извличане на всички заявки за помощ
        pass

    def update_help_request(self, request_id, data):
        # Логика за актуализиране на заявка за помощ
        pass

    def delete_help_request(self, request_id):
        # Логика за изтриване на заявка за помощ
        pass

    def approve_request(self, help_id, admin_user, note=None):
        # ... изпълни логиката за одобрение (update status, save)
        # записваме audit запис
        log = AuditLog(
            action="approve",
            actor_id=getattr(admin_user, "id", None),
            actor_name=getattr(admin_user, "username", None),
            target_type="help_request",
            target_id=help_id,
            details={"note": note} if note else None,
        )
        db.session.add(log)
        db.session.commit()
        # върни резултат (съществуващ код)
        return {"ok": True}

    def reject_request(self, help_id, admin_user, reason=None):
        # ... reject logic ...
        log = AuditLog(
            action="reject",
            actor_id=getattr(admin_user, "id", None),
            actor_name=getattr(admin_user, "username", None),
            target_type="help_request",
            target_id=help_id,
            details={"reason": reason} if reason else None,
        )
        db.session.add(log)
        db.session.commit()
        return {"ok": True}

    def _apply_filters_query(self, q, filters):
        if not MODELS_AVAILABLE:
            return q
        if filters.get("date_from"):
            q = q.filter(
                HelpRequest.created_at >= datetime.fromisoformat(filters["date_from"])
            )
        if filters.get("date_to"):
            q = q.filter(
                HelpRequest.created_at <= datetime.fromisoformat(filters["date_to"])
            )
        if filters.get("status"):
            q = q.filter(HelpRequest.status == filters["status"])
        if filters.get("region"):
            q = q.filter(HelpRequest.region == filters["region"])
        if filters.get("volunteer_id"):
            q = q.filter(HelpRequest.volunteer_id == int(filters["volunteer_id"]))
        return q

    def get_dashboard_stats(self, filters):
        if not MODELS_AVAILABLE:
            return {
                "counts_by_status": [],
                "volunteers_by_city": [],
                "top_request_types": [],
                "timeseries": [],
                "warning": "Models HelpRequest/Volunteer not found - implement src/models/help_request.py and src/models/volunteer.py to enable DB stats.",
            }

        out = {}
        q = db.session.query(HelpRequest)
        q = self._apply_filters_query(q, filters)

        # counts by status
        status_counts = (
            db.session.query(HelpRequest.status, db.func.count(HelpRequest.id))
            .group_by(HelpRequest.status)
            .all()
        )
        out["counts_by_status"] = [{"status": s, "count": c} for s, c in status_counts]

        # volunteers by city
        vol_by_city = (
            db.session.query(Volunteer.city, db.func.count(Volunteer.id))
            .group_by(Volunteer.city)
            .order_by(db.func.count(Volunteer.id).desc())
            .limit(50)
            .all()
        )
        out["volunteers_by_city"] = [{"city": c, "count": n} for c, n in vol_by_city]

        # top request types
        types = (
            db.session.query(HelpRequest.type, db.func.count(HelpRequest.id))
            .group_by(HelpRequest.type)
            .order_by(db.func.count(HelpRequest.id).desc())
            .limit(10)
            .all()
        )
        out["top_request_types"] = [{"type": t, "count": cnt} for t, cnt in types]

        # time series active vs completed (simple last 30 days)
        series = []
        today = utc_now().date()
        for i in range(30):
            day = today - timedelta(days=29 - i)
            start = datetime.combine(day, datetime.min.time())
            end = datetime.combine(day, datetime.max.time())
            active = (
                db.session.query(HelpRequest)
                .filter(
                    HelpRequest.created_at <= end, HelpRequest.status != "completed"
                )
                .count()
            )
            completed = (
                db.session.query(HelpRequest)
                .filter(
                    HelpRequest.updated_at >= start, HelpRequest.status == "completed"
                )
                .count()
            )
            series.append(
                {"date": day.isoformat(), "active": active, "completed": completed}
            )
        out["timeseries"] = series

        return out

    def export_requests(self, filters, fmt="excel"):
        if not MODELS_AVAILABLE:
            raise RuntimeError(
                "Models HelpRequest/Volunteer not found. Add them under src/models/ to enable export."
            )

        q = db.session.query(HelpRequest)
        q = self._apply_filters_query(q, filters)
        rows = []
        for r in q.all():
            rows.append(
                {
                    "id": r.id,
                    "title": getattr(r, "title", None),
                    "status": getattr(r, "status", None),
                    "type": getattr(r, "type", None),
                    "region": getattr(r, "region", None),
                    "volunteer": getattr(getattr(r, "volunteer", None), "name", None),
                    "created_at": getattr(r, "created_at", None),
                    "updated_at": getattr(r, "updated_at", None),
                }
            )

        # pandas lazy import
        try:
            import pandas as pd  # local import
        except Exception as e:
            raise RuntimeError(
                "pandas is required for export_requests. Install with: pip install pandas openpyxl"
            ) from e

        df = pd.DataFrame(rows)

        tmpdir = tempfile.gettempdir()
        if fmt == "excel":
            path = os.path.join(
                tmpdir, f"help_requests_{int(utc_now().timestamp())}.xlsx"
            )
            df.to_excel(path, index=False, engine="openpyxl")
            return (
                path,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                os.path.basename(path),
            )
        elif fmt == "pdf":
            try:
                from jinja2 import Template
                from weasyprint import HTML
            except Exception as e:
                raise RuntimeError(
                    "weasyprint/jinja2 required for PDF export. Install with: pip install weasyprint jinja2"
                ) from e
            html = Template(
                """
            <h1>Help Requests</h1>
            <table border="1" cellspacing="0" cellpadding="4">
            <tr>{% for c in cols %}<th>{{c}}</th>{% endfor %}</tr>
            {% for row in rows %}
            <tr>{% for c in cols %}<td>{{ row[c] }}</td>{% endfor %}</tr>
            {% endfor %}
            </table>
            """
            ).render(
                cols=list(df.columns), rows=df.fillna("").to_dict(orient="records")
            )
            path = os.path.join(
                tmpdir, f"help_requests_{int(utc_now().timestamp())}.pdf"
            )
            HTML(string=html).write_pdf(path)
            return path, "application/pdf", os.path.basename(path)
        else:
            raise NotImplementedError()

    def create_help(self, data):
        print(f"Creating help request with data: {data}")  # Debug log
        # Create a new request
        req = Request(
            name=data.get("name"),
            phone=data.get("phone"),
            email=data.get("email"),
            location=data.get("location"),
            category=data.get("category"),
            description=data.get("description"),
            urgency=data.get("urgency"),
            status="pending",
        )
        db.session.add(req)
        db.session.commit()
        print(f"Created request with id: {req.id}")  # Debug log
        return {"success": True, "id": req.id}
