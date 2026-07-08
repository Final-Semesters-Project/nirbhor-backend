import json
import firebase_admin
from firebase_admin import credentials, messaging
from loguru import logger

from app.core.config import settings


def init_firebase() -> None:
    """
    Initialize Firebase Admin SDK once at app startup.
    Supports both file path (local dev) and JSON string (Render production).
    """
    if firebase_admin._apps:
        return  # already initialized

    try:
        if settings.FIREBASE_CREDENTIALS_JSON:
            # Production: JSON string stored in environment variable
            cred_dict = json.loads(settings.FIREBASE_CREDENTIALS_JSON)
            cred = credentials.Certificate(cred_dict)
        else:
            # Local development: JSON file on disk
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)

        firebase_admin.initialize_app(cred)
        logger.success("Firebase Admin SDK initialized successfully")
    except Exception as e:
        logger.error(f"Firebase initialization failed: {e}")
        raise
