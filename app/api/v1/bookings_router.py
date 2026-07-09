from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db_session
from app.core.i18n import get_lang
from app.api.dependencies import get_current_seeker, get_current_provider, get_current_user
from app.models.user_model import User
from app.schemas.booking_schema import BookingInitiateResponse, BookingInitiateSchema, BookingListItem, BookingRespondFromNotificationSchema, LastInitiatedActiveBookingSchema, SingleBookingDetailResponse
from app.schemas.pagination_schema import PageResponse
from app.services.booking_service import BookingService
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


@router.get("/provider/me", response_model=PageResponse[BookingListItem])
async def provider_incoming_bookings(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_provider),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """Provider's 'Incoming Bookings' tab — shows only IN_PROGRESS bookings."""
    return await BookingService.get_provider_incoming(
        provider_id=current_user.id,
        db=db,
        lang=lang,
        page=page,
        page_size=page_size
    )


@router.get("/provider/me/completed", response_model=list[BookingListItem])
async def provider_completed_bookings(
    current_user: User = Depends(get_current_provider),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """Provider's 'Incoming Bookings' tab — shows only IN_PROGRESS bookings."""
    return await BookingService.get_providers_completed_bookings(
        provider_id=current_user.id,
        db=db,
        lang=lang,
    )


@router.get("/seeker/me", response_model=PageResponse[BookingListItem])
async def seeker_booking_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_seeker),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """Seeker's full booking history including open INITIATED entries."""
    return await BookingService.get_seeker_history(
        seeker_id=current_user.id,
        db=db,
        lang=lang,
        page=page,
        page_size=page_size
    )


@router.get("/seeker/last_active_initiated", response_model=LastInitiatedActiveBookingSchema)
async def seekers_last_active_initiated_bookings(
    current_user: User = Depends(get_current_seeker),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """
    Called when seeker opens/foregrounds the app.
    When seeker initiates a new booking by getting the phone number and returns to the app afterwards,
    the app will show the last initiated booking on the home screen/search page. Seeker can click "CANCEL" if the booking is cancelled or Confirm if it's accepted.
    Accepting the booking will ask for the work schedule. If the seeker opens the  
    """
    return await BookingService.get_seeker_last_active_initiated(
        seeker_id=current_user.id,
        db=db,
        lang=lang
    )


@router.get("/{booking_id}", response_model=SingleBookingDetailResponse)
async def get_booking_detail(
    booking_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """
    Single booking detail — accessible by both seeker and provider of that booking.
    Shows job location coordinates to provider when status is IN_PROGRESS.
    """

    return await BookingService.get_single_booking(
        booking_id=booking_id,
        current_user_id=current_user.id,
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
    hired=false → CANCELLED.

    Let seekers confirm the bookings from the "My Bookings" page if the status == INITIATED. So that they doesn't have to wait for the FCM notification.
    If the seeker already confirms the booking, then it will show IN_PROGRESS.
    """
    return await BookingService.respond_to_booking(
        booking_id=booking_id,
        data=data,
        seeker_id=current_user.id,
        db=db,
        lang=lang,
    )


@router.patch("/{booking_id}/complete", status_code=200)
async def mark_booking_completed(
    booking_id: UUID,
    current_user: User = Depends(get_current_seeker),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """Seeker confirms the job is done, triggered by the completion prompt FCM. or from the "My Bookings -> Single Booking Details" page if the status == IN_PROGRESS. Then the review form will show."""
    return await BookingService.mark_completed(
        booking_id=booking_id,
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
