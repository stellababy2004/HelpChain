from backend.helpchain_backend.src.app import create_app

with create_app().app_context():
    from backend.helpchain_backend.src.extensions import db

    print("Tables:", sorted(db.metadata.tables.keys())[:50])
    print("Total tables:", len(db.metadata.tables))
