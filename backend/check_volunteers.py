import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from .models import Volunteer
from .extensions import db
from flask import Flask

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///C:/Users/Stella Barbarella/OneDrive/Documents/chatGPT/Projet BG/HelpChain/instance/volunteers.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    volunteers = Volunteer.query.all()
    print(f"Found {len(volunteers)} volunteers:")
    for v in volunteers:
        print(
            f"- {v.name} ({v.email}): Level {v.level}, Points {v.points}, Experience {v.experience}"
        )
