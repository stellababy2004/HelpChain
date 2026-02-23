import pytest


@pytest.mark.usefixtures("real_app")
def test_volunteer_query_count(real_app):
    from backend.extensions import db
    from backend.models import Volunteer

    with real_app.app_context():
        # Test the exact query pattern from admin_volunteers
        query = db.session.query(Volunteer)

        # Apply search filter like in the route
        search = ""  # Empty search
        location_filter = ""  # Empty location filter

        if search:
            query = query.filter(
                (Volunteer.name.ilike(f"%{search}%"))
                | (Volunteer.email.ilike(f"%{search}%"))
                | (Volunteer.phone.ilike(f"%{search}%"))
            )

        if location_filter:
            query = query.filter(Volunteer.location.ilike(f"%{location_filter}%"))

        # Test count
        count = query.count()
        assert isinstance(count, int)

        # Test pagination
        page = 1
        per_page = 25
        volunteers = query.offset((page - 1) * per_page).limit(per_page).all()
        assert isinstance(volunteers, list)
