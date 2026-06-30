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


# ── Verifications ──────────────────────────────────────────────────────────────

@router.get("/pendingVerifications", response_model=list[VerificationListItem])
async def list_pending_verifications(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """List all providers with PENDING verification status, oldest first."""
    return await AdminService.get_pending_verifications(db=db, lang=lang)


@router.patch(
    "/verifications/{provider_id}",
    response_model=VerificationActionResponse,
)
async def handle_verification(
    provider_id: UUID,
    data: VerificationActionSchema,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """
    Approve or reject a provider's verification request.
    - approve → verification_level becomes VERIFIED, rejection_reason cleared
    - reject  → rejection_reason required, provider stays BASIC
    """
    return await AdminService.handle_verification(
        provider_id=provider_id,
        data=data,
        db=db,
        lang=lang,
    )

# ── Reports ────────────────────────────────────────────────────────────────────


@router.get("/reports", response_model=list[ReportListItem])
async def list_reports(
    status: str | None = Query(
        None, description="Filter: pending, reviewed, action_taken"),
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db_session),
    # lang: str = Depends(get_lang),
):
    return await AdminService.get_reports(db=db, status_filter=status)


@router.patch("/reports/{report_id}", response_model=ReportActionResponse)
async def handle_report(
    report_id: UUID,
    data: ReportActionSchema,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """
    - action_taken  → suspends reported user
    - reviewed → marks report REVIEWED. If already action_taken then can not set to REVIEWED
    - under_investigation  → marks report from PENDING to UNDER_INVESTIGATION to investigate
    """
    return await AdminService.handle_report(
        report_id=report_id,
        data=data,
        db=db,
        lang=lang,
    )
