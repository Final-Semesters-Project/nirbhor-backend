from pydantic import BaseModel, ConfigDict, Field
import uuid
from app.models.provider_profile_model import VerificationLevel, VerificationStatus
from app.models.user_model import Role
from datetime import datetime


class SeekerMeSchema(BaseModel):
    user_id: uuid.UUID
    role: Role = Role.SEEKER
    phone: str
    name: str
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProviderMeSchema(BaseModel):
    user_id: uuid.UUID
    role: Role = Role.SEEKER
    phone: str
    name: str
    is_active: bool
    verification_level: VerificationLevel = Field(
        ...,
        description="Verification level of the provider. (basic, verified, trusted)",
    )
    verification_status: VerificationStatus = Field(
        ...,
        description="Verification status of the provider. (pending, approved, rejected)",
    )
    # verification_rejection_reason: str | None
    # base_location: str, point?

    working_radius_km: int
    has_smartphone: bool

    is_available: bool
    average_rating: float | None

    photo_url: str | None = None
    nid_url_front: str | None = None
    nid_url_back: str | None = None

    warning_status: bool

    ai_review_summary: str | None

    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
