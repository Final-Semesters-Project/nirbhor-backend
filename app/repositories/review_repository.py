from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.review_model import Review
from app.models.booking_model import Booking, BookingStatus
from app.repositories.base_repository import BaseRepository


class ReviewRepository(BaseRepository[Review]):
    def __init__(self, db: AsyncSession):
        super().__init__(Review, db)

    async def create_review(
        self,
        booking_id: UUID,
        reviewer_id: UUID,
        reviewee_id: UUID,
        rating: int,
        comment: str | None,
        is_anonymous: bool,
    ) -> Review:
        review = Review(
            booking_id=booking_id,
            reviewer_id=reviewer_id,
            reviewee_id=reviewee_id,
            rating=rating,
            comment=comment,
            is_anonymous=is_anonymous,
        )
        self.db.add(review)
        await self.db.flush()
        return review

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

    async def get_existing_review(
        self, booking_id: UUID, reviewer_id: UUID
    ) -> Review | None:
        """Check if this reviewer already reviewed this booking."""
        result = await self.db.execute(
            select(Review)
            .where(Review.booking_id == booking_id)
            .where(Review.reviewer_id == reviewer_id)
        )
        return result.scalar_one_or_none()

    async def recalculate_provider_rating(
        self, provider_id: UUID
    ) -> float | None:
        """
        Recalculate and return the new average rating for a provider.
        Called after every new review. Service writes it back to ProviderProfile.
        """
        from sqlalchemy import func
        result = await self.db.execute(
            select(func.avg(Review.rating))
            .where(Review.reviewee_id == provider_id)
        )
        return result.scalar_one_or_none()
