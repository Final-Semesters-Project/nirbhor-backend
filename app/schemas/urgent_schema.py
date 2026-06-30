from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime
from app.models.urgent_broadcast_model import BroadcastStatus


class UrgentBroadcastCreateSchema(BaseModel):
    skill_id: int
    latitude: float = Field(..., description="Seeker's latitude")
    longitude: float = Field(..., description="Seeker's longitude")


class UrgentBroadcastCreateResponse(BaseModel):
    """Seeker receives this when they initiate an urgent broadcast."""
    broadcast_id: UUID
    status: BroadcastStatus
    expires_at: datetime
    message: str

    model_config = ConfigDict(from_attributes=True)


class BroadcastStatusResponseForSeeker(BaseModel):
    """
    Used when FCM fails to show the provider data to seeker then use this as fallback.
    Seeker polls this to check if their urgent broadcast was claimed.
    Returns claimed provider's name only — phone is shared via FCM separately.
    In your current stub phase the seeker can poll this endpoint as fallback.
    """
    broadcast_id: UUID
    status: BroadcastStatus
    expires_at: datetime
    seconds_remaining: int
    claimed_by_name: str | None     # None if not yet claimed
    # claimed_at: datetime | None     # None if not yet claimed

    model_config = {"from_attributes": True}


class ClaimedBroadcastResponseToProvider(BaseModel):
    """
    Returned to provider after successfully claiming a broadcast.
    Includes seeker phone so provider can call immediately.
    """
    broadcast_id: UUID
    status: BroadcastStatus
    seeker_name: str
    seeker_phone: str

    model_config = ConfigDict(from_attributes=True)


class UrgentBroadcastDetailResponse(BaseModel):
    """Returned when provider fetches broadcast details after FCM tap."""
    broadcast_id: UUID
    status: BroadcastStatus
    skill_id: int
    skill_name: str
    expires_at: datetime
    seeker_latitude: float | None   # so provider can navigate
    seeker_longitude: float | None

    model_config = ConfigDict(from_attributes=True)
