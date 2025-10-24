import json
from pathlib import Path

from appy import app, db

# Опит за модели от двата възможни модула
try:
    from models_with_analytics import Permission, Role
except Exception:
    from models import Permission, Role  # fallback


def get_or_create_permission(code: str, description: str | None = None):
    perm = db.session.execute(
        db.select(Permission).filter_by(codename=code)
    ).scalar_one_or_none()
    if perm:
        return perm
    perm = Permission(
        name=code.replace(":", " ").title() if hasattr(Permission, "name") else None,
        codename=code,
        description=description if hasattr(Permission, "description") else None,
    )
    db.session.add(perm)
    return perm


def get_or_create_role(name: str, slug: str | None, description: str | None):
    q = db.select(Role).filter_by(name=name)
    role = db.session.execute(q).scalar_one_or_none()
    if role:
        # обновяваме описанието/slug ако колоните съществуват
        if hasattr(role, "slug") and slug:
            role.slug = slug
        if hasattr(role, "description") and description:
            role.description = description
        return role
    kwargs = {"name": name}
    if hasattr(Role, "slug"):
        kwargs["slug"] = slug
    if hasattr(Role, "description"):
        kwargs["description"] = description
    role = Role(**kwargs)
    db.session.add(role)
    return role


def ensure_rel(role, perm):
    """
    Закачва perm към role, ако нямат връзка.
    Работи и при relationship collection (role.permissions).
    """
    if not hasattr(role, "permissions"):
        return  # няма релация в модела – нищо не правим
    # проверка по code/ id
    for p in role.permissions:
        if (
            getattr(p, "id", None) == getattr(perm, "id", object())
            or getattr(p, "codename", None) == perm.codename
        ):
            return
    role.permissions.append(perm)


def main():
    roles_path = Path(__file__).with_name("roles.json")
    if not roles_path.exists():
        raise SystemExit(f"roles.json не е намерен: {roles_path}")

    data = json.loads(roles_path.read_text(encoding="utf-8"))

    created_roles = 0
    created_perms = 0

    with app.app_context():
        for r in data.get("roles", []):
            role = get_or_create_role(r["name"], r.get("slug"), r.get("description"))
            # Създаваме всички разрешения от списъка
            for code in r.get("permissions", []):
                perm = db.session.execute(
                    db.select(Permission).filter_by(codename=code)
                ).scalar_one_or_none()
                if not perm:
                    perm = get_or_create_permission(code)
                    created_perms += 1
                ensure_rel(role, perm)
            created_roles += 1

        db.session.commit()

    print("[OK] Ролите са синхронизирани.")
    print(f"  Роли обработени: {created_roles}")
    print(f"  Нови permissions: {created_perms}")


if __name__ == "__main__":
    main()
