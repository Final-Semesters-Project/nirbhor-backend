from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime


class ProviderSearchResult(BaseModel):
    """One provider card returned from the search endpoint."""
    user_id: UUID
    name: str                       # localized (en or bn)
    photo_url: str | None
    # NOTE: phone is intentionally excluded — revealed only after booking initiation
    skill_name: str          # localized skill names
    verification_level: str
    average_rating: float | None
    distance_km: float
    working_radius_km: int
    has_smartphone: bool
    is_available: bool
    last_active_at: datetime | None


class ProviderSearchResponse(BaseModel):
    providers: list[ProviderSearchResult]
    expanded_radius: bool
    warning: str | None

    model_config = ConfigDict(from_attributes=True)


class ProviderSearchResponsePaginated(BaseModel):
    items: list[ProviderSearchResult] = []  # ProviderSearchResult
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool
    expanded_radius: bool
    warning: str | None

    model_config = ConfigDict(from_attributes=True)


class ProviderSearchNotFoundResponse(BaseModel):
    items: list = []
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool
    expanded_radius: bool
    warning: str | None

    model_config = ConfigDict(from_attributes=True)
