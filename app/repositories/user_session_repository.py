from app.repositories.base_repository import BaseRepository
from app.models.user_session_model import UserSession
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import uuid


class UserSessionRepository(BaseRepository[UserSession]):
    def __init__(self, db: AsyncSession):
        super().__init__(UserSession, db)

    async def get_by_refresh_token(self, token: str) -> UserSession | None:
        return await self.db.scalar(
            select(UserSession).where(UserSession.refresh_token == token)
        )

    async def delete_by_refresh_token(self, token: str) -> None:
        await self.db.execute(
            delete(UserSession).where(UserSession.refresh_token == token)
        )

    async def delete_all_refresh_tokens_for_user(self, user_id: uuid.UUID) -> None:
        # used for logout-all-devices
        await self.db.execute(
            delete(UserSession).where(UserSession.user_id == user_id)
        )
