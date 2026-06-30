from loguru import logger

from app.db.session import AsyncSessionLocal
from app.repositories.urgent_repository import UrgentBroadcastRepository


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
        seeker_ids = await repo.expire_stale_broadcasts()

        if not seeker_ids:
            return

        await db.commit()

        logger.info(
            f"Expired {len(seeker_ids)} stale broadcasts, "
            f"notifying seekers: {seeker_ids}"
        )

        for seeker_id in seeker_ids:
            # TODO: send FCM to seeker
            # await NotificationService.send_broadcast_expired(seeker_id)
            logger.info(
                f"[stub] Notifying seeker {seeker_id}: no one responded")
