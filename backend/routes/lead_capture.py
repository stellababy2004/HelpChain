from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify
from backend.extensions import csrf
from backend.extensions import db
from backend.helpchain_backend.src.models.professional_lead import ProfessionalLead

lead_capture_bp = Blueprint("lead_capture", __name__)


def notify_admin_new_lead(email, score):
    level = "HOT LEAD" if score >= 20 else "LEAD"
    print(f"[{level}] New lead: {email} | score={score}")


def send_followup_email(email):
    print(
        "[FOLLOWUP EMAIL READY]",
        {
            "to": email,
            "subject": "HelpChain — Démonstration",
            "body": (
                "Bonjour,\n\n"
                "Nous avons bien reçu votre intérêt pour HelpChain.\n\n"
                "Souhaitez-vous voir concrètement comment cela fonctionnerait dans votre structure ?\n\n"
                "👉 https://helpchain.live/contact\n\n"
                "Bien à vous,\nHelpChain"
            ),
        },
    )


@lead_capture_bp.route("/api/lead-capture", methods=["POST"])
@csrf.exempt
def capture_lead():
    try:
        data = request.get_json() or {}

        email = (data.get("email") or "").strip().lower()
        page = data.get("page") or "unknown"
        intent = data.get("intent") or "unknown"
        source = data.get("source") or "lead_capture_popup"

        if not email:
            return jsonify({"error": "missing email"}), 400

        score = 0

        if page in ["/offre", "/deploiement"]:
            score += 10

        if intent == "high":
            score += 10

        is_hot = score >= 20
        status = "qualified" if is_hot else "new"

        next_action_at = datetime.utcnow() + timedelta(days=1) if is_hot else None
        next_action_note = (
            "Relancer rapidement : intérêt fort détecté sur une page à forte intention."
            if is_hot
            else None
        )

        note = (
            f"{'HOT_LEAD' if is_hot else 'LEAD'} | "
            f"page={page} | intent={intent} | score={score} | source={source}"
        )

        existing = ProfessionalLead.query.filter_by(email=email).first()

        if existing:
            existing.source = existing.source or source
            existing.notes = f"{existing.notes or ''}\n{note}".strip()

            if is_hot:
                existing.status = "qualified"
                existing.next_action_at = next_action_at
                existing.next_action_note = next_action_note
        else:
            lead = ProfessionalLead(
                email=email,
                profession="structure_locale",
                source=source,
                status=status,
                notes=note,
                next_action_at=next_action_at,
                next_action_note=next_action_note,
            )
            db.session.add(lead)

        db.session.commit()

        notify_admin_new_lead(email, score)

        if is_hot:
            send_followup_email(email)

        return jsonify(
            {
                "status": "ok",
                "score": score,
                "lead_status": status,
                "hot_lead": is_hot,
            }
        )

    except Exception as e:
        db.session.rollback()
        print("LEAD_CAPTURE_ERROR:", str(e))
        return jsonify({"error": "server error"}), 500