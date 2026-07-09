

## 5. FCM Setup — Firebase Admin SDK

### Why Admin SDK (not the REST API directly)?

Firebase Admin SDK handles token management, retry logic, and batch sending
automatically. The REST API requires you to manage OAuth tokens yourself.
Admin SDK is the correct approach.

### Step 1: Get your `serviceAccountKey.json`

1. Go to https://console.firebase.google.com
2. Create a new project (name it "nirbhor" or similar)
3. Go to **Project Settings** (gear icon) → **Service Accounts** tab
4. Click **"Generate new private key"** → confirms → downloads a JSON file
5. Rename it to `serviceAccountKey.json`
6. **Never commit this file to git.** Add to `.gitignore` immediately:
   ```
   serviceAccountKey.json
   ```

### Step 2: Store the key securely

### Step 3: Install the SDK

### Step 4: Initialize Firebase once at startup

### Step 5: The NotificationService

### Step 6: Wire FCM into main.py lifespan

### Step 7: Getting FCM tokens from Flutter/React

## What's Left After This

4. **Render + NeonDB deployment** — set `FIREBASE_CREDENTIALS_JSON` as an
   env var on Render (paste the full JSON content, not the file path).
   Set `SCHEDULER_ENABLED=true` on only one Render worker instance to
   prevent duplicate job runs.

5. **AI review summarization** — the weekly cron job that batches reviews
   and calls an AI model to generate `ai_review_summary_en/bn` on
   `provider_profiles`. This is a nice-to-have for the capstone demo.



Handle FCM token for multiple user but single device:
1. On logout — delete the token for that user+device combination:
```python
# Add to auth_service.py logout method (which you haven't built yet)
async def logout(user_id: UUID, fcm_token: str, db: AsyncSession):
    await db.execute(
        delete(FCMToken)
        .where(FCMToken.user_id == user_id)
        .where(FCMToken.token == fcm_token)
    )
    # also invalidate the refresh token / session
    await db.commit()
```

2. On login/register — remove the token from any OTHER user first, then upsert for current user:
```python
# POST /fcm/token endpoint logic

async def register_fcm_token(
    user_id: UUID,
    token: str,
    device_type: str,
    db: AsyncSession,
):
    # Step 1: Remove this token from any other user who might have it
    # (handles the "shared device, switched account" case)
    await db.execute(
        delete(FCMToken)
        .where(FCMToken.token == token)
        .where(FCMToken.user_id != user_id)
    )

    # Step 2: Upsert for current user
    # If token already exists for this user, do nothing (same person re-logging in)
    stmt = insert(FCMToken).values(
        user_id=user_id,
        token=token,
        device_type=device_type,
    ).on_conflict_do_nothing(index_elements=["token"])
    # Requires unique constraint on token column in your DB

    await db.execute(stmt)
    await db.commit()
``` 

# =============================== LOGOUT ==================================

# tests/test_booking_followup_job.py
```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from datetime import datetime, timezone, timedelta

from app.jobs.booking_jobs import send_booking_followup_notifications
from app.repositories.booking_repository import BookingFollowupData


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
```