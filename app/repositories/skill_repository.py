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
