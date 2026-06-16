from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime
from app.models.urgent_broadcast_model import BroadcastStatus


class UrgentBroadcastCreateSchema(BaseModel):
    skill_id: int
    latitude: float = Field(..., description="Seeker's latitude")
    longitude: float = Field(..., description="Seeker's longitude")


class UrgentBroadcastResponse(BaseModel):
    broadcast_id: UUID
    status: BroadcastStatus
    expires_at: datetime
    message: str

    model_config = ConfigDict(from_attributes=True)


class ClaimedBroadcastResponse(BaseModel):
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
