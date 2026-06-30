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

    async def get_users(
        self,
        role_filter: str | None = None,
        is_active_filter: bool | None = None,
    ) -> list[User]:
        stmt = select(User).order_by(User.created_at.desc())
        if role_filter:
            stmt = stmt.where(User.role == role_filter)
        if is_active_filter is not None:
            stmt = stmt.where(User.is_active == is_active_filter)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_user_detail(self, user_id: UUID) -> dict | None:
        user = await self.db.get(User, user_id)
        if not user:
            return None

        total_bookings = await self.db.scalar(
            select(func.count())
            .select_from(Booking)
            .where(
                (Booking.seeker_id == user_id) | (Booking.provider_id == user_id)
            )
        )

        profile = None
        if user.role == Role.PROVIDER:
            profile = await self.db.get(ProviderProfile, user_id)

        return {
            "user": user,
            "total_bookings": total_bookings or 0,
            "profile": profile,
        }

    async def toggle_user_active(self, user_id: UUID) -> User:
        user = await self.db.get(User, user_id)
        user.is_active = not user.is_active
        await self.db.flush()
        return user

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
    async def get_users(
        db: AsyncSession,
        role_filter: str | None = None,
        is_active_filter: bool | None = None,
    ) -> list[AdminUserListItem]:
        repo = AdminRepository(db)
        users = await repo.get_users(role_filter, is_active_filter)
        return [
            AdminUserListItem(
                user_id=u.id,
                name=u.name_en,
                phone=u.phone_en,
                role=u.role.value,
                is_active=u.is_active,
                last_active_at=u.last_active_at,
                created_at=u.created_at,
            )
            for u in users
        ]

    @staticmethod
    async def get_user_detail(
        user_id: UUID, db: AsyncSession, lang: str
    ) -> AdminUserDetail:
        repo = AdminRepository(db)
        data = await repo.get_user_detail(user_id)
        if not data:
            raise DomainValidationError(t("user_not_found", lang))

        u = data["user"]
        profile = data["profile"]

        return AdminUserDetail(
            user_id=u.id,
            name=u.name_en,
            phone=u.phone_en,
            role=u.role.value,
            is_active=u.is_active,
            last_active_at=u.last_active_at,
            created_at=u.created_at,
            total_bookings=data["total_bookings"],
            average_rating=profile.average_rating if profile else None,
            verification_level=profile.verification_level.value if profile else None,
            verification_status=profile.verification_status.value if profile else None,
        )

    @staticmethod
    async def toggle_user_active(
        user_id: UUID, db: AsyncSession, lang: str
    ) -> dict:
        repo = AdminRepository(db)
        user = await repo.toggle_user_active(user_id)
        if not user:
            raise DomainValidationError(t("user_not_found", lang))
        await db.commit()
        logger.info(
            f"Admin toggled user {user_id} is_active → {user.is_active}"
        )
        return {
            "user_id": user_id,
            "is_active": user.is_active,
            "message": t("user_status_updated", lang),
        }

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


@router.patch("/reports/{report_id}", response_model=ReportActionResponse)
async def handle_report(
    report_id: UUID,
    data: ReportActionSchema,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """
    - dismiss  → marks report REVIEWED, no action on reported user
    - reviewed → marks report REVIEWED
    - suspend  → marks report ACTION_TAKEN + sets reported user is_active=False
    """
    return await AdminService.handle_report(
        report_id=report_id,
        data=data,
        db=db,
        lang=lang,
    )


# ── Users ──────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=list[AdminUserListItem])
async def list_users(
    role: str | None = Query(None, description="Filter: SEEKER, PROVIDER, ADMIN"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    return await AdminService.get_users(
        db=db, role_filter=role, is_active_filter=is_active
    )


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def get_user_detail(
    user_id: UUID,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    return await AdminService.get_user_detail(
        user_id=user_id, db=db, lang=lang
    )


@router.patch("/users/{user_id}/toggle", status_code=200)
async def toggle_user_active(
    user_id: UUID,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """Enable or disable a user account. Toggles current is_active value."""
    return await AdminService.toggle_user_active(
        user_id=user_id, db=db, lang=lang
    )


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