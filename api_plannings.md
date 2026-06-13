# Domain 1: Bookings Management (/app/api/v1/bookings/)
- Handles: Intent-to-Book Workflow.
1. POST /api/v1/bookings/initiate
- Trigger: Seeker clicks "Request to Call" on a provider's profile.
- Logic:
    - Count active INITIATED records for the calling seeker; reject if they are spamming multiple open numbers simultaneously.

    - Insert a row into bookings with status = BookingStatus.INITIATED and set call_unlocked_at = datetime.utcnow().

    - Response: Returns the raw phone number of the provider so the frontend can trigger the native system dialer.

2. PATCH /api/v1/bookings/{booking_id}/respond
- Trigger: Seeker responds to the 2-hour or 24-hour FCM notification prompt ("Did you end up hiring...?").
Payload Schema: {"hired": bool, "work_schedule": datetime | None}
- Logic:
    - If hired == True: Update status directly to IN_PROGRESS (bypassing CONFIRMED as discussed) and save the explicit work_schedule. Automatically bump last_active_at for both users here to trigger Implied Activity tracking.

    - If hired == False: Update status to CANCELLED.

3. GET /api/v1/bookings/provider/me
- Trigger: Provider opens their "Incoming Bookings" tab (matches your incoming_bookings.png UI mockup).
- Logic: Query bookings table where provider_id == current_user.id AND status == BookingStatus.IN_PROGRESS. (This cleanly isolates and hides INITIATED records from their screen).

4. GET /api/v1/bookings/seeker/me
- Trigger: Seeker opens their booking history list.

- Logic: Query all records matching seeker_id == current_user.id (including INITIATED entries so they can see past numbers they requested).


# Domain 2: Location-Aware Search (/app/api/v1/search/)
5. GET /api/v1/search/providers
- Handles: Discovery & Search Requirements.
- Query Parameters: `skill_category_id: int`, `seeker_lat: float`, `seeker_lng: float`, `search_radius_km: int | None = 1` 
- Logic:
    - Execute a PostGIS geospatial query matching providers whose `base_location` and defined `working_radius_km` overlap with the seeker's point coordinates.
    - Filter out providers where `is_available == False` (off-duty toggles) or where `last_active_at` is older than 60 days.
    - Apply your explicit Provider Ranking Score formula right inside the SQLAlchemy query selection using mathematical weights:
        `score = (1/distance_km) + (rating * 2) + (verification_level * 3) + activity_bonus`
    - Return localized `name_bn` or `name_en` fields dynamically by inspecting the Accept-Language header wrapper.

# Domain 3: Emergency Broadcasts (/app/api/v1/urgent/)
- Handles: Atomic multi-device Urgent Services ("Need It NOW") engine.
6. POST /api/v1/urgent/broadcast
- Trigger: Seeker requests an emergency asset dispatch.
- Logic: 
    - Insert an item into `urgent_broadcasts` with `status = BROADCASTING` and `expires_at = now() + 5 minutes`. Collect active target tokens within 3 KM with `has_smartphone == True` and trigger simultaneous high-priority FCM payloads.

7. POST /api/v1/urgent/broadcast/{broadcast_id}/claim
- Trigger: Fast-acting provider taps "Accept" on their screen.
- Logic: Run an atomic database transaction with a pessimistic lock (with_for_update()) to prevent race conditions:
    ```python
        # Ensure only the fastest write wins
        stmt = select(UrgentBroadcast).where(UrgentBroadcast.id == id).with_for_update()
    ```
    If status is still `BROADCASTING`, switch it to `CLAIMED` and set `claimed_by_provider_id`. If already claimed, raise a `409 Conflict` (or customized message) indicating the job was taken.

# 🛠️ Infrastructure & Version Controls (/app/api/v1/config/)
8. GET /api/v1/config/app-version
- Trigger: App startup verification sequence.
- Query Parameters: platform: str, current_version: str
- Logic: Read your app_versions database metadata. If current_version falls strictly behind the minimum_required_version, notify the application wrapper to trigger a full structural hard-lock block screen.

⏰ Background Automation Tasks (/app/jobs/)
To keep your application code snappy, offload execution lifecycles to your embedded internal APScheduler tasks engine:

