import pytest
from httpx import AsyncClient

"""
run this one file
docker exec -it nirbhor_backend_dev pytest tests/test_auth/test_registration.py -v
"""

SEEKER_URL = "/api/v1/auth/register/seeker"
PROVIDER_URL = "/api/v1/auth/register/provider"


# ══════════════════════════════════════════════════════════════════
# SEEKER REGISTRATION
# ══════════════════════════════════════════════════════════════════

class TestSeekerRegistration:

    async def test_seeker_registration_success(
        self,
        client: AsyncClient,
        seeker_payload: dict,
    ):
        """Happy path — valid data should return 201 with tokens."""
        response = await client.post(SEEKER_URL, json=seeker_payload)

        assert response.status_code == 201

        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["role"] == "seeker"
        assert "user_id" in data

        # tokens should be non-empty strings
        assert len(data["access_token"]) > 0
        assert len(data["refresh_token"]) > 0

    async def test_seeker_registration_sets_httponly_cookie(
        self,
        client: AsyncClient,
        seeker_payload: dict,
    ):
        """Web clients rely on HttpOnly cookie for refresh token."""
        response = await client.post(SEEKER_URL, json=seeker_payload)

        assert response.status_code == 201
        assert "refresh_token" in response.cookies
        cookie = response.cookies["refresh_token"]
        assert cookie is not None

    async def test_seeker_registration_stores_session(
        self,
        client: AsyncClient,
        seeker_payload: dict,
        db_session
    ):
        """Refresh token must be stored in user_sessions table."""
        from sqlalchemy import select
        from app.models.user_session_model import UserSession

        response = await client.post(SEEKER_URL, json=seeker_payload)
        assert response.status_code == 201

        refresh_token = response.json()["refresh_token"]

        session = await db_session.scalar(
            select(UserSession).where(
                UserSession.refresh_token == refresh_token)
        )
        assert session is not None
        assert session.expires_at is not None

    async def test_seeker_duplicate_phone_returns_409(
        self,
        client: AsyncClient,
        seeker_payload: dict,
    ):
        """Same phone number registered twice should fail with 409."""
        # first registration
        first = await client.post(SEEKER_URL, json=seeker_payload)
        assert first.status_code == 201

        # second registration with same phone
        second = await client.post(SEEKER_URL, json=seeker_payload)
        assert second.status_code == 409
        assert "already exists" in second.json()["detail"].lower()

    async def test_seeker_invalid_phone_returns_422(
        self,
        client: AsyncClient,
    ):
        """Invalid phone number format should fail with 422 validation error."""
        response = await client.post(SEEKER_URL, json={
            "name": "Test",
            "phone": "12345",           # invalid — not Bangladeshi format
            "password": "password123",
        })
        assert response.status_code == 422

    async def test_seeker_invalid_phone_formats(
        self,
        client: AsyncClient,
    ):
        """Multiple invalid phone formats."""
        invalid_phones = [
            "12345",            # too short
            "016309565670",     # too long
            "01130956567",      # invalid prefix (011)
            "00630956567",      # doesn't start with 01
            "0163095656a",      # contains letter
            "",                 # empty
        ]
        for phone in invalid_phones:
            response = await client.post(SEEKER_URL, json={
                "name": "Test",
                "phone": phone,
                "password": "password123",
            })
            assert response.status_code == 422, (
                f"Expected 422 for phone '{phone}', got {response.status_code}"
            )

    async def test_seeker_short_password_returns_422(
        self,
        client: AsyncClient,
    ):
        """Password under 8 characters should fail."""
        response = await client.post(SEEKER_URL, json={
            "name": "Test",
            "phone": "01630956567",
            "password": "short",        # only 5 chars
        })
        assert response.status_code == 422

    async def test_seeker_missing_required_fields_returns_422(
        self,
        client: AsyncClient,
    ):
        """Missing name, phone, or password should fail."""
        # missing phone
        response = await client.post(SEEKER_URL, json={
            "name": "Test",
            "password": "password123",
            # phone missing
        })
        assert response.status_code == 422

        # missing password
        response = await client.post(SEEKER_URL, json={
            "name": "Test",
            "phone": "01630956567",
            # password missing
        })
        assert response.status_code == 422

        # empty body
        response = await client.post(SEEKER_URL, json={})
        assert response.status_code == 422

    async def test_seeker_access_token_is_valid_jwt(
        self,
        client: AsyncClient,
        seeker_payload: dict,
    ):
        """Access token should be a decodable JWT with correct claims."""
        from app.core.security import Security

        response = await client.post(SEEKER_URL, json=seeker_payload)
        assert response.status_code == 201

        access_token = response.json()["access_token"]
        payload = Security.decode_access_token(access_token)

        assert payload is not None
        assert payload["type"] == "access"
        assert payload["role"] == "seeker"
        assert "sub" in payload      # user_id
        assert "exp" in payload      # expiry
        assert "iat" in payload      # issued at

    @pytest.mark.parametrize("phone", [
        "12345",
        "016309565670",
        "01130956567",
        "00630956567",
        "0163095656a",
        "",
    ])
    async def test_seeker_invalid_phones(
        self,
        client: AsyncClient,
        phone,
        seeker_payload: dict,
        # seed_test_skills
    ):
        """
        check for invalid phone numbers
        """
        payload = {**seeker_payload, "phone": phone}

        response = await client.post(SEEKER_URL, json=payload)
        assert response.status_code == 422

    async def test_seeker_empty_name_returns_422(
        self,
        client: AsyncClient,
        seeker_payload: dict
    ):
        payload = {**seeker_payload, "name_en": "", "name_bn": ""}
        response = await client.post(SEEKER_URL, json=payload)
        assert response.status_code == 422

    async def test_seeker_whitespace_name_returns_422(
        self,
        client: AsyncClient,
        seeker_payload
    ):
        payload = {**seeker_payload, "name_en": "   ", "name_bn": "   "}
        response = await client.post(SEEKER_URL, json=payload)
        assert response.status_code == 422

    async def test_seeker_response_user_id_is_valid_uuid(
        self,
        client: AsyncClient,
        seeker_payload: dict
    ):
        import uuid
        response = await client.post(SEEKER_URL, json=seeker_payload)
        assert response.status_code == 201

        user_id = response.json()["user_id"]
        try:
            uuid.UUID(user_id)   # raises ValueError if not valid UUID
        except ValueError:
            pytest.fail(f"user_id '{user_id}' is not a valid UUID")

