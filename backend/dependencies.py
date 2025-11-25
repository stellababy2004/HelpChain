import functools


# Dummy require_role за Flask (разрешава всички роли)
def require_role(*allowed_roles):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            # Тук може да добавиш реална проверка по сесия/роли ако искаш
            return fn(*args, **kwargs)

        return wrapper

    return decorator
