from app.db.base import Base
from sqlalchemy import String, Integer, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.mixins.timestamp_mixin import TimestampMixin
from app.models.mixins.uuid_mixin import UUIDMixin
import uuid


class Team(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "teams"

    leader_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("provider_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
    )

    team_size: Mapped[int] = mapped_column(Integer, nullable=False)

    has_vehicle: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False)

    # many teams can have one leader (provider)
    leader: Mapped["ProviderProfile"] = relationship(  # type: ignore
        back_populates="teams",
        uselist=False,
    )

    # one team has many bookings (added after team_id added to Booking)
    bookings: Mapped[list["Booking"]] = relationship(  # type: ignore
        back_populates="team",
    )
