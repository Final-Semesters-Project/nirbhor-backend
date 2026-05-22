from app.db.base import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean
import enum
from sqlalchemy import Enum as sqlEnum, DateTime
from app.models.mixins.timestamp_mixin import TimestampMixin
from app.models.mixins.uuid_mixin import UUIDMixin
from datetime import datetime


class Role(str, enum.Enum):
    SEEKER = "seeker"
    PROVIDER = "provider"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

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
        server_default=Role.SEEKER.value
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )  # False = banned by admins

    last_active_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    firebase_uid: Mapped[str | None] = mapped_column(
        String,
        unique=True,
        nullable=True,
        index=True
    )  # Firebase phone/google auth UID

    google_email: Mapped[str | None] = mapped_column(
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
