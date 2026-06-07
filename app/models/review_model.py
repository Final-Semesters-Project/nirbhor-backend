import uuid
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.mixins.uuid_mixin import UUIDMixin
from app.models.mixins.timestamp_mixin import TimestampMixin


class Review(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "reviews"

    __table_args__ = (
        # CONSTRAINT 1: one review per party per booking
        # prevents seeker from submitting two reviews for same booking
        UniqueConstraint(
            "booking_id", "reviewer_id",
            name="uq_review_booking_reviewer"
        ),

        # CONSTRAINT 2: rating must be between 1 and 5
        CheckConstraint(
            "rating >= 1 AND rating <= 5",
            name="ck_review_rating_range"),
    )

    booking_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
    )
    booking: Mapped["Booking"] = relationship(  # type: ignore
        back_populates="reviews",
        uselist=False,
    )

    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    reviewer: Mapped["User"] = relationship(  # type: ignore
        back_populates="reviews_given",
        foreign_keys=[reviewer_id],  # two FKs → users, must specify
        uselist=False,
    )

    reviewee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    reviewee: Mapped["User"] = relationship(  # type: ignore
        back_populates="reviews_received",
        foreign_keys=[reviewee_id],
        uselist=False,
    )

    rating: Mapped[int] = mapped_column(Integer, nullable=False)

    comment: Mapped[str | None] = mapped_column(String, nullable=True)

    is_anonymous: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False)
