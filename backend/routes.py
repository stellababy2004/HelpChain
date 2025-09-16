import os
from flask_mail import Mail, Message
from dotenv import load_dotenv

load_dotenv()

app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER")
app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT"))
app.config["MAIL_USE_TLS"] = os.environ.get("MAIL_USE_TLS") == "True"
app.config["MAIL_USE_SSL"] = os.environ.get("MAIL_USE_SSL") == "True"
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_DEFAULT_SENDER")

mail = Mail(app)


@app.route("/volunteer_register", methods=["GET", "POST"])
def volunteer_register():
    form = VolunteerRegisterForm()
    if form.validate_on_submit():
        # ... запис в базата данни ...
        msg = Message(
            subject="Нова регистрация на доброволец",
            recipients=["contact@helpchain.live"],
            body=f"Име: {form.name.data}\nИмейл: {form.email.data}\nТелефон: {form.phone.data}\nЛокация: {form.location.data}",
        )
        mail.send(msg)
        flash("Успешна регистрация!", "success")
        return redirect(url_for("home"))
    return render_template("volunteer_register.html", form=form)
