from app.db.base import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Index, String, Boolean
import enum
from sqlalchemy import Enum as sqlEnum, DateTime
from app.models.mixins.timestamp_mixin import TimestampMixin
from app.models.mixins.uuid_mixin import UUIDMixin
from datetime import datetime
from pydantic import EmailStr


class Role(str, enum.Enum):
    SEEKER = "seeker"
    PROVIDER = "provider"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    name_en: Mapped[str] = mapped_column(String, nullable=False)

    name_bn: Mapped[str] = mapped_column(String, nullable=False)

    phone_en: Mapped[str] = mapped_column(
        String, nullable=False, unique=True, index=True)  # Login and Calls

    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[Role] = mapped_column(
        sqlEnum(
            Role,
            name="role",
            native_enum=False,  # to auto generate enum in alembic versions
            # values_callable is used to store the string values eg: "admin" instead of the Enum ADMIN in DB
            values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False,
        default=Role.SEEKER,
        server_default=Role.SEEKER.value,
        # index=True
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )  # False = banned by admins

    last_active_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        # index=True
    )

    firebase_uid: Mapped[str | None] = mapped_column(
        String,
        unique=True,
        nullable=True,
        index=True
    )  # Firebase phone/google auth UID

    google_email: Mapped[EmailStr | None] = mapped_column(
        String,
        unique=True,
        nullable=True,
        index=True
    )  # Linked Google account email

    # 1-1 relationship to provider profile (let us do user.provider_profile)
    provider_profile: Mapped["ProviderProfile | None"] = relationship(  # type: ignore
        back_populates="user",
        uselist=False,  # for 1-to-1
        cascade="all, delete-orphan"  # delete profile when user is deleted
    )

    # 1-to-many relationship to fcm token
    fcm_token: Mapped[list["FCMToken"]] = relationship(  # type: ignore
        back_populates="user",
        uselist=True,  # for 1-to-many
        cascade="all, delete-orphan"  # delete token when user is deleted
    )

    bookings_as_seeker: Mapped[list["Booking"]] = relationship(  # type: ignore
        back_populates="seeker",
        foreign_keys="Booking.seeker_id",
        cascade="all, delete-orphan"
    )

    bookings_as_provider: Mapped[list["Booking"]] = relationship(  # type: ignore
        back_populates="provider",
        foreign_keys="Booking.provider_id",
        # No cascade because deleting a user shouldn't delete booking records
    )

    # relationship to urgent broadcast
    urgent_broadcasts: Mapped[list["UrgentBroadcast"]] = relationship(  # type: ignore
        back_populates="seeker",
        foreign_keys="UrgentBroadcast.seeker_id",
    )

    claimed_broadcasts: Mapped[list["UrgentBroadcast"]] = relationship(  # type: ignore
        back_populates="claimed_by",
        foreign_keys="UrgentBroadcast.claimed_by_provider_id",
    )

    # relationship to user session
    sessions: Mapped[list["UserSession"]] = relationship(  # type: ignore
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # relationship to user report
    reports_made: Mapped[list["UserReport"]] = relationship(  # type: ignore
        back_populates="reporter",
        foreign_keys="UserReport.reporter_id",
    )
    reports_received: Mapped[list["UserReport"]] = relationship(  # type: ignore
        back_populates="reported_user",
        foreign_keys="UserReport.reported_user_id",
    )

    # relationship to review
    reviews_given: Mapped[list["Review"]] = relationship(  # type: ignore
        back_populates="reviewer",
        foreign_keys="Review.reviewer_id",
    )

    reviews_received: Mapped[list["Review"]] = relationship(  # type: ignore
        back_populates="reviewee",
        foreign_keys="Review.reviewee_id",
    )

    __table_args__ = (
        Index("ix_users_created_at", "created_at", "id"),
    )
