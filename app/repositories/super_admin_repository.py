from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import aliased

from app.models.user_model import User, Role
from app.models.admin_audit_log_model import AdminAuditLog
from app.repositories.base_repository import BaseRepository


class SuperAdminRepository(BaseRepository[AdminAuditLog]):
    def __init__(self, db: AsyncSession):
        super().__init__(AdminAuditLog, db)

    # ── Admin account management ───────────────────────────────────────────────

    async def get_all_admins(self) -> list[User]:
        """
        Returns all ADMIN (not SUPER_ADMIN) accounts.
        Super admin manages regular admins — not other super admins.
        """
        result = await self.db.execute(
            select(User).where(User.role == Role.ADMIN).order_by(User.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_admin_by_id(self, admin_id: UUID) -> User | None:
        """Fetch a single admin. Only returns ADMIN role — never SUPER_ADMIN."""
        result = await self.db.execute(
            select(User)
            .where(User.id == admin_id)
            .where(User.role == Role.ADMIN)  # cannot target super_admins
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
                "log_id": row.AdminAuditLog.id,
                "admin_name": row.admin_name or "Deleted Admin",
                "admin_role": row.AdminAuditLog.admin_role,
                "action": row.AdminAuditLog.action,
                "target_user_id": row.AdminAuditLog.target_user_id,
                "target_user_name": row.target_name,
                "details": row.AdminAuditLog.details,
                "performed_at": row.AdminAuditLog.performed_at,
            }
            for row in result.all()
        ]
