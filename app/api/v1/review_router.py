from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db_session
from app.core.i18n import get_lang
from app.api.dependencies import get_current_user
from app.models.user_model import User
from app.schemas.review_schema import ReviewCreateSchema, ReviewResponse
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
