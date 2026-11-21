import asyncio
import pytest
from httpx import AsyncClient

"""
run this one file
docker exec -it nirbhor_backend_dev pytest tests/test_auth/test_login.py -v
"""

LOGIN_URL = "/api/v1/auth/login"
SEEKER_REGISTER_URL = "/api/v1/auth/register/seeker"
PROVIDER_REGISTER_URL = "/api/v1/auth/register/provider"


# helper — register and return payload used
async def register_seeker(client: AsyncClient, payload: dict) -> dict:
    response = await client.post(SEEKER_REGISTER_URL, json=payload)
    assert response.status_code == 201
    return payload


class TestPasswordLogin:

    async def test_login_success(
        self,
        client: AsyncClient,
        seeker_payload: dict,
    ):
        """Registered user can login with correct credentials."""
        await register_seeker(client, seeker_payload)
        # force sleep to avoid race condition. (to prevent crash because it Generates 2 jwt in same time and causes unique violation error)
        await asyncio.sleep(1.1)

        response = await client.post(LOGIN_URL, data={
            "username": seeker_payload["phone"],
            "password": seeker_payload["password"],
        })

        assert response.status_code == 200

        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["role"] == "seeker"
        assert "user_id" in data

    async def test_login_sets_httponly_cookie(
        self,
        client: AsyncClient,
        seeker_payload: dict,
    ):
        """Login must set refresh token in HttpOnly cookie for web clients."""
        await register_seeker(client, seeker_payload)

        # force sleep to avoid race condition. (to prevent crash because it Generates 2 jwt in same time and causes unique violation error)
        await asyncio.sleep(1.1)

        response = await client.post(LOGIN_URL, data={
            "username": seeker_payload["phone"],
            "password": seeker_payload["password"],
        })

        assert response.status_code == 200
        assert "refresh_token" in response.cookies

    async def test_login_wrong_password_returns_401(
        self,
        client: AsyncClient,
        seeker_payload: dict,
    ):
        """Wrong password must return 401, not 403 or 500."""
        await register_seeker(client, seeker_payload)

        # force sleep to avoid race condition. (to prevent crash because it Generates 2 jwt in same time and causes unique violation error)
        await asyncio.sleep(1.1)

        response = await client.post(LOGIN_URL, data={
            "username": seeker_payload["phone"],
            "password": "wrongPassword",
        })

        assert response.status_code == 401

    async def test_login_nonexistent_phone_returns_401(
        self,
        client: AsyncClient,
    ):
        """Unregistered phone must return 401."""
        response = await client.post(LOGIN_URL, data={
            "username": "01999999999",
            "password": "somePassword",
        })
        assert response.status_code == 401

    async def test_login_returns_valid_jwt(
        self,
        client: AsyncClient,
        seeker_payload: dict,
    ):
        """Access token must be a valid JWT with correct claims."""
        from app.core.security import Security

        await register_seeker(client, seeker_payload)

        # force sleep to avoid race condition. (to prevent crash because it Generates 2 jwt in same time and causes unique violation error)
        await asyncio.sleep(1.1)

        response = await client.post(LOGIN_URL, data={
            "username": seeker_payload["phone"],
            "password": seeker_payload["password"],
        })

        assert response.status_code == 200

        access_token = response.json()["access_token"]
        payload = Security.decode_access_token(access_token)
        assert payload is not None, "Failed to decode access token"

        assert payload["type"] == "access"
        assert payload["role"] == "seeker"
        assert "sub" in payload
        assert "exp" in payload

    async def test_login_creates_new_session_each_time(
        self,
        client: AsyncClient,
        seeker_payload: dict,
        db_session,
    ):
        """
        Each login creates a separate session row.
        Two logins = two rows in user_sessions.
        This supports multi-device login.
        """
        from sqlalchemy import select, func
        from app.models.user_session_model import UserSession
        from app.models.user_model import User

        await register_seeker(client, seeker_payload)

        # force sleep to avoid race condition. (to prevent crash because it Generates 2 jwt in same time and causes unique violation error)
        await asyncio.sleep(1.1)

        # login twice — simulates two devices
        for _ in range(2):
            response = await client.post(LOGIN_URL, data={
                "username": seeker_payload["phone"],
                "password": seeker_payload["password"],
            })
            assert response.status_code == 200
            # force sleep to avoid race condition. (to prevent crash because it Generates 2 jwt in same time and causes unique violation error)
            await asyncio.sleep(1.1)

        # find the user
        user = await db_session.scalar(
            select(User).where(User.phone_en == seeker_payload["phone"])
        )

        # count sessions — registration creates 1, two logins create 2 more = 3 total
        session_count = await db_session.scalar(
            select(func.count()).where(UserSession.user_id == user.id)
        )
        assert session_count == 3

    async def test_login_sends_form_data_not_json(
        self,
        client: AsyncClient,
        seeker_payload: dict,
    ):
        """
        OAuth2PasswordRequestForm requires form data, not JSON.
        Sending JSON must return 422.
        """
        await register_seeker(client, seeker_payload)

        # sending as JSON instead of form data
        response = await client.post(LOGIN_URL, json={
            "username": seeker_payload["phone"],
            "password": seeker_payload["password"],
        })
        assert response.status_code == 422

    async def test_suspended_user_cannot_login(
        self,
        client: AsyncClient,
        seeker_payload: dict,
        db_session,
    ):
        """Suspended accounts must receive 403, not 200."""
        from sqlalchemy import select
        from app.models.user_model import User

        await register_seeker(client, seeker_payload)

        # suspend the user directly in DB
        user = await db_session.scalar(
            select(User).where(User.phone_en == seeker_payload["phone"])
        )
        user.is_active = False
        await db_session.commit()

        response = await client.post(LOGIN_URL, data={
            "username": seeker_payload["phone"],
            "password": seeker_payload["password"],
        })
        assert response.status_code == 403

    async def test_login_does_not_reveal_which_field_is_wrong(
        self,
        client: AsyncClient,
        seeker_payload: dict,
    ):
        """
        Security: wrong phone and wrong password must return
        identical error messages — no user enumeration.
        """
        await register_seeker(client, seeker_payload)

        wrong_phone = await client.post(LOGIN_URL, data={
            "username": "01999999999",   # doesn't exist
            "password": "anypassword",
        })

        wrong_password = await client.post(LOGIN_URL, data={
            "username": seeker_payload["phone"],  # exists
            "password": "wrongpassword",
        })

        assert wrong_phone.status_code == 401
        assert wrong_password.status_code == 401
        # same error message — attacker can't tell which was wrong
        assert wrong_phone.json()["detail"] == wrong_password.json()["detail"]
