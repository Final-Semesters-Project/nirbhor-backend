from fastapi import Depends, HTTPException, status, APIRouter
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.i18n import MESSAGES, get_lang
from app.db.session import get_db_session

"""
# Domain 1: Bookings Management (/app/api/v1/bookings/)
- Handles: Intent-to-Book Workflow.
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

router = APIRouter(prefix="/bookings", tags=["Bookings"])

# Initiate a new booking: Seeker clicks "Request to Call" on a provider's profile


# @router.post(
#     "/initiate",
#     response_model=dict,
#     summary="Create a new category",
# )
# async def create_new_category(
#     data: CategoryCreateSchema,
#     db: AsyncSession = Depends(get_db_session),
#     lang: str = Depends(get_lang),
# ):
#     return await CategoryService.create_category(data=data, db=db, lang=lang)
