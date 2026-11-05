from datetime import datetime, timedelta, timezone
from loguru import logger
from sqlalchemy import func, or_, select, update

from app.db.session import AsyncSessionLocal
from app.models.provider_profile_model import ProviderProfile, VerificationLevel, VerificationStatus
from app.models.review_model import Review
from app.models.user_model import User
from app.models.user_report_model import UserReport, ReportStatus

MIN_REVIEWS, MIN_REVIEWERS = 10, 5
PROMOTE_RATING, DEMOTE_RATING = 4.2, 3.8
REPORT_WINDOW_DAYS = 90


async def evaluate_provider_trust() -> None:
    """
    Promote (VERIFIED → TRUSTED):
      1. NID verified (level VERIFIED, status APPROVED), active account, no warning banner
      2. At least 10 reviews from at least 5 distinct seekers, so one friend can't pump the count
      3. Average rating of 4.2 or higher
      4. No PENDING or ACTION_TAKEN report against them in the last 90 days

    Demote (TRUSTED → VERIFIED):
      1. Rating below 3.8, or warning banner on, or an ACTION_TAKEN report in the last 90 days

    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=REPORT_WINDOW_DAYS)

    enough_reviews = (
        select(Review.reviewee_id)
        .group_by(Review.reviewee_id)
        .having(
            func.count() >= MIN_REVIEWS,
            func.count(func.distinct(Review.reviewer_id)) >= MIN_REVIEWERS,
        )
    )
    flagged = select(UserReport.reported_user_id).where(
        UserReport.created_at >= cutoff,
        UserReport.status.in_(
            [ReportStatus.PENDING, ReportStatus.ACTION_TAKEN]),
    )
    sanctioned = select(UserReport.reported_user_id).where(
        UserReport.created_at >= cutoff, UserReport.status == ReportStatus.ACTION_TAKEN
    )
    active_users = select(User.id).where(User.is_active.is_(True))

    async with AsyncSessionLocal() as db:
        promoted = (await db.execute(
            update(ProviderProfile)
            .where(
                ProviderProfile.verification_level == VerificationLevel.VERIFIED,
                ProviderProfile.verification_status == VerificationStatus.APPROVED,
                ProviderProfile.warning_status.is_(False),
                ProviderProfile.average_rating >= PROMOTE_RATING,
                ProviderProfile.user_id.in_(enough_reviews),
                ProviderProfile.user_id.in_(active_users),
                ProviderProfile.user_id.not_in(flagged),
            )
            .values(verification_level=VerificationLevel.TRUSTED)
            .returning(ProviderProfile.user_id)
        )).scalars().all()

        demoted = (await db.execute(
            update(ProviderProfile)
            .where(
                ProviderProfile.verification_level == VerificationLevel.TRUSTED,
                or_(
                    ProviderProfile.average_rating < DEMOTE_RATING,
                    ProviderProfile.warning_status.is_(True),
                    ProviderProfile.user_id.in_(sanctioned),
                ),
            )
            .values(verification_level=VerificationLevel.VERIFIED)
            .returning(ProviderProfile.user_id)
        )).scalars().all()

        await db.commit()

    if promoted or demoted:
        logger.info(
            f"Trust evaluation: {len(promoted)} promoted, {len(demoted)} demoted")
