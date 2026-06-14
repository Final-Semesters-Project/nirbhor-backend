
from datetime import datetime, timedelta, timezone
from loguru import logger
from sqlalchemy import update
from app.db.session import AsyncSessionLocal
from app.models.booking_model import Booking, BookingStatus
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

        logger.info(
            f"Booking followup job: {len(bookings)} bookings ready for FCM")

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
        # get the 48 hours ago timestamp from now
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
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
