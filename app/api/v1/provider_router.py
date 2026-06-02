from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import DomainIntegrityError
from app.core.i18n import MESSAGES, get_lang, t, make_validated_body
from app.db.session import get_db_session
from app.schemas.auth_schema import (
    SeekerRegisterSchema,
    ProviderRegisterSchema,
    AuthResponseSchema,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/provider", tags=["Provider Management"])


# Provider profile data
"""
GET /api/v1/providers/me/profile
→ name, photo, verification level, rating, jobs done, radius, skills, ai summary
"""


# / me router
"""
# for seeker
{
    "user_id": "uuid",
    "role": "SEEKER",
    "phone": "016...",
    "name": "Rahim",
    "is_active": true,
}

# for provider — needs more data to render their dashboard
{
    "user_id": "uuid", 
    "role": "PROVIDER",
    "phone": "016...",
    "name": "Karim",
    "is_active": true,
    "verification_level": "BASIC",
    "is_available": true,
    "average_rating": 4.6,
    "working_radius_km": 5,
}
"""
