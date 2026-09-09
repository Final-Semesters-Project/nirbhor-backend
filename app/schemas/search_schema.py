from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime


class ProviderSearchResult(BaseModel):
    """One provider card returned from the search endpoint."""
    user_id: UUID
    name: str                       # localized (en or bn)
    photo_url: str | None
    skill_name: str          # localized skill names
    verification_level: str
    average_rating: float | None
    distance_km: float
    working_radius_km: int
    has_smartphone: bool
    is_available: bool
    last_active_at: datetime | None
    # phone is intentionally excluded — revealed only after booking initiation

    # model_config = ConfigDict(from_attributes=True)


class ProviderSearchResponse(BaseModel):
    providers: list[ProviderSearchResult]
    expanded_radius: bool
    warning: str | None

    model_config = ConfigDict(from_attributes=True)