The Midnight Expiry Clean (run_daily_at_midnight): Scan for any INITIATED rows remaining unconfirmed for more than 48 hours and switch them globally to AUTO_EXPIRED.

The Urgent Expiry Sweeper (run_every_minute): Scan for entries remaining BROADCASTING where expires_at is past the current timestamp, flag them as EXPIRED, and push an FCM fallback error update back to the waiting seeker.

The 15-Day Visibility Ping: Scan for providers with no interactive activity update records between 15 and 30 days old, and issue a free "Tap to Stay Visible" FCM notification card sequence to refresh their placement metrics safely.


======================================== CODE ========================================

# Nirbhor — Domains 1, 2, 3 Implementation

## File Map

```
app/
├── schemas/
│   ├── booking_schema.py
│   ├── search_schema.py
│   └── urgent_schema.py
├── repositories/
│   ├── booking_repository.py
│   ├── search_repository.py
│   └── urgent_repository.py
├── services/
│   ├── booking_service.py
│   ├── search_service.py
│   └── urgent_service.py
└── api/v1/
    ├── bookings.py
    ├── search.py
    └── urgent.py
```

---

## ⚙️ Setup Required Before Running

### 1. Register the new routers in `app/api/v1/router.py`

### 2. Add a missing i18n key => added

### 3. FCM (stub for now, real implementation later)

The `NotificationService` below is a stub. Firebase Admin SDK setup is a
separate task. For now the stubs log the intent without actually sending.

---

## 1. Schemas

## 2. Repositories

## 3. Services

## 4. Routers

## 5. One Method to Add to `UserRepository`


# APScheduler
# app/jobs/booking_jobs.py
```python
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy import update

from app.db.session import AsyncSessionLocal
from app.models.booking import Booking, BookingStatus
from app.repositories.booking_repository import BookingRepository


async def send_booking_followup_notifications():
    """
    Runs every 5 minutes via APScheduler.
    Finds INITIATED bookings that crossed the 2-hour mark and sends FCM.

    Why a polling job instead of scheduling per booking:
    APScheduler with multiple Gunicorn workers would fire duplicate jobs
    if each booking schedules its own. A single polling job with a time
    window is simpler and safe.
    """
    async with AsyncSessionLocal() as db:
        repo = BookingRepository(db)
        bookings = await repo.get_initiated_ready_for_followup()

        if not bookings:
            return

        logger.info(f"Booking followup job: {len(bookings)} bookings ready for FCM")

        for booking in bookings:
            # Status guard: only send if still INITIATED
            # (could have been confirmed/cancelled in the last 5 mins)
            if booking.status != BookingStatus.INITIATED:
                continue

            logger.info(
                f"Sending 2hr follow-up FCM for booking {booking.id} "
                f"to seeker {booking.seeker_id}"
            )
            # TODO: await NotificationService.send_booking_followup(
            #     seeker_id=booking.seeker_id,
            #     booking_id=booking.id,
            #     attempt=1
            # )


async def expire_stale_bookings():
    """
    Runs nightly at midnight via APScheduler.
    INITIATED bookings older than 48 hours → AUTO_EXPIRED.
    This is unchanged from the original design.
    """
    async with AsyncSessionLocal() as db:
        cutoff = datetime.utcnow() - timedelta(hours=48)
        result = await db.execute(
            update(Booking)
            .where(Booking.status == BookingStatus.INITIATED)
            .where(Booking.call_unlocked_at < cutoff)
            .values(status=BookingStatus.AUTO_EXPIRED)
            .returning(Booking.id)
        )
        expired = len(result.all())
        await db.commit()
        if expired:
            logger.info(f"Nightly cleanup: expired {expired} stale bookings")
```

# register jobs

```python
# In lifespan, after setup_logging():
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.jobs.booking_jobs import send_booking_followup_notifications, expire_stale_bookings

scheduler = AsyncIOScheduler()
scheduler.add_job(send_booking_followup_notifications, "interval", minutes=5)
scheduler.add_job(expire_stale_bookings, "cron", hour=0, minute=0)
scheduler.start()
yield
scheduler.shutdown()
```