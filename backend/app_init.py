from flask import Flask
from flask_mail import Mail

# Create Flask app
app = Flask(__name__)

# Initialize Flask-Mail
mail = Mail(app)
