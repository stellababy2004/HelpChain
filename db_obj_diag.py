from backend.helpchain_backend.src.app import create_app
app = create_app()
with app.app_context():
    from backend.helpchain_backend.src.extensions import db as ext_db
    import backend.models as m
    print('extensions.db id:', id(ext_db))
    print('models.db exists:', hasattr(m, 'db'))
    if hasattr(m, 'db'):
        print('models.db id:', id(m.db))
        print('same db object:', m.db is ext_db)
    print('ext metadata tables:', len(ext_db.metadata.tables))
    if hasattr(m, 'db'):
        print('models metadata tables:', len(m.db.metadata.tables))
