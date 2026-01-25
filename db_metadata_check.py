from backend.helpchain_backend.src.app import create_app
app = create_app()
with app.app_context():
    from backend.extensions import db
    import backend.models  # важно: да се импортне, за да се регистрират моделите
    print('Tables in metadata:', len(db.metadata.tables))
    print(sorted(db.metadata.tables.keys())[:30])
