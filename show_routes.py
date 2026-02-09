from backend.helpchain_backend.src.app import create_app

app = create_app()


def show(ep):
    f = app.view_functions.get(ep)
    if not f:
        print(f"[MISS] {ep}")
        return
    code = getattr(f, "__code__", None)
    print(f"\n=== {ep} ===")
    print("func   :", f)
    print("module :", getattr(f, "__module__", None))
    if code:
        print("file   :", code.co_filename)
        print("line   :", code.co_firstlineno)
    print("name   :", getattr(f, "__name__", None))


show("main.index")
show("index")
