from pydantic import BaseModel, model_validator
from datetime import datetime
from enum import Enum
from loguru import logger
from pydantic import BaseModel, ConfigDict, field_validator, Field, ValidationInfo
import re
from uuid import UUID
from app.core.schema_validators import (
    validate_phone,
    validate_password,
    validate_radius,
    validate_name,
)
from app.core.i18n import MESSAGES
from enum import Enum


class RegistrationBaseSchema(BaseModel):
    name_en: str
    name_bn: str
    phone: str = Field(
        ..., description="Phone number must start with 01[3-9] (BD only)"
    )
    password: str = Field(..., description="Password must be at least 8 characters")
    preferred_lang: str = Field(..., description="en or bn")

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
    home_latitude: float = Field(
        ..., description="Seeker home latitude"
    )  # seeker sends coordinates
    home_longitude: float = Field(..., description="Seeker home longitude")
    home_address: str = Field(..., description="Seeker home address in text")

    @model_validator(mode="after")
    def address_all_or_none(self):
        group = [self.home_latitude, self.home_longitude, self.home_address]
        if any(v is not None for v in group) and not all(v is not None for v in group):
            raise ValueError(
                "home_latitude, home_longitude and home_address must be sent together."
            )
        return self


class ProviderRegisterSchema(RegistrationBaseSchema):
    skill_ids: list[int]  # list of skill IDs from the skills table
    latitude: float  # seeker sends coordinates
    longitude: float
    working_radius_km: int = Field(
        ..., description="Working radius must be between 1 and 5 km"
    )
    has_smartphone: bool
    # base_address: str | None = None
    # @model_validator(mode="after")
    # def location_fields_together(self):
    #     group = [self.latitude, self.longitude, self.base_address]
    #     if any(v is not None for v in group) and not all(v is not None for v in group):
    #         raise ValueError("latitude, longitude and base_address must be updated together.")
    #     return self

    @field_validator("working_radius_km", mode="after")
    @classmethod
    def validate_radius(cls, v: int, info: ValidationInfo) -> int:
        return validate_radius(v, info=info)


class AuthResponseSchema(BaseModel):
    access_token: str = Field(
        ...,
        description="Read from response body. Send in Authorization header: Bearer <token>",
    )
    refresh_token: str = Field(
        ...,
        description="Flutter reads from response body. Web ignores this from response body because its in HttpOnly cookie. Send in request body: refresh_token=<token>",
    )
    token_type: str = "bearer"
    role: str
    user_id: UUID

    model_config = ConfigDict(from_attributes=True)


class RefreshTokenSchema(BaseModel):
    refresh_token: str = Field(
        ..., description="Flutter: send refresh token in request body"
    )


class LogoutSchema(BaseModel):
    refresh_token: str
    fcm_token: str | None = None  # optional: also clear this device's FCM token


class DeviceType(str, Enum):
    ANDROID = "android"
    IOS = "ios"
    WEB = "web"


class FCMTokenRequest(BaseModel):
    token: str
    device_type: DeviceType = DeviceType.ANDROID
