import cloudinary
import cloudinary.uploader
from loguru import logger
from app.core.config import settings
from fastapi import UploadFile, HTTPException, status

# Cloudinary Configuration
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True,
)


async def upload_image_to_cloudinary(file: UploadFile, folder: str) -> dict:
    """
    Uploads an image to Cloudinary and returns the URL and Public ID.
    """
    try:
        # Read file content
        file_content = await file.read()

        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            file_content,
            folder=f"provider_app/{folder}",  # Organize by folders
            resource_type="image"
        )

        return {
            "url": result.get("secure_url"),
            "public_id": result.get("public_id")
        }
    except Exception as e:
        logger.error(f"Cloudinary Upload Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload image to storage"
        )
    finally:
        await file.close()


async def delete_image_from_cloudinary(public_id: str):
    try:
        if not public_id:
            return None
        result = cloudinary.uploader.destroy(public_id)
        logger.success(f"Image deleted from Cloudinary: {public_id}")
        return result
    except Exception as e:
        logger.error(f"Error deleting image from Cloudinary: {e}")
        return None
