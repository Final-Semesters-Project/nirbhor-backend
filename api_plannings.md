**Next batch (core app flows):**
- `GET /api/v1/urgent/broadcast/{id}/status` — seeker polls to see if broadcast was claimed (or use FCM)

**After that (admin panel):**
- `GET /api/v1/admin/dashboard` — counts summary
- `GET /api/v1/admin/verifications` — pending verification list
- `PATCH /api/v1/admin/verifications/{provider_id}` — approve/reject
- `GET /api/v1/admin/reports` — flagged profiles
- `PATCH /api/v1/admin/reports/{report_id}` — dismiss/suspend
- `GET /api/v1/admin/users` — user list with filters
- `PATCH /api/v1/admin/users/{user_id}/toggle` — enable/disable account
- `GET /api/v1/admin/analytics` — stats + graphs

# Nirbhor — Provider Public Profile, Broadcast Status, Admin APIs + FCM Setup

## File Map

```
app/
├── schemas/
│   ├── provider_schema.py     ← add PublicProviderProfile response
│   ├── admin_schema.py        ← new: all admin response schemas
│   └── urgent_schema.py       ← add BroadcastStatusResponse
├── repositories/
│   ├── provider_repository.py ← add get_public_profile
│   ├── admin_repository.py    ← new
│   └── urgent_repository.py   ← add get_broadcast_status
├── services/
│   ├── provider_service.py    ← add get_public_profile
│   ├── admin_service.py       ← new
│   └── urgent_service.py      ← add get_broadcast_status
├── api/v1/
│   ├── providers.py           ← add GET /{provider_id}/public
│   ├── admin.py               ← new
│   └── urgent.py              ← add GET /{id}/status
└── services/
    └── notification_service.py ← FCM implementation
```


## 1. Schemas

### `app/schemas/provider_schema.py` — add public profile response

### `app/schemas/urgent_schema.py` — add status response

### `app/schemas/admin_schema.py` — new

## 2. Repositories

### `app/repositories/provider_repository.py` — add public profile fetch

### `app/repositories/urgent_repository.py` — add status fetch

### `app/repositories/admin_repository.py` — new

```python


class AdminRepository:
    # ── Dashboard ─────────────────────────────────────────────────────────────

    # ── Verifications ─────────────────────────────────────────────────────────

    # ── Reports ───────────────────────────────────────────────────────────────

    # ── Users ─────────────────────────────────────────────────────────────────

    # ── Analytics ─────────────────────────────────────────────────────────────

    async def get_analytics(self) -> dict:
        now = datetime.now(timezone.utc)

        total_users = await self.db.scalar(select(func.count()).select_from(User))
        total_bookings = await self.db.scalar(select(func.count()).select_from(Booking))
        avg_rating = await self.db.scalar(
            select(func.avg(ProviderProfile.average_rating))
            .where(ProviderProfile.average_rating.is_not(None))
        )
        seeker_count = await self.db.scalar(
            select(func.count()).select_from(User).where(User.role == Role.SEEKER)
        )
        provider_count = await self.db.scalar(
            select(func.count()).select_from(User).where(User.role == Role.PROVIDER)
        )
        active_providers = await self.db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == Role.PROVIDER)
            .where(User.last_active_at >= now - timedelta(days=30))
        )

        # Bookings per week for last 8 weeks
        # DATE_TRUNC groups timestamps into week buckets
        from sqlalchemy import text
        weekly_result = await self.db.execute(
            select(
                func.date_trunc("week", Booking.created_at).label("week_start"),
                func.count().label("count"),
            )
            .where(Booking.created_at >= now - timedelta(weeks=8))
            .group_by(text("week_start"))
            .order_by(text("week_start"))
        )
        bookings_per_week = [
            {"week_start": r.week_start, "count": r.count}
            for r in weekly_result.all()
        ]

        seeker_count = seeker_count or 0
        provider_count = provider_count or 0
        ratio = round(seeker_count / provider_count, 2) if provider_count > 0 else None

        return {
            "total_users": total_users or 0,
            "total_bookings": total_bookings or 0,
            "average_provider_rating": round(float(avg_rating), 2) if avg_rating else None,
            "active_providers_count": active_providers or 0,
            "seeker_count": seeker_count,
            "provider_count": provider_count,
            "seeker_to_provider_ratio": ratio,
            "bookings_per_week": bookings_per_week,
        }
```

