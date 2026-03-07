from backend.helpchain_backend.src.app import create_app
from backend.extensions import db
import backend.models as models

DB_URI = "sqlite:///C:/dev/HelpChain.bg/instance/hc_local_dev.db"
app = create_app({
    "SQLALCHEMY_DATABASE_URI": DB_URI,
    "ALLOW_DEFAULT_TENANT_FALLBACK": True,
})

with app.app_context():
    db.create_all()
    if not models.Structure.query.filter_by(slug="default").first():
        db.session.add(models.Structure(name="Default", slug="default"))
        db.session.commit()

app.run(host="127.0.0.1", port=5000, debug=False)