# ══════════════════════════════════════════════════════════════════
# PROVIDER REGISTRATION
# ══════════════════════════════════════════════════════════════════


class TestProviderRegistration:

    async def test_provider_registration_success(
        self,
        client: AsyncClient,
        provider_payload: dict,
        seed_test_skills
    ):
        """Happy path for provider registration."""
        response = await client.post(PROVIDER_URL, json=provider_payload)

        assert response.status_code == 201

        data = response.json()
        assert data["role"] == "provider"
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_provider_invalid_radius_returns_422(
        self,
        client: AsyncClient,
        provider_payload: dict,
    ):
        """Radius outside 1-10km should fail."""
        # too large
        payload = {**provider_payload, "working_radius_km": 15}
        response = await client.post(PROVIDER_URL, json=payload)
        assert response.status_code == 422

        # zero
        payload = {**provider_payload, "working_radius_km": 0}
        response = await client.post(PROVIDER_URL, json=payload)
        assert response.status_code == 422

    async def test_provider_duplicate_phone_returns_409(
        self,
        client: AsyncClient,
        provider_payload: dict,
        seed_test_skills
    ):
        """Same phone registered twice should return 409."""
        first = await client.post(PROVIDER_URL, json=provider_payload)
        assert first.status_code == 201

        second = await client.post(PROVIDER_URL, json=provider_payload)
        assert second.status_code == 409

    async def test_seeker_and_provider_cannot_share_phone(
        self,
        client: AsyncClient,
        seeker_payload: dict,
        provider_payload: dict,
    ):
        """
        Phone uniqueness is global across all roles.
        If a seeker registers with a phone, provider cannot use same phone.
        """
        # same phone for both
        shared_phone = "01630956567"
        seeker = {**seeker_payload, "phone": shared_phone}
        provider = {**provider_payload, "phone": shared_phone}

        seeker_response = await client.post(SEEKER_URL, json=seeker)
        assert seeker_response.status_code == 201

        provider_response = await client.post(PROVIDER_URL, json=provider)
        assert provider_response.status_code == 409

    @pytest.mark.parametrize("phone", [
        "12345",
        "016309565670",
        "01130956567",
        "00630956567",
        "0163095656a",
        "",
    ])
    async def test_provider_invalid_phones(
        self,
        client: AsyncClient,
        phone,
        provider_payload: dict
    ):
        """
        check for invalid phone numbers
        """
        payload = {**provider_payload, "phone": phone}

        response = await client.post(PROVIDER_URL, json=payload)
        assert response.status_code == 422

    async def test_provider_empty_name_returns_422(
        self,
        client: AsyncClient,
        provider_payload: dict
    ):
        payload = {**provider_payload, "name_en": "", "name_bn": ""}
        response = await client.post(PROVIDER_URL, json=payload)
        assert response.status_code == 422

    async def test_provider_whitespace_name_returns_422(
        self,
        client: AsyncClient,
        provider_payload
    ):
        payload = {**provider_payload, "name_en": "   ", "name_bn": "   "}
        response = await client.post(PROVIDER_URL, json=payload)
        assert response.status_code == 422

    async def test_provider_missing_location_returns_422(
        self,
        client: AsyncClient,
        provider_payload: dict
    ):
        payload = {**provider_payload}
        del payload["latitude"]

        response = await client.post(PROVIDER_URL, json=payload)
        assert response.status_code == 422

    async def test_provider_missing_smartphone_flag_returns_422(
            self,
            client: AsyncClient,
            provider_payload: dict):
        payload = {**provider_payload}
        del payload["has_smartphone"]
        response = await client.post(PROVIDER_URL, json=payload)
        assert response.status_code == 422

    async def test_provider_invalid_skill_ids_returns_400(
        self,
        client: AsyncClient,
        provider_payload: dict
    ):
        """Non-existent skill IDs should fail with integrity error."""
        payload = {**provider_payload, "skill_ids": [99999, 88888]}
        response = await client.post(PROVIDER_URL, json=payload)
        assert response.status_code == 400
