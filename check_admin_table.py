from backend.helpchain_backend.src.app import create_app
from backend.extensions import db

app = create_app()
with app.app_context():
    print('has admin_users:', 'admin_users' in db.metadata.tables)
    print([k for k in db.metadata.tables.keys() if 'admin' in k])
