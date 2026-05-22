from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.mixins.timestamp_mixin import TimestampMixin
import uuid


class ProviderSkillLink(TimestampMixin, Base):
    __tablename__ = "provider_skill_links"

    # both provider_id and skill_id are primary keys. This makes it a composite primary key
    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("provider_profiles.user_id", ondelete="CASCADE"),
        primary_key=True,
    )  # user_id is the primary key of provider_profiles

    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # back-reference to provider
    provider: Mapped["ProviderProfile"] = relationship(  # type: ignore
        back_populates="skill_links",
    )

    # back-reference to skill
    skill: Mapped["Skill"] = relationship(  # type: ignore
        back_populates="provider_links",
    )
