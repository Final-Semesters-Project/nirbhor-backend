from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db_session
from app.core.i18n import get_lang
from app.api.dependencies import get_current_admin_or_super_admin
from app.models.user_model import User, Role
from app.models.user_report_model import ReportStatus
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
from app.schemas.pagination_schema import PageResponse
from app.services.admin_service import AdminService

router = APIRouter(prefix="/admin", tags=["Admin Management"])

# ── Dashboard ──────────────────────────────────────────────────────────────────


@router.get("/dashboard", response_model=AdminDashboardResponse)
async def admin_dashboard(
    current_user: User = Depends(get_current_admin_or_super_admin),
    db: AsyncSession = Depends(get_db_session),
):
    return await AdminService.get_dashboard(db=db)


# ── Verifications ──────────────────────────────────────────────────────────────
@router.get("/pendingVerifications", response_model=PageResponse[VerificationListItem])
async def list_pending_verifications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_admin_or_super_admin),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """List all providers with PENDING verification status, oldest first."""
    return await AdminService.get_pending_verifications(
        db=db, lang=lang, page=page, page_size=page_size
    )


@router.patch(
    "/verifications/{provider_id}",
    response_model=VerificationActionResponse,
)
async def handle_verification(
    provider_id: UUID,
    data: VerificationActionSchema,
    current_user: User = Depends(get_current_admin_or_super_admin),
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
        current_admin_id=current_user.id,
        data=data,
        db=db,
        lang=lang,
    )


# ── Reports ────────────────────────────────────────────────────────────────────
@router.get("/reports", response_model=PageResponse[ReportListItem])
async def list_reports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: ReportStatus | None = Query(
        None, description="Filter: pending, reviewed, action_taken"
    ),
    _: User = Depends(get_current_admin_or_super_admin),
    db: AsyncSession = Depends(get_db_session),
    # lang: str = Depends(get_lang),
):
    return await AdminService.get_reports(
        db=db, status_filter=status, page=page, page_size=page_size
    )


@router.patch("/reports/{report_id}", response_model=ReportActionResponse)
async def handle_report(
    report_id: UUID,
    data: ReportActionSchema,
    current_user: User = Depends(get_current_admin_or_super_admin),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """
    - action_taken  → suspends reported user + status becomes ACTION_TAKEN
    - reviewed → marks report REVIEWED. If already action_taken then can not set to REVIEWED
    - under_investigation  → marks report from PENDING to UNDER_INVESTIGATION to investigate. Once investigated, can be set to REVIEWED/ACTION_TAKEN
    """
    return await AdminService.handle_report(
        report_id=report_id,
        current_admin_id=current_user.id,
        data=data,
        db=db,
        lang=lang,
    )


# ── Users ──────────────────────────────────────────────────────────────────────


# TODO: apply pagination
@router.get("/users", response_model=PageResponse[AdminUserListItem])
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    role: Role | None = Query(None, description="Filter: seeker, provider, admin"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    _: User = Depends(get_current_admin_or_super_admin),
    db: AsyncSession = Depends(get_db_session),
):
    return await AdminService.get_users(
        db=db,
        role_filter=role,
        is_active_filter=is_active,
        page=page,
        page_size=page_size,
    )


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def get_user_detail(
    user_id: UUID,
    _: User = Depends(get_current_admin_or_super_admin),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    return await AdminService.get_user_detail(user_id=user_id, db=db, lang=lang)


@router.patch("/users/{user_id}/toggle", status_code=200)
async def toggle_user_active(
    user_id: UUID,
    _: User = Depends(get_current_admin_or_super_admin),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """Enable or disable a user account. Toggles current is_active value."""
    return await AdminService.toggle_user_active(user_id=user_id, db=db, lang=lang)


# ── Analytics ──────────────────────────────────────────────────────────────────


@router.get("/analytics", response_model=AdminAnalyticsResponse)
async def get_analytics(
    _: User = Depends(get_current_admin_or_super_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Stats for admin dashboard — totals, ratios, weekly booking graph data."""
    return await AdminService.get_analytics(db=db)
