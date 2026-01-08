def test_print_routes(real_app, capsys):
    rules = sorted((r.rule, r.endpoint, sorted(r.methods)) for r in real_app.url_map.iter_rules())
    for rule, endpoint, methods in rules:
        print(f"{rule:40}  {endpoint:35}  {','.join(m for m in methods if m in {'GET','POST','PUT','DELETE'})}")
    out = capsys.readouterr().out
    assert "/" in out
