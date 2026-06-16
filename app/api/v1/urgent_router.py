
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_provider, get_current_seeker
from app.core.i18n import get_lang
from app.db.session import get_db_session
from app.models.user_model import User
from app.schemas.urgent_schema import ClaimedBroadcastResponse, UrgentBroadcastCreateSchema, UrgentBroadcastDetailResponse, UrgentBroadcastResponse
from app.services.urgent_service import UrgentService


router = APIRouter(prefix="/urgentBroadcast", tags=["Urgent Broadcasts"])


@router.post(
    "/broadcast",
    response_model=UrgentBroadcastResponse,
    status_code=201
)
async def create_urgent_broadcast(
    data: UrgentBroadcastCreateSchema,
    current_user: User = Depends(get_current_seeker),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """
    Seeker triggers 'Need It NOW'.
    Creates broadcast row + fires FCM to all nearby providers with smartphones.
    Expires in 5 minutes if no one claims.
    """
    return await UrgentService.create_broadcast(
        data=data,
        seeker_id=current_user.id,
        db=db,
        lang=lang,
    )


@router.post("/broadcast/{broadcast_id}/claim", status_code=200, response_model=ClaimedBroadcastResponse)
async def claim_urgent_broadcast(
    broadcast_id: UUID,
    current_user: User = Depends(get_current_provider),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """
    Provider taps 'Accept'. Atomic pessimistic lock ensures only one wins.
    409 if another provider already claimed it.
    """
    return await UrgentService.claim_broadcast(
        broadcast_id=broadcast_id,
        provider_id=current_user.id,
        db=db,
        lang=lang,
    )


@router.get("/broadcast/{broadcast_id}", response_model=UrgentBroadcastDetailResponse)
async def get_broadcast_detail(
    broadcast_id: UUID,
    current_user: User = Depends(get_current_provider),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """
    Provider fetches broadcast details after tapping the FCM notification.
    Returns skill, status, and seeker coordinates for navigation.
    """
    return await UrgentService.get_broadcast(
        broadcast_id=broadcast_id,
        db=db,
        lang=lang,
    )
