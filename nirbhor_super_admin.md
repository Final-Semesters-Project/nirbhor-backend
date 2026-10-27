# Nirbhor — Super Admin Implementation

## What super admin adds on top of regular admin

| Feature | Regular Admin | Super Admin |
|---|---|---|
| Dashboard, verifications, reports, users, analytics | ✅ | ✅ |
| Suspend/unsuspend regular users (seekers, providers) | ✅ | ✅ |
| Create new admin accounts | ❌ | ✅ |
| Delete/deactivate admin accounts | ❌ | ✅ |
| View admin activity audit log | ❌ | ✅ |
| Cannot be suspended by regular admin | N/A | ✅ (protected) |

---

## 4. Repository

```python
# app/repositories/super_admin_repository.py

from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import aliased

from app.models.user_model import User, Role
from app.models.admin_audit_log_model import AdminAuditLog


class SuperAdminRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Admin account management ───────────────────────────────────────────────

    async def get_all_admins(self) -> list[User]:
        """
        Returns all ADMIN (not SUPER_ADMIN) accounts.
        Super admin manages regular admins — not other super admins.
        """
        result = await self.db.execute(
            select(User)
            .where(User.role == Role.ADMIN)
            .order_by(User.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_admin_by_id(self, admin_id: UUID) -> User | None:
        """Fetch a single admin. Only returns ADMIN role — never SUPER_ADMIN."""
        result = await self.db.execute(
            select(User)
            .where(User.id == admin_id)
            .where(User.role == Role.ADMIN)   # cannot target super_admins
        )
        return result.scalar_one_or_none()

    async def create_admin(
        self,
        phone: str,
        password_hash: str,
        name_en: str,
        name_bn: str,
    ) -> User:
        user = User(
            phone_en=phone,
            password_hash=password_hash,
            role=Role.ADMIN,
            name_en=name_en,
            name_bn=name_bn,
            is_active=True,
            preferred_lang="en",
            created_at=datetime.now(timezone.utc),
            last_active_at=datetime.now(timezone.utc),
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def toggle_admin_active(self, admin_id: UUID) -> User | None:
        """
        Enable or disable a regular admin account.
        Only targets ADMIN role — super admins are protected.
        """
        user = await self.get_admin_by_id(admin_id)
        if not user:
            return None
        user.is_active = not user.is_active
        await self.db.flush()
        return user

    # ── Audit log ──────────────────────────────────────────────────────────────

    async def write_audit_log(
        self,
        admin_id: UUID,
        admin_role: str,
        action: str,
        target_user_id: UUID | None = None,
        details: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        """
        Records an admin action. Call this from ANY admin service method
        (not just super admin) to build a complete audit trail.
        Fire-and-forget — never raises, logs error if it fails.
        """
        try:
            log = AdminAuditLog(
                admin_id=admin_id,
                admin_role=admin_role,
                action=action,
                target_user_id=target_user_id,
                details=details,
                ip_address=ip_address,
                performed_at=datetime.now(timezone.utc),
            )
            self.db.add(log)
            await self.db.flush()
        except Exception as e:
            from loguru import logger
            logger.error(f"Failed to write audit log: {e}")

    async def get_audit_logs(
        self,
        page: int = 1,
        page_size: int = 50,
        admin_id_filter: UUID | None = None,
    ) -> list[dict]:
        """
        Fetch audit logs with admin name joined.
        Super admin sees all logs; optionally filter by admin.
        """
        AdminUser = aliased(User, name="admin_user")
        TargetUser = aliased(User, name="target_user")

        stmt = (
            select(
                AdminAuditLog,
                AdminUser.name_en.label("admin_name"),
                TargetUser.name_en.label("target_name"),
            )
            .outerjoin(AdminUser, AdminAuditLog.admin_id == AdminUser.id)
            .outerjoin(TargetUser, AdminAuditLog.target_user_id == TargetUser.id)
            .order_by(AdminAuditLog.performed_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )

        if admin_id_filter:
            stmt = stmt.where(AdminAuditLog.admin_id == admin_id_filter)

        result = await self.db.execute(stmt)

        return [
            {
                "log_id":           row.AdminAuditLog.id,
                "admin_name":       row.admin_name or "Deleted Admin",
                "admin_role":       row.AdminAuditLog.admin_role,
                "action":           row.AdminAuditLog.action,
                "target_user_id":   row.AdminAuditLog.target_user_id,
                "target_user_name": row.target_name,
                "details":          row.AdminAuditLog.details,
                "performed_at":     row.AdminAuditLog.performed_at,
            }
            for row in result.all()
        ]
```

