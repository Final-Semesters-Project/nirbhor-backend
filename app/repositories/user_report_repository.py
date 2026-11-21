from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.booking_model import Booking
from app.models.user_model import User
from app.models.user_report_model import UserReport
from app.repositories.base_repository import BaseRepository


class UserReportRepository(BaseRepository[UserReport]):
    def __init__(self, db: AsyncSession):
        super().__init__(UserReport, db)

    async def create_report(
        self,
        reporter_id: UUID,
        reported_user_id: UUID,
        booking_id: UUID | None,
        reason: str,
    ) -> UserReport:
        report = UserReport(
            reporter_id=reporter_id,
            reported_user_id=reported_user_id,
            booking_id=booking_id,
            reason=reason,
        )
        self.db.add(report)
        await self.db.flush()
        return report

    async def get_reported_user(self, user_id: UUID) -> User | None:
        return await self.db.get(User, user_id)

    async def get_booking(self, booking_id: UUID) -> Booking | None:
        return await self.db.get(Booking, booking_id)

    def get_reports_by_reporter_stmt(self, reporter_id: UUID):
        return (
            select(UserReport)
            .where(UserReport.reporter_id == reporter_id)
            .order_by(UserReport.created_at.desc(), UserReport.id.desc())
        )
