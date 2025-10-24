"""
Shared Flask app and mail initialization to avoid circular imports
"""

import os
from flask import Flask
from flask_mail import Mail

# Calculate template and static directories
backend_dir = os.path.dirname(__file__)
_templates = [
    os.path.join(backend_dir, "templates"),
    os.path.join(backend_dir, "HelpChain.bg", "backend", "templates"),
    os.path.join(backend_dir, "helpchain-backend", "src", "templates"),
]
_static = [
    os.path.join(backend_dir, "static"),
    os.path.join(backend_dir, "HelpChain.bg", "backend", "static"),
    os.path.join(backend_dir, "helpchain-backend", "src", "static"),
]

# Find existing directories
template_folder = None
static_folder = None
for t_dir in _templates:
    if os.path.isdir(t_dir):
        template_folder = t_dir
        break
for s_dir in _static:
    if os.path.isdir(s_dir):
        static_folder = s_dir
        break

# Create Flask app instance
app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)

# Set basic configuration (the full config is done in appy.py)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

# Initialize Flask-Mail
mail = Mail(app)

# Export app and mail for use in other modules
__all__ = ['app', 'mail']