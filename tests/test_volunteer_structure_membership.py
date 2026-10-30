import pytest
from sqlalchemy.exc import IntegrityError

from backend.models import Structure, Volunteer, VolunteerStructureMembership


def _rows(session):
    volunteer = Volunteer(name="Test volunteer", email="membership-model@test.local")
    structure_a = Structure(name="Membership A", slug="membership-a")
    structure_b = Structure(name="Membership B", slug="membership-b")
    session.add_all([volunteer, structure_a, structure_b])
    session.flush()
    return volunteer, structure_a, structure_b


def test_membership_supports_independent_structure_statuses(session):
    volunteer, structure_a, structure_b = _rows(session)
    session.add_all(
        [
            VolunteerStructureMembership(
                volunteer_id=volunteer.id,
                structure_id=structure_a.id,
                status="approved",
            ),
            VolunteerStructureMembership(
                volunteer_id=volunteer.id,
                structure_id=structure_b.id,
                status="pending",
            ),
        ]
    )
    session.commit()

    rows = (
        session.query(VolunteerStructureMembership)
        .filter_by(volunteer_id=volunteer.id)
        .order_by(VolunteerStructureMembership.structure_id)
        .all()
    )
    assert [row.status for row in rows] == ["approved", "pending"]


def test_membership_rejects_duplicate_volunteer_structure(session):
    volunteer, structure_a, _structure_b = _rows(session)
    session.add(
        VolunteerStructureMembership(
            volunteer_id=volunteer.id,
            structure_id=structure_a.id,
            status="pending",
        )
    )
    session.commit()
    session.add(
        VolunteerStructureMembership(
            volunteer_id=volunteer.id,
            structure_id=structure_a.id,
            status="approved",
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_membership_rejects_unknown_status(session):
    volunteer, structure_a, _structure_b = _rows(session)
    session.add(
        VolunteerStructureMembership(
            volunteer_id=volunteer.id,
            structure_id=structure_a.id,
            status="active",
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()
