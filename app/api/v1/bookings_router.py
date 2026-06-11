from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db_session
from app.core.i18n import get_lang
from app.api.dependencies import get_current_user, get_current_seeker, get_current_provider
from app.models.user_model import Role, User
from app.schemas.booking_schema import BookingInitiateResponse, BookingInitiateSchema, BookingListItem, BookingRespondFromNotificationSchema
from app.services.booking_service import BookingService
from app.core.exceptions import DomainValidationError
from app.core.i18n import t

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.post(
    "/initiate",
    response_model=BookingInitiateResponse,
    status_code=201,
    summary="Initiate a booking request and get provider phone number",
)
async def initiate_booking(
    data: BookingInitiateSchema,
    current_user: User = Depends(get_current_seeker),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """Seeker clicks 'Request to Call'. Creates booking, reveals provider phone."""
    return await BookingService.initiate_booking(
        data=data,
        seeker_id=current_user.id,
        db=db,
        lang=lang,
    )


@router.patch("/{booking_id}/respond", status_code=200)
async def respond_to_booking(
    booking_id: UUID,
    data: BookingRespondFromNotificationSchema,
    current_user: User = Depends(get_current_seeker),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """
    Seeker responds to the FCM follow-up.
    hired=true  → IN_PROGRESS + work_schedule required
    hired=false → CANCELLED
    """
    return await BookingService.respond_to_booking(
        booking_id=booking_id,
        data=data,
        seeker_id=current_user.id,
        db=db,
        lang=lang,
    )


@router.get("/provider/me",
            # response_model=list[BookingListItem]
            )
async def provider_incoming_bookings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """Provider's 'Incoming Bookings' tab — shows only IN_PROGRESS bookings."""
    if current_user.role != Role.PROVIDER:
        raise DomainValidationError(t("booking_not_yours", lang))

    return await BookingService.get_provider_incoming(
        provider_id=current_user.id,
        db=db,
        lang=lang,
    )


@router.get("/seeker/me", response_model=list[BookingListItem])
async def seeker_booking_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """Seeker's full booking history including open INITIATED entries."""
    if current_user.role != Role.SEEKER:
        raise DomainValidationError(t("booking_not_yours", lang))

    return await BookingService.get_seeker_history(
        seeker_id=current_user.id,
        db=db,
        lang=lang,
    )
"""
accept_language: Annotated[str | None,
                               Header(alias="Accept-Language")] = "en"
# Pass the header value down to your i18n handler or service layer
lang = "bn" if accept_language and accept_language.startswith(
        "bn") else "en"
"""