---

## 3. Services

### `app/services/provider_service.py` — add public profile

### `app/services/urgent_service.py` — add broadcast status

### `app/services/admin_service.py` — new

```python

class AdminService:
    @staticmethod
    async def get_analytics(db: AsyncSession) -> AdminAnalyticsResponse:
        repo = AdminRepository(db)
        data = await repo.get_analytics()
        return AdminAnalyticsResponse(**data)
```

---

## 4. Routers

### `app/api/v1/providers.py` — add public profile endpoint

### `app/api/v1/urgent.py` — add status endpoint

### `app/api/v1/admin.py` — new

```python


# ── Reports ────────────────────────────────────────────────────────────────────

# ── Users ──────────────────────────────────────────────────────────────────────




# ── Analytics ──────────────────────────────────────────────────────────────────

@router.get("/analytics", response_model=AdminAnalyticsResponse)
async def get_analytics(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Stats for admin dashboard — totals, ratios, weekly booking graph data."""
    return await AdminService.get_analytics(db=db)
```

### Register in `app/api/v1/router.py`

```python
from app.api.v1 import admin

api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
```

---

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

For local development: place the file at the project root and reference it
via an env variable. For Render.com production: paste the JSON content as an
environment variable (not a file).

```python
# app/core/config.py — add these settings
FIREBASE_CREDENTIALS_PATH: str = "serviceAccountKey.json"
# OR for production (JSON string in env var):
FIREBASE_CREDENTIALS_JSON: str | None = None
```

### Step 3: Install the SDK

```bash
pip install firebase-admin
```

Add to `requirements.txt`:
```
firebase-admin==6.5.0
```

### Step 4: Initialize Firebase once at startup

```python
# app/core/firebase.py

import json
import firebase_admin
from firebase_admin import credentials, messaging
from loguru import logger

from app.core.config import settings


def init_firebase() -> None:
    """
    Initialize Firebase Admin SDK once at app startup.
    Supports both file path (local dev) and JSON string (Render production).
    """
    if firebase_admin._apps:
        return  # already initialized

    try:
        if settings.FIREBASE_CREDENTIALS_JSON:
            # Production: JSON string stored in environment variable
            cred_dict = json.loads(settings.FIREBASE_CREDENTIALS_JSON)
            cred = credentials.Certificate(cred_dict)
        else:
            # Local development: JSON file on disk
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)

        firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialized successfully")
    except Exception as e:
        logger.error(f"Firebase initialization failed: {e}")
        raise


# Call in main.py lifespan:
# from app.core.firebase import init_firebase
# init_firebase()
```

### Step 5: The NotificationService

