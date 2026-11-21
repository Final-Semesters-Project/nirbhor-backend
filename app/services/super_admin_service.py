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
    async def get_all_admins(db: AsyncSession, lang: str) -> list[AdminListItem]:
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
        logger.info(f"Super admin {super_admin_id} created new admin {admin.id}")

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
