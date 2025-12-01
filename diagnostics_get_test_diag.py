import json
import sys
import traceback

try:
    # appy module lives under the `backend` package
    import backend.appy as appy
    app = getattr(appy, 'app', None)
    if app is None:
        try:
            app = appy.create_app()
        except Exception:
            # best-effort: try create_app with default testing config
            app = appy.create_app({'TESTING': True})
    app.testing = True

    with app.test_client() as client:
        resp = client.get('/__test_diag')
        print('STATUS:', resp.status_code)
        try:
            print(json.dumps(resp.get_json(), indent=2, ensure_ascii=False))
        except Exception:
            print('RAW:', resp.get_data(as_text=True))
except Exception:
    print('DIAGNOSTIC FAILED', file=sys.stderr)
    traceback.print_exc()
    sys.exit(2)
