from flask import render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
import os

UPLOAD_FOLDER = 'static/profile_pics'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Имейл настройки за Zoho
app.config['MAIL_SERVER'] = 'smtppro.zoho.eu'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'contact@helpchain.live'
app.config['MAIL_PASSWORD'] = 'eAaPfTsEFZNv'

mail = Mail(app)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def send_notification_email(subject, recipients, body):
    msg = Message(subject, recipients=recipients, body=body, sender=app.config['MAIL_USERNAME'])
    mail.send(msg)

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    user = User.query.get(session["user_id"])
    if request.method == "POST":
        user.name = request.form["name"]
        user.email = request.form["email"]
        if "profile_pic" in request.files:
            file = request.files["profile_pic"]
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                user.profile_pic = filename
        db.session.commit()
        flash("Профилът е обновен!", "success")
        return redirect(url_for("profile"))
    return render_template("profile.html", user=user)

@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    user = User.query.get(session["user_id"])
    if request.method == "POST":
        old = request.form["old_password"]
        new = request.form["new_password"]
        if user.check_password(old):
            user.set_password(new)
            db.session.commit()
            flash("Паролата е сменена!", "success")
            return redirect(url_for("profile"))
        else:
            flash("Грешна стара парола!", "danger")
    return render_template("change_password.html")

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        message = request.form["message"]
        # Изпращане на имейл до админ
        send_notification_email(
            "Обратна връзка от HelpChain",
            ["contact@helpchain.live"],
            f"Име: {name}\nИмейл: {email}\nСъобщение: {message}"
        )
        flash("Благодарим за обратната връзка!", "success")
        return redirect(url_for("contact"))
    return render_template("contact.html")

@app.route("/search", methods=["GET"])
def search():
    q = request.args.get("q", "")
    status = request.args.get("status", "")
    location = request.args.get("location", "")
    volunteers = Volunteer.query
    requests_ = Request.query

    if q:
        volunteers = volunteers.filter(Volunteer.name.ilike(f"%{q}%"))
        requests_ = requests_.filter(Request.description.ilike(f"%{q}%"))
    if status:
        requests_ = requests_.filter_by(status=status)
    if location:
        volunteers = volunteers.filter_by(location=location)

    volunteers = volunteers.all()
    requests_ = requests_.all()
    return render_template("search.html", volunteers=volunteers, requests=requests_, q=q, status=status, location=location)

@app.route("/about")
def about():
    return render_template("about.html")

# Пример при нова заявка:
@app.route("/new_request", methods=["POST"])
def new_request():
    # ... твоя код за създаване на заявка ...
    send_notification_email(
        "Нова заявка в HelpChain",
        ["contact@helpchain.live"],
        "Има нова заявка в платформата!"
    )
    flash("Заявката е изпратена!", "success")
    return redirect(url_for("index"))