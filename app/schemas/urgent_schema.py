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
    broadcast_id: UUID | None
    status: BroadcastStatus | str = Field(...,
                                          description="broadcasting or no_providers")
    expires_at: datetime | None
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


class UrgentBroadcastCancelResponse(BaseModel):
    broadcast_id: UUID
    status: BroadcastStatus
    message: str


class SeekerUrgentBroadcastItem(BaseModel):
    """One row of the seeker's urgent history. Provider phone only while CLAIMED."""
    broadcast_id: UUID
    status: BroadcastStatus
    skill_id: int
    skill_name: str
    created_at: datetime
    expires_at: datetime
    # only while BROADCASTING, to restore the countdown
    seconds_remaining: int | None
    cancelled_at: datetime | None
    provider_name: str | None          # None until someone claims
    provider_phone: str | None         # only while the job is active (CLAIMED)

    model_config = ConfigDict(from_attributes=True)


class ProviderUrgentBroadcastItem(BaseModel):
    """One row of the provider's accepted urgent jobs. Phone and location only while CLAIMED."""
    broadcast_id: UUID
    status: BroadcastStatus
    skill_id: int
    skill_name: str
    created_at: datetime
    cancelled_at: datetime | None
    seeker_name: str
    seeker_phone: str | None
    seeker_latitude: float | None
    seeker_longitude: float | None

    model_config = ConfigDict(from_attributes=True)


class ProviderCancelBroadcastResponse(BaseModel):
    broadcast_id: UUID
    status: BroadcastStatus
    message: str


class CompleteUrgentBroadcastResponse(BaseModel):
    broadcast_id: UUID
    status: BroadcastStatus
    completed_at: datetime
    message: str

    model_config = ConfigDict(from_attributes=True)
