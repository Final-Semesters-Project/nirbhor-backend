from app.db.base import Base
from app.models.mixins.timestamp_mixin import TimestampMixin
from app.models.mixins.uuid_mixin import UUIDMixin
from sqlalchemy import Integer, String, ForeignKey, Enum as sqlEnum, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid
import enum
from datetime import datetime
from geoalchemy2 import Geometry


class BookingStatus(str, enum.Enum):
    INITIATED = "initiated"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    AUTO_EXPIRED = "auto_expired"


class Booking(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "bookings"

    seeker_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # one booking belongs to one user but the relationship is many to one
    seeker: Mapped["User"] = relationship(  # type: ignore
        back_populates="bookings_as_seeker",
        foreign_keys=[seeker_id],
        uselist=False,
    )

    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # one booking belongs to one user but the relationship is many to one
    provider: Mapped["User"] = relationship(  # type: ignore
        back_populates="bookings_as_provider",
        foreign_keys=[provider_id],
        uselist=False,
    )

    skill_id: Mapped[int] = mapped_column(
        # don't delete the skill if a booking exists (ondelete="RESTRICT")
        ForeignKey("skills.id", ondelete="RESTRICT"),
        nullable=False,
    )

    skill: Mapped["Skill"] = relationship(  # type: ignore
        uselist=False,
        # No back_populates because we do not need skills.bookings
    )

    status: Mapped[BookingStatus] = mapped_column(
        sqlEnum(
            BookingStatus,
            name="booking_status",
            native_enum=False,  # to auto generate enum in alembic versions
            # values_callable is used to store the string values eg: "admin" instead of the Enum ADMIN in DB
            values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False,
        default=BookingStatus.INITIATED,
        server_default=BookingStatus.INITIATED.value
    )

    call_unlocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    work_schedule: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # PostGIS point — stores (longitude, latitude)
    job_location: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
        nullable=False,
    )

    # team_id and team relationship added later when Team model exists
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"),  # SET NULL not CASCADE
        nullable=True,
    )
    team: Mapped["Team | None"] = relationship(  # type: ignore
        back_populates="bookings",
        uselist=False,
    )

    # relationships to review model
    reviews: Mapped[list["Review"]] = relationship(  # type: ignore
        back_populates="booking",
        cascade="all, delete-orphan",
    )
