import enum
from sqlalchemy import Enum as sqlEnum, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.models.mixins.uuid_mixin import UUIDMixin
from app.models.mixins.timestamp_mixin import TimestampMixin


class Platform(str, enum.Enum):
    ANDROID = "android"
    IOS = "ios"


class AppVersion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "app_versions"

    platform: Mapped[Platform] = mapped_column(
        sqlEnum(
            Platform,
            name="platform",
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        unique=True,  # one row per platform
    )

    # app will be blocked if version is below this
    minimum_required_version: Mapped[str] = mapped_column(
        String, nullable=False)

    # shown in "update available" banner
    latest_version: Mapped[str] = mapped_column(String, nullable=False)
