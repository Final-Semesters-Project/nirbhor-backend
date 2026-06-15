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
    broadcast_id: UUID
    status: BroadcastStatus
    yours: bool
    seeker_phone: str

    model_config = ConfigDict(from_attributes=True)
