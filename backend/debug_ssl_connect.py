import ssl
import sys
import traceback

_orig_ssl_init = getattr(ssl.SSLSocket, "__init__", None)
_orig_ssl_close = getattr(ssl.SSLSocket, "close", None)


def _wrapped_ssl_init(self, *args, **kwargs):
    try:
        print(
            f"[debug_ssl_connect] ssl.SSLSocket.__init__ called for id={hex(id(self))}"
        )
        traceback.print_stack(limit=10)
    except Exception:
        pass
    if _orig_ssl_init:
        return _orig_ssl_init(self, *args, **kwargs)


def _wrapped_ssl_close(self, *args, **kwargs):
    try:
        print(f"[debug_ssl_connect] ssl.SSLSocket.close called for id={hex(id(self))}")
    except Exception:
        pass
    if _orig_ssl_close:
        return _orig_ssl_close(self, *args, **kwargs)


try:
    ssl.SSLSocket.__init__ = _wrapped_ssl_init
    ssl.SSLSocket.close = _wrapped_ssl_close
except Exception:
    pass
