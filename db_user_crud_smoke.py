from backend.helpchain_backend.src.app import create_app

app = create_app()
with app.app_context():
    import backend.models as m
    from backend.extensions import db

    u = m.User(email="crud_test@example.com")
    db.session.add(u)
    db.session.commit()
    uid = u.id
    u2 = m.User.query.get(uid)
    print("created id:", uid, "found:", bool(u2))
    u2.email = "crud_test2@example.com"
    db.session.commit()
    u3 = m.User.query.get(uid)
    print("updated email:", u3.email)
    db.session.delete(u3)
    db.session.commit()
    print("deleted exists:", bool(m.User.query.get(uid)))
