import os
import sys

sys.path.insert(0, "backend")

from flask import Flask
from models import Volunteer

from extensions import db

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///instance/volunteers.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    volunteers = Volunteer.query.all()
    print(f"Found {len(volunteers)} volunteers:")
    for v in volunteers:
        print(f"  - {v.name} ({v.email})")
