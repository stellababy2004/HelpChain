from __future__ import annotations

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from backend.models import SocialRequest, Structure, User, db

bp = Blueprint("social_requests", __name__, url_prefix="/requests")

NEED_TYPES = [
    ("aide_alimentaire", "Aide alimentaire"),
    ("aide_administrative", "Aide administrative"),
    ("visite_senior", "Visite senior"),
    ("urgence_sociale", "Urgence sociale"),
    ("autre", "Autre"),
]
URGENCIES = [
    ("low", "Faible"),
    ("medium", "Moyenne"),
    ("high", "Élevée"),
]


def _safe_int(v: str | None) -> int | None:
    if not v:
        return None
    try:
        return int(v)
    except ValueError:
        return None


def _utcnow():
    return datetime.utcnow()


@bp.get("")
def list_requests():
    items = SocialRequest.query.order_by(SocialRequest.created_at.desc()).limit(200).all()
    return render_template("requests/list.html", items=items)


@bp.get("/new")
def new_request():
    structures = Structure.query.order_by(Structure.name.asc()).all()
    return render_template(
        "requests/new.html",
        need_types=NEED_TYPES,
        urgencies=URGENCIES,
        structures=structures,
    )


@bp.post("/new")
def create_request():
    structure_id = _safe_int(request.form.get("structure_id"))
    if not structure_id:
        flash("Structure requise.", "danger")
        return redirect(url_for("social_requests.new_request"))

    need_type = (request.form.get("need_type") or "").strip()
    urgency = (request.form.get("urgency") or "medium").strip()
    description = (request.form.get("description") or "").strip()
    person_ref = (request.form.get("person_ref") or "").strip() or None

    if not need_type:
        flash("Type de besoin requis.", "danger")
        return redirect(url_for("social_requests.new_request"))
    if not description:
        flash("Description requise.", "danger")
        return redirect(url_for("social_requests.new_request"))

    sr = SocialRequest(
        structure_id=structure_id,
        need_type=need_type,
        urgency=urgency,
        person_ref=person_ref,
        description=description,
        status="new",
    )
    db.session.add(sr)
    db.session.commit()

    flash("Demande créée.", "success")
    return redirect(url_for("social_requests.details", req_id=sr.id))


@bp.get("/<int:req_id>")
def details(req_id: int):
    sr = SocialRequest.query.get_or_404(req_id)
    structure = Structure.query.get(sr.structure_id)
    users = User.query.order_by(User.email.asc()).limit(300).all()
    assignee = User.query.get(sr.assigned_to_user_id) if sr.assigned_to_user_id else None
    return render_template(
        "requests/details.html",
        sr=sr,
        structure=structure,
        users=users,
        assignee=assignee,
    )


@bp.post("/<int:req_id>/assign")
def assign(req_id: int):
    sr = SocialRequest.query.get_or_404(req_id)
    user_id = _safe_int(request.form.get("assigned_to_user_id"))
    if not user_id:
        flash("Utilisateur requis.", "danger")
        return redirect(url_for("social_requests.details", req_id=req_id))

    u = User.query.get(user_id)
    if not u:
        flash("Utilisateur invalide.", "danger")
        return redirect(url_for("social_requests.details", req_id=req_id))

    sr.assigned_to_user_id = u.id
    sr.assigned_at = _utcnow()
    if sr.status == "new":
        sr.status = "in_progress"

    db.session.commit()
    flash("Assignation effectuee.", "success")
    return redirect(url_for("social_requests.details", req_id=req_id))


@bp.post("/<int:req_id>/unassign")
def unassign(req_id: int):
    sr = SocialRequest.query.get_or_404(req_id)
    sr.assigned_to_user_id = None
    sr.assigned_at = None
    db.session.commit()
    flash("Assignation supprimee.", "success")
    return redirect(url_for("social_requests.details", req_id=req_id))
