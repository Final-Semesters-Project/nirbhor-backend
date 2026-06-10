from uuid import UUID
from fastapi import APIRouter, Depends
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


"""

1. POST /api/v1/bookings/initiate
- Trigger: Seeker clicks "Request to Call" on a provider's profile.
- Logic:
    - Count active INITIATED records for the calling seeker; reject if they are spamming multiple open numbers simultaneously.

    - Insert a row into bookings with status = BookingStatus.INITIATED and set call_unlocked_at = datetime.utcnow().

    - Response: Returns the raw phone number of the provider so the frontend can trigger the native system dialer.

2. PATCH /api/v1/bookings/{booking_id}/respond
- Trigger: Seeker responds to the 2-hour or 24-hour FCM notification prompt ("Did you end up hiring...?").
Payload Schema: {"hired": bool, "work_schedule": datetime | None}
- Logic:
    - If hired == True: Update status directly to IN_PROGRESS (bypassing CONFIRMED as discussed) and save the explicit work_schedule. Automatically bump last_active_at for both users here to trigger Implied Activity tracking.

    - If hired == False: Update status to CANCELLED.

3. GET /api/v1/bookings/provider/me
- Trigger: Provider opens their "Incoming Bookings" tab (matches your incoming_bookings.png UI mockup).
- Logic: Query bookings table where provider_id == current_user.id AND status == BookingStatus.IN_PROGRESS. (This cleanly isolates and hides INITIATED records from their screen).

4. GET /api/v1/bookings/seeker/me
- Trigger: Seeker opens their booking history list.

- Logic: Query all records matching seeker_id == current_user.id (including INITIATED entries so they can see past numbers they requested).
"""
