from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from app.repositories.admin_repository import AdminRepository
from app.schemas.admin_schema import (
    AdminDashboardResponse,
    VerificationListItem,
    VerificationActionSchema,
    VerificationActionResponse,
    ReportListItem,
    ReportActionSchema,
    ReportActionResponse,
    AdminUserListItem,
    AdminUserDetail,
    AdminAnalyticsResponse,
)
from app.models.user_report_model import ReportStatus
from app.core.exceptions import DomainValidationError, DomainIntegrityError
from app.core.i18n import t


class AdminService:
    @staticmethod
    async def get_dashboard(db: AsyncSession) -> AdminDashboardResponse:
        repo = AdminRepository(db)
        data = await repo.get_dashboard_counts()
        return AdminDashboardResponse(**data)
