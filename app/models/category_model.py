from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.mixins.uuid_mixin import UUIDMixin
from app.models.mixins.timestamp_mixin import TimestampMixin


class Category(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "categories"

    name_en: Mapped[str] = mapped_column(String, nullable=False)

    name_bn: Mapped[str] = mapped_column(String, nullable=False)

    skills: Mapped[list["Skill"]] = relationship(  # type: ignore
        back_populates="category",
        uselist=True,  # one category has many skills, -> returns a list
    )
