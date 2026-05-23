from pydantic import BaseModel, ConfigDict, field_validator
import re
from uuid import UUID


def validate_phone(phone: str) -> str:
    """Validates Bangladeshi phone numbers: 01XXXXXXXXX"""
    pattern = r'^01[3-9]\d{8}$'
    if not re.match(pattern, phone):
        raise ValueError(
            "Invalid Bangladeshi phone number. Must be 11 digits starting with 01")
    return phone


class RegistrationBaseSchema(BaseModel):
    name: str
    phone: str
    password: str

    @field_validator("phone")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        return validate_phone(v)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class SeekerRegisterSchema(RegistrationBaseSchema):
    pass


class ProviderRegisterSchema(RegistrationBaseSchema):
    skill_ids: list[int]          # list of skill IDs from the skills table
    latitude: float               # seeker sends coordinates
    longitude: float
    working_radius_km: int
    has_smartphone: bool

    @field_validator("working_radius_km")
    @classmethod
    def validate_radius(cls, v: int) -> int:
        if v < 1 or v > 10:
            raise ValueError("Working radius must be between 1 and 10 km")
        return v


class AuthResponseSchema(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: UUID

    model_config = ConfigDict(from_attributes=True)
