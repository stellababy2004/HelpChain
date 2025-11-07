import functools
import os
import sqlite3
import traceback
from datetime import datetime

_orig_connect = sqlite3.connect


@functools.wraps(_orig_connect)
def _wrapped_connect(*args, **kwargs):
    try:
        print("[debug_sqlite_connect] sqlite3.connect called with args:", args, kwargs)
        stack = traceback.format_stack(limit=20)
        # write a compact, file-backed trace to help aggregate callsites during traced runs
        try:
            trace_dir = os.path.join(os.path.dirname(__file__), "tools")
            os.makedirs(trace_dir, exist_ok=True)
            trace_file = os.path.join(trace_dir, "sqlite_connect_traces.txt")
            with open(trace_file, "a", encoding="utf-8") as f:
                f.write(
                    f"--- sqlite3.connect called: {datetime.utcnow().isoformat()} id={hex(id(args))} args={args!r} kwargs={kwargs!r} ---\n"
                )
                for line in stack:
                    f.write(line)
                f.write("\n")
        except Exception:
            # keep tracing best-effort and not fail the runtime
            pass
    except Exception:
        pass
    return _orig_connect(*args, **kwargs)


sqlite3.connect = _wrapped_connect

# Also wrap sqlite3.Connection.close to report when a connection is closed
if hasattr(sqlite3, "Connection"):
    _Conn = sqlite3.Connection
    _orig_close = _Conn.close

    def _wrapped_close(self, *a, **kw):
        try:
            print(
                f"[debug_sqlite_connect] Connection.close() called for {hex(id(self))}"
            )
        except Exception:
            pass
        return _orig_close(self, *a, **kw)

    try:
        _Conn.close = _wrapped_close
    except Exception:
        pass


# Also wrap the dbapi2 module's connect if present (SQLAlchemy can use sqlite3.dbapi2)
try:
    import sqlite3 as _sqlite_pkg

    dbapi2 = getattr(_sqlite_pkg, "dbapi2", None)
    if dbapi2 is not None and hasattr(dbapi2, "connect"):
        _orig_dbapi2_connect = dbapi2.connect

        @functools.wraps(_orig_dbapi2_connect)
        def _wrapped_dbapi2_connect(*args, **kwargs):
            try:
                stack = traceback.format_stack(limit=20)
                try:
                    trace_dir = os.path.join(os.path.dirname(__file__), "tools")
                    os.makedirs(trace_dir, exist_ok=True)
                    trace_file = os.path.join(trace_dir, "sqlite_connect_traces.txt")
                    with open(trace_file, "a", encoding="utf-8") as f:
                        f.write(
                            f"--- sqlite3.dbapi2.connect called: {datetime.utcnow().isoformat()} id={hex(id(args))} args={args!r} kwargs={kwargs!r} ---\n"
                        )
                        for line in stack:
                            f.write(line)
                        f.write("\n")
                except Exception:
                    pass
            except Exception:
                pass
            return _orig_dbapi2_connect(*args, **kwargs)

        try:
            dbapi2.connect = _wrapped_dbapi2_connect
        except Exception:
            pass
except Exception:
    pass