```python
# app/services/notification_service.py

from uuid import UUID
from firebase_admin import messaging
from loguru import logger


class NotificationService:

    @staticmethod
    async def send_urgent_broadcast(
        tokens: list[str],
        broadcast_id: UUID,
        skill_name: str,
    ) -> None:
        """
        Send high-priority FCM to all nearby providers simultaneously.
        Uses MulticastMessage for batch delivery (up to 500 tokens per call).
        """
        if not tokens:
            return

        message = messaging.MulticastMessage(
            tokens=tokens,
            data={
                # 'data' payload (not 'notification') so Flutter/React can handle
                # it even when app is backgrounded, and extract broadcast_id
                "type": "URGENT_BROADCAST",
                "broadcast_id": str(broadcast_id),
                "skill_name": skill_name,
            },
            notification=messaging.Notification(
                title=f"জরুরি কাজ! / Urgent Job!",
                body=f"আপনার কাছে কেউ {skill_name} চাইছেন। / Someone needs {skill_name} urgently.",
            ),
            android=messaging.AndroidConfig(priority="high"),
            apns=messaging.APNSConfig(
                headers={"apns-priority": "10"}
            ),
        )

        try:
            response = messaging.send_each_for_multicast(message)
            logger.info(
                f"Urgent broadcast FCM: {response.success_count} sent, "
                f"{response.failure_count} failed out of {len(tokens)} tokens"
            )
        except Exception as e:
            # FCM failure must never crash the booking flow
            logger.error(f"FCM urgent broadcast failed: {e}")

    @staticmethod
    async def send_booking_followup(
        seeker_fcm_token: str,
        booking_id: UUID,
        provider_name: str,
        attempt: int,
    ) -> None:
        """2-hour and 24-hour follow-up: 'Did you hire [provider]?'"""
        if not seeker_fcm_token:
            return

        message = messaging.Message(
            token=seeker_fcm_token,
            data={
                "type": "BOOKING_FOLLOWUP",
                "booking_id": str(booking_id),
                "attempt": str(attempt),
            },
            notification=messaging.Notification(
                title="বুকিং আপডেট / Booking Update",
                body=f"আপনি কি {provider_name} কে নিয়োগ করেছেন? / Did you hire {provider_name}?",
            ),
        )

        try:
            messaging.send(message)
            logger.info(
                f"Booking followup FCM sent: booking={booking_id} attempt={attempt}"
            )
        except Exception as e:
            logger.error(f"FCM booking followup failed: {e}")

    @staticmethod
    async def send_completion_prompt(
        seeker_fcm_token: str,
        booking_id: UUID,
        provider_name: str,
    ) -> None:
        """'Your job with [provider] should be done. Tap to review!'"""
        if not seeker_fcm_token:
            return

        message = messaging.Message(
            token=seeker_fcm_token,
            data={
                "type": "COMPLETION_PROMPT",
                "booking_id": str(booking_id),
            },
            notification=messaging.Notification(
                title="কাজ সম্পন্ন? / Job Done?",
                body=f"{provider_name} এর সাথে আপনার কাজ শেষ হয়ে থাকলে রিভিউ দিন।",
            ),
        )

        try:
            messaging.send(message)
        except Exception as e:
            logger.error(f"FCM completion prompt failed: {e}")

    @staticmethod
    async def send_broadcast_expired(seeker_fcm_token: str) -> None:
        """'No one responded. Please try a manual search.'"""
        if not seeker_fcm_token:
            return

        message = messaging.Message(
            token=seeker_fcm_token,
            data={"type": "BROADCAST_EXPIRED"},
            notification=messaging.Notification(
                title="কোনো সাড়া নেই / No Response",
                body="কেউ সাড়া দেননি। ম্যানুয়াল অনুসন্ধান করুন। / No one responded. Try manual search.",
            ),
        )

        try:
            messaging.send(message)
        except Exception as e:
            logger.error(f"FCM broadcast expired notification failed: {e}")

    @staticmethod
    async def send_broadcast_claimed(
        seeker_fcm_token: str,
        provider_name: str,
    ) -> None:
        """Notify seeker that a provider accepted their urgent request."""
        if not seeker_fcm_token:
            return

        message = messaging.Message(
            token=seeker_fcm_token,
            data={"type": "BROADCAST_CLAIMED", "provider_name": provider_name},
            notification=messaging.Notification(
                title="প্রোভাইডার পাওয়া গেছে! / Provider Found!",
                body=f"{provider_name} আপনার অনুরোধ গ্রহণ করেছেন। / {provider_name} accepted your request.",
            ),
        )

        try:
            messaging.send(message)
        except Exception as e:
            logger.error(f"FCM broadcast claimed notification failed: {e}")

    @staticmethod
    async def send_verification_approved(provider_fcm_token: str) -> None:
        message = messaging.Message(
            token=provider_fcm_token,
            data={"type": "VERIFICATION_APPROVED"},
            notification=messaging.Notification(
                title="যাচাইকরণ সম্পন্ন! / Verified!",
                body="আপনার অ্যাকাউন্ট যাচাই হয়েছে। এখন আপনি ব্লু টিক পাবেন।",
            ),
        )
        try:
            messaging.send(message)
        except Exception as e:
            logger.error(f"FCM verification approved failed: {e}")
```

### Step 6: Wire FCM into main.py lifespan

```python
# app/main.py — in lifespan, before yield

from app.core.firebase import init_firebase
init_firebase()
```

### Step 7: Getting FCM tokens from Flutter/React

Flutter (provider/seeker mobile app):
```dart
// In Flutter — add firebase_messaging package
// pubspec.yaml: firebase_messaging: ^14.x.x

final fcmToken = await FirebaseMessaging.instance.getToken();
// Send this token to your backend after login:
// POST /api/v1/fcm/token  { "token": fcmToken, "device_type": "ANDROID" }
```

You already have an `fcm_tokens` table. You need one small endpoint to
receive and store tokens:

