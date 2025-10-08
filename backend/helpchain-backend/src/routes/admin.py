from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
)
from flask_login import login_required, current_user
from ..models import Request, RequestLog, Volunteer, AdminUser, db
from werkzeug.utils import secure_filename
import os

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Админ вход"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        admin_user = AdminUser.query.filter_by(username=username).first()
        if admin_user and admin_user.check_password(password):
            if admin_user.two_factor_enabled:
                session["pending_admin_user_id"] = admin_user.id
                return redirect(url_for("admin.admin_2fa"))
            else:
                from flask_login import login_user

                login_user(admin_user)
                return redirect(url_for("admin.admin_dashboard"))
        flash("Невалидно потребителско име или парола.", "error")
    return render_template("admin_login.html")


@admin_bp.route("/admin/2fa", methods=["GET", "POST"])
def admin_2fa():
    """2FA верификация за админ"""
    user_id = session.get("pending_admin_user_id")
    if not user_id:
        return redirect(url_for("admin.admin_login"))

    admin_user = AdminUser.query.get(user_id)
    if not admin_user:
        return redirect(url_for("admin.admin_login"))

    if request.method == "POST":
        token = request.form.get("token")
        if admin_user.verify_totp(token):
            from flask_login import login_user

            login_user(admin_user)
            session.pop("pending_admin_user_id", None)
            return redirect(url_for("admin.admin_dashboard"))
        else:
            flash("Невалиден 2FA код.", "error")

    return render_template("admin_2fa.html")


@admin_bp.route("/admin/2fa/setup", methods=["GET", "POST"])
@login_required
def admin_2fa_setup():
    """Настройка на 2FA за админ"""
    if not isinstance(current_user, AdminUser):
        flash("Нямате достъп.", "error")
        return redirect(url_for("main.index"))

    if request.method == "POST":
        token = request.form.get("token")
        if current_user.verify_totp(token):
            current_user.enable_2fa()
            flash("2FA е активиран успешно!", "success")
            return redirect(url_for("admin.admin_dashboard"))
        else:
            flash("Невалиден код.", "error")

    uri = current_user.get_totp_uri()
    return render_template("admin_2fa_setup.html", totp_uri=uri)


@admin_bp.route("/admin/2fa/disable", methods=["POST"])
@login_required
def admin_2fa_disable():
    """Деактивиране на 2FA за админ"""
    if not isinstance(current_user, AdminUser):
        flash("Нямате достъп.", "error")
        return redirect(url_for("main.index"))

    current_user.disable_2fa()
    flash("2FA е деактивиран.", "success")
    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/admin")
@login_required
def admin_dashboard():
    """Админ панел"""
    if not current_user.is_admin:
        flash("Нямате достъп до админ панела.", "error")
        return redirect(url_for("main.dashboard"))

    requests = Request.query.all()
    logs = RequestLog.query.all()
    volunteers = Volunteer.query.all()
    logs_dict = {}
    for log in logs:
        if log.request_id not in logs_dict:
            logs_dict[log.request_id] = []
        logs_dict[log.request_id].append(log)

    # Convert to JSON serializable format
    requests_dict = [
        {
            "id": r.id,
            "name": r.name,
            "phone": r.phone,
            "email": r.email,
            "location": r.location,
            "category": r.category,
            "description": r.description,
            "status": r.status,
            "urgency": r.urgency,
        }
        for r in requests
    ]

    volunteers_dict = [
        {
            "id": v.id,
            "name": v.name,
            "email": v.email,
            "phone": v.phone,
            "location": v.location,
            "skills": v.skills,
        }
        for v in volunteers
    ]

    return render_template(
        "admin_dashboard.html",
        requests={"items": requests},
        logs_dict=logs_dict,
        requests_json=requests_dict,
        volunteers=volunteers,
        volunteers_json=volunteers_dict,
    )


@admin_bp.route("/admin_volunteers")
@login_required
def admin_volunteers():
    """Управление на доброволци"""
    if not current_user.is_admin:
        flash("Нямате достъп.", "error")
        return redirect(url_for("main.index"))

    volunteers = Volunteer.query.all()
    return render_template("admin_volunteers.html", volunteers=volunteers)


@admin_bp.route("/admin_volunteers/add", methods=["GET", "POST"])
@login_required
def add_volunteer():
    """Добавяне на доброволец"""
    if not current_user.is_admin:
        flash("Нямате достъп.", "error")
        return redirect(url_for("main.index"))

    if request.method == "POST":
        volunteer = Volunteer(
            name=request.form["name"],
            email=request.form["email"],
            phone=request.form["phone"],
            location=request.form["location"],
            skills=request.form.get("skills", ""),
        )
        db.session.add(volunteer)
        db.session.commit()
        flash("Доброволецът е добавен успешно!", "success")
        return redirect(url_for("admin.admin_volunteers"))

    return render_template("add_volunteer.html")


@admin_bp.route("/delete_volunteer/<int:id>", methods=["POST"])
@login_required
def delete_volunteer(id):
    """Изтриване на доброволец"""
    if not current_user.is_admin:
        flash("Нямате достъп.", "error")
        return redirect(url_for("main.index"))

    volunteer = Volunteer.query.get_or_404(id)
    db.session.delete(volunteer)
    db.session.commit()
    flash("Доброволецът е изтрит успешно!", "success")
    return redirect(url_for("admin.admin_volunteers"))


@admin_bp.route("/admin_volunteers/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_volunteer(id):
    """Редактиране на доброволец"""
    if not current_user.is_admin:
        flash("Нямате достъп.", "error")
        return redirect(url_for("main.index"))

    volunteer = Volunteer.query.get_or_404(id)
    if request.method == "POST":
        volunteer.name = request.form["name"]
        volunteer.email = request.form["email"]
        volunteer.phone = request.form["phone"]
        volunteer.location = request.form["location"]
        volunteer.skills = request.form.get("skills", "")
        db.session.commit()
        flash("Промените са запазени!", "success")
        return redirect(url_for("admin.admin_volunteers"))

    return render_template("edit_volunteer.html", volunteer=volunteer)


@admin_bp.route("/export_volunteers")
@login_required
def export_volunteers():
    """Експорт на доброволци като CSV"""
    if not current_user.is_admin:
        flash("Нямате достъп.", "error")
        return redirect(url_for("main.index"))

    from io import StringIO
    import csv
    from flask import Response

    volunteers = Volunteer.query.all()
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(["Име", "Имейл", "Телефон", "Град/регион", "Умения"])
    for v in volunteers:
        cw.writerow([v.name, v.email, v.phone, v.location, v.skills])

    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=volunteers.csv"},
    )


@admin_bp.route("/update_status/<int:req_id>", methods=["POST"])
@login_required
def update_status(req_id):
    """Обновяване статуса на заявка"""
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403

    new_status = request.form.get("status")
    if new_status:
        req = Request.query.get_or_404(req_id)
        old_status = req.status
        req.status = new_status
        db.session.commit()

        # Log the status change
        log_entry = RequestLog(
            request_id=req_id,
            status=new_status,
            changed_by=current_user.id if hasattr(current_user, "id") else None,
        )
        db.session.add(log_entry)
        db.session.commit()

    return jsonify({"success": True})