---

## 5. Service

```python
# app/services/super_admin_service.py

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.repositories.super_admin_repository import SuperAdminRepository
from app.repositories.user_repository import UserRepository
from app.schemas.super_admin_schema import (
    CreateAdminSchema,
    AdminListItem,
    AuditLogItem,
)
from app.core.security import Security
from app.core.exceptions import DomainIntegrityError, DomainValidationError
from app.core.i18n import t
from app.core.cache import UserCacheService


class SuperAdminService:

    @staticmethod
    async def get_all_admins(
        db: AsyncSession, lang: str
    ) -> list[AdminListItem]:
        repo = SuperAdminRepository(db)
        admins = await repo.get_all_admins()
        return [
            AdminListItem(
                user_id=a.id,
                name=a.name_en,
                phone=a.phone_en,
                role=a.role.value,
                is_active=a.is_active,
                created_at=a.created_at,
                last_active_at=a.last_active_at,
            )
            for a in admins
        ]

    @staticmethod
    async def create_admin(
        data: CreateAdminSchema,
        super_admin_id: UUID,
        db: AsyncSession,
        lang: str,
    ) -> AdminListItem:
        repo = SuperAdminRepository(db)
        user_repo = UserRepository(db)

        # Phone must be unique
        existing = await user_repo.get_by_phone(data.phone)
        if existing:
            raise DomainIntegrityError(t("phone_already_registered", lang))

        password_hash = await Security.hash_password_async(data.password)
        admin = await repo.create_admin(
            phone=data.phone,
            password_hash=password_hash,
            name_en=data.name_en,
            name_bn=data.name_bn,
        )

        # Audit log
        await repo.write_audit_log(
            admin_id=super_admin_id,
            admin_role="super_admin",
            action="create_admin",
            target_user_id=admin.id,
            details=f"Created admin account for {data.phone}",
        )

        await db.commit()
        logger.info(
            f"Super admin {super_admin_id} created new admin {admin.id}"
        )

        return AdminListItem(
            user_id=admin.id,
            name=admin.name_en,
            phone=admin.phone_en,
            role=admin.role.value,
            is_active=admin.is_active,
            created_at=admin.created_at,
            last_active_at=admin.last_active_at,
        )

    @staticmethod
    async def toggle_admin_active(
        admin_id: UUID,
        super_admin_id: UUID,
        db: AsyncSession,
        lang: str,
    ) -> dict:
        repo = SuperAdminRepository(db)

        admin = await repo.toggle_admin_active(admin_id)
        if not admin:
            # Either not found OR it was a super_admin (protected)
            raise DomainValidationError(t("user_not_found", lang))

        # Evict from cache immediately so suspension takes effect
        UserCacheService.invalidate(str(admin_id))

        await repo.write_audit_log(
            admin_id=super_admin_id,
            admin_role="super_admin",
            action="toggle_admin_active",
            target_user_id=admin_id,
            details=f"Set is_active={admin.is_active}",
        )

        await db.commit()
        logger.info(
            f"Super admin {super_admin_id} toggled admin {admin_id} "
            f"is_active → {admin.is_active}"
        )

        return {
            "user_id": admin_id,
            "is_active": admin.is_active,
            "message": t("user_status_updated", lang),
        }

    @staticmethod
    async def get_audit_logs(
        db: AsyncSession,
        lang: str,
        page: int = 1,
        page_size: int = 50,
        admin_id_filter: UUID | None = None,
    ) -> list[AuditLogItem]:
        repo = SuperAdminRepository(db)
        rows = await repo.get_audit_logs(
            page=page,
            page_size=page_size,
            admin_id_filter=admin_id_filter,
        )
        return [
            AuditLogItem(
                log_id=r["log_id"],
                admin_name=r["admin_name"],
                admin_role=r["admin_role"],
                action=r["action"],
                target_user_id=r["target_user_id"],
                target_user_name=r["target_user_name"],
                details=r["details"],
                performed_at=r["performed_at"],
            )
            for r in rows
        ]
```

