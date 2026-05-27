from loguru import logger
from pydantic import BaseModel, ConfigDict, field_validator, Field, ValidationInfo
import re
from uuid import UUID
from app.core.schema_validators import validate_phone, validate_password, validate_radius
from app.core.i18n import MESSAGES


# def validate_phone(phone: str, info: ValidationInfo) -> str:
#     """Validates Bangladeshi phone numbers: 01XXXXXXXXX"""
#     pattern = r'^01[3-9]\d{8}$'
#     if not re.match(pattern, phone):
#         # 1. Safely extract lang from context, defaulting to English if missing
#         lang = "en"
#         if info.context and "lang" in info.context:
#             lang = info.context["lang"]

#         # 2. Log in English for developers
#         logger.error(f"Invalid phone number schema check: {phone}")

#         raise ValueError(
#             MESSAGES[lang]["invalid_phone_number"]
#         )
#     return phone


class RegistrationBaseSchema(BaseModel):
    name_en: str
    name_bn: str
    phone: str = Field(
        ...,
        description="Phone number must start with 01[3-9] (BD only)"
    )
    password: str = Field(
        ...,
        description="Password must be at least 8 characters"
    )

    @field_validator("phone", mode="after")
    @classmethod
    def validate_phone_number(cls, v: str, info: ValidationInfo) -> str:
        return validate_phone(v, info)

    @field_validator("password", mode="after")
    @classmethod
    def validate_password(cls, v: str, info: ValidationInfo) -> str:
        # if len(v) < 8:
        #     logger.error("Password must be at least 8 characters")
        #     raise ValueError("Password must be at least 8 characters")
        # return v
        return validate_password(v, info=info)


class SeekerRegisterSchema(RegistrationBaseSchema):
    pass


class ProviderRegisterSchema(RegistrationBaseSchema):
    skill_ids: list[int]          # list of skill IDs from the skills table
    latitude: float               # seeker sends coordinates
    longitude: float
    working_radius_km: int = Field(
        ...,
        description="Working radius must be between 1 and 5 km"
    )
    has_smartphone: bool
    photo_url: str | None = None
    nid_url: str | None = None

    @field_validator("working_radius_km", mode="after")
    @classmethod
    def validate_radius(cls, v: int, info: ValidationInfo) -> int:
        # if v < 1 or v > 5:
        #     logger.error("Working radius must be between 1 and 5 km")
        #     raise ValueError("Working radius must be between 1 and 5 km")
        # return v
        return validate_radius(v, info=info)


class AuthResponseSchema(BaseModel):
    access_token: str = Field(
        ...,
        description="Read from response body. Send in Authorization header: Bearer <token>"
    )
    refresh_token: str = Field(
        ...,
        description="Flutter reads from response body. Web ignores this from response body because its in HttpOnly cookie. Send in request body: refresh_token=<token>"
    )
    token_type: str = "bearer"
    role: str
    user_id: UUID

    model_config = ConfigDict(from_attributes=True)


class RefreshTokenSchema(BaseModel):
    refresh_token: str = Field(
        ...,
        description="Flutter: send refresh token in request body"
    )
