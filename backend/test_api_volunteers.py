from appy import app, db

from .models import Volunteer


class TestVolunteerAPI:
    """Test cases for volunteer-related API endpoints."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()

    def teardown_method(self):
        """Clean up after each test method."""
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            # Best-effort: dispose engine to close any DBAPI connections
            # left open by SQLAlchemy internals so tests don't leak sqlite3
            # Connection objects. Swallow errors to remain robust across
            # different SQLAlchemy versions and DB backends.
            try:
                db.engine.dispose()
            except Exception:
                pass

    def test_get_nearby_volunteers_success(self):
        """Test successful retrieval of nearby volunteers."""
        with self.app.app_context():
            # Create test volunteers
            vol1 = Volunteer(
                name="Иван Иванов",
                email="ivan@example.com",
                phone="+359123456789",
                skills="Помощ при пазаруване",
                location="София",
                latitude=42.6977,
                longitude=23.3219,
            )
            vol2 = Volunteer(
                name="Мария Петрова",
                email="maria@example.com",
                phone="+359987654321",
                skills="Транспорт",
                location="Пловдив",
                latitude=42.1354,
                longitude=24.7453,
            )
            vol3 = Volunteer(
                name="Георги Димитров",
                email="georgi@example.com",
                phone="+359555666777",
                skills="Консултации",
                location="София",
                latitude=42.7,
                longitude=23.3,
            )
            db.session.add_all([vol1, vol2, vol3])
            db.session.commit()

            # Test nearby search from Sofia center
            response = self.client.get(
                "/api/volunteers/nearby?lat=42.6977&lng=23.3219&radius=50"
            )
            assert response.status_code == 200

            data = response.get_json()
            assert "volunteers" in data
            assert "count" in data
            assert "search_location" in data
            assert "radius_km" in data

            # Should find at least 2 volunteers in Sofia area
            assert data["count"] >= 2

            # Check that volunteers are sorted by distance
            volunteers = data["volunteers"]
            for i in range(len(volunteers) - 1):
                assert volunteers[i]["distance_km"] <= volunteers[i + 1]["distance_km"]

            # Check volunteer data structure
            for vol in volunteers:
                assert "id" in vol
                assert "name" in vol
                assert "latitude" in vol
                assert "longitude" in vol
                assert "distance_km" in vol

    def test_get_nearby_volunteers_no_location(self):
        """Test nearby search when no volunteers have location data."""
        with self.app.app_context():
            # Create volunteer without location
            vol = Volunteer(
                name="Иван Без Координати",
                email="ivan2@example.com",
                skills="Обща помощ",
            )
            db.session.add(vol)
            db.session.commit()

            response = self.client.get(
                "/api/volunteers/nearby?lat=42.6977&lng=23.3219&radius=10"
            )
            assert response.status_code == 200

            data = response.get_json()
            assert data["count"] == 0
            assert len(data["volunteers"]) == 0

    def test_get_nearby_volunteers_invalid_params(self):
        """Test nearby search with invalid parameters."""
        # Invalid latitude
        response = self.client.get(
            "/api/volunteers/nearby?lat=invalid&lng=23.3219&radius=10"
        )
        assert response.status_code == 400
        assert "error" in response.get_json()

        # Invalid longitude
        response = self.client.get(
            "/api/volunteers/nearby?lat=42.6977&lng=invalid&radius=10"
        )
        assert response.status_code == 400

        # Invalid radius
        response = self.client.get(
            "/api/volunteers/nearby?lat=42.6977&lng=23.3219&radius=invalid"
        )
        assert response.status_code == 400

    def test_update_volunteer_location_success(self):
        """Test successful update of volunteer location."""
        with self.app.app_context():
            # Create test volunteer
            vol = Volunteer(
                name="Тест Доброволец", email="test@example.com", skills="Тест умения"
            )
            db.session.add(vol)
            db.session.commit()
            vol_id = vol.id

            # Update location
            update_data = {
                "latitude": 42.6977,
                "longitude": 23.3219,
                "location": "София",
            }
            response = self.client.put(
                f"/api/volunteers/{vol_id}/location", json=update_data
            )
            assert response.status_code == 200

            data = response.get_json()
            assert data["success"]
            assert data["volunteer_id"] == vol_id
            assert data["location"]["lat"] == 42.6977
            assert data["location"]["lng"] == 23.3219
            assert data["location"]["text"] == "София"

            # Verify in database
            updated_vol = db.session.get(Volunteer, vol_id)
            assert updated_vol.latitude == 42.6977
            assert updated_vol.longitude == 23.3219
            assert updated_vol.location == "София"

    def test_update_volunteer_location_partial_data(self):
        """Test update location with only coordinates (no location string)."""
        with self.app.app_context():
            # Create test volunteer
            vol = Volunteer(
                name="Тест Доброволец 2",
                email="test2@example.com",
                location="Стара Загора",
            )
            db.session.add(vol)
            db.session.commit()
            vol_id = vol.id

            # Update only coordinates
            update_data = {"latitude": 42.5, "longitude": 25.6}
            response = self.client.put(
                f"/api/volunteers/{vol_id}/location", json=update_data
            )
            assert response.status_code == 200

            # Verify location string is preserved
            updated_vol = db.session.get(Volunteer, vol_id)
            assert updated_vol.latitude == 42.5
            assert updated_vol.longitude == 25.6
            assert updated_vol.location == "Стара Загора"  # Should be unchanged

    def test_update_volunteer_location_not_found(self):
        """Test update location for non-existent volunteer."""
        update_data = {"latitude": 42.6977, "longitude": 23.3219, "location": "София"}
        response = self.client.put("/api/volunteers/99999/location", json=update_data)
        assert response.status_code == 404
        assert "error" in response.get_json()

    def test_update_volunteer_location_invalid_data(self):
        """Test update location with invalid data."""
        with self.app.app_context():
            # Create test volunteer
            vol = Volunteer(name="Тест", email="test@example.com")
            db.session.add(vol)
            db.session.commit()
            vol_id = vol.id

            # Missing latitude
            response = self.client.put(
                f"/api/volunteers/{vol_id}/location", json={"longitude": 23.3219}
            )
            assert response.status_code == 400

            # Missing longitude
            response = self.client.put(
                f"/api/volunteers/{vol_id}/location", json={"latitude": 42.6977}
            )
            assert response.status_code == 400

            # Invalid latitude type
            response = self.client.put(
                f"/api/volunteers/{vol_id}/location",
                json={"latitude": "invalid", "longitude": 23.3219},
            )
            assert response.status_code == 400

            # Invalid longitude type
            response = self.client.put(
                f"/api/volunteers/{vol_id}/location",
                json={"latitude": 42.6977, "longitude": "invalid"},
            )
            assert response.status_code == 400