---

## 6. Router

```python
# app/api/v1/super_admin_router.py

from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.core.i18n import get_lang
from app.core.dependencies import get_current_user
from app.models.user_model import User, Role
from app.schemas.super_admin_schema import (
    CreateAdminSchema,
    AdminListItem,
    AuditLogItem,
)
from app.services.super_admin_service import SuperAdminService
from app.core.exceptions import DomainValidationError
from app.core.i18n import t

router = APIRouter()


def require_super_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency: only super_admin role passes.
    Regular admins are blocked — they cannot access super admin routes.
    """
    if current_user.role != Role.SUPER_ADMIN:
        raise DomainValidationError("Super admin access required.")
    return current_user


# ── Admin account management ───────────────────────────────────────────────────

@router.get("/admins", response_model=list[AdminListItem])
async def list_admins(
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """List all regular admin accounts. Super admins not included."""
    return await SuperAdminService.get_all_admins(db=db, lang=lang)


@router.post("/admins", response_model=AdminListItem, status_code=201)
async def create_admin(
    data: CreateAdminSchema,
    current_user: User = Depends(require_super_admin),
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
    current_user: User = Depends(require_super_admin),
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
    _: User = Depends(require_super_admin),
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
```

---

## 7. Register in router.py

```python
# app/api/v1/router.py

from app.api.v1 import super_admin_router

api_router.include_router(
    super_admin_router.router,
    prefix="/super-admin",
    tags=["Super Admin"],
)
```

---

## 8. Protect regular admin toggle from targeting super_admins

Your existing `AdminService.toggle_user_active` in `admin_service.py` should
not be able to suspend a super_admin. Add one check:

```python
# app/services/admin_service.py — in toggle_user_active

@staticmethod
async def toggle_user_active(user_id: UUID, db: AsyncSession, lang: str) -> dict:
    from app.core.cache import UserCacheService
    from app.models.user_model import Role

    repo = AdminRepository(db)

    # First check if user is a super_admin — regular admins cannot touch them
    user = await db.get(User, user_id)
    if not user:
        raise DomainValidationError(t("user_not_found", lang))
    if user.role == Role.SUPER_ADMIN:
        raise DomainValidationError(t("admin_only", lang))  # 400 — access denied

    toggled = await repo.toggle_user_active(user_id)
    UserCacheService.invalidate(str(user_id))
    await db.commit()

    logger.info(f"Admin toggled user {user_id} is_active → {toggled.is_active}")
    return {
        "user_id": user_id,
        "is_active": toggled.is_active,
        "message": t("user_status_updated", lang),
    }
```

---

## 9. Add audit logging to existing admin actions (optional but recommended)

To build a real audit trail, call `write_audit_log` inside your existing
`admin_service.py` methods. Example for `handle_verification`:

```python
# In admin_service.py handle_verification — after commit:

from app.repositories.super_admin_repository import SuperAdminRepository

super_repo = SuperAdminRepository(db)
await super_repo.write_audit_log(
    admin_id=current_admin_id,   # pass this through from the router
    admin_role="admin",
    action="approve_verification" if data.action == "approve" else "reject_verification",
    target_user_id=provider_id,
    details=data.rejection_reason if data.action == "reject" else None,
)
```

This requires adding `current_admin_id: UUID` as a parameter to admin service
methods — pass it from the router via `current_user.id`.

---

## 10. i18n keys to add

```python
"super_admin_only": {
    "en": "Super admin access required.",
    "bn": "সুপার অ্যাডমিন অ্যাক্সেস প্রয়োজন।"
},
```

---

## Route summary

| Method | URL | Who can call | What it does |
|--------|-----|-------------|-------------|
| GET | `/api/v1/super-admin/admins` | super_admin | List all regular admins |
| POST | `/api/v1/super-admin/admins` | super_admin | Create a new admin |
| PATCH | `/api/v1/super-admin/admins/{id}/toggle` | super_admin | Enable/disable an admin |
| GET | `/api/v1/super-admin/audit-logs` | super_admin | View all admin activity |
