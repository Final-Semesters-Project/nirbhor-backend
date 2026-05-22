import uuid
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.mixins.timestamp_mixin import TimestampMixin


class Skill(TimestampMixin, Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    name_en: Mapped[str] = mapped_column(String, nullable=False)

    name_bn: Mapped[str] = mapped_column(String, nullable=False)

    # skill to category is many-to-1
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False
    )

    # many skills → one category, back-reference to category
    category: Mapped["Category"] = relationship(  # type: ignore
        back_populates="skills",
        uselist=False,  # one skill belongs to one category, -> uselist=False
    )

    # one skill → many provider_skill_links, relationship to provider_skill_link
    provider_links: Mapped[list["ProviderSkillLink"]] = relationship(  # type: ignore
        back_populates="skill",
    )
