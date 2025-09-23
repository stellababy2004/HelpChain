# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, redirect, url_for, flash, current_app
from flask_mail import Message

from .forms import VolunteerForm
from .models import db, Volunteer

# Blueprint за публични маршрути
routes_bp = Blueprint("routes", __name__)


@routes_bp.route("/volunteer_register", methods=["GET", "POST"])
def volunteer_register():
    form = VolunteerForm()
    if form.validate_on_submit():
        email = form.email.data.strip()

        # предотвратяване на дублиращи регистрации
        if Volunteer.query.filter_by(email=email).first():
            flash("Този имейл вече е регистриран!", "danger")
            return redirect(url_for("routes.volunteer_register"))

        # запис в базата
        v = Volunteer(
            name=form.name.data.strip(),
            email=email,
            phone=form.phone.data.strip(),
            location=form.location.data.strip(),
        )
        db.session.add(v)
        db.session.commit()

        # имейл известие – използваме вече инициализирания Mail от app
        sender = (
            current_app.config.get("MAIL_DEFAULT_SENDER")
            or current_app.config.get("MAIL_USERNAME")
        )
        if sender:
            msg = Message(
                subject="Нова регистрация на доброволец",
                recipients=[sender],
                body=(
                    f"Име: {form.name.data}\n"
                    f"Имейл: {form.email.data}\n"
                    f"Телефон: {form.phone.data}\n"
                    f"Локация: {form.location.data}"
                ),
            )
            # Mail е достъпен през current_app.extensions["mail"]
            current_app.extensions["mail"].send(msg)

        flash("Успешна регистрация!", "success")
        return redirect(url_for("index"))

    return render_template("volunteer_register.html", form=form)
