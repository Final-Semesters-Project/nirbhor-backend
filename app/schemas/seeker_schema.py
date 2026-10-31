# app/schemas/seeker_schema.py (new)
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints


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
    home_address: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=255)]


class SeekerAddressResponse(BaseModel):
    # all None when the seeker has not saved an address yet
    latitude: float | None = None
    longitude: float | None = None
    home_address: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=255)] | None = None
