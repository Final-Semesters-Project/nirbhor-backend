import uuid
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
from app.core.schema_validators import validate_radius
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
    working_radius_km: int | None

    skills: list[SkillInfo]

    model_config = ConfigDict(from_attributes=True)


class ProviderProfileUpdateSchema(BaseModel):
    # name: str | None = Field( # for auth profile update - both users
    # ..., description="Name of the provider. EN/BN name update based on the language selected")
    photo_url: str | None
    nid_url: str | None
    latitude: float | None = Field(
        ..., description="Limit updating location once in every 15 days and prompt to verify the working radius everytime the location is updated")
    longitude: float | None = Field(
        ..., description="Limit updating location once in every 15 days and prompt to verify the working radius everytime the location is updated")
    working_radius_km: int | None
    has_smartphone: bool | None
    is_available: bool | None

    @field_validator("working_radius_km", mode="after")
    @classmethod
    def validate_radius(cls, v: int, info: ValidationInfo) -> int:
        return validate_radius(v, info=info)

    """
    for admins to update
    verification_level: Mapped[VerificationLevel] = mapped_column(
        sqlEnum(
            VerificationLevel,
            name="verification_level",
            native_enum=False,  # to auto generate enum in alembic versions
            # values_callable is used to store the string values eg: "admin" instead of the Enum ADMIN in DB
            values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False,
        default=VerificationLevel.BASIC,
        server_default=VerificationLevel.BASIC.value
    )

    verification_status: Mapped[VerificationStatus] = mapped_column(
        sqlEnum(
            VerificationStatus,
            name="verification_status",
            native_enum=False,  # to auto generate enum in alembic versions
            # values_callable is used to store the string values eg: "admin" instead of the Enum ADMIN in DB
            values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False,
        default=VerificationStatus.PENDING,
        server_default=VerificationStatus.PENDING.value
    )

    verification_rejection_reason: Mapped[str | None] = mapped_column(
        String, nullable=True)

    # auto update
    average_rating: Mapped[float | None] = mapped_column(
        Float, nullable=True, default=None)

    warning_status: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False)

    ai_review_summary_en: Mapped[str | None] = mapped_column(
        String, nullable=True)

    ai_review_summary_bn: Mapped[str | None] = mapped_column(
        String, nullable=True)
    """
