from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Update, func, literal_column, select

from app.models.provider_profile_model import ProviderProfile
from app.models.review_model import Review
from app.models.booking_model import Booking, BookingStatus
from app.models.user_model import User
from app.repositories.base_repository import BaseRepository

MIN_COST_SAMPLES, COST_WINDOW, ROUND_TO = 3, 20, 50


def _round(x: float) -> int:
    return int(round(x / ROUND_TO) * ROUND_TO)


class ReviewRepository(BaseRepository[Review]):
    def __init__(self, db: AsyncSession):
        super().__init__(Review, db)

    async def recompute_cost_range(self, provider_id: UUID) -> None:
        recent = (
            select(Booking.final_cost)
            .where(Booking.provider_id == provider_id, Booking.final_cost.is_not(None))
            .order_by(Booking.created_at.desc())
            .limit(COST_WINDOW)
            .subquery()
        )
        n, p25, p75 = (await self.db.execute(
            select(
                func.count(),
                func.percentile_cont(literal_column(
                    "0.25")).within_group(recent.c.final_cost),
                func.percentile_cont(literal_column(
                    "0.75")).within_group(recent.c.final_cost),
            ).select_from(recent)
        )).one()

        enough = n >= MIN_COST_SAMPLES
        await self.db.execute(
            Update(ProviderProfile)
            .where(ProviderProfile.user_id == provider_id)
            .values(
                cost_range_min=_round(p25) if enough else None,
                cost_range_max=_round(p75) if enough else None,
                cost_sample_count=n,
            )
        )

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

    def get_all_review_for_a_provider(
        self, provider_id: UUID
    ):
        """
        Returns the SELECT statement for provider reviews.
        Used by both paginate() to create paginated response.

        NOT async — returns a Select object, not a coroutine.
        The paginator needs the raw statement to apply LIMIT/OFFSET and COUNT.
        """
        return (
            select(Review, User)
            .join(User, Review.reviewer_id == User.id)
            .where(Review.reviewee_id == provider_id)
            .order_by(Review.created_at.desc())
        )
