from backend.helpchain_backend.src.app import create_app

app = create_app()
with app.app_context():
    import backend.models as m
    from backend.extensions import db

    names = ["User", "Volunteer", "Request", "AdminUser"]
    print("db is:", db)
    for n in names:
        cls = getattr(m, n, None)
        print(n, "exists=", cls is not None, "is_db_Model=", bool(cls and hasattr(cls, "__table__")), "base=", (cls.__mro__[1].__name__ if cls else None))
    print("metadata tables:", len(db.metadata.tables))
