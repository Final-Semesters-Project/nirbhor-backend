from app.db.base import Base
from app.models.mixins.uuid_mixin import UUIDMixin
from app.models.mixins.timestamp_mixin import TimestampMixin
from sqlalchemy import String, ForeignKey, Enum as sqlEnum
import enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid


class DeviceType(str, enum.Enum):
    ANDROID = "android"
    IOS = "ios"
    WEB = "web"


class FCMToken(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "fcm_tokens"

    # may-to-1 with users, because user can have multiple devices
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
    )

    # one user has one fcm token, back-reference to user
    user: Mapped["User"] = relationship(  # type: ignore
        back_populates="fcm_token",
        uselist=False,
    )

    token: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    device_type: Mapped[DeviceType] = mapped_column(
        sqlEnum(
            DeviceType,
            name="device_type",
            native_enum=False,  # to auto generate enum in alembic versions
            # values_callable is used to store the string values eg: "admin" instead of the Enum ADMIN in DB
            values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False,
        default=DeviceType.ANDROID,
        server_default=DeviceType.ANDROID.value
    )
