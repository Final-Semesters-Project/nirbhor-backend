from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.core.i18n import get_lang
from app.api.dependencies import get_current_admin
from app.models.user_model import User, Role
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
from app.services.admin_service import AdminService
from app.core.exceptions import DomainValidationError
from app.core.i18n import t

router = APIRouter(prefix="/admin", tags=["Admin Management"])

# ── Dashboard ──────────────────────────────────────────────────────────────────


@router.get("/dashboard", response_model=AdminDashboardResponse)
async def admin_dashboard(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db_session),
):
    return await AdminService.get_dashboard(db=db)
