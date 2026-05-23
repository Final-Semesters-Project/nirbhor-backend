import enum
import uuid
from app.db.base import Base
from app.models.mixins.timestamp_mixin import TimestampMixin
from app.models.mixins.uuid_mixin import UUIDMixin
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Enum as sqlEnum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geometry


class BroadcastStatus(str, enum.Enum):
    BROADCASTING = "broadcasting"
    CLAIMED = "claimed"
    EXPIRED = "expired"

# is fcm like a message broker? does it store notification messages? what if user is offline?


class UrgentBroadcast(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "urgent_broadcasts"

    seeker_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    seeker: Mapped["User"] = relationship(  # type: ignore
        back_populates="urgent_broadcasts",
        foreign_keys=[seeker_id],
        uselist=False,
    )

    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id", ondelete="RESTRICT"),
        nullable=False,
    )
    skill: Mapped["Skill"] = relationship(uselist=False)  # type: ignore

    # PostGIS point — seeker's location at time of request
    location: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
        nullable=False,
    )

    status: Mapped[BroadcastStatus] = mapped_column(
        sqlEnum(
            BroadcastStatus,
            name="broadcast_status",
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=BroadcastStatus.BROADCASTING,
        server_default=BroadcastStatus.BROADCASTING.value,
    )

    # set atomically when first provider claims — nullable until claimed
    claimed_by_provider_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    claimed_by: Mapped["User | None"] = relationship(  # type: ignore
        back_populates="claimed_broadcasts",
        foreign_keys=[claimed_by_provider_id],  # two FKs → users, must specify
        uselist=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
