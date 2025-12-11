"""Test-only instrumentation for SQLAlchemy engines/sessions.

This module is imported only when HELPCHAIN_TEST_DEBUG=="1" to avoid
affecting production. It wraps db.session.commit/flush to print bind
info and attaches engine.connect handlers to log which engine creates
DBAPI connections during tests.
"""

import os

try:
    from backend.extensions import db
except Exception:
    db = None

if os.environ.get("HELPCHAIN_TEST_DEBUG") == "1" and db is not None:
    try:
        # Wrap commit/flush
        sess = getattr(db, "session", None)
        if sess is not None:
            try:
                orig_commit = sess.commit

                def commit_and_log(*a, **kw):
                    try:
                        bind = getattr(sess, "bind", None)
                        bind_id = id(bind) if bind is not None else None
                        try:
                            bind_url = getattr(bind, "url", None)
                        except Exception:
                            bind_url = None
                        print(
                            f"[EXT DEBUG] session.commit called session_id={id(sess)} bind_id={bind_id} bind_url={bind_url}"
                        )
                    except Exception:
                        pass
                    return orig_commit(*a, **kw)

                sess.commit = commit_and_log
            except Exception:
                pass

            try:
                orig_flush = sess.flush

                def flush_and_log(*a, **kw):
                    try:
                        bind = getattr(sess, "bind", None)
                        bind_id = id(bind) if bind is not None else None
                        try:
                            bind_url = getattr(bind, "url", None)
                        except Exception:
                            bind_url = None
                        print(
                            f"[EXT DEBUG] session.flush called session_id={id(sess)} bind_id={bind_id} bind_url={bind_url}"
                        )
                    except Exception:
                        pass
                    return orig_flush(*a, **kw)

                sess.flush = flush_and_log
            except Exception:
                pass
    except Exception:
        pass

    try:
        from sqlalchemy import event

        engines = []
        try:
            if hasattr(db, "engines"):
                try:
                    engines.extend(list(db.engines.values()))
                except Exception:
                    try:
                        for e in db.engines:
                            engines.append(e)
                    except Exception:
                        pass
        except Exception:
            pass

        try:
            try:
                default_eng = db.get_engine()
            except Exception:
                default_eng = getattr(db, "engine", None)
            if default_eng is not None:
                engines.append(default_eng)
        except Exception:
            pass

        uniq = {}
        for e in engines:
            try:
                if e is None:
                    continue
                uniq[id(e)] = e
            except Exception:
                pass

        for eng in list(uniq.values()):
            try:

                def on_connect(dbapi_conn, conn_rec, eng=eng):
                    try:
                        try:
                            url = getattr(eng, "url", None)
                        except Exception:
                            url = None
                        print(
                            f"[EXT DEBUG] engine.connect event engine_id={id(eng)} url={url} dbapi_conn={id(dbapi_conn)}"
                        )
                    except Exception:
                        pass

                event.listen(eng, "connect", on_connect)
            except Exception:
                pass
    except Exception:
        pass
