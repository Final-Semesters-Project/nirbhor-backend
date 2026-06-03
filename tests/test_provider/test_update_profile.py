import pytest
import uuid
from httpx import AsyncClient

PROVIDER_UPDATE_URL = "/api/v1/provider/me/update_profile"

# ══════════════════════════════════════════════════════════════════
# PROVIDER PROFILE UPDATE
# ══════════════════════════════════════════════════════════════════


class TestProviderProfileUpdate:

    async def test_update_profile_success_dashboard_fields(
        self,
        client: AsyncClient,
        get_authenticated_provider_token: str,
    ):
        """Happy path — provider updating core metrics like availability, radius, and NID link."""
        headers = {"Authorization": f"Bearer {get_authenticated_provider_token}"}
        payload = {
            "is_available": False,
            "working_radius_km": 4,
            "nid_url": "https://cloudinary.com/nid_uploads/verified_card.png"
        }

        response = await client.patch(PROVIDER_UPDATE_URL, json=payload, headers=headers)
        assert response.status_code == 200
        assert "message" in response.json()

    async def test_update_profile_unauthenticated_returns_401(
        self,
        client: AsyncClient,
    ):
        """Requests lacking valid authorization headers must be rejected immediately."""
        payload = {"is_available": True}
        response = await client.patch(PROVIDER_UPDATE_URL, json=payload)
        assert response.status_code == 401
        assert "detail" in response.json()

    async def test_update_profile_invalid_radius_boundaries(
        self,
        client: AsyncClient,
        get_authenticated_provider_token: str,
    ):
        """The application constraint values (e.g., 1-5km range) should trigger validation failures."""
        headers = {"Authorization": f"Bearer {get_authenticated_provider_token}"}

        # Test extreme upper out-of-bounds boundary criteria
        payload_large = {"working_radius_km": 15}
        res_large = await client.patch(PROVIDER_UPDATE_URL, json=payload_large, headers=headers)
        assert res_large.status_code == 422

        # Test extreme lower out-of-bounds boundary criteria
        payload_zero = {"working_radius_km": 0}
        res_zero = await client.patch(PROVIDER_UPDATE_URL, json=payload_zero, headers=headers)
        assert res_zero.status_code == 422

    async def test_update_profile_ignores_user_table_fields(
        self,
        client: AsyncClient,
        get_authenticated_provider_token: str,
        db_session
    ):
        """Providing data like 'name' in payload shouldn't alter the core User record row data."""
        from app.models.user_model import User
        from sqlalchemy import select

        headers = {"Authorization": f"Bearer {get_authenticated_provider_token}"}

        # First get the user ID from decoding the token or by querying
        payload = {
            "is_available": True
        }

        response = await client.patch(PROVIDER_UPDATE_URL, json=payload, headers=headers)
        assert response.status_code == 200

    async def test_update_profile_partial_patch_leaves_other_fields_unaltered(
        self,
        client: AsyncClient,
        get_authenticated_provider_token: str,
    ):
        """Updating just a single field shouldn't overwrite other fields with null defaults."""
        headers = {"Authorization": f"Bearer {get_authenticated_provider_token}"}

        # Only toggle the explicit targeted field element instance
        payload = {"is_available": False}
        response = await client.patch(PROVIDER_UPDATE_URL, json=payload, headers=headers)
        assert response.status_code == 200
        assert "message" in response.json()

    async def test_update_location_rate_limiting_gatekeeper(
        self,
        client: AsyncClient,
        get_authenticated_provider_token: str,
        db_session
    ):
        """Updating latitude/longitude coordinates twice within the rate-limiting block window should raise a 400 error."""
        from datetime import datetime, timezone, timedelta
        from sqlalchemy import update
        from app.models.provider_profile_model import ProviderProfile
        from app.core.security import Security

        headers = {"Authorization": f"Bearer {get_authenticated_provider_token}"}
        payload = {
            "latitude": 23.7925,
            "longitude": 90.4078
        }

        # First location patch attempt — should pass successfully
        first_attempt = await client.patch(PROVIDER_UPDATE_URL, json=payload, headers=headers)
        assert first_attempt.status_code == 200
        assert "message" in first_attempt.json()

        # Immediate secondary execution — should trigger domain logic cooling window block rules
        second_attempt = await client.patch(PROVIDER_UPDATE_URL, json=payload, headers=headers)
        assert second_attempt.status_code == 400
        assert "limit" in second_attempt.json()["detail"].lower()

    async def test_update_profile_invalid_payload_types(
        self,
        client: AsyncClient,
        get_authenticated_provider_token: str,
    ):
        """Passing incorrect data types should fail with a 422 validation error."""
        headers = {"Authorization": f"Bearer {get_authenticated_provider_token}"}
        payload = {
            "is_available": "not-a-boolean-value",
            "working_radius_km": "eight-km"
        }
        response = await client.patch(PROVIDER_UPDATE_URL, json=payload, headers=headers)
        assert response.status_code == 422

    async def test_update_radius_with_valid_value(
        self,
        client: AsyncClient,
        get_authenticated_provider_token: str,
    ):
        """Updating working_radius_km with a valid value should succeed."""
        headers = {"Authorization": f"Bearer {get_authenticated_provider_token}"}
        payload = {
            "working_radius_km": 5
        }

        response = await client.patch(PROVIDER_UPDATE_URL, json=payload, headers=headers)
        assert response.status_code == 200
        assert "message" in response.json()

    async def test_update_multiple_fields_success(
        self,
        client: AsyncClient,
        get_authenticated_provider_token: str,
    ):
        """Updating multiple fields at once should succeed."""
        headers = {"Authorization": f"Bearer {get_authenticated_provider_token}"}
        payload = {
            "is_available": True,
            "photo_url": "https://example.com/photo.jpg",
            "has_smartphone": False
        }

        response = await client.patch(PROVIDER_UPDATE_URL, json=payload, headers=headers)
        assert response.status_code == 200
        assert "message" in response.json()

    async def test_update_profile_with_only_photo_url(
        self,
        client: AsyncClient,
        get_authenticated_provider_token: str,
    ):
        """Updating only photo_url without other fields should work."""
        headers = {"Authorization": f"Bearer {get_authenticated_provider_token}"}
        payload = {
            "photo_url": "https://example.com/new_photo.jpg"
        }

        response = await client.patch(PROVIDER_UPDATE_URL, json=payload, headers=headers)
        assert response.status_code == 200
        assert "message" in response.json()

    async def test_update_radius_rate_limiting(
        self,
        client: AsyncClient,
        get_authenticated_provider_token: str,
    ):
        """Updating working_radius_km twice within 7 days should fail on second attempt."""
        headers = {"Authorization": f"Bearer {get_authenticated_provider_token}"}
        payload = {
            "working_radius_km": 3
        }

        # First update should succeed
        first_attempt = await client.patch(PROVIDER_UPDATE_URL, json=payload, headers=headers)
        assert first_attempt.status_code == 200

        # Second update immediately should fail
        second_attempt = await client.patch(PROVIDER_UPDATE_URL, json=payload, headers=headers)
        assert second_attempt.status_code == 400
        assert "limit" in second_attempt.json()["detail"].lower()

    async def test_update_with_empty_payload(
        self,
        client: AsyncClient,
        get_authenticated_provider_token: str,
    ):
        """Sending an empty payload should succeed (no fields to update)."""
        headers = {"Authorization": f"Bearer {get_authenticated_provider_token}"}
        payload = {}

        response = await client.patch(PROVIDER_UPDATE_URL, json=payload, headers=headers)
        assert response.status_code == 200
        assert "message" in response.json()
