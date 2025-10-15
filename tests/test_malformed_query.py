#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to reproduce the malformed SQL query error
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))


def test_volunteer_queries():
    """Test various volunteer query patterns to find malformed SQL"""

    # Import the app and use its context
    from appy import app, db, Volunteer

    with app.app_context():
        print("Testing volunteer queries...")

        # Test 1: Basic query
        try:
            query = db.session.query(Volunteer)
            result = query.limit(5).all()
            print(f"✓ Basic query works: {len(result)} volunteers")
        except Exception as e:
            print(f"✗ Basic query failed: {e}")

        # Test 2: Search query like admin_volunteers
        try:
            search = "test"
            query = db.session.query(Volunteer)
            query = query.filter(
                (Volunteer.name.ilike(f"%{search}%"))
                | (Volunteer.email.ilike(f"%{search}%"))
                | (Volunteer.phone.ilike(f"%{search}%"))
            )
            result = query.limit(5).all()
            print(f"✓ Search query works: {len(result)} results")
        except Exception as e:
            print(f"✗ Search query failed: {e}")

        # Test 3: Pagination query like admin_volunteers
        try:
            search = ""
            location_filter = ""
            sort_by = "name"
            sort_order = "asc"
            page = 1
            per_page = 25

            query = db.session.query(Volunteer)

            # Apply filters
            if search:
                query = query.filter(
                    (Volunteer.name.ilike(f"%{search}%"))
                    | (Volunteer.email.ilike(f"%{search}%"))
                    | (Volunteer.phone.ilike(f"%{search}%"))
                )

            if location_filter:
                query = query.filter(Volunteer.location.ilike(f"%{location_filter}%"))

            # Apply sorting
            if sort_by == "name":
                query = query.order_by(
                    Volunteer.name.asc()
                    if sort_order == "asc"
                    else Volunteer.name.desc()
                )
            elif sort_by == "location":
                query = query.order_by(
                    Volunteer.location.asc()
                    if sort_order == "asc"
                    else Volunteer.location.desc()
                )
            elif sort_by == "created_at":
                query = query.order_by(
                    Volunteer.created_at.asc()
                    if sort_order == "asc"
                    else Volunteer.created_at.desc()
                )
            else:
                query = query.order_by(Volunteer.id.asc())

            # Apply pagination
            total_volunteers = query.count()
            volunteers = query.offset((page - 1) * per_page).limit(per_page).all()

            print(
                f"✓ Pagination query works: {len(volunteers)} volunteers, total: {total_volunteers}"
            )
        except Exception as e:
            print(f"✗ Pagination query failed: {e}")

        # Test 4: Check raw SQL generation
        try:
            query = db.session.query(Volunteer).filter(Volunteer.email.ilike("%test%"))
            sql = str(query.statement.compile(db.engine))
            print(f"✓ SQL generation works: {sql[:100]}...")
        except Exception as e:
            print(f"✗ SQL generation failed: {e}")

        # Test 5: Test with empty search
        try:
            query = db.session.query(Volunteer).filter(Volunteer.email.ilike("%%"))
            result = query.limit(5).all()
            print(f"✓ Empty search works: {len(result)} results")
        except Exception as e:
            print(f"✗ Empty search failed: {e}")

        # Test 6: Test with special characters in search
        try:
            search_terms = ["%", "_", "'", '"', "test%", "%test", "test_test"]
            for term in search_terms:
                try:
                    query = db.session.query(Volunteer).filter(
                        Volunteer.email.ilike(f"%{term}%")
                    )
                    result = query.limit(1).all()
                    print(f"✓ Special char '{term}' works")
                except Exception as e:
                    print(f"✗ Special char '{term}' failed: {e}")
        except Exception as e:
            print(f"✗ Special characters test failed: {e}")


if __name__ == "__main__":
    test_volunteer_queries()
