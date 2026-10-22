import pytest


@pytest.fixture
def linked_intervenant(init_test_data, session):
    from backend.models import Intervenant, Structure

    structure = Structure(
        name="Volunteer authorized structure", slug="volunteer-authorized"
    )
    session.add(structure)
    session.flush()
    actor = Intervenant(
        structure_id=structure.id,
        legacy_volunteer_id=init_test_data["volunteer"].id,
        actor_type="volunteer",
        is_active=True,
    )
    session.add(actor)
    session.commit()
    return actor


@pytest.mark.parametrize("request_status", ["open", "in_progress", "done"])
@pytest.mark.parametrize("discovery", ["smart", "basic"])
def test_smart_match_action_agrees_with_help(
    authenticated_volunteer_client,
    init_test_data,
    session,
    request_status,
    linked_intervenant,
    discovery,
    monkeypatch,
):
    from backend.models import Request
    from backend.helpchain_backend.src.services.matching_v1 import (
        _MATCH_CACHE,
        get_matched_requests_v1,
    )

    volunteer = init_test_data["volunteer"]
    volunteer.location = "Paris"
    volunteer.skills = "documents logement transport"
    volunteer.availability = "weekends"
    volunteer.is_active = True
    volunteer.volunteer_onboarded = True
    req = Request(
        title="documents logement transport",
        description="Volunteer match",
        city="Paris",
        priority="urgent",
        status=request_status,
        structure_id=linked_intervenant.structure_id,
    )
    session.add(req)
    session.commit()
    _MATCH_CACHE.clear()
    matches = get_matched_requests_v1(volunteer, min_percent=0)
    if discovery == "basic":
        from backend.helpchain_backend.src.routes import main as main_routes

        monkeypatch.setattr(
            main_routes, "get_matched_requests_v1", lambda *args, **kwargs: []
        )
    dashboard = authenticated_volunteer_client.get("/volunteer/dashboard")
    assert dashboard.status_code == 200
    action = f"/volunteer/requests/{req.id}/help"
    offered = action in dashboard.get_data(as_text=True)
    response = authenticated_volunteer_client.post(action)
    if offered:
        assert response.status_code == 303
    assert offered == (request_status == "open")
    assert (req.id in {r.id for r, _, _ in matches}) == offered
    if not offered:
        assert response.status_code == 404


@pytest.mark.parametrize(
    "change",
    [
        "closed",
        "unlinked",
        "moved",
        "request_moved",
        "inactive",
        "ambiguous",
        "professional",
    ],
)
def test_smart_match_cache_rechecks_eligibility(
    authenticated_volunteer_client, init_test_data, session, linked_intervenant, change
):
    from backend.models import Intervenant, Request
    from backend.helpchain_backend.src.services.matching_v1 import (
        _MATCH_CACHE,
        get_matched_requests_v1,
    )

    volunteer = init_test_data["volunteer"]
    volunteer.location = "Paris"
    volunteer.availability = "weekends"
    volunteer.is_active = True
    req = Request(
        title="Cached match",
        city="Paris",
        status="open",
        structure_id=linked_intervenant.structure_id,
    )
    session.add(req)
    session.commit()
    _MATCH_CACHE.clear()
    assert req.id in {
        r.id for r, _, _ in get_matched_requests_v1(volunteer, min_percent=0)
    }
    if change == "closed":
        req.status = "done"
    elif change == "unlinked":
        linked_intervenant.legacy_volunteer_id = None
    elif change == "moved":
        linked_intervenant.structure_id = init_test_data["structure"].id
    elif change == "request_moved":
        req.structure_id = init_test_data["structure"].id
    elif change == "inactive":
        linked_intervenant.is_active = False
    elif change == "professional":
        linked_intervenant.actor_type = "social_worker"
    else:
        session.add(
            Intervenant(
                legacy_volunteer_id=volunteer.id,
                structure_id=init_test_data["structure"].id,
                is_active=True,
            )
        )
    session.commit()
    assert req.id not in {
        r.id for r, _, _ in get_matched_requests_v1(volunteer, min_percent=0)
    }
    assert (
        authenticated_volunteer_client.post(
            f"/volunteer/requests/{req.id}/help"
        ).status_code
        == 404
    )


