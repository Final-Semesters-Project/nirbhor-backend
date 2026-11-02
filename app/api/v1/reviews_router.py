from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db_session
from app.core.i18n import get_lang
from app.api.dependencies import get_current_seeker, get_current_user
from app.models.user_model import User
from app.schemas.pagination_schema import PageResponse
from app.schemas.review_schema import ReviewCreateSchema, ReviewResponse, reviewListItem
from app.services.review_service import ReviewService

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.post("", response_model=ReviewResponse, status_code=201)
async def create_review(
    data: ReviewCreateSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """
    Submit a rating and optional comment after a booking is COMPLETED.
    Both seeker and provider can review. One review per party per booking.
    Seeker→Provider reviews update the provider's public average_rating.
    Provider→Seeker reviews are stored but private (admin only).
    """
    return await ReviewService.create_review(
        data=data,
        reviewer_id=current_user.id,
        reviewer_role=current_user.role,
        db=db,
        lang=lang,
    )


@router.get(
    "/provider/{provider_id}",
    summary="Seeker can see the reviews of a provider",
    response_model=PageResponse[reviewListItem]
)
async def get_provider_reviews(
    provider_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_seeker),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),

):
    return await ReviewService.get_provider_reviews(
        provider_id=provider_id,
        db=db,
        lang=lang,
        page_size=page_size,
        page=page
    )
