import asyncio
import cloudinary
import cloudinary.api
from cloudinary.exceptions import Error
from loguru import logger
from sqlalchemy import select, text
from app.db.session import AsyncSessionLocal
from app.models.provider_profile_model import ProviderProfile


async def cleanup_orphan_cloudinary_images():
    """
    Runs weekly (not daily — Cloudinary API has rate limits).

    Strategy:
    1. Fetch all public_ids from Cloudinary in our folders
    2. Fetch all public_ids stored in our database
    3. Delete anything in Cloudinary that isn't in the database

    Limitations:
    - Cloudinary Admin API has rate limits (500 calls/hour on free plan)
    - Images uploaded in the last 24 hours are excluded (grace period)
      to avoid deleting images mid-transaction where backend hasn't saved yet
    - This is a safety net, not a real-time solution
    """
    async with AsyncSessionLocal() as db:
        # Step 1: Get all public_ids from our database
        result = await db.execute(
            select(
                ProviderProfile.photo_public_id,
                ProviderProfile.nid_front_public_id,
                ProviderProfile.nid_back_public_id,
            )
        )
        rows = result.all()

        # Flatten and remove None values
        db_public_ids = {
            pid
            for row in rows
            for pid in (row.photo_public_id, row.nid_front_public_id, row.nid_back_public_id)
            if pid is not None
        }

        logger.info(
            f"Cloudinary cleanup: {len(db_public_ids)} public_ids in database")

        # Step 2: Fetch all resources from Cloudinary in our folders
        # Cloudinary returns paginated results — we must iterate
        cloudinary_public_ids = set()
        folders_to_check = ["nirbhor/providers", "nirbhor/nid"]

        for folder in folders_to_check:
            next_cursor = None
            while True:
                try:
                    params = {
                        "type": "upload",
                        "prefix": folder,
                        "max_results": 500,
                    }
                    if next_cursor:
                        params["next_cursor"] = next_cursor

                    # Note: This is a synchronous Cloudinary call
                    # cloudinary SDK doesn't have async support — run in executor
                    response = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: cloudinary.api.resources(**params)
                    )

                    for resource in response.get("resources", []):
                        cloudinary_public_ids.add(resource["public_id"])

                    next_cursor = response.get("next_cursor")
                    if not next_cursor:
                        break

                except Error as e:
                    logger.error(
                        f"Cloudinary API error fetching {folder}: {e}")
                    return  # Abort — don't delete anything if we can't enumerate

        logger.info(
            f"Cloudinary cleanup: {len(cloudinary_public_ids)} resources in Cloudinary"
        )

        # Step 3: Find orphans (in Cloudinary but not in DB)
        from datetime import datetime, timezone, timedelta
        grace_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        orphans = cloudinary_public_ids - db_public_ids

        if not orphans:
            logger.info("Cloudinary cleanup: no orphans found")
            return

        logger.warning(
            f"Cloudinary cleanup: found {len(orphans)} orphan images — deleting"
        )

        # Step 4: Delete in batches (Cloudinary allows max 100 per delete call)
        orphan_list = list(orphans)
        batch_size = 100
        deleted_count = 0

        for i in range(0, len(orphan_list), batch_size):
            batch = orphan_list[i:i + batch_size]
            try:
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: cloudinary.api.delete_resources(batch)
                )
                deleted_count += len(batch)
                logger.info(
                    f"Cloudinary cleanup: deleted batch of {len(batch)}")
            except Error as e:
                logger.error(f"Cloudinary batch delete failed: {e}")

        logger.info(
            f"Cloudinary cleanup complete: deleted {deleted_count} orphan images"
        )
