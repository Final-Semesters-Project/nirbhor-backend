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

    @staticmethod
    async def get_pending_verifications(
        db: AsyncSession, lang: str
    ) -> list[VerificationListItem]:
        repo = AdminRepository(db)
        rows = await repo.get_pending_verifications()
        return [
            VerificationListItem(
                user_id=user.id,
                name=user.name_en,
                phone=user.phone_en,
                photo_url=profile.photo_url,
                nid_url_front=profile.nid_url_front,
                nid_url_back=profile.nid_url_back,
                verification_level=profile.verification_level.value,
                verification_status=profile.verification_status.value,
                submitted_at=profile.updated_at or profile.created_at,
            )
            for user, profile in rows
        ]
