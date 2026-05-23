from typing import Generic, TypeVar, Type
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.base import Base
import uuid

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Generic repository with common CRUD operations.
    Specific repositories inherit this and add complex queries.
    """

    # initialize repository with model and db session
    def __init__(self, model: Type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db

    # ========== generic CRUD operations ==========
    async def get_by_id(self, id: uuid.UUID) -> ModelType | None:
        return await self.db.get(self.model, id)

    async def create(self, **kwargs) -> ModelType:
        instance = self.model(**kwargs)  # keyword arguments
        self.db.add(instance)
        await self.db.flush()  # gets PK without committing
        return instance

    async def update(self, instance: ModelType, **kwargs) -> ModelType:
        for key, value in kwargs.items():
            setattr(instance, key, value)
        await self.db.flush()
        return instance

    async def delete(self, instance: ModelType) -> None:
        await self.db.delete(instance)
        await self.db.flush()

    async def get_all(self) -> list[ModelType]:
        result = await self.db.execute(select(self.model))
        return list(result.scalars().all())