@pytest.mark.parametrize("linked", [False, True])
def test_default_tenant_does_not_authorize_volunteer_interest(
    authenticated_volunteer_client, init_test_data, session, linked
):
    from backend.models import Intervenant, Request, Structure
    from backend.helpchain_backend.src.models.volunteer_interest import (
        VolunteerInterest,
    )
    from backend.helpchain_backend.src.services.matching_v1 import (
        _MATCH_CACHE,
        get_matched_requests_v1,
    )

    volunteer = init_test_data["volunteer"]
    volunteer.location = "Paris"
    volunteer.skills = "documents logement transport"
    volunteer.availability = "weekends"
    volunteer.volunteer_onboarded = True
    if linked:
        other = Structure(name="Explicit membership", slug="explicit-membership")
        session.add(other)
        session.flush()
        session.add(
            Intervenant(
                structure_id=other.id,
                legacy_volunteer_id=volunteer.id,
                is_active=True,
            )
        )
    req = Request(
        title="documents logement transport",
        city="Paris",
        status="open",
        priority="urgent",
        structure_id=init_test_data["structure"].id,
    )
    session.add(req)
    session.commit()
    _MATCH_CACHE.clear()
    assert req.id not in {
        r.id for r, _, _ in get_matched_requests_v1(volunteer, min_percent=0)
    }
    action = f"/volunteer/requests/{req.id}/help"
    dashboard = authenticated_volunteer_client.get("/volunteer/dashboard")
    assert dashboard.status_code == 200
    assert action not in dashboard.get_data(as_text=True)
    assert authenticated_volunteer_client.post(action).status_code == 404
    assert (
        VolunteerInterest.query.filter_by(
            volunteer_id=volunteer.id, request_id=req.id
        ).first()
        is None
    )


@pytest.mark.parametrize(
    "restriction", ["other_tenant", "assigned_elsewhere", "archived", "deleted"]
)
def test_unrelated_request_is_not_actionable(
    authenticated_volunteer_client,
    init_test_data,
    session,
    restriction,
    linked_intervenant,
):
    from datetime import datetime
    from backend.models import Request, Structure
    from backend.helpchain_backend.src.models.volunteer_interest import (
        VolunteerInterest,
    )
    from backend.helpchain_backend.src.services.matching_v1 import (
        _MATCH_CACHE,
        get_matched_requests_v1,
    )

    volunteer = init_test_data["volunteer"]
    volunteer.location = "Paris"
    volunteer.skills = "documents logement transport"
    volunteer.availability = "weekends"
    volunteer.is_active = True
    volunteer.volunteer_onboarded = True
    structure_id = linked_intervenant.structure_id
    if restriction == "other_tenant":
        other = Structure(name="Unrelated tenant", slug="unrelated-interest-tenant")
        session.add(other)
        session.flush()
        structure_id = other.id
    req = Request(
        title="documents logement transport",
        city="Paris",
        priority="urgent",
        status="open",
        structure_id=structure_id,
        assigned_volunteer_id=(
            volunteer.id + 100 if restriction == "assigned_elsewhere" else None
        ),
        is_archived=restriction == "archived",
        deleted_at=datetime.now() if restriction == "deleted" else None,
    )
    session.add(req)
    session.commit()
    _MATCH_CACHE.clear()
    assert req.id not in {
        r.id for r, _, _ in get_matched_requests_v1(volunteer, min_percent=0)
    }
    action = f"/volunteer/requests/{req.id}/help"
    dashboard = authenticated_volunteer_client.get("/volunteer/dashboard")
    assert dashboard.status_code == 200
    assert action not in dashboard.get_data(as_text=True)
    assert authenticated_volunteer_client.post(action).status_code == 404
    for endpoint in ("", "/can-help", "/cant-help"):
        path = f"/volunteer/requests/{req.id}{endpoint}"
        response = (
            authenticated_volunteer_client.get(path)
            if not endpoint
            else authenticated_volunteer_client.post(path)
        )
        assert response.status_code == 404
    assert (
        VolunteerInterest.query.filter_by(
            volunteer_id=volunteer.id, request_id=req.id
        ).first()
        is None
    )


