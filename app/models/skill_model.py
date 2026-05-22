import uuid
from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Enum as sqlEnum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
import enum
from app.models.mixins.uuid_mixin import UUIDMixin
from app.models.mixins.timestamp_mixin import TimestampMixin


class Skill(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "skills"

    name_en: Mapped[str] = mapped_column(String, nullable=False)

    name_bn: Mapped[str] = mapped_column(String, nullable=False)

    # skill to category is many-to-1
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False
    )

    # back-reference to category
    category: Mapped["Category"] = relationship(  # type: ignore
        back_populates="skills",
        uselist=False,  # one skill belongs to one category, -> uselist=False
    )
