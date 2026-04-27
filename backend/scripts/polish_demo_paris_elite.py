
from datetime import datetime, timedelta, timezone

from backend.appy import app
from backend.extensions import db
from backend.models import Request, Structure

DEMO_MARKER = "[DEMO] Paris Elite"


FIXES = {
    "apr?s": "apr?s",
    "d?h?bergement": "d?h?bergement",
    "coordonn?er": "coordonner",
    "r?solution": "r?solution",
    "Relogement temporaire apr?s rupture familiale": "Relogement temporaire apr?s rupture familiale",
    "Orientation jeune sans solution d?h?bergement": "Orientation jeune sans solution d?h?bergement",
    "Situation familiale ? coordonner": "Situation familiale ? coordonner",
    "Demande urgente orientation sociale": "Demande urgente d?orientation sociale",
}


def set_if_exists(obj, **values):
    for key, value in values.items():
        if hasattr(obj, key):
            setattr(obj, key, value)


def clean_text(value):
    if not value:
        return value

    for bad, good in FIXES.items():
        value = value.replace(bad, good)

    value = value.replace("?", "?") if "Paris Elite ?" in value else value
    value = value.replace("[DEMO] Paris Elite ?", "[DEMO] Paris Elite ?")
    return value


def polish_requests():
    now = datetime.now(timezone.utc)

    rows = Request.query.filter(Request.title.like("%[DEMO] Paris Elite%")).all()

    if not rows:
        print("No Paris Elite demo requests found.")
        return

    for r in rows:
        if hasattr(r, "title"):
            r.title = clean_text(r.title)

        if hasattr(r, "description"):
            r.description = (
                "Situation de d?monstration ? suivi institutionnel, orientation, "
                "assignation et tra?abilit? op?rationnelle."
            )

        if hasattr(r, "updated_at"):
            r.updated_at = now - timedelta(hours=(r.id or 1) * 2)

    priority_plan = [
        ("Urgence alimentaire famille monoparentale", "critical", "new"),
        ("Relogement temporaire apr?s rupture familiale", "high", "in_progress"),
        ("Isolement senior sans suivi r?gulier", "medium", "assigned"),
        ("Aide administrative droits sociaux", "medium", "assigned"),
        ("Orientation jeune sans solution d?h?bergement", "high", "in_progress"),
        ("Besoin colis alimentaire urgent", "critical", "new"),
        ("Suivi dossier sant? fragile", "medium", "pending"),
        ("Demande accompagnement mobilit?", "low", "done"),
        ("Situation familiale ? coordonner", "high", "in_progress"),
        ("Personne isol?e sans contact r?cent", "medium", "new"),
        ("Demande urgente d?orientation sociale", "critical", "new"),
        ("Suivi de dossier partenaire", "medium", "pending"),
    ]

    for fragment, priority, status in priority_plan:
        r = Request.query.filter(Request.title.like(f"%{fragment}%")).first()
        if r:
            set_if_exists(
                r,
                priority=priority,
                status=status,
                updated_at=now - timedelta(hours=priority_plan.index((fragment, priority, status)) + 1),
            )

    success = Request.query.filter(Request.title.like("%Relogement senior finalis?%")).first()
    if not success:
        structure = Structure.query.filter_by(slug="paris-elite-demo").first() or Structure.query.first()

        success = Request()
        set_if_exists(
            success,
            title="[DEMO] Paris Elite ? Relogement senior finalis? en 48h",
            description=(
                "Cas d?monstrateur cl?tur? : demande re?ue, qualifi?e, orient?e, "
                "suivie et r?solue avec tra?abilit? compl?te."
            ),
            city="Boulogne-Billancourt",
            category="Logement / senior",
            priority="medium",
            status="done",
            structure_id=getattr(structure, "id", None),
            requester_name="Usager Demo Success",
            requester_email="demo.success@example.org",
            requester_phone="+33100000099",
            created_at=now - timedelta(days=6),
            updated_at=now - timedelta(days=1),
        )
        db.session.add(success)

    db.session.commit()

    print(f"Polished requests: {len(rows)}")
    print("Added/verified success story request.")


def print_summary():
    total = Request.query.filter(Request.title.like("%[DEMO] Paris Elite%")).count()
    critical = Request.query.filter(
        Request.title.like("%[DEMO] Paris Elite%"),
        Request.priority.in_(["critical", "high"]),
    ).count()
    done = Request.query.filter(
        Request.title.like("%[DEMO] Paris Elite%"),
        Request.status == "done",
    ).count()
    open_ = Request.query.filter(
        Request.title.like("%[DEMO] Paris Elite%"),
        Request.status != "done",
    ).count()

    print("")
    print("DEMO POLISH SUMMARY")
    print(f"Total demo requests: {total}")
    print(f"Urgent/high priority: {critical}")
    print(f"Open: {open_}")
    print(f"Done: {done}")


def main():
    with app.app_context():
        polish_requests()
        print_summary()


if __name__ == "__main__":
    main()
