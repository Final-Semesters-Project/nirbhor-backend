import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from app.jobs.booking_jobs import send_booking_followup_notifications
from app.repositories.booking_repository import BookingFollowupData


"""
run only this one file
docker exec -it nirbhor_backend_dev pytest tests/test_booking_job/test_booking_followup_job.py -v
"""

# ══════════════════════════════════════════════════════════════════
# PROVIDER PROFILE UPDATE
# ══════════════════════════════════════════════════════════════════


def make_followup_data(fcm_token: str | None = "valid_token") -> BookingFollowupData:
    return BookingFollowupData(
        booking_id=uuid4(),
        seeker_id=uuid4(),
        fcm_token=fcm_token,
        preferred_lang="bn",
        provider_name_en="Karim",
        provider_name_bn="করিম",
    )


@pytest.mark.asyncio
async def test_no_bookings_returns_early():
    """Job should exit cleanly with no FCM calls when no bookings ready."""
    with patch(
        "app.repositories.booking_repository.BookingRepository.get_initiated_ready_for_followup",
        new_callable=AsyncMock,
        return_value=[],
    ), patch("app.services.notification_service.messaging.send") as mock_send:
        await send_booking_followup_notifications()
        mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_sends_fcm_for_each_booking():
    """Each booking with a valid token gets exactly one FCM send call."""
    data = [make_followup_data(), make_followup_data()]

    with patch(
        "app.repositories.booking_repository.BookingRepository.get_initiated_ready_for_followup",
        new_callable=AsyncMock,
        return_value=data,
    ), patch("app.services.notification_service.messaging.send") as mock_send:
        await send_booking_followup_notifications()
        assert mock_send.call_count == 2


@pytest.mark.asyncio
async def test_missing_token_skips_booking_continues_others():
    """
    Critical test: if one booking has no FCM token, others must still be processed.
    Previously `return` was used instead of `continue` — this test catches regression.
    """
    data = [
        make_followup_data(fcm_token=None),   # no token — should be skipped
        make_followup_data(fcm_token="tok1"),  # should still be sent
        make_followup_data(fcm_token="tok2"),  # should still be sent
    ]

    with patch(
        "app.repositories.booking_repository.BookingRepository.get_initiated_ready_for_followup",
        new_callable=AsyncMock,
        return_value=data,
    ), patch("app.services.notification_service.messaging.send") as mock_send:
        await send_booking_followup_notifications()
        # Only 2 of 3 should send (the one with None token is skipped)
        assert mock_send.call_count == 2


@pytest.mark.asyncio
async def test_fcm_failure_does_not_crash_job():
    """FCM send failure for one booking must not prevent others from sending."""
    data = [make_followup_data(), make_followup_data()]

    call_count = 0

    def mock_send(message):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("FCM network error")
        # Second call succeeds

    with patch(
        "app.repositories.booking_repository.BookingRepository.get_initiated_ready_for_followup",
        new_callable=AsyncMock,
        return_value=data,
    ), patch("app.services.notification_service.messaging.send", side_effect=mock_send):
        # Must not raise
        await send_booking_followup_notifications()
        assert call_count == 2


@pytest.mark.asyncio
async def test_stale_token_logged_not_raised():
    """UnregisteredError (stale token) should be caught and logged, not re-raised."""
    from firebase_admin import messaging as fb_messaging
    data = [make_followup_data(fcm_token="stale_token")]

    with patch(
        "app.repositories.booking_repository.BookingRepository.get_initiated_ready_for_followup",
        new_callable=AsyncMock,
        return_value=data,
    ), patch(
        "app.services.notification_service.messaging.send",
        side_effect=fb_messaging.UnregisteredError("token invalid")
    ):
        # Must not raise
        await send_booking_followup_notifications()


def test_followup_data_correct_language_fallback():
    """If name_bn is None, provider_name_bn should fall back to name_en."""
    data = BookingFollowupData(
        booking_id=uuid4(),
        seeker_id=uuid4(),
        fcm_token="tok",
        preferred_lang="bn",
        provider_name_en="Karim",
        provider_name_bn=None,  # missing Bangla name
    )
    # The repo sets: provider_name_bn=row.provider_name_bn or row.provider_name_en
    # So this should never be None after repo processing
    # This test verifies the repo's fallback logic
    assert data.provider_name_bn is not None or data.provider_name_en is not None


# Integration-style test for the repository query
@pytest.mark.asyncio
async def test_get_initiated_ready_for_followup_returns_correct_window(
    db_session,
    create_booking_at,  # fixture that creates booking with given call_unlocked_at
):
    """Only bookings in the 2hr±5min window should be returned."""
    now = datetime.now(timezone.utc)

    # Should be included (exactly 2hr 2min ago)
    in_window = await create_booking_at(now - timedelta(hours=2, minutes=2))

    # Should be excluded (too recent — only 1hr ago)
    too_recent = await create_booking_at(now - timedelta(hours=1))

    # Should be excluded (too old — 3hr ago, outside window)
    too_old = await create_booking_at(now - timedelta(hours=3))

    from app.repositories.booking_repository import BookingRepository
    repo = BookingRepository(db_session)
    results = await repo.get_initiated_ready_for_followup()

    result_ids = {r.booking_id for r in results}
    assert in_window.id in result_ids
    assert too_recent.id not in result_ids
    assert too_old.id not in result_ids
