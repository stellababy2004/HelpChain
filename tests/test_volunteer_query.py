import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from appy import Volunteer, app, db

with app.app_context():
    try:
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

        print("Query created successfully")

        # Test count
        print("Testing count...")
        count = query.count()
        print(f"Count result: {count}")

        # Test pagination
        print("Testing pagination...")
        page = 1
        per_page = 25
        volunteers = query.offset((page - 1) * per_page).limit(per_page).all()
        print(f"Pagination result: {len(volunteers)} items")

        print("All tests completed successfully")
    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