class TestVolunteerIntegration:
    """Integration Ñ‚ÐµÑÑ‚Ð¾Ð²Ðµ Ð·Ð° volunteer Ñ„ÑƒÐ½ÐºÑ†Ð¸Ð¾Ð½Ð°Ð»Ð½Ð¾ÑÑ‚"""

    def test_volunteer_login_flow(self, client, init_test_data):
        """Ð¢ÐµÑÑ‚ Ð·Ð° volunteer login Ð¿Ñ€Ð¾Ñ†ÐµÑ"""
        volunteer = init_test_data["volunteer"]

        # Test login via session
        with client.session_transaction() as sess:
            sess["volunteer_logged_in"] = True
            sess["volunteer_id"] = volunteer.id

        # Check dashboard access
        response = client.get("/volunteer_dashboard")
        assert response.status_code == 200

        data = response.get_data(as_text=True)

        # Check if volunteer name is displayed
        if hasattr(volunteer, "name") and volunteer.name:
            assert volunteer.name in data

        # Check for core volunteer dashboard shell
        assert "dashboard" in data.lower() or "volunteer" in data.lower()

        # Check for location form fields
        assert "latitude" in data and "longitude" in data

    def test_volunteer_dashboard_content(
        self, authenticated_volunteer_client, init_test_data
    ):
        """Ð¢ÐµÑÑ‚ Ð·Ð° ÑÑŠÐ´ÑŠÑ€Ð¶Ð°Ð½Ð¸ÐµÑ‚Ð¾ Ð½Ð° volunteer dashboard"""
        client = authenticated_volunteer_client

        response = client.get("/volunteer_dashboard")
        assert response.status_code == 200

        data = response.get_data(as_text=True)

        # Basic content checks
        assert len(data) > 500  # Reasonable content length
        assert "dashboard" in data.lower() or "Ñ‚Ð°Ð±Ð»Ð¾" in data.lower()

    def test_volunteer_location_update(self, authenticated_volunteer_client):
        """Ð¢ÐµÑÑ‚ Ð·Ð° Ð¾Ð±Ð½Ð¾Ð²ÑÐ²Ð°Ð½Ðµ Ð½Ð° Ð»Ð¾ÐºÐ°Ñ†Ð¸ÑÑ‚Ð° Ð½Ð° volunteer"""
        client = authenticated_volunteer_client

        # Get volunteer ID from session
        volunteer_id = 1  # Use a test volunteer ID

        # Test location update API
        response = client.put(
            f"/api/volunteers/{volunteer_id}/location",
            json={"latitude": 42.6977, "longitude": 23.3219, "location": "Ð¡Ð¾Ñ„Ð¸Ñ"},
        )

        # Should succeed
        assert response.status_code in [200, 404]  # 404 if volunteer doesn't exist

    def test_volunteer_profile_access(self, authenticated_volunteer_client):
        """Ð¢ÐµÑÑ‚ Ð·Ð° Ð´Ð¾ÑÑ‚ÑŠÐ¿ Ð´Ð¾ volunteer Ð¿Ñ€Ð¾Ñ„Ð¸Ð»"""
        client = authenticated_volunteer_client

        response = client.get("/volunteer_profile")
        # Profile might not exist, so check reasonable response
        assert response.status_code in [200, 404, 302]

    def test_volunteer_logout(self, authenticated_volunteer_client):
        """Ð¢ÐµÑÑ‚ Ð·Ð° volunteer logout"""
        client = authenticated_volunteer_client

        # Test logout
        response = client.get("/volunteer_logout")
        assert response.status_code in [200, 302]

        # After logout, dashboard should redirect
        response = client.get("/volunteer_dashboard")
        assert response.status_code in [302, 403, 401]

    def test_volunteer_dashboard_empty_state_has_no_fabricated_requests(
        self, authenticated_volunteer_client, monkeypatch
    ):
        """Empty volunteer dashboard should render guidance without demo requests."""
        from backend.helpchain_backend.src.routes import main as main_routes
        from backend.models import Request

        monkeypatch.setattr(
            main_routes,
            "scoped_requests_query",
            lambda: Request.query.filter(Request.id == -1),
        )
        monkeypatch.setattr(
            main_routes, "get_matched_requests_v1", lambda *args, **kwargs: []
        )

        response = authenticated_volunteer_client.get("/volunteer_dashboard")

        assert response.status_code == 200

        data = response.get_data(as_text=True)
        assert "dashboard" in data.lower() or "volunteer" in data.lower()
        assert "Exemple de demande" not in data
        assert "Exemple démo" not in data
        assert "Voir un exemple" not in data

    def test_volunteer_can_express_interest_then_view_request(
        self,
        authenticated_volunteer_client,
        init_test_data,
        session,
        linked_intervenant,
    ):
        """Regression: interest grants access to request details."""
        from backend.models import Request
        from backend.helpchain_backend.src.models.volunteer_interest import (
            VolunteerInterest,
        )

        client = authenticated_volunteer_client
        volunteer = init_test_data["volunteer"]

        req = Request(
            title="Volunteer flow regression test",
            description="Test request",
            status="open",
            structure_id=linked_intervenant.structure_id,
        )
        session.add(req)
        session.commit()

        response = client.post(
            f"/volunteer/requests/{req.id}/help",
            follow_redirects=False,
        )
        assert response.status_code == 303

        interest = VolunteerInterest.query.filter_by(
            volunteer_id=volunteer.id,
            request_id=req.id,
        ).first()

        assert interest is not None
        assert interest.status == "pending"

        response = client.get(f"/volunteer/requests/{req.id}")
        assert response.status_code == 200

        # An existing interest continues to grant viewing after discovery ends.
        req.status = "in_progress"
        session.commit()
        assert client.get(f"/volunteer/requests/{req.id}").status_code == 200

        linked_intervenant.legacy_volunteer_id = None
        volunteer.volunteer_onboarded = True
        session.commit()
        dashboard = client.get("/volunteer/dashboard")
        assert dashboard.status_code == 200
        assert req.title in dashboard.get_data(as_text=True)
        assert client.get(f"/volunteer/requests/{req.id}").status_code == 200

    def test_assigned_volunteer_can_view_request_from_another_structure(
        self, authenticated_volunteer_client, init_test_data, session
    ):
        """Assigned volunteer must not be blocked by legacy default tenant scope."""
        from backend.models import Request, Structure

        volunteer = init_test_data["volunteer"]

        other_structure = Structure(
            name="Other volunteer structure",
            slug="other-volunteer-structure",
        )
        session.add(other_structure)
        session.commit()

        req = Request(
            title="Cross-structure assigned request",
            description="Regression test for legacy volunteer tenant scope",
            status="in_progress",
            structure_id=other_structure.id,
            assigned_volunteer_id=volunteer.id,
        )
        session.add(req)
        session.commit()

        response = authenticated_volunteer_client.get(f"/volunteer/requests/{req.id}")

        assert response.status_code == 200

    @pytest.mark.parametrize(
        "action_path",
        ["can-help", "cant-help"],
    )
    def test_assigned_volunteer_can_signal_on_cross_structure_request(
        self,
        authenticated_volunteer_client,
        init_test_data,
        session,
        action_path,
    ):
        """Assigned volunteer can signal on a request from another structure."""
        from backend.models import Request, Structure

        volunteer = init_test_data["volunteer"]

        other_structure = Structure(
            name="Cross structure signal test",
            slug=f"cross-structure-signal-{action_path}",
        )
        session.add(other_structure)
        session.commit()

        req = Request(
            title="Cross-structure signal request",
            description="Regression test for volunteer action tenant scope",
            status="in_progress",
            structure_id=other_structure.id,
            assigned_volunteer_id=volunteer.id,
        )
        session.add(req)
        session.commit()

        response = authenticated_volunteer_client.post(
            f"/volunteer/requests/{req.id}/{action_path}",
            follow_redirects=False,
        )

        assert response.status_code == 303

    def test_assigned_volunteer_can_help_cross_structure_request(
        self, authenticated_volunteer_client, init_test_data, session
    ):
        """Assigned volunteer can express interest across structures."""
        from backend.models import Request, Structure

        volunteer = init_test_data["volunteer"]

        other_structure = Structure(
            name="Cross structure help test",
            slug="cross-structure-help-test",
        )
        session.add(other_structure)
        session.commit()

        req = Request(
            title="Cross-structure help request",
            description="Regression test for volunteer help tenant scope",
            status="in_progress",
            structure_id=other_structure.id,
            assigned_volunteer_id=volunteer.id,
        )
        session.add(req)
        session.commit()

        response = authenticated_volunteer_client.post(
            f"/volunteer/requests/{req.id}/help",
            follow_redirects=False,
        )

        assert response.status_code == 303
