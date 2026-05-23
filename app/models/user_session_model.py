import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.mixins.uuid_mixin import UUIDMixin
from app.models.mixins.timestamp_mixin import TimestampMixin


class UserSession(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "user_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    user: Mapped["User"] = relationship(  # type: ignore
        back_populates="sessions",
        uselist=False,
    )

    refresh_token: Mapped[str] = mapped_column(
        String, nullable=False, unique=True)

    # "Android 14 | Samsung Galaxy A54 | App v1.2.0" — parsed from User-Agent
    device_info: Mapped[str | None] = mapped_column(String, nullable=True)

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
