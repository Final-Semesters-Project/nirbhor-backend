from typing import Sequence
from uuid import UUID

from app.models.provider_skill_link_model import ProviderSkillLink
from app.repositories.base_repository import BaseRepository
from app.models.skill_model import Skill
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_


class SkillRepository(BaseRepository[Skill]):
    def __init__(self, db: AsyncSession):
        super().__init__(Skill, db)

    async def get_by_name(self, name_en: str | None, name_bn: str | None) -> Skill | None:
        if name_en is None and name_bn is None:
            return None

        conditions = []

        if name_en is not None:
            conditions.append(Skill.name_en == name_en)
        if name_bn is not None:
            conditions.append(Skill.name_bn == name_bn)

        result = await self.db.execute(
            select(Skill).where(
                or_(
                    *conditions  # unpack the list
                )
            )
        )
        return result.scalars().first()

    async def check_if_provider_has_skill(
            self,
            skill_id: int,
            provider_id: UUID
    ):
        result = await self.db.execute(
            select(ProviderSkillLink)
            .where(ProviderSkillLink.skill_id == skill_id)
            .where(ProviderSkillLink.provider_id == provider_id)
        )
        return result.scalars().first()

    async def get_skills_by_category(self, category_id: int) -> Sequence[Skill]:
        result = await self.db.execute(
            select(Skill)
            .where(Skill.category_id == category_id)
            .order_by(Skill.id)
        )
        return result.scalars().all()
