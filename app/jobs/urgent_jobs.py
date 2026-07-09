from loguru import logger
from app.db.session import AsyncSessionLocal
from app.repositories.urgent_repository import UrgentBroadcastRepository
from app.services.notification_service import NotificationService


async def expire_stale_broadcasts():
    """
    Runs every minute via APScheduler.
    Marks BROADCASTING records past expires_at as EXPIRED.
    Sends FCM to seekers to notify them nobody responded.

    Why every minute: broadcasts expire after 5 minutes.
    A 1-minute polling interval means max 1 minute of extra wait
    before the seeker learns nobody responded — acceptable.
    """
    async with AsyncSessionLocal() as db:
        repo = UrgentBroadcastRepository(db)
        expired_tokens = await repo.expire_stale_broadcasts()

        if not expired_tokens:
            logger.debug(f"Urgent job: No stale broadcasts to expire")
            return

        await db.commit()

        logger.info(
            f"Expired stale broadcasts, notifying {len(expired_tokens)} seekers")

        for fcm_token, preferred_lang in expired_tokens:
            # send FCM to seeker
            await NotificationService.send_broadcast_expired(seeker_fcm_token=fcm_token, preferred_lang=preferred_lang)
