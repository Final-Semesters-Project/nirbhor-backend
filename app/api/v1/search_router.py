from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db_session
from app.core.i18n import get_lang
from app.api.dependencies import get_current_seeker
from app.models.user_model import User
from app.core.i18n import t
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("/providers")
async def search_providers(
    skill_id: int = Query(..., description="Skill ID selected from dropdown"),
    seeker_lat: float = Query(..., description="Seeker's current latitude"),
    seeker_lng: float = Query(..., description="Seeker's current longitude"),
    search_radius_km: int = Query(
        1, ge=1, le=5, description="Search radius in KM"),
    current_user: User = Depends(get_current_seeker),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """
    Geo-aware provider search with ranking score.
    Auto-expands to 2km if no results found within requested radius.
    Phone numbers are never included in search results.
    """
    return await SearchService.find_providers(
        skill_id=skill_id,
        seeker_lat=seeker_lat,
        seeker_lng=seeker_lng,
        search_radius_km=search_radius_km,
        db=db,
        lang=lang,
    )

"""
# Domain 2: Location-Aware Search (/app/api/v1/search/)
5. GET /api/v1/search/providers
- Handles: Discovery & Search Requirements.
- Query Parameters: `skill_category_id: int`, `seeker_lat: float`, `seeker_lng: float`, `search_radius_km: int | None = 1` 
- Logic:
    - Execute a PostGIS geospatial query matching providers whose `base_location` and defined `working_radius_km` overlap with the seeker's point coordinates.
    - Filter out providers where `is_available == False` (off-duty toggles) or where `last_active_at` is older than 60 days.
    - Apply your explicit Provider Ranking Score formula right inside the SQLAlchemy query selection using mathematical weights:
        `score = (1/distance_km) + (rating * 2) + (verification_level * 3) + activity_bonus`
    - Return localized `name_bn` or `name_en` fields dynamically by inspecting the Accept-Language header wrapper.
"""
