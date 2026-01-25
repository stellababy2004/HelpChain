from backend.helpchain_backend.src.app import create_app

app = create_app()

print("== TEMPLATE DEBUG ==")
print("app.root_path:", app.root_path)
print("app.template_folder:", app.template_folder)
print("jinja loader:", app.jinja_loader)
print("searchpath:", getattr(app.jinja_loader, "searchpath", None))

with app.app_context():
    # list a few templates Jinja can see
    env = app.jinja_env
    try:
        names = sorted(env.list_templates())
        print("templates found:", len(names))
        print("sample:", names[:30])
    except Exception as e:
        print("list_templates failed:", e)
