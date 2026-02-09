from backend.helpchain_backend.src.app import create_app

app = create_app()
with app.app_context():
    import inspect

    from backend.helpchain_backend.src.routes import main as m

    print(inspect.getsource(m.index))
