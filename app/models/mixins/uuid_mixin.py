import uuid
from sqlalchemy import UUID
from sqlalchemy.orm import Mapped, mapped_column

# Mixins are used, so that we don't have to repeat the same code in every model


class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
