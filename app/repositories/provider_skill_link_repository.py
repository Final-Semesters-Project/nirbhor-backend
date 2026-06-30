from uuid import UUID

from sqlalchemy import select
from app.models.provider_skill_link_model import ProviderSkillLink
from app.repositories.base_repository import BaseRepository
from sqlalchemy.ext.asyncio import AsyncSession


class ProviderSkillLinkRepository(BaseRepository[ProviderSkillLink]):
    def __init__(self, db: AsyncSession):
        super().__init__(ProviderSkillLink, db)

    async def get_provider_skill_link(
            self,
            provider_id: UUID,
            skill_id: int
    ) -> ProviderSkillLink | None:
        stmt = (
            select(ProviderSkillLink)
            .where(ProviderSkillLink.provider_id == provider_id)
            .where(ProviderSkillLink.skill_id == skill_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
