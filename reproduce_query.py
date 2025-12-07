import os
import sys

sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))
import models
from flask import Flask

from backend.extensions import db

app = Flask(__name__)
app.config['TESTING']=True
app.config['SQLALCHEMY_DATABASE_URI']='sqlite:///:memory:'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS']=False

print('Initializing app and db')
db.init_app(app)
with app.app_context():
    db.create_all()
    u = models.User(username='t', email='e', password_hash='p')
    db.session.add(u)
    db.session.commit()
    print('Inserted user id=', u.id)
    try:
        q = models.User.query.filter_by(username='t').first()
        print('Query result:', q)
    except Exception as e:
        print('Query raised:', e)
    # inspect tables
    try:
        from backend import models as bm
        from backend.extensions import db as ext_db
        print('Flask engine tables:', ext_db.engine.table_names())
    except Exception as e:
        print('Engine inspect error', e)
