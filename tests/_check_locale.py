from backend import appy

app = appy.app
with app.test_client() as c:
    resp = c.get("/_locale")
    print("STATUS", resp.status_code)
    print(resp.get_data(as_text=True))
    # Also ensure set_language to bg works
    resp2 = c.get("/set_language/bg", follow_redirects=False)
    print("SET_BG_STATUS", resp2.status_code)
    # Now inspect locale after setting
    resp3 = c.get("/_locale")
    print("AFTER_SET", resp3.get_data(as_text=True))
