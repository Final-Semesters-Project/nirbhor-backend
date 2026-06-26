from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
from app.core.schema_validators import validate_radius
from app.models.provider_profile_model import VerificationLevel


class SkillInfo(BaseModel):
    id: int
    name: str


class ProviderDashboardSchema(BaseModel):
    user_id: UUID
    name: str = Field(...,
                      description="EN/BN Name of the provider based on the language")
    photo_url: str | None = Field(
        ...,
        description="Photo URL of the provider. None if there is no photo yet",
    )
    is_available: bool = Field(
        ...,
        description="For I am available",
    )
    verification_level: VerificationLevel = Field(
        ..., description="Verification level of the provider. (basic, verified, trusted)")
    average_rating: float | None = Field(
        ...,
        description="Average rating of the provider. None if there is no rating yet",
    )
    total_jobs_done: int | None = Field(
        ...,
        description="Total number of jobs done by the provider. None if there are no jobs done yet",
    )
    ai_review_summary: str | None
    working_radius_km: int | None

    skills: list[SkillInfo]

    model_config = ConfigDict(from_attributes=True)


class ProviderProfileUpdateSchema(BaseModel):
    # name: str | None = Field( # for auth profile update - both users
    # ..., description="Name of the provider. EN/BN name update based on the language selected")
    photo_url: str | None = None
    photo_public_id: str | None = None

    nid_url_front: str | None = None
    nid_front_public_id: str | None = None

    nid_url_back: str | None = None
    nid_back_public_id: str | None = None

    latitude: float | None = Field(
        None, description="Limit updating location once in every 15 days and prompt to verify the working radius everytime the location is updated")
    longitude: float | None = Field(
        None, description="Limit updating location once in every 15 days and prompt to verify the working radius everytime the location is updated")
    working_radius_km: int | None = None
    has_smartphone: bool | None = None
    is_available: bool | None = None

    @field_validator("working_radius_km", mode="after")
    @classmethod
    def validate_radius(cls, v: int, info: ValidationInfo) -> int:
        if v is None:
            return None
        return validate_radius(v, info=info)


class AddNewSkillSchema(BaseModel):
    skill_ids: list[int]


class PublicSkill(BaseModel):
    id: int
    name: str   # localized

    model_config = ConfigDict(from_attributes=True)


class PublicProviderProfile(BaseModel):
    """
    Public-facing provider profile — visible to seekers.
    Phone is intentionally excluded (revealed only after booking initiation).
    NID urls excluded (private documents).
    """
    user_id: UUID
    name: str                           # localized
    photo_url: str | None
    verification_level: VerificationLevel
    average_rating: float | None
    working_radius_km: int
    has_smartphone: bool
    is_available: bool
    ai_review_summary: str | None       # localized
    skills: list[PublicSkill]
    last_active_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
