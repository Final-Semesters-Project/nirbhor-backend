from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_super_admin
from app.db.session import get_db_session
from app.core.i18n import get_lang
from app.models.user_model import User, Role
from app.schemas.super_admin_schema import (
    CreateAdminSchema,
    AdminListItem,
    AuditLogItem,
)
from app.services.super_admin_service import SuperAdminService
from app.core.exceptions import DomainValidationError
from app.core.i18n import t

router = APIRouter(prefix="/super-admin", tags=["Super Admin"])


# ── Admin account management ───────────────────────────────────────────────────


@router.get("/admins", response_model=list[AdminListItem])
async def list_admins(
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """List all regular admin accounts. Super admins not included."""
    return await SuperAdminService.get_all_admins(db=db, lang=lang)


@router.post("/admins", response_model=AdminListItem, status_code=201)
async def create_admin(
    data: CreateAdminSchema,
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """Create a new regular admin account."""
    return await SuperAdminService.create_admin(
        data=data,
        super_admin_id=current_user.id,
        db=db,
        lang=lang,
    )


@router.patch("/admins/{admin_id}/toggle", status_code=200)
async def toggle_admin_active(
    admin_id: UUID,
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """
    Enable or disable a regular admin account.
    Super admin accounts are protected — this endpoint cannot target them.
    """
    return await SuperAdminService.toggle_admin_active(
        admin_id=admin_id,
        super_admin_id=current_user.id,
        db=db,
        lang=lang,
    )


# ── Audit log ──────────────────────────────────────────────────────────────────


@router.get("/audit-logs", response_model=list[AuditLogItem])
async def get_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    admin_id: UUID | None = Query(default=None, description="Filter by specific admin"),
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """
    View all admin actions. Optionally filter by a specific admin's ID.
    Newest first, paginated.
    """
    return await SuperAdminService.get_audit_logs(
        db=db,
        lang=lang,
        page=page,
        page_size=page_size,
        admin_id_filter=admin_id,
    )
