import py_compile

try:
    py_compile.compile(
        r"c:\dev\HelpChain\HelpChain.bg\backend\extensions.py", doraise=True
    )
    print("compiled OK")
except Exception as e:
    import traceback

    traceback.print_exc()
