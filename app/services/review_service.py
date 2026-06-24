from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import DomainIntegrityError, DomainValidationError
from app.core.i18n import t
from app.models.provider_profile_model import ProviderProfile
from app.models.user_model import Role
from app.repositories.review_repository import ReviewRepository
from app.schemas.review_schema import ReviewCreateSchema, ReviewResponse
from loguru import logger


class ReviewService:

    @staticmethod
    async def create_review(
        data: ReviewCreateSchema,
        reviewer_id: UUID,
        reviewer_role: Role,
        db: AsyncSession,
        lang: str,
    ) -> ReviewResponse:
        review_repo = ReviewRepository(db)

        # 1. Booking must be completed and confirmed
        booking = await review_repo.get_booking_for_review(data.booking_id)
        if not booking:
            raise DomainValidationError(t("review_not_eligible", lang))

        # 2. Reviewer must be a party to this booking
        if reviewer_id not in (booking.seeker_id, booking.provider_id):
            raise DomainValidationError(t("booking_not_yours", lang))

        # 3. Reviewee is the other party
        reviewee_id = (
            booking.provider_id
            if reviewer_id == booking.seeker_id
            else booking.seeker_id
        )

        # 4. One review per party per booking (check if reviewer has already reviewed)
        existing = await review_repo.get_existing_review(data.booking_id, reviewer_id)
        if existing:
            raise DomainIntegrityError(t("review_already_exists", lang))

        # 5. Create review
        review = await review_repo.create_review(
            booking_id=data.booking_id,
            reviewer_id=reviewer_id,
            reviewee_id=reviewee_id,
            rating=data.rating,
            comment=data.comment,
            is_anonymous=data.is_anonymous,
        )

        # 6. Recalculate provider's average rating
        # Only seeker→provider reviews affect public rating (spec: asymmetric trust)
        if reviewer_id == booking.seeker_id:
            new_avg = await review_repo.recalculate_provider_rating(reviewee_id)
            if new_avg is not None:
                provider_profile = await db.get(ProviderProfile, reviewee_id)
                if provider_profile:
                    provider_profile.average_rating = new_avg
                    # Auto-flag low ratings per spec
                    provider_profile.warning_status = new_avg < 3.0
                    logger.info(
                        f"Provider {reviewee_id} avg rating updated to {new_avg:.2f}"
                    )

        await db.commit()
        logger.info(
            f"Review created: booking {data.booking_id} "
            f"by {reviewer_id} → {reviewee_id} rating={data.rating}"
        )

        return ReviewResponse(
            review_id=review.id,
            booking_id=review.booking_id,
            rating=review.rating,
            comment=review.comment,
            is_anonymous=review.is_anonymous,
        )
