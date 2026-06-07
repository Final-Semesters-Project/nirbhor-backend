from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from geoalchemy2.functions import ST_MakePoint, ST_SetSRID
from app.models.booking_model import Booking, BookingStatus
from app.models.user_model import User
from app.repositories.base_repository import BaseRepository


class BookingRepository(BaseRepository[Booking]):
    def __init__(self, db: AsyncSession):
        super().__init__(Booking, db)

    async def count_active_initiated(self, seeker_id: UUID) -> int:
        """
        Count INITIATED bookings from this seeker within the last 2 hours.
        We only count within 2 hours because that's when the first FCM fires.
        After 2 hours the seeker is done unlocking numbers for this session.
        """
        two_hours_ago = datetime.utcnow() - timedelta(hours=2)
        result = await self.db.execute(
            select(func.count())
            .where(Booking.seeker_id == seeker_id)
            .where(Booking.status == BookingStatus.INITIATED)
            # within current session
            .where(Booking.call_unlocked_at >= two_hours_ago)
        )
        return result.scalar_one()
