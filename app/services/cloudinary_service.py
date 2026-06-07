import cloudinary
import cloudinary.uploader
from loguru import logger
from app.core.config import settings

# Cloudinary Configuration
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True,
)


async def delete_image_from_cloudinary(public_id: str) -> dict | None:
    """
    Deletes an asset from Cloudinary using its public_id.
    Returns the Cloudinary response dict or None if failed.
    """

    try:
        if not public_id:
            return None
        result = cloudinary.uploader.destroy(public_id)

        if result.get("result") == "ok":
            logger.success(
                f"Asset successfully deleted from Cloudinary: {public_id}")
        else:
            logger.warning(
                f"Cloudinary delete returned unexpected status for {public_id}: {result}")

        return result
    except Exception as e:
        logger.error(f"Error deleting image from Cloudinary: {e}")
        return None
