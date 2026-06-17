from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.review_model import Review
from app.models.booking_model import Booking, BookingStatus
from app.repositories.base_repository import BaseRepository


class ReviewRepository(BaseRepository[Review]):
    def __init__(self, db: AsyncSession):
        super().__init__(Review, db)

    async def get_booking_for_review(self, booking_id: UUID) -> Booking | None:
        """
        Fetch booking only if it's eligible for review:
        status=COMPLETED and confirmed_at IS NOT NULL.
        """
        result = await self.db.execute(
            select(Booking)
            .where(Booking.id == booking_id)
            .where(Booking.status == BookingStatus.COMPLETED)
            .where(Booking.confirmed_at.is_not(None))
        )
        return result.scalar_one_or_none()
