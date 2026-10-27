from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone

from sqlalchemy.orm import Mapped, mapped_column
from app.models.mixins.timestamp_mixin import TimestampMixin
from app.models.mixins.uuid_mixin import UUIDMixin
from app.db.base import Base
import uuid


class AdminAuditLog(UUIDMixin, TimestampMixin, Base):
    """
    Records every admin action for super admin review.
    Written by the service layer whenever an admin performs
    a moderation action (approve, reject, suspend, toggle, etc.)
    """

    __tablename__ = "admin_audit_logs"

    # Who did the action
    admin_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,  # nullable so logs survive if admin is deleted
    )
    admin_role = Column(String, nullable=False)  # "admin" or "super_admin"

    # What they did
    action: Mapped[str] = mapped_column(
        String, nullable=False
    )  # "approve_verification", "suspend_user" etc.

    target_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    details: Mapped[str] = mapped_column(
        Text, nullable=True
    )  # JSON string of extra context

    ip_address: Mapped[str] = mapped_column(String, nullable=True)

    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
