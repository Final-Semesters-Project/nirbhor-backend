import uuid
from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Enum as sqlEnum, Float, ForeignKey, Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
import enum
from app.models.mixins.uuid_mixin import UUIDMixin
from app.models.mixins.timestamp_mixin import TimestampMixin
from pydantic import EmailStr


class VerificationLevel(str, enum.Enum):
    BASIC = "BASIC"
    VERIFIED = "VERIFIED"
    TRUSTED = "TRUSTED"


class VerificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ProviderProfile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "provider_profiles"

    # 1-to-1 with users — user_id IS the primary key
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # back-reference to user
    user: Mapped["User"] = relationship(  # type: ignore
        back_populates="provider_profile",
        uselist=False,
    )

    name_en: Mapped[str] = mapped_column(String, nullable=False)

    name_bn: Mapped[str] = mapped_column(String, nullable=False)

    photo_url: Mapped[str | None] = mapped_column(String, nullable=True)

    nid_url: Mapped[str | None] = mapped_column(String, nullable=True)

    verification_level: Mapped[VerificationLevel] = mapped_column(
        sqlEnum(
            VerificationLevel,
            name="verification_level",
            native_enum=False,  # to auto generate enum in alembic versions
            # values_callable is used to store the string values eg: "admin" instead of the Enum ADMIN in DB
            values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False,
        default=VerificationLevel.BASIC,
        server_default=VerificationLevel.BASIC.value
    )

    verification_status: Mapped[VerificationStatus] = mapped_column(
        sqlEnum(
            VerificationStatus,
            name="verification_status",
            native_enum=False,  # to auto generate enum in alembic versions
            # values_callable is used to store the string values eg: "admin" instead of the Enum ADMIN in DB
            values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False,
        default=VerificationStatus.PENDING,
        server_default=VerificationStatus.PENDING.value
    )

    verification_rejection_reason: Mapped[str | None] = mapped_column(
        String, nullable=True)

    # PostGIS point — stores (longitude, latitude)
    base_location: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326),
        nullable=False,
    )

    working_radius_km: Mapped[int] = mapped_column(Integer, nullable=False)

    has_smartphone: Mapped[bool] = mapped_column(Boolean, nullable=False)

    is_available: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False)

    average_rating: Mapped[float | None] = mapped_column(
        Float, nullable=True, default=None)

    warning_status: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False)

    ai_review_summary_en: Mapped[str | None] = mapped_column(
        String, nullable=True)

    ai_review_summary_bn: Mapped[str | None] = mapped_column(
        String, nullable=True)
