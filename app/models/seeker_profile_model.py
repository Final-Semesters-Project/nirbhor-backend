import uuid
from geoalchemy2 import Geometry
from sqlalchemy import (
    ForeignKey,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.mixins.timestamp_mixin import TimestampMixin


class SeekerProfile(TimestampMixin, Base):
    __tablename__ = "seeker_profiles"

    # 1-to-1 with users — user_id IS the primary key
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )  # this is the primary key, No UUIDMixin

    # back-reference to user
    user: Mapped["User"] = relationship(  # type: ignore
        back_populates="seeker_profile",
        uselist=False,
    )

    # PostGIS point — stores (longitude, latitude)
    home_location: Mapped[object] = mapped_column(
        Geometry(
            geometry_type="POINT", srid=4326, spatial_index=False
        ),  # Make it false after migration
        nullable=False,
    )

    home_address: Mapped[str] = mapped_column(String(255), nullable=False)
