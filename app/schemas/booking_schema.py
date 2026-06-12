from uuid import UUID
from loguru import logger
from pydantic import BaseModel, model_validator, field_validator, Field, ConfigDict
from datetime import datetime, timezone
from app.core.i18n import t
from app.models.booking_model import BookingStatus


class BookingInitiateSchema(BaseModel):
    """Seeker clicks 'Request to Call' on a provider profile."""
    provider_id: UUID
    skill_id: int
    latitude: float = Field(..., description="Seeker's latitude")
    longitude: float = Field(..., description="Seeker's longitude")


class BookingInitiateResponse(BaseModel):
    booking_id: UUID
    provider_phone: str = Field(
        ...,
        description="Revealed only after initiation")
    provider_name: str
    status: BookingStatus

    model_config = ConfigDict(from_attributes=True)


class BookingRespondFromNotificationSchema(BaseModel):
    """Seeker responds to the FCM follow-up notification."""
    hired: bool
    work_schedule: datetime | None = None

    @model_validator(mode="after")
    def work_schedule_required_if_hired(self) -> "BookingRespondFromNotificationSchema":
        if self.hired and self.work_schedule is None:
            raise ValueError("work schedule is required when hired is true.")
        return self

    @field_validator("work_schedule")
    @classmethod
    def work_schedule_must_be_future(cls, v: datetime | None) -> datetime | None:
        if v is not None and v <= datetime.now(timezone.utc):
            raise ValueError("work schedule must be a future time.")
        return v


class BookingListItem(BaseModel):
    """Used for both seeker history and provider incoming list."""
    booking_id: UUID
    status: BookingStatus
    skill_id: int
    skill_name: str
    created_at: datetime
    work_schedule: datetime | None
    # seeker sees provider info; provider sees seeker info
    other_party_name: str
    other_party_phone: str | None  # None until INITIATED for seeker view

    model_config = ConfigDict(from_attributes=True)
