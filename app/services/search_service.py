from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from app.core.i18n import t
from app.repositories.search_repository import SearchRepository
from app.schemas.search_schema import ProviderSearchResult, ProviderSearchResponse

# If no results found within requested radius, auto-expand once to this
AUTO_EXPAND_KM = 2


class SearchService:
    @staticmethod
    async def find_providers(
        skill_id: int,
        seeker_lat: float,
        seeker_lng: float,
        search_radius_km: int,
        db: AsyncSession,
        lang: str,
    ) -> ProviderSearchResponse:
        """
        Search for providers. If none found in requested radius,
        automatically expands to AUTO_EXPAND_KM and returns a warning flag.
        """
        search_repo = SearchRepository(db)

        rows = await search_repo.find_providers(
            skill_id=skill_id,
            seeker_lat=seeker_lat,
            seeker_lng=seeker_lng,
            search_radius_km=search_radius_km,
            lang=lang,
        )

        expanded = False
        if not rows and search_radius_km < AUTO_EXPAND_KM:
            # Auto-expand once silently
            rows = await search_repo.find_providers(
                skill_id=skill_id,
                seeker_lat=seeker_lat,
                seeker_lng=seeker_lng,
                search_radius_km=AUTO_EXPAND_KM,
                lang=lang,
            )
            expanded = True
            logger.info(
                f"Search auto-expanded from {search_radius_km}km to {AUTO_EXPAND_KM}km "
                f"for skill {skill_id}"
            )

        if not rows:
            return (
                ProviderSearchResponse(
                    providers=[],
                    expanded_radius=expanded,
                    warning=t("no_providers_found", lang),
                )
            )

        # get the currently searched skill name
        skills_name = await search_repo.get_skill_name(
            skill_id, lang
        )

        providers = [
            ProviderSearchResult(
                user_id=r.user_id,
                name=r.name,
                skill_name=skills_name,
                verification_level=r.verification_level.value,
                average_rating=r.average_rating,
                distance_km=round(r.distance_km, 2),
                working_radius_km=r.working_radius_km,
                has_smartphone=r.has_smartphone,
                is_available=r.is_available,
                last_active_at=r.last_active_at,
            )
            for r in rows
        ]
        logger.info(
            f"Found {len(providers)} providers for skill {skill_id} in radius {search_radius_km}km"
        )
        return (
            ProviderSearchResponse(
                providers=providers,
                expanded_radius=expanded,
                warning=t("search_radius_expanded_warning",
                          lang) if expanded else None,
            )
        )
