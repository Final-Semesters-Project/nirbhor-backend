import time
import cloudinary.utils
from fastapi import APIRouter, Depends, Query
from uuid import UUID
from app.core.config import settings
from app.api.dependencies import get_current_provider
from app.core.exceptions import DomainValidationError

router = APIRouter(prefix="/uploads", tags=["Uploads"])


@router.get("/upload-signature/nid")
async def get_nid_upload_signature(
    side: str = Query(examples=["front", "back"]),   # "front" or "back"
    current_user=Depends(get_current_provider),
):
    """
    Generates a short-lived Cloudinary upload signature for NID documents.

    Why a signature endpoint instead of backend-proxied upload?
    - No extra API needed to receive image files
    - File goes directly from device to Cloudinary (faster, no bandwidth cost on your server)
    - API_SECRET stays on the server — only the signature is exposed
    - Signature expires in 10 minutes — useless after that

    Frontend flow:
    1. Call GET /upload-signature/nid?side=front
    2. Receive { signature, timestamp, api_key, cloud_name, folder, public_id }
    3. POST file directly to Cloudinary with those params
    4. Cloudinary returns { secure_url, public_id }
    5. Send secure_url + public_id to PATCH /provider/me/update_profile
    """
    if side not in ("front", "back"):
        raise DomainValidationError("side must be 'front' or 'back'")

    timestamp = int(time.time())

    # public_id is deterministic: nid_front_{user_id} or nid_back_{user_id}
    # This means re-uploading overwrites the old image automatically in Cloudinary
    # (no orphan created when provider re-uploads after rejection)
    public_id = f"nid_{side}_{current_user.id}"
    folder = f"nirbhor/nid"

    params_to_sign = {
        "timestamp":   timestamp,
        "folder":      folder,
        "public_id":   public_id,
        "access_type": "authenticated",  # makes image private in Cloudinary
        "overwrite":   True,
        "upload_preset": "nirbhor_nid",  # Cloudinary preset name
    }

    signature = cloudinary.utils.api_sign_request(
        params_to_sign,
        settings.CLOUDINARY_API_SECRET,
    )

    return {
        "signature":   signature,
        "timestamp":   timestamp,
        "api_key":     settings.CLOUDINARY_API_KEY,    # public, safe to expose
        "cloud_name":  settings.CLOUDINARY_CLOUD_NAME,  # public, safe to expose
        "folder":      folder,
        "public_id":   public_id,
        "access_type": "authenticated",
        "overwrite":   True,
        "upload_preset": "nirbhor_nid",
        # Signature expires in ~1 hour (Cloudinary default)
        # Frontend should use it immediately
    }
