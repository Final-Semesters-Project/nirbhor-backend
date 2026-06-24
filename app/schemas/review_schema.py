from pydantic import BaseModel, field_validator, ConfigDict, Field
from uuid import UUID


class ReviewCreateSchema(BaseModel):
    booking_id: UUID
    rating: int = Field(..., description="Rating must be between 1 and 5")
    comment: str | None = None
    is_anonymous: bool = Field(
        True, description="Default is True for Seekers and False for Providers")

    @field_validator("rating")
    @classmethod
    def rating_must_be_valid(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("rating must be between 1 and 5.")
        return v


class ReviewResponse(BaseModel):
    review_id: UUID
    booking_id: UUID
    rating: int
    comment: str | None
    is_anonymous: bool

    model_config = ConfigDict(from_attributes=True)
