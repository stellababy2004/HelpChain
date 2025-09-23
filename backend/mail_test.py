# -*- coding: utf-8 -*-
from flask import Flask, render_template, request
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

app.config["MAIL_SERVER"] = "smtp.zoho.eu"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = "contact@helpchain.live"
app.config["MAIL_PASSWORD"] = "kaHa5fsY5Aph"
app.config["MAIL_DEFAULT_SENDER"] = "contact@helpchain.live"

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

mail = Mail(app)
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    # други полета...

class Request(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('requests', lazy=True))


@app.route("/")
def index():
    try:
        subject = "Test email"
        body = "Hello, this is a test message in plain English. Regards, HelpChain Team"
        msg = Message(subject=subject, recipients=["your_email@gmail.com"])
        msg.body = body
        mail.send(msg)
        return "Email sent successfully!"
    except Exception as e:
        return f"Error: {e}"
    


def send_registration_email(user_email, user_name):
    msg = Message(
        subject="Welcome to HelpChain!",
        recipients=[user_email],
        sender="contact@helpchain.live",
    )
    # Използвай HTML шаблон за имейла
    msg.html = render_template("email_templates/welcome_email.html", name=user_name)
    mail.send(msg)


@app.route("/send_registration")
def send_reg():
    try:
        send_registration_email("your_email@gmail.com", "TestUser")
        return "Registration email sent!"
    except Exception as e:
        return f"Error: {e}"


@app.route("/new_request", methods=["POST"])
def new_request():
    data = request.json
    user = User.query.filter_by(email=data["email"]).first()
    if not user:
        return "User not found", 404
    req = Request(title=data["title"], description=data["description"], user_id=user.id)
    db.session.add(req)
    db.session.commit()
    return "Request created!", 201


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
