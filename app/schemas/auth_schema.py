from datetime import datetime

from loguru import logger
from pydantic import BaseModel, ConfigDict, field_validator, Field, ValidationInfo
import re
from uuid import UUID
from app.core.schema_validators import validate_phone, validate_password, validate_radius, validate_name
from app.core.i18n import MESSAGES


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
        return validate_password(v, info=info)

    @field_validator("name_en", mode="after")
    @classmethod
    def validate_en_name(cls, v: str, info: ValidationInfo) -> str:
        return validate_name(v, info=info)

    @field_validator("name_bn", mode="after")
    @classmethod
    def validate_bn_name(cls, v: str, info: ValidationInfo) -> str:
        return validate_name(v, info=info)


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
    nid_url_front: str | None = None
    nid_url_back: str | None = None

    @field_validator("working_radius_km", mode="after")
    @classmethod
    def validate_radius(cls, v: int, info: ValidationInfo) -> int:
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
