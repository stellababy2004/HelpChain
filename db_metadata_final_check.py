from backend.helpchain_backend.src.app import create_app

app = create_app()
with app.app_context():
    import backend.models
    from backend.extensions import db

    print("metadata tables:", len(db.metadata.tables))
    print("users in metadata:", "users" in db.metadata.tables)
    print("volunteers in metadata:", "volunteers" in db.metadata.tables)
    print("requests in metadata:", "requests" in db.metadata.tables)
