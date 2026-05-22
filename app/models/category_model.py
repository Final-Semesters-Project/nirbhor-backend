from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.mixins.timestamp_mixin import TimestampMixin


class Category(TimestampMixin, Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    name_en: Mapped[str] = mapped_column(String, nullable=False)

    name_bn: Mapped[str] = mapped_column(String, nullable=False)

    # one category → many skills
    skills: Mapped[list["Skill"]] = relationship(  # type: ignore
        back_populates="category",
        cascade="all, delete-orphan",
    )
