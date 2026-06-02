import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.provider_profile_model import VerificationLevel


class SkillInfo(BaseModel):
    id: int
    name: str


class ProviderDashboardSchema(BaseModel):
    user_id: uuid.UUID
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
    working_radius_km: int
    skills: list[SkillInfo]

    model_config = ConfigDict(from_attributes=True)
