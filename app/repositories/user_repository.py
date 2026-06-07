from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user_model import User
from app.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: AsyncSession):
        super().__init__(User, db)  # set model and session from BaseRepository and

    async def get_by_phone(self, phone: str) -> User | None:
        return await self.db.scalar(
            select(User).where(User.phone_en == phone)
        )


"""
For selected columns query:
Approach A: Returning a List of Dictionaries (Fastest & Flexible)
async def get_specific_columns(self, columns: list[str]) -> list[dict]:
        # 1. Dynamically map string names to actual SQLAlchemy Column objects
        query_columns = [getattr(User, col) for col in columns]
        
        # 2. Build the query: select(User.id, User.name_en)
        query = select(*query_columns)
        
        # 3. Execute and turn row tuples into cleanly mapped dictionaries
        result = await self.db.execute(query)
        return [row._asdict() for row in result.all()]

In the code/service layer:
user_data = await user_repo.get_specific_columns(["id", "phone_en"])
# Returns: [{"id": "uuid-123", "phone_en": "017..."}, ...]
"""

"""
Approach B: Using SQLAlchemy Async load_only (Returns Partial Models)
from sqlalchemy.orm import load_only

class UserRepository(BaseRepository[User]):
    # ...

    async def get_users_optimized(self) -> list[User]:
        # Only fetch id and phone_en from the DB
        query = select(User).options(load_only(User.id, User.phone_en))
        result = await self.db.execute(query)
        return list(result.scalars().all())
"""
