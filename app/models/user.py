from app.db.base import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Boolean
from pydantic import EmailStr
import enum
from sqlalchemy import Enum as sqlEnum, DateTime
from app.models.mixins.timestamp_mixin import TimestampMixin
from app.models.mixins.uuid_mixin import UUIDMixin
from datetime import datetime


class Role(enum.Enum):
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

    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    firebase_uid: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=True,
        index=True
    )  # Firebase phone/google auth UID

    google_email: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=True,
        index=True
    )  # Linked Google account email
