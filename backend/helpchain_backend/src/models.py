from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import pyotp
from werkzeug.security import generate_password_hash, check_password_hash

from .extensions import db


class Request(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    location = db.Column(db.String(100))
    category = db.Column(db.String(50))
    description = db.Column(db.Text)
    urgency = db.Column(db.String(20), default="normal")
    status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class RequestLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("request.id"))
    action = db.Column(db.String(50))
    old_status = db.Column(db.String(20))
    new_status = db.Column(db.String(20))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Volunteer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    skills = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(150), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AdminUser(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True)
    email = db.Column(db.String(120), unique=True)
    password_hash = db.Column(db.String(128))
    twofa_secret = db.Column(db.String(32))
    twofa_enabled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def enable_2fa(self):
        if not self.twofa_secret:
            self.twofa_secret = pyotp.random_base32()
        self.twofa_enabled = True

    def disable_2fa(self):
        self.twofa_enabled = False
        self.twofa_secret = None

    def verify_totp(self, token):
        if not self.twofa_secret:
            return False
        totp = pyotp.TOTP(self.twofa_secret)
        return totp.verify(token)

    def get_totp_uri(self):
        if not self.twofa_secret:
            self.twofa_secret = pyotp.random_base32()
        totp = pyotp.TOTP(self.twofa_secret)
        return totp.provisioning_uri(name=self.username, issuer_name="HelpChain")