```python
# Add to app/api/v1/auth.py or a new fcm.py router

@router.post("/fcm/token", status_code=201)
async def register_fcm_token(
    token: str,
    device_type: str,   # ANDROID, IOS, WEB
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Called by Flutter/React after login to register the device FCM token."""
    from app.models.fcm_token import FCMToken
    from sqlalchemy.dialects.postgresql import insert

    # Upsert — avoid duplicates if same token registered twice
    stmt = insert(FCMToken).values(
        user_id=current_user.id,
        token=token,
        device_type=device_type,
    ).on_conflict_do_nothing()

    await db.execute(stmt)
    await db.commit()
    return {"registered": True}
```

---

## What's Left After This

**Done after this batch:**
- All seeker flows ✓
- All provider flows ✓
- All admin flows ✓
- FCM infrastructure ✓

**Remaining before submission:**

1. **Wire FCM into job stubs** — replace `# TODO` comments in
   `booking_jobs.py` and `urgent_jobs.py` with actual
   `NotificationService` calls. You need to fetch the user's FCM token
   from `fcm_tokens` table before calling each notification method.

2. **Alembic migration** — run `alembic revision --autogenerate` to pick up
   any model changes, then `alembic upgrade head`.

3. **Test the admin endpoints** — create an admin user directly in the DB
   (seed script) since there's no admin registration endpoint by design.

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
```python
# app/schemas/auth_schema.py

from pydantic import BaseModel

class LogoutSchema(BaseModel):
    refresh_token: str
    fcm_token: str | None = None   # optional: also clear this device's FCM token
```

```python
# app/repositories/user_repository.py — add this method

async def delete_session_by_refresh_token(self, refresh_token: str) -> bool:
    """Deletes the session row matching this refresh token. Returns True if found."""
    from sqlalchemy import delete
    result = await self.db.execute(
        delete(UserSession)
        .where(UserSession.refresh_token == refresh_token)
        .returning(UserSession.id)
    )
    return result.first() is not None
```

```python
# app/services/auth_service.py

@staticmethod
async def logout(
    data: LogoutSchema,
    access_token: str,
    user_id: UUID,
    db: AsyncSession,
    lang: str,
) -> dict:
    user_repo = UserRepository(db)

    # 1. Delete the refresh token session row — this is the durable logout
    deleted = await user_repo.delete_session_by_refresh_token(data.refresh_token)
    if not deleted:
        # Not fatal — token might already be gone (e.g. double logout tap)
        logger.warning(f"Logout: refresh token not found for user {user_id}")

    # 2. Blocklist the current access token until it naturally expires
    # Access tokens are short-lived (1hr), so the TTL cache entry only
    # needs to live until the token's own expiry — no need to track forever.
    from app.core.security import decode_access_token
    from app.core.cache import ttl_cache  # your Redis/TTL cache client

    payload = decode_access_token(access_token)
    remaining_seconds = max(0, payload["exp"] - int(datetime.now(timezone.utc).timestamp()))
    if remaining_seconds > 0:
        await ttl_cache.set(
            key=f"blocklist:{access_token}",
            value="1",
            ttl_seconds=remaining_seconds,
        )

    # 3. Optionally remove this device's FCM token so a stale session
    # can't receive notifications meant for whoever logs in next
    if data.fcm_token:
        from sqlalchemy import delete
        from app.models.fcm_token import FCMToken
        await db.execute(
            delete(FCMToken)
            .where(FCMToken.user_id == user_id)
            .where(FCMToken.token == data.fcm_token)
        )

    await db.commit()
    logger.info(f"User {user_id} logged out")

    return {"message": t("logout_successful", lang)}
```

```python
# app/api/v1/auth.py

@router.post("/logout", status_code=200)
async def logout(
    data: LogoutSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
    authorization: str = Header(...),
):
    """
    Logs out the current device:
    - Deletes the refresh token session (other devices stay logged in)
    - Blocklists the current access token until it naturally expires
    - Optionally removes this device's FCM token
    """
    access_token = authorization.replace("Bearer ", "")
    return await AuthService.logout(
        data=data,
        access_token=access_token,
        user_id=current_user.id,
        db=db,
        lang=lang,
    )
```

```python
# In your get_current_user dependency, after decoding the token
if await ttl_cache.exists(f"blocklist:{token}"):
    raise HTTPException(status_code=401, detail=t("token_revoked", lang))
```


