import uuid
from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Enum as sqlEnum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
import enum
from app.models.mixins.timestamp_mixin import TimestampMixin


class VerificationLevel(str, enum.Enum):
    BASIC = "basic"
    VERIFIED = "verified"
    TRUSTED = "trusted"


class VerificationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ProviderProfile(TimestampMixin, Base):
    __tablename__ = "provider_profiles"

    # 1-to-1 with users — user_id IS the primary key
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )  # this is the primary key, No UUIDMixin

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
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
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

    # add skill_links relationship
    skill_links: Mapped[list["ProviderSkillLink"]] = relationship(  # type: ignore
        back_populates="provider",
        cascade="all, delete-orphan",
    )
