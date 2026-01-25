from backend.helpchain_backend.src.app import create_app
app = create_app()
with app.app_context():
    from backend.helpchain_backend.src.routes import main as m
    import inspect
    print(inspect.getsource(m.index))