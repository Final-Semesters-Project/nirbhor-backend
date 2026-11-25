from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request, Response
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_provider, get_current_seeker, get_current_user
from app.core.i18n import get_lang
from app.db.session import get_db_session
from app.models.urgent_broadcast_model import BroadcastStatus
from app.models.user_model import User
from app.schemas.pagination_schema import PageResponse
from app.schemas.urgent_schema import BroadcastStatusResponseForSeeker, ClaimedBroadcastResponseToProvider, CompleteUrgentBroadcastResponse, ProviderCancelBroadcastResponse, ProviderUrgentBroadcastItem, SeekerUrgentBroadcastItem, UrgentBroadcastCreateSchema, UrgentBroadcastDetailResponse, UrgentBroadcastCreateResponse
from app.services.urgent_service import UrgentService
from app.core.rate_limiter import limiter

router = APIRouter(prefix="/urgentBroadcast", tags=["Urgent Broadcasts"])


@router.post(
    "/broadcast",
    response_model=UrgentBroadcastCreateResponse,
    status_code=201
)
@limiter.limit("3/minute")  # prevent broadcast spam
async def create_urgent_broadcast(
    request: Request,
    response: Response,
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
    result = await UrgentService.create_broadcast(
        data=data,
        seeker_id=current_user.id,
        db=db,
        lang=lang,
    )
    if result.status == "no_providers":
        response.status_code = 200
    return result


@router.get("/seeker/broadcasts", response_model=PageResponse[SeekerUrgentBroadcastItem])
async def get_my_urgent_broadcasts_as_seeker(
    status_filter: BroadcastStatus | None = Query(None, alias="status"),
    active_only: bool = Query(
        False, description="Only broadcasting or claimed"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_seeker),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """All urgent broadcasts of this seeker (current, completed, cancelled, expired), newest first."""
    return await UrgentService.get_seeker_broadcasts(
        seeker_id=current_user.id, db=db, lang=lang, page=page, page_size=page_size,
        status=status_filter, active_only=active_only)


@router.get("/provider/broadcasts", response_model=PageResponse[ProviderUrgentBroadcastItem])
async def get_my_urgent_broadcasts_as_provider(
    status_filter: BroadcastStatus | None = Query(None, alias="status"),
    active_only: bool = Query(
        False, description="Only jobs currently claimed"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_provider),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """All urgent jobs this provider accepted, newest first."""
    return await UrgentService.get_provider_broadcasts(
        provider_id=current_user.id, db=db, lang=lang, page=page, page_size=page_size,
        status=status_filter, active_only=active_only)


@router.patch("/broadcast/{broadcast_id}/provider-cancel",
              response_model=ProviderCancelBroadcastResponse, status_code=200)
async def cancel_broadcast_by_provider(
    broadcast_id: UUID,
    current_user: User = Depends(get_current_provider),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """Provider releases an accepted urgent job. The seeker gets a push to request again."""
    return await UrgentService.cancel_broadcast_by_provider(
        broadcast_id=broadcast_id, provider_id=current_user.id, db=db, lang=lang)


@router.post("/broadcast/{broadcast_id}/claim", status_code=200, response_model=ClaimedBroadcastResponseToProvider)
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


@router.post("/broadcast/{broadcast_id}/completed", status_code=200,
             response_model=CompleteUrgentBroadcastResponse
             )
async def complete_urgent_broadcast(
    broadcast_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """
    Provider/Seeker Completes an urgent broadcast. Atomic pessimistic lock ensures only one wins.
    409 if seeker/provider already completes it.
    """
    return await UrgentService.complete_broadcast(
        broadcast_id=broadcast_id,
        user_id=current_user.id,
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


@router.get("/broadcast/{broadcast_id}/status", response_model=BroadcastStatusResponseForSeeker)
async def get_broadcast_status(
    broadcast_id: UUID,
    current_user: User = Depends(get_current_seeker),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """
    Seeker polls this to check if their urgent broadcast was claimed.
    Frontend polls every 10-15 seconds while the countdown timer is showing.
    When status changes to CLAIMED, show the provider name on screen.
    Stop polling when status is CLAIMED or EXPIRED.
    """
    return await UrgentService.get_broadcast_status(
        broadcast_id=broadcast_id,
        db=db,
        lang=lang,
    )


@router.patch("/broadcast/{broadcast_id}/cancel", status_code=200)
async def cancel_broadcast(
    broadcast_id: UUID,
    current_user: User = Depends(get_current_seeker),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """
    Seeker cancels an urgent broadcast by tapping 'Cancel'.
    """
    return await UrgentService.cancel_broadcast(
        broadcast_id=broadcast_id,
        db=db,
        lang=lang,
        current_user_id=current_user.id,
    )
