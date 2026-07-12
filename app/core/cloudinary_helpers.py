import asyncio

import cloudinary
import cloudinary.uploader
from loguru import logger
from app.core.config import settings


# Cloudinary Configuration
def init_cloudinary():
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )


async def delete_image_from_cloudinary(
        public_id: str,
        authenticated: bool = False
) -> bool:
    """
    Deletes an image from Cloudinary by public_id.

    authenticated=True  → NID photos (stored with access_type='authenticated')
                          Requires type='authenticated' in destroy() call,
                          otherwise Cloudinary looks in public uploads and
                          returns 'not found' silently.

    authenticated=False → Profile photos (public storage, default)

    Returns True if deletion succeeded, False otherwise.
    Never raises — caller does not need to handle Cloudinary errors.

    Why run_in_executor?
    cloudinary.uploader.destroy() is a synchronous blocking HTTP call.
    Running it in executor releases the event loop while waiting.
    """

    if not public_id:
        return False

    resource_type = "authenticated" if authenticated else "upload"

    def _destroy() -> bool:
        result = cloudinary.uploader.destroy(
            public_id,
            invalidate=True,    # clears CDN cache — important for authenticated images
            type=resource_type,  # critical for authenticated images
        )

        return result.get("result") == "ok"

    loop = asyncio.get_event_loop()

    try:

        success = await loop.run_in_executor(None, _destroy)

        if success:
            logger.success(
                f"Asset successfully deleted from Cloudinary. public_id: {public_id}, (authenticated: {authenticated})")
        else:
            logger.warning(
                f"Cloudinary delete returned unexpected status for public_id: {public_id}  "
                f"(authenticated: {authenticated})"
            )
        return success

    except Exception as e:
        # logger.opt(exception=e) attaches the full traceback to this log entry.
        # Without it, only the error message string is logged and you lose
        # the stack trace — making it hard to know which line failed.
        # This is Loguru's equivalent of logger.error(msg, exc_info=True)
        # in stdlib logging.
        logger.opt(exception=e).error(
            f"Cloudinary: failed to delete {public_id}")

        return False
