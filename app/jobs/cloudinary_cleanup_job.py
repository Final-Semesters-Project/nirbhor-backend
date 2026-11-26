import asyncio
from functools import partial
import cloudinary
import cloudinary.api
from cloudinary.exceptions import Error
from loguru import logger
from sqlalchemy import select, text
from app.db.session import AsyncSessionLocal
from datetime import datetime, timezone, timedelta
from app.models.provider_profile_model import ProviderProfile
from app.models.seeker_profile_model import SeekerProfile


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
        # Step 1: Get all public_ids from our database (seeker and provider)
        provider_rows = (
            await db.execute(
                select(
                    ProviderProfile.photo_public_id,
                    ProviderProfile.nid_front_public_id,
                    ProviderProfile.nid_back_public_id,
                )
            )
        ).all()

        seeker_rows = (
            await db.execute(select(SeekerProfile.photo_public_id))
        ).all()

        # Flatten and remove None values
        db_public_ids = {
            pid
            for row in provider_rows
            for pid in (row.photo_public_id, row.nid_front_public_id, row.nid_back_public_id)
            if pid is not None
        } | {
            row.photo_public_id
            for row in seeker_rows
            if row.photo_public_id is not None
        }

        logger.info(
            f"Cloudinary cleanup: {len(db_public_ids)} public_ids in database")

        grace_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        # Root ("") holds unsigned profile uploads; "nirbhor/nid" holds authenticated NIDs
        targets = [
            ("", "upload"),
            ("nirbhor/nid", "authenticated"),
        ]

        total_deleted = 0

        # for folder in folders_to_check:
        for prefix, delivery_type in targets:
            cloudinary_public_ids = set()
            next_cursor = None

            while True:
                try:
                    params = {
                        "type": delivery_type,
                        "max_results": 500,
                    }
                    if prefix:
                        params["prefix"] = prefix
                    if next_cursor:
                        params["next_cursor"] = next_cursor

                    # Note: This is a synchronous Cloudinary call
                    # cloudinary SDK doesn't have async support — run in executor
                    # response = await asyncio.get_event_loop().run_in_executor(
                    response = await asyncio.get_running_loop().run_in_executor(
                        None,
                        # lambda: cloudinary.api.resources(**params)
                        partial(cloudinary.api.resources, **params),
                    )

                    for resource in response.get("resources", []):
                        # cloudinary_public_ids.add(resource["public_id"])

                        # Skip NID assets when scanning root ("")
                        if not prefix and resource["public_id"].startswith("nirbhor/"):
                            continue

                        created_at = datetime.fromisoformat(
                            resource["created_at"].replace("Z", "+00:00")
                        )

                        if created_at < grace_cutoff:
                            cloudinary_public_ids.add(resource["public_id"])
                            logger.info(
                                f"Cloudinary cleanup: {len(cloudinary_public_ids)} resources in Cloudinary"
                            )
                    next_cursor = response.get("next_cursor")
                    if not next_cursor:
                        break
                except Error as e:
                    logger.error(
                        f"Cloudinary API error fetching prefix='{prefix}' ({delivery_type}): {e}"
                    )
                    return  # Abort safely on API error

            orphans = list(cloudinary_public_ids - db_public_ids)
            logger.info(
                f"Cloudinary cleanup [{prefix or 'root'}/{delivery_type}]: "
                f"{len(cloudinary_public_ids)} eligible, {len(orphans)} orphans"
            )

            for i in range(0, len(orphans), 100):
                batch = orphans[i: i + 100]

                try:
                    await asyncio.get_running_loop().run_in_executor(
                        None,
                        partial(
                            cloudinary.api.delete_resources,
                            batch,
                            type=delivery_type
                        ),
                    )
                    total_deleted += len(batch)
                except Error as e:
                    logger.error(
                        f"Cloudinary batch delete failed: {e}"
                    )

        logger.info(
            f"Cloudinary cleanup complete: deleted {total_deleted} orphan images")
