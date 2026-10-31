# app/schemas/seeker_schema.py (new)
from pydantic import BaseModel, Field


class SeekerAddressUpdateSchema(BaseModel):
    """Replaces the whole address, so all three fields are required."""

    latitude: float = Field(
        ...,
        description="Limit updating location once in every 15 days and prompt to verify the working radius everytime the location is updated",
    )
    longitude: float = Field(
        ...,
        description="Limit updating location once in every 15 days and prompt to verify the working radius everytime the location is updated",
    )
    home_address: str


class SeekerAddressResponse(BaseModel):
    # all None when the seeker has not saved an address yet
    latitude: float | None = None
    longitude: float | None = None
    home_address: str | None = None
