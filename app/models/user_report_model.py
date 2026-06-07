import uuid
from sqlalchemy import Enum as sqlEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.mixins.uuid_mixin import UUIDMixin
from app.models.mixins.timestamp_mixin import TimestampMixin
import enum


class ReportStatus(str, enum.Enum):
    PENDING = "pending"
    REVIEWED = "reviewed"
    ACTION_TAKEN = "action_taken"


class UserReport(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "user_reports"

    reporter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    reporter: Mapped["User"] = relationship(  # type: ignore
        back_populates="reports_made",
        foreign_keys=[reporter_id],  # two FKs → users
        uselist=False,
    )

    reported_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    reported_user: Mapped["User"] = relationship(  # type: ignore
        back_populates="reports_received",
        foreign_keys=[reported_user_id],
        uselist=False,
    )

    # nullable — report may not be tied to a specific booking
    booking_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("bookings.id", ondelete="SET NULL"),
        nullable=True,
    )
    booking: Mapped["Booking | None"] = relationship(  # type: ignore
        uselist=False)

    reason: Mapped[str] = mapped_column(String, nullable=False)

    status: Mapped[ReportStatus] = mapped_column(
        sqlEnum(
            ReportStatus,
            name="report_status",
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ReportStatus.PENDING,
        server_default=ReportStatus.PENDING.value,
    )
