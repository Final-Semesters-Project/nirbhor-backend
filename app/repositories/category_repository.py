from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.base_repository import BaseRepository
from sqlalchemy import select, or_
from app.models.category_model import Category
from app.models.skill_model import Skill


class CategoryRepository(BaseRepository[Category]):
    def __init__(self, db: AsyncSession):
        super().__init__(Category, db)

    async def get_by_name(self, name_en: str | None, name_bn: str | None) -> Category | None:
        if name_en is None and name_bn is None:
            return None

        conditions = []

        if name_en is not None:
            conditions.append(Category.name_en == name_en)
        if name_bn is not None:
            conditions.append(Category.name_bn == name_bn)

        result = await self.db.execute(
            select(Category).where(
                or_(
                    *conditions  # unpack the list
                )
            )
        )
        return result.scalars().first()

    async def get_all_categories(self) -> Sequence[Category]:
        result = await self.db.execute(
            select(Category).order_by(Category.id)
        )
        return result.scalars().all()
